"""Backend de vendas do RTC Check com Mercado Pago.

Roda no servidor do vendedor, nunca na máquina do cliente, e cumpre o contrato
de docs/checkout.md: cria o checkout hospedado, valida o webhook assinado,
confere valor, moeda, status e idempotência, emite a licença Ed25519 somente
após pagamento aprovado e envia a chave por e-mail. O aplicativo desktop
continua conhecendo apenas a URL HTTPS pública deste servidor.

Chaves de API, segredo de webhook e a chave privada de emissão vivem no
ambiente deste processo e nunca aparecem em resposta HTTP nem em log.
"""

from __future__ import annotations

import json
import os
import smtplib
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import mercadopago as mp
from .edicao import Plano, gerar_chave

MAX_CORPO_WEBHOOK = 64 * 1024
_TRAVA_REGISTRO = threading.Lock()

# Estados do contrato em docs/checkout.md.
LICENCA_EMITIDA = "licenca_emitida"
PAGAMENTO_IGNORADO = "pagamento_ignorado"
PAGAMENTO_DUPLICADO = "pagamento_duplicado"
PAGAMENTO_RECUSADO = "pagamento_recusado"
PAGAMENTO_CANCELADO = "pagamento_cancelado"
REEMBOLSO_CONFIRMADO = "reembolso_confirmado"

_STATUS_ENCERRADOS = {
    "cancelled": PAGAMENTO_CANCELADO,
    "refunded": REEMBOLSO_CONFIRMADO,
    "charged_back": REEMBOLSO_CONFIRMADO,
}


@dataclass(frozen=True)
class ConfigVendas:
    """Configuração do servidor; tudo vem do ambiente, nada do repositório."""

    url_publica: str
    segredo_webhook: str
    diretorio: Path
    smtp_host: str = ""
    smtp_porta: int = 465
    smtp_usuario: str = ""
    smtp_senha: str = ""
    remetente: str = ""


def carregar_config() -> ConfigVendas:
    url_publica = os.environ.get("RTC_CHECK_VENDAS_URL", "").strip().rstrip("/")
    if not url_publica.startswith("https://"):
        raise SystemExit(
            "defina RTC_CHECK_VENDAS_URL com a URL HTTPS pública deste servidor"
        )
    segredo = os.environ.get("PAYMENT_WEBHOOK_SECRET", "").strip()
    if not segredo:
        raise SystemExit(
            "defina PAYMENT_WEBHOOK_SECRET com a assinatura secreta do webhook"
        )
    try:
        mp.token_de_acesso()
    except mp.ErroMercadoPago as erro:
        raise SystemExit(str(erro)) from erro
    try:
        smtp_porta = int(os.environ.get("SMTP_PORT", "465"))
    except ValueError as erro:
        raise SystemExit("SMTP_PORT precisa ser um número de porta") from erro
    return ConfigVendas(
        url_publica=url_publica,
        segredo_webhook=segredo,
        diretorio=Path(os.environ.get("RTC_CHECK_VENDAS_DIR", "vendas")),
        smtp_host=os.environ.get("SMTP_HOST", "").strip(),
        smtp_porta=smtp_porta,
        smtp_usuario=os.environ.get("SMTP_USER", "").strip(),
        smtp_senha=os.environ.get("SMTP_PASS", ""),
        remetente=os.environ.get("SMTP_FROM", "").strip(),
    )


def _arquivo_de_vendas(diretorio: Path) -> Path:
    return diretorio / "vendas.jsonl"


def ja_processado(diretorio: Path, id_pagamento: str) -> bool:
    arquivo = _arquivo_de_vendas(diretorio)
    if not arquivo.exists():
        return False
    with _TRAVA_REGISTRO:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    for linha in linhas:
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(registro, dict) and registro.get("id_pagamento") == id_pagamento:
            return True
    return False


def registrar_venda(diretorio: Path, registro: dict[str, Any]) -> None:
    diretorio.mkdir(parents=True, exist_ok=True)
    linha = json.dumps(registro, ensure_ascii=False, sort_keys=True)
    with _TRAVA_REGISTRO, _arquivo_de_vendas(diretorio).open("a", encoding="utf-8") as arquivo:
        arquivo.write(linha + "\n")


