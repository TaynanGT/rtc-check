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
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import mercadopago as mp
from .edicao import Plano, _b64_codificar, _chave_privada, gerar_chave

MAX_CORPO_WEBHOOK = 64 * 1024
LIMITE_DE_COMPRAS_POR_MINUTO = 10
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


def _diretorio_de_dados() -> Path:
    """Resolve RTC_CHECK_VENDAS_DIR com validação do caminho.

    Caminho relativo fica confinado ao diretório de trabalho do serviço (um
    valor com ``..`` que escape dele é recusado). Caminho absoluto — ex.: o
    disco persistente do Render — precisa morar numa raiz de dados usual, o
    que barra typos e valores hostis apontando para áreas do sistema.
    """
    bruto = os.environ.get("RTC_CHECK_VENDAS_DIR", "vendas").strip() or "vendas"
    if os.path.isabs(bruto):
        candidato = os.path.normpath(bruto)
        if candidato.startswith("/var/"):
            return Path(candidato)
        if candidato.startswith("/srv/"):
            return Path(candidato)
        if candidato.startswith("/opt/"):
            return Path(candidato)
        if candidato.startswith("/data/"):
            return Path(candidato)
        if candidato.startswith("/home/"):
            return Path(candidato)
        raise SystemExit(
            "RTC_CHECK_VENDAS_DIR absoluto precisa ficar em /var, /srv, /opt, "
            f"/data ou /home: {bruto!r}"
        )
    raiz = os.getcwd()
    candidato = os.path.normpath(os.path.join(raiz, bruto))
    if not candidato.startswith(raiz + os.sep):
        raise SystemExit(
            f"RTC_CHECK_VENDAS_DIR relativo precisa ficar dentro de {raiz}: {bruto!r}"
        )
    return Path(candidato)


def _normalizar_pem(texto: str) -> str:
    """Reconstrói o PEM quando o campo de ambiente achatou as quebras de linha.

    Campos de variável de ambiente costumam colar o bloco numa linha só, e o
    formato PEM exige os marcadores em linhas próprias. O corpo base64 é
    extraído entre os marcadores e o bloco é remontado.
    """
    inicio = "-----BEGIN PRIVATE KEY-----"
    fim = "-----END PRIVATE KEY-----"
    aparado = texto.strip()
    if inicio not in aparado or fim not in aparado:
        return aparado
    corpo = aparado.split(inicio, 1)[1].split(fim, 1)[0]
    corpo_limpo = "".join(corpo.split())
    return f"{inicio}\n{corpo_limpo}\n{fim}\n"


def _pem_ed25519_valido(texto: str) -> bool:
    try:
        chave = serialization.load_pem_private_key(texto.encode(), password=None)
    except (ValueError, TypeError):
        return False
    return isinstance(chave, Ed25519PrivateKey)