@dataclass(frozen=True)
class ResultadoDaVenda:
    desfecho: str
    detalhe: str = ""
    chave: str = ""
    email_do_comprador: str = ""
    plano: str = ""


def processar_pagamento(
    id_pagamento: str,
    diretorio: Path,
    *,
    buscar_pagamento: Callable[[str], dict[str, Any]] | None = None,
    hoje: date | None = None,
) -> ResultadoDaVenda:
    """Aplica o contrato do checkout a uma notificação de pagamento.

    A licença só é emitida com status aprovado, moeda e valor corretos e id de
    pagamento inédito. Estados finais (cancelamento, reembolso, chargeback) são
    registrados para acompanhamento; a chave já emitida expira sozinha.
    """
    if ja_processado(diretorio, id_pagamento):
        return ResultadoDaVenda(PAGAMENTO_DUPLICADO, "webhook repetido; nada a fazer")

    buscar = buscar_pagamento or mp.obter_pagamento
    pagamento = buscar(id_pagamento)
    status = str(pagamento.get("status", ""))
    metadata = pagamento.get("metadata")
    codigo_plano = str(
        (metadata.get("rtc_check_plano") if isinstance(metadata, dict) else None)
        or pagamento.get("external_reference")
        or ""
    )
    plano = mp.PLANOS_DE_VENDA.get(codigo_plano)
    agora = datetime.now().isoformat(timespec="seconds")

    if status in _STATUS_ENCERRADOS:
        evento = _STATUS_ENCERRADOS[status]
        registrar_venda(
            diretorio,
            {
                "id_pagamento": id_pagamento,
                "evento": evento,
                "plano": codigo_plano,
                "registrado_em": agora,
            },
        )
        return ResultadoDaVenda(evento, f"status {status} registrado para acompanhamento")

    if status != "approved":
        return ResultadoDaVenda(
            PAGAMENTO_IGNORADO,
            f"status {status or 'desconhecido'} não emite licença",
        )

    moeda = str(pagamento.get("currency_id", ""))
    valor = float(pagamento.get("transaction_amount") or 0.0)
    pagador = pagamento.get("payer")
    email = str((pagador.get("email") if isinstance(pagador, dict) else None) or "")

    if plano is None:
        motivo = "pagamento aprovado sem plano do RTC Check reconhecido"
    elif moeda != mp.MOEDA:
        motivo = f"moeda {moeda or 'desconhecida'} fora do esperado"
    elif abs(valor - plano.preco) >= 0.01:
        motivo = f"valor R$ {valor:.2f} difere do preço do plano {plano.codigo}"
    elif not email:
        motivo = "pagamento aprovado sem e-mail do comprador"
    else:
        motivo = ""
    if motivo:
        registrar_venda(
            diretorio,
            {
                "id_pagamento": id_pagamento,
                "evento": PAGAMENTO_RECUSADO,
                "motivo": motivo,
                "registrado_em": agora,
            },
        )
        return ResultadoDaVenda(PAGAMENTO_RECUSADO, motivo)

    assert plano is not None
    expira_em = (hoje or date.today()) + timedelta(days=plano.dias_de_licenca)
    chave = gerar_chave(Plano.ESCRITORIO, expira_em, email)
    registrar_venda(
        diretorio,
        {
            "id_pagamento": id_pagamento,
            "evento": LICENCA_EMITIDA,
            "plano": plano.codigo,
            "valor": valor,
            "email": email,
            "expira_em": expira_em.isoformat(),
            "chave": chave,
            "registrado_em": agora,
        },
    )
    return ResultadoDaVenda(
        LICENCA_EMITIDA,
        f"licença {plano.codigo} emitida até {expira_em.isoformat()}",
        chave=chave,
        email_do_comprador=email,
        plano=plano.codigo,
    )


def enviar_chave_por_email(
    config: ConfigVendas, destinatario: str, chave: str, codigo_plano: str
) -> bool:
    """Envia a chave ao comprador; sem SMTP configurado, fica só no registro."""
    if not config.smtp_host:
        return False
    mensagem = EmailMessage()
    mensagem["From"] = config.remetente or config.smtp_usuario
    mensagem["To"] = destinatario
    mensagem["Subject"] = "Sua licença do RTC Check — plano Escritório"
    mensagem.set_content(
        "Obrigado pela compra do RTC Check (plano Escritório, "
        f"{codigo_plano}).\n\n"
        "Sua chave de licença:\n\n"
        f"{chave}\n\n"
        "Para ativar, rode no computador onde o RTC Check está instalado:\n\n"
        f"  rtc-check --licenca {chave}\n\n"
        "Ou cole a chave no campo de licença da interface visual (rtc-check --app).\n"
        "Dúvidas: responda este e-mail.\n"
    )
    with smtplib.SMTP_SSL(config.smtp_host, config.smtp_porta, timeout=30) as smtp:
        if config.smtp_usuario:
            smtp.login(config.smtp_usuario, config.smtp_senha)
        smtp.send_message(mensagem)
    return True


_PAGINA_PLANOS = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RTC Check — assinar o plano Escritório</title>
<style>body{font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto;
padding:0 1rem;line-height:1.5}a.btn{display:inline-block;background:#0f766e;
color:#fff;padding:.7rem 1.2rem;border-radius:.4rem;text-decoration:none;
margin-right:.6rem}</style></head><body>
<h1>RTC Check — plano Escritório</h1>
<p>Pagamento processado pelo Mercado Pago. A chave de licença chega no e-mail
informado no checkout, normalmente em poucos minutos após a aprovação.</p>
<p><a class="btn" href="/comprar/mensal">Mensal — R$ 149</a>
<a class="btn" href="/comprar/anual">Anual — R$ 1.490</a></p>
<p>A varredura básica continua gratuita para sempre:
<a href="https://taynangt.github.io/rtc-check/">página do projeto</a>.</p>
</body></html>"""

_PAGINA_OBRIGADO = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RTC Check — pagamento recebido</title>
<style>body{font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto;
padding:0 1rem;line-height:1.5}</style></head><body>
<h1>Obrigado!</h1>
<p>Assim que o Mercado Pago confirmar o pagamento, a chave de licença será
enviada para o e-mail informado no checkout. Guarde-a: a ativação é
<code>rtc-check --licenca SUA-CHAVE</code>.</p>
<p>Se a chave não chegar em até uma hora, verifique a caixa de spam ou responda
o e-mail de contato da compra.</p>
</body></html>"""