def garantir_chave_de_emissao(diretorio: Path) -> None:
    """Garante uma chave Ed25519 de emissão para este processo.

    Ordem: RTC_CHECK_CHAVE_PRIVADA (caminho de um PEM), depois
    RTC_CHECK_CHAVE_PRIVADA_PEM (o conteúdo do PEM, para hospedagem sem disco
    persistente) e, por fim, geração local no primeiro boot. Em hospedagem
    sem disco (ex.: plano gratuito do Render), o PEM gerado é mostrado no log
    privado do serviço para o operador copiá-lo para o ambiente — sem isso, um
    reinício criaria outra chave e as licenças já vendidas seriam órfãs.
    """
    if os.environ.get("RTC_CHECK_CHAVE_PRIVADA"):
        return
    caminho = diretorio / "emissor-ed25519.pem"
    bruto = os.environ.get("RTC_CHECK_CHAVE_PRIVADA_PEM", "")
    pem_do_ambiente = _normalizar_pem(bruto)
    if pem_do_ambiente and not _pem_ed25519_valido(pem_do_ambiente):
        # Placeholder ou valor truncado não pode virar a chave do emissor. O
        # diagnóstico ajuda o operador sem expor conteúdo além do marcador.
        tem_marcador = "-----BEGIN PRIVATE KEY-----" in bruto
        print(
            "RTC_CHECK_CHAVE_PRIVADA_PEM não contém um PEM Ed25519 válido "
            f"(valor com {len(bruto.strip())} caracteres, marcador BEGIN "
            f"{'presente' if tem_marcador else 'AUSENTE'}); ignorando e "
            "usando/gerando a chave local",
            file=sys.stderr,
        )
        pem_do_ambiente = ""
    os.environ["RTC_CHECK_ORIGEM_DA_CHAVE"] = (
        "ambiente" if pem_do_ambiente else "disco-local"
    )
    if pem_do_ambiente:
        diretorio.mkdir(parents=True, exist_ok=True)
        caminho.write_text(pem_do_ambiente + "\n", encoding="utf-8")
        caminho.chmod(0o600)
    elif not caminho.exists():
        diretorio.mkdir(parents=True, exist_ok=True)
        privada = Ed25519PrivateKey.generate()
        pem = privada.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        caminho.write_bytes(pem)
        caminho.chmod(0o600)
        print(f"chave de emissão Ed25519 gerada em {caminho}", file=sys.stderr)
        if os.environ.get("RENDER") or os.environ.get("RTC_CHECK_MOSTRAR_PEM") == "1":
            print(
                "esta hospedagem pode não ter disco persistente. Copie o bloco "
                "abaixo para a variável de ambiente RTC_CHECK_CHAVE_PRIVADA_PEM "
                "para a chave sobreviver a reinícios:\n" + pem.decode(),
                file=sys.stderr,
            )
    os.environ["RTC_CHECK_CHAVE_PRIVADA"] = str(caminho)


def chave_publica_do_emissor() -> str:
    """Chave pública (base64url) correspondente à chave de emissão em uso."""
    publica = _chave_privada().public_key()
    return _b64_codificar(
        publica.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )


def carregar_config() -> ConfigVendas:
    # Plataformas como o Render informam a própria URL pública do serviço.
    url_publica = (
        os.environ.get("RTC_CHECK_VENDAS_URL", "").strip()
        or os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    ).rstrip("/")
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
    diretorio = _diretorio_de_dados()
    garantir_chave_de_emissao(diretorio)
    return ConfigVendas(
        url_publica=url_publica,
        segredo_webhook=segredo,
        diretorio=diretorio,
        smtp_host=os.environ.get("SMTP_HOST", "").strip(),
        smtp_porta=smtp_porta,
        smtp_usuario=os.environ.get("SMTP_USER", "").strip(),
        smtp_senha=os.environ.get("SMTP_PASS", ""),
        remetente=os.environ.get("SMTP_FROM", "").strip(),
    )


def _arquivo_de_vendas(diretorio: Path) -> Path:
    return diretorio / "vendas.jsonl"


def eventos_registrados(diretorio: Path, id_pagamento: str) -> set[str]:
    """Eventos já gravados para um pagamento; base da idempotência por evento.

    A idempotência precisa ser por (pagamento, evento), não por pagamento: um
    reembolso chega depois da emissão da licença para o mesmo id e ainda
    precisa ser registrado.
    """
    arquivo = _arquivo_de_vendas(diretorio)
    if not arquivo.exists():
        return set()
    with _TRAVA_REGISTRO:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    eventos: set[str] = set()
    for linha in linhas:
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(registro, dict) and registro.get("id_pagamento") == id_pagamento:
            eventos.add(str(registro.get("evento", "")))
    return eventos


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
    expira_em: str = ""


def processar_pagamento(
    id_pagamento: str,
    diretorio: Path,
    *,
    buscar_pagamento: Callable[[str], dict[str, Any]] | None = None,
    hoje: date | None = None,
) -> ResultadoDaVenda:
    """Aplica o contrato do checkout a uma notificação de pagamento.

    A licença só é emitida com status aprovado, ambiente de produção, moeda e
    valor corretos e no máximo uma vez por pagamento. Estados finais
    (cancelamento, reembolso, chargeback) são registrados mesmo quando chegam
    depois da emissão; a chave já emitida expira sozinha. O pagamento é sempre
    reconsultado na API — o corpo do webhook nunca é confiável.
    """
    eventos = eventos_registrados(diretorio, id_pagamento)
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
        if evento in eventos:
            return ResultadoDaVenda(PAGAMENTO_DUPLICADO, f"{evento} já registrado")
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

    if LICENCA_EMITIDA in eventos:
        return ResultadoDaVenda(
            PAGAMENTO_DUPLICADO, "licença já emitida para este pagamento"
        )

    moeda = str(pagamento.get("currency_id", ""))
    valor = float(pagamento.get("transaction_amount") or 0.0)
    pagador = pagamento.get("payer")
    email = str((pagador.get("email") if isinstance(pagador, dict) else None) or "")

    if pagamento.get("live_mode") is False:
        motivo = "pagamento do ambiente de teste do Mercado Pago não emite licença"
    elif plano is None:
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
        if PAGAMENTO_RECUSADO in eventos:
            return ResultadoDaVenda(PAGAMENTO_DUPLICADO, "recusa já registrada")
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

    if plano is None:  # impossível após a validação acima; explícito para tipos
        raise mp.ErroMercadoPago("plano ausente após validação do pagamento")
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
        expira_em=expira_em.isoformat(),
    )