def _handler(config: ConfigVendas) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "RTCCheckVendas/1.0"

        def log_message(self, formato: str, *args: object) -> None:
            # Nunca registrar cabeçalhos, corpo ou dados do comprador.
            if len(args) > 1 and str(args[1]) >= "400":
                super().log_message(formato, *args)

        def _enviar(
            self, corpo: bytes, tipo: str, status: HTTPStatus = HTTPStatus.OK
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, dados: object, status: HTTPStatus = HTTPStatus.OK) -> None:
            self._enviar(
                json.dumps(dados, ensure_ascii=False).encode(),
                "application/json; charset=utf-8",
                status,
            )

        def _html(self, pagina: str) -> None:
            self._enviar(pagina.encode(), "text/html; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            caminho = urlparse(self.path).path
            if caminho == "/":
                self._html(_PAGINA_PLANOS)
            elif caminho == "/obrigado":
                self._html(_PAGINA_OBRIGADO)
            elif caminho == "/saude":
                self._json({"ok": True})
            elif caminho.startswith("/comprar/"):
                self._comprar(caminho.removeprefix("/comprar/"))
            else:
                self._json({"erro": "recurso não encontrado"}, HTTPStatus.NOT_FOUND)

        def _comprar(self, codigo: str) -> None:
            plano = mp.PLANOS_DE_VENDA.get(codigo)
            if plano is None:
                self._json({"erro": "plano desconhecido"}, HTTPStatus.NOT_FOUND)
                return
            try:
                url = mp.criar_preferencia(plano, config.url_publica)
            except mp.ErroMercadoPago as erro:
                print(f"checkout indisponível: {erro}", file=sys.stderr)
                self._json(
                    {"erro": "checkout temporariamente indisponível"},
                    HTTPStatus.BAD_GATEWAY,
                )
                return
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", url)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/webhook/mercadopago":
                self._json({"erro": "recurso não encontrado"}, HTTPStatus.NOT_FOUND)
                return
            self._webhook()

        def _webhook(self) -> None:
            consulta = parse_qs(urlparse(self.path).query)
            try:
                tamanho = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                tamanho = 0
            corpo: dict[str, Any] = {}
            if 0 < tamanho <= MAX_CORPO_WEBHOOK:
                try:
                    lido = json.loads(self.rfile.read(tamanho).decode())
                    if isinstance(lido, dict):
                        corpo = lido
                except (json.JSONDecodeError, UnicodeDecodeError):
                    corpo = {}

            dado = corpo.get("data")
            id_do_dado = str(
                (consulta.get("data.id") or consulta.get("id") or [""])[0]
                or (dado.get("id") if isinstance(dado, dict) else "")
                or ""
            )
            tipo = str(
                (consulta.get("type") or consulta.get("topic") or [""])[0]
                or corpo.get("type")
                or ""
            )
            if tipo != "payment":
                self._json({"desfecho": PAGAMENTO_IGNORADO, "detalhe": f"tópico {tipo!r}"})
                return

            assinatura_ok = mp.validar_assinatura_webhook(
                self.headers.get("x-signature", ""),
                id_do_dado,
                self.headers.get("x-request-id", ""),
                config.segredo_webhook,
            )
            if not assinatura_ok:
                self._json(
                    {"erro": "assinatura do webhook inválida"}, HTTPStatus.UNAUTHORIZED
                )
                return

            try:
                resultado = processar_pagamento(id_do_dado, config.diretorio)
            except mp.ErroMercadoPago as erro:
                # 500 faz o Mercado Pago reenviar a notificação mais tarde.
                print(f"webhook adiado: {erro}", file=sys.stderr)
                self._json(
                    {"erro": "pagamento não pôde ser consultado agora"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            if resultado.desfecho == LICENCA_EMITIDA:
                try:
                    enviado = enviar_chave_por_email(
                        config,
                        resultado.email_do_comprador,
                        resultado.chave,
                        resultado.plano,
                    )
                    if not enviado:
                        print(
                            "SMTP não configurado; envie a chave manualmente "
                            f"(pagamento {id_do_dado}, registrada em vendas.jsonl)",
                            file=sys.stderr,
                        )
                except (smtplib.SMTPException, OSError) as erro:
                    print(
                        f"falha ao enviar e-mail do pagamento {id_do_dado}: {erro}; "
                        "a chave está em vendas.jsonl",
                        file=sys.stderr,
                    )
            self._json({"desfecho": resultado.desfecho, "detalhe": resultado.detalhe})

    return Handler


def executar(config: ConfigVendas, porta: int) -> int:
    servidor = ThreadingHTTPServer(("0.0.0.0", porta), _handler(config))
    print(f"RTC Check Vendas escutando na porta {servidor.server_port}")
    print(f"Checkout público: {config.url_publica} — Ctrl+C para encerrar.")
    try:
        servidor.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nRTC Check Vendas encerrado.")
    finally:
        servidor.server_close()
    return 0


def main() -> int:
    config = carregar_config()
    try:
        porta = int(os.environ.get("PORT", "8080"))
    except ValueError as erro:
        raise SystemExit("PORT precisa ser um número entre 1 e 65535") from erro
    if not 1 <= porta <= 65535:
        raise SystemExit("PORT precisa estar entre 1 e 65535")
    return executar(config, porta)


if __name__ == "__main__":
    raise SystemExit(main())