def enviar_chave_por_email(
    config: ConfigVendas,
    destinatario: str,
    chave: str,
    codigo_plano: str,
    expira_em: str = "",
    id_pagamento: str = "",
) -> bool:
    """Envia a chave ao comprador; sem SMTP configurado, fica só no registro."""
    if not config.smtp_host:
        return False
    mensagem = EmailMessage()
    mensagem["From"] = config.remetente or config.smtp_usuario
    mensagem["To"] = destinatario
    # Cópia oculta para o vendedor: em hospedagem sem disco persistente, o
    # e-mail é o registro durável da chave emitida.
    copia_do_vendedor = config.smtp_usuario or config.remetente
    if copia_do_vendedor:
        mensagem["Bcc"] = copia_do_vendedor
    mensagem["Subject"] = "Sua licença do RTC Check — plano Escritório"
    validade = ""
    if expira_em:
        try:
            validade = f", válida até {date.fromisoformat(expira_em):%d/%m/%Y}"
        except ValueError:
            validade = ""
    referencia = (
        f"Referência da compra: pagamento Mercado Pago {id_pagamento}.\n"
        if id_pagamento
        else ""
    )
    mensagem.set_content(
        "Obrigado pela compra do RTC Check (plano Escritório, "
        f"{codigo_plano}{validade}).\n\n"
        "Sua chave de licença:\n\n"
        f"{chave}\n\n"
        "Para ativar, rode no computador onde o RTC Check está instalado:\n\n"
        f"  rtc-check --licenca {chave}\n\n"
        "Ou cole a chave no campo de licença da interface visual (rtc-check --app).\n"
        f"{referencia}"
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
%%MENSAGEM%%
<p>Se a chave não chegar, verifique a caixa de spam ou responda
o e-mail de contato da compra.</p>
</body></html>"""

_MENSAGEM_APROVADO = (
    "<p>Assim que o Mercado Pago confirmar o pagamento, a chave de licença será "
    "enviada para o e-mail informado no checkout, normalmente em poucos minutos. "
    "Guarde-a: a ativação é <code>rtc-check --licenca SUA-CHAVE</code>.</p>"
)
_MENSAGEM_PENDENTE = (
    "<p>Seu pagamento está <strong>aguardando compensação</strong> (comum no "
    "boleto, que pode levar até 3 dias úteis). Assim que o Mercado Pago "
    "confirmar, a chave de licença será enviada para o e-mail informado no "
    "checkout. A ativação é <code>rtc-check --licenca SUA-CHAVE</code>.</p>"
)


def _handler(config: ConfigVendas) -> type[BaseHTTPRequestHandler]:
    compras_recentes: dict[str, list[float]] = {}
    trava_compras = threading.Lock()

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
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            )
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

        def do_HEAD(self) -> None:  # noqa: N802
            # Monitores de disponibilidade costumam usar HEAD.
            caminho = urlparse(self.path).path
            conhecido = caminho in {"/", "/obrigado", "/saude", "/chave-publica"}
            self.send_response(
                HTTPStatus.OK if conhecido else HTTPStatus.NOT_FOUND
            )
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            caminho = urlparse(self.path).path
            if caminho == "/":
                self._html(_PAGINA_PLANOS)
            elif caminho == "/obrigado":
                consulta = parse_qs(urlparse(self.path).query)
                retorno = str(
                    (consulta.get("collection_status") or consulta.get("status") or [""])[0]
                )
                pendente = retorno in {"pending", "in_process"}
                self._html(
                    _PAGINA_OBRIGADO.replace(
                        "%%MENSAGEM%%",
                        _MENSAGEM_PENDENTE if pendente else _MENSAGEM_APROVADO,
                    )
                )
            elif caminho == "/saude":
                self._json(
                    {
                        "ok": True,
                        # true = RTC_CHECK_CHAVE_PRIVADA_PEM válida: a chave
                        # de emissão sobrevive a reinícios e deploys.
                        "chave_fixada_no_ambiente": (
                            os.environ.get("RTC_CHECK_ORIGEM_DA_CHAVE") == "ambiente"
                        ),
                    }
                )
            elif caminho == "/chave-publica":
                self._chave_publica()
            elif caminho.startswith("/comprar/"):
                self._comprar(caminho.removeprefix("/comprar/"))
            else:
                self._json({"erro": "recurso não encontrado"}, HTTPStatus.NOT_FOUND)

        def _chave_publica(self) -> None:
            # Chave pública é pública: é ela que as instalações dos clientes
            # usam (via CHAVE_PUBLICA_PADRAO) para validar as licenças vendidas.
            try:
                publica = chave_publica_do_emissor()
            except ValueError:
                self._json(
                    {"erro": "chave de emissão ainda não configurada"},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
                return
            self._json(
                {
                    "chave_publica": publica,
                    "instrucao": (
                        "copie este valor para CHAVE_PUBLICA_PADRAO em "
                        "src/rtc_check/edicao.py"
                    ),
                }
            )

        def _ip_do_cliente(self) -> str:
            # Atrás do proxy da hospedagem, o IP real vem em X-Forwarded-For.
            encaminhado = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            return encaminhado or self.client_address[0]

        def _dentro_do_limite_de_compras(self) -> bool:
            agora = time.monotonic()
            ip = self._ip_do_cliente()
            with trava_compras:
                historico = [t for t in compras_recentes.get(ip, []) if agora - t < 60]
                if len(historico) >= LIMITE_DE_COMPRAS_POR_MINUTO:
                    compras_recentes[ip] = historico
                    return False
                historico.append(agora)
                compras_recentes[ip] = historico
                if len(compras_recentes) > 10_000:
                    compras_recentes.clear()
            return True

        def _comprar(self, codigo: str) -> None:
            plano = mp.PLANOS_DE_VENDA.get(codigo)
            if plano is None:
                self._json({"erro": "plano desconhecido"}, HTTPStatus.NOT_FOUND)
                return
            if not self._dentro_do_limite_de_compras():
                self._json(
                    {"erro": "muitas tentativas deste endereço; aguarde um minuto"},
                    HTTPStatus.TOO_MANY_REQUESTS,
                )
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

            # Uma linha auditável por notificação, sem e-mail nem chave.
            print(f"webhook: pagamento={id_do_dado} desfecho={resultado.desfecho}")
            if resultado.desfecho == LICENCA_EMITIDA:
                try:
                    enviado = enviar_chave_por_email(
                        config,
                        resultado.email_do_comprador,
                        resultado.chave,
                        resultado.plano,
                        resultado.expira_em,
                        id_do_dado,
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
    # Servidor público atrás do proxy TLS da hospedagem. Vazio = todas as
    # interfaces; RTC_CHECK_VENDAS_BIND restringe quando houver motivo.
    endereco = os.environ.get("RTC_CHECK_VENDAS_BIND", "")
    servidor = ThreadingHTTPServer((endereco, porta), _handler(config))
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
