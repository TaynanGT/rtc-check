"""Edições do RTC Check: plano gratuito, teste grátis e planos pagos.

A varredura e o relatório de texto são gratuitos para sempre, sem cadastro:
qualquer pessoa consegue descobrir se o acervo dela tem bloqueio antes do corte
de 03/08/2026. Exportação (JSON, CSV, HTML), portão de CI, regras de cadastro
e os relatórios comparativo e por CNPJ fazem parte dos planos pagos, com 14 dias
de teste grátis liberados por um comando local.

Sobre a honestidade do mecanismo: o RTC Check é AGPL, então o código deste
módulo está aberto e qualquer pessoa consegue contorná-lo. Isso é intencional e
não é um problema. A chave assinada existe para deixar o limite do plano
explícito e para evitar compartilhamento casual, não para ser DRM. Quem paga
está comprando priorização de atualizações após revisão técnica, suporte e o
direito de redistribuir; nada disso um patch local entrega.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PREFIXO_CHAVE = "RTC2"
DIAS_DE_TESTE = 14
URL_PLANOS = "https://taynangt.github.io/rtc-check/#precos"

# Chave pública Ed25519 do emissor oficial (o servidor de vendas em
# https://rtc-check-vendas.onrender.com/chave-publica). Ela pode estar no
# programa: só a chave privada, mantida fora do repositório, emite licenças.
CHAVE_PUBLICA_PADRAO = "4cbmXWpYzkAeQDfhM4u-iBl_WOJuhXFfd6LlTcqJanU"
# Chaves de emissores anteriores seguem confiáveis: licenças vendidas antes de
# uma troca de chave continuam validando após a atualização do aplicativo.
CHAVES_PUBLICAS_ANTERIORES: tuple[str, ...] = (
    "_N26nweHMOt1wkfAMGO_mZmPnVqB0IuqfnA7TOVhRpY",
)


class Plano(StrEnum):
    COMUNIDADE = "comunidade"
    TESTE = "teste"
    ESCRITORIO = "escritorio"
    PLATAFORMA = "plataforma"


NOME_DO_PLANO = {
    Plano.COMUNIDADE: "Comunidade",
    Plano.TESTE: "Teste grátis",
    Plano.ESCRITORIO: "Escritório",
    Plano.PLATAFORMA: "Plataforma",
}

# Teste grátis e Escritório liberam o mesmo conjunto de recursos. O que a
# Plataforma acrescenta é contratual (redistribuição), não técnico.
NIVEL = {
    Plano.COMUNIDADE: 0,
    Plano.TESTE: 2,
    Plano.ESCRITORIO: 2,
    Plano.PLATAFORMA: 3,
}


class Recurso(StrEnum):
    VARREDURA = "varredura"
    RELATORIO_TEXTO = "relatorio-texto"
    LISTA_COMPLETA = "lista-completa"
    FORMATO_JSON = "formato-json"
    FORMATO_CSV = "formato-csv"
    FORMATO_HTML = "formato-html"
    SAIDA_ARQUIVO = "saida-arquivo"
    PORTAO_CI = "portao-ci"
    REGRA_NCM = "regra-ncm"
    REGRA_GTIN = "regra-gtin"
    POR_CNPJ = "por-cnpj"
    COMPARATIVO = "comparativo"


PLANO_MINIMO: dict[Recurso, Plano] = {
    Recurso.VARREDURA: Plano.COMUNIDADE,
    Recurso.RELATORIO_TEXTO: Plano.COMUNIDADE,
    Recurso.LISTA_COMPLETA: Plano.ESCRITORIO,
    Recurso.FORMATO_JSON: Plano.ESCRITORIO,
    Recurso.FORMATO_CSV: Plano.ESCRITORIO,
    Recurso.FORMATO_HTML: Plano.ESCRITORIO,
    Recurso.SAIDA_ARQUIVO: Plano.ESCRITORIO,
    Recurso.PORTAO_CI: Plano.ESCRITORIO,
    Recurso.REGRA_NCM: Plano.ESCRITORIO,
    Recurso.REGRA_GTIN: Plano.ESCRITORIO,
    Recurso.POR_CNPJ: Plano.ESCRITORIO,
    Recurso.COMPARATIVO: Plano.ESCRITORIO,
}

DESCRICAO_DO_RECURSO: dict[Recurso, str] = {
    Recurso.VARREDURA: "varredura local ilimitada do acervo de XML",
    Recurso.RELATORIO_TEXTO: "relatório de texto com o total de bloqueios e SKUs",
    Recurso.LISTA_COMPLETA: "lista completa dos SKUs bloqueados, não só os primeiros",
    Recurso.FORMATO_JSON: "saída em JSON, para integrar com o ERP",
    Recurso.FORMATO_CSV: "planilha CSV para o time de cadastro",
    Recurso.FORMATO_HTML: "relatório HTML para o contador ou a diretoria",
    Recurso.SAIDA_ARQUIVO: "gravar o relatório em arquivo (--saida)",
    Recurso.PORTAO_CI: "travar o build quando houver bloqueio (--falhar-em-bloqueio)",
    Recurso.REGRA_NCM: "regra NCM001: NCM ausente ou fora do formato de 8 dígitos",
    Recurso.REGRA_GTIN: "regra GTIN001: dígito verificador GS1 inválido",
    Recurso.POR_CNPJ: "quebra do resultado por emitente (--por-cnpj)",
    Recurso.COMPARATIVO: "comparativo entre duas execuções (--comparar)",
}

# As regras RTC tratam o corte de agosto e ficam no plano gratuito: é o que faz
# a ferramenta valer para todo mundo. NCM e GTIN são higiene de cadastro.
REGRAS_GRATUITAS = frozenset(
    {"RTC001", "RTC002", "RTC003", "RTC004", "RTC005", "RTC006"}
)
REGRAS_POR_RECURSO: dict[Recurso, frozenset[str]] = {
    Recurso.REGRA_NCM: frozenset({"NCM001"}),
    Recurso.REGRA_GTIN: frozenset({"GTIN001"}),
}

# Quantos SKUs bloqueados o relatório de texto detalha no plano gratuito.
LIMITE_GRATUITO_DE_SKUS = 5
LIMITE_PAGO_DE_SKUS = 20


class LicencaInvalida(Exception):
    """Chave de licença malformada, adulterada ou vencida."""


class TesteIndisponivel(Exception):
    """O teste grátis já foi usado neste diretório de configuração."""


def _b64_codificar(valor: bytes) -> str:
    return base64.urlsafe_b64encode(valor).decode().rstrip("=")


def _b64_decodificar(valor: str) -> bytes:
    try:
        decodificado = base64.urlsafe_b64decode(valor + "=" * (-len(valor) % 4))
    except (binascii.Error, ValueError) as erro:
        raise LicencaInvalida("codificação da chave inválida") from erro
    if _b64_codificar(decodificado) != valor:
        raise LicencaInvalida("codificação da chave inválida")
    return decodificado


def _chaves_publicas() -> list[Ed25519PublicKey]:
    """Chaves de verificação confiáveis, da mais atual para as anteriores."""
    do_ambiente = os.environ.get("RTC_CHECK_CHAVE_PUBLICA")
    textos = (
        [do_ambiente]
        if do_ambiente
        else [CHAVE_PUBLICA_PADRAO, *CHAVES_PUBLICAS_ANTERIORES]
    )
    chaves = []
    for texto in textos:
        try:
            chaves.append(Ed25519PublicKey.from_public_bytes(_b64_decodificar(texto)))
        except (LicencaInvalida, ValueError) as erro:
            raise LicencaInvalida("chave pública de licença inválida") from erro
    return chaves


def _chave_privada(caminho: str | None = None) -> Ed25519PrivateKey:
    origem = caminho or os.environ.get("RTC_CHECK_CHAVE_PRIVADA")
    if not origem:
        raise ValueError(
            "para emitir licença, defina RTC_CHECK_CHAVE_PRIVADA com o caminho do PEM"
        )
    try:
        chave = serialization.load_pem_private_key(Path(origem).read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as erro:
        raise ValueError("não foi possível carregar a chave privada de licença") from erro
    if not isinstance(chave, Ed25519PrivateKey):
        raise ValueError("a chave privada de licença precisa ser Ed25519")
    return chave


def diretorio_de_config() -> Path:
    """Onde ficam a licença e o registro do teste grátis."""
    forcado = os.environ.get("RTC_CHECK_HOME")
    if forcado:
        return Path(forcado)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "rtc-check"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "rtc-check"


def _arquivo_de_licenca() -> Path:
    return diretorio_de_config() / "licenca.txt"


def _arquivo_de_teste() -> Path:
    return diretorio_de_config() / "teste.json"


def gerar_chave(
    plano: Plano,
    expira_em: date,
    titular: str,
    caminho_chave_privada: str | None = None,
) -> str:
    """Emite uma licença Ed25519; a chave privada nunca faz parte do pacote."""
    carga = json.dumps(
        {"expira_em": expira_em.isoformat(), "plano": plano.value, "titular": titular},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    assinatura = _chave_privada(caminho_chave_privada).sign(carga)
    return f"{PREFIXO_CHAVE}.{_b64_codificar(carga)}.{_b64_codificar(assinatura)}"


def _decodificar(chave: str) -> tuple[Plano, date, str]:
    partes = chave.strip().split(".")
    if len(partes) != 3 or partes[0] != PREFIXO_CHAVE:
        raise LicencaInvalida("formato de chave não reconhecido")

    _, corpo, assinatura = partes
    try:
        carga = _b64_decodificar(corpo)
        bytes_da_assinatura = _b64_decodificar(assinatura)
        verificada = False
        for chave_publica in _chaves_publicas():
            try:
                chave_publica.verify(bytes_da_assinatura, carga)
                verificada = True
                break
            except InvalidSignature:
                continue
        if not verificada:
            raise LicencaInvalida("chave corrompida")
        dados = json.loads(carga.decode())
    except (LicencaInvalida, UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise LicencaInvalida("chave corrompida") from erro

    try:
        plano = Plano(str(dados["plano"]))
        expira_em = date.fromisoformat(str(dados["expira_em"]))
        titular = str(dados["titular"])
    except (KeyError, ValueError) as erro:
        raise LicencaInvalida("conteúdo da chave inválido") from erro

    return plano, expira_em, titular


def validar_chave(chave: str, hoje: date | None = None) -> Edicao:
    plano, expira_em, titular = _decodificar(chave)
    if expira_em < (hoje or date.today()):
        raise LicencaInvalida(f"licença vencida em {expira_em.isoformat()}")
    return Edicao(plano=plano, titular=titular, expira_em=expira_em)


@dataclass(frozen=True)
class Edicao:
    """O que esta instalação pode fazer agora."""

    plano: Plano = Plano.COMUNIDADE
    titular: str = ""
    expira_em: date | None = None
    aviso: str = ""

    @property
    def nome(self) -> str:
        return NOME_DO_PLANO[self.plano]

    @property
    def pago(self) -> bool:
        return NIVEL[self.plano] > 0

    def dias_restantes(self, hoje: date | None = None) -> int | None:
        if self.expira_em is None:
            return None
        return (self.expira_em - (hoje or date.today())).days

    def tem(self, recurso: Recurso) -> bool:
        return NIVEL[self.plano] >= NIVEL[PLANO_MINIMO[recurso]]

    @property
    def recursos_liberados(self) -> list[Recurso]:
        return [r for r in Recurso if self.tem(r)]

    @property
    def recursos_bloqueados(self) -> list[Recurso]:
        return [r for r in Recurso if not self.tem(r)]

    @property
    def regras_ativas(self) -> frozenset[str]:
        regras = set(REGRAS_GRATUITAS)
        for recurso, codigos in REGRAS_POR_RECURSO.items():
            if self.tem(recurso):
                regras |= codigos
        return frozenset(regras)

    @property
    def limite_de_skus(self) -> int:
        return LIMITE_PAGO_DE_SKUS if self.tem(Recurso.LISTA_COMPLETA) else LIMITE_GRATUITO_DE_SKUS


def _ler_teste(hoje: date) -> tuple[Edicao | None, str]:
    """Devolve a edição de teste, se estiver valendo, e um aviso quando venceu."""
    arquivo = _arquivo_de_teste()
    if not arquivo.exists():
        return None, ""
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        expira_em = date.fromisoformat(str(dados["expira_em"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None, "registro do teste grátis ilegível; seguindo no plano Comunidade"

    if expira_em < hoje:
        return None, f"teste grátis venceu em {expira_em.strftime('%d/%m/%Y')}"
    return Edicao(plano=Plano.TESTE, expira_em=expira_em), ""


def iniciar_teste(hoje: date | None = None) -> Edicao:
    """Libera os 14 dias de teste uma vez por diretório de configuração."""
    hoje = hoje or date.today()
    arquivo = _arquivo_de_teste()
    if arquivo.exists():
        edicao, _ = _ler_teste(hoje)
        if edicao is not None and edicao.expira_em is not None:
            raise TesteIndisponivel(
                f"o teste grátis já está ativo até {edicao.expira_em:%d/%m/%Y}"
            )
        raise TesteIndisponivel(
            f"o teste grátis deste diretório de configuração já foi usado. Planos: {URL_PLANOS}"
        )

    expira_em = hoje + timedelta(days=DIAS_DE_TESTE)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        json.dumps(
            {
                "iniciado_em": hoje.isoformat(),
                "expira_em": expira_em.isoformat(),
                "registrado_em": datetime.now().isoformat(timespec="seconds"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return Edicao(plano=Plano.TESTE, expira_em=expira_em)


def salvar_licenca(chave: str, hoje: date | None = None) -> Edicao:
    """Confere a chave e guarda no diretório de config para as próximas execuções."""
    edicao = validar_chave(chave, hoje)
    arquivo = _arquivo_de_licenca()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(chave.strip() + "\n", encoding="utf-8")
    return edicao


def _chave_configurada(chave_da_linha: str | None) -> tuple[str | None, str]:
    if chave_da_linha:
        return chave_da_linha, "--licenca"
    do_ambiente = os.environ.get("RTC_CHECK_LICENCA")
    if do_ambiente:
        return do_ambiente, "RTC_CHECK_LICENCA"
    arquivo = _arquivo_de_licenca()
    if arquivo.exists():
        try:
            conteudo = arquivo.read_text(encoding="utf-8").strip()
        except OSError:
            return None, ""
        if conteudo:
            return conteudo, str(arquivo)
    return None, ""


def resolver(chave: str | None = None, hoje: date | None = None) -> Edicao:
    """Descobre em qual edição esta execução está rodando.

    Ordem: chave explícita, variável de ambiente, arquivo de licença, teste
    grátis em andamento e, por fim, o plano Comunidade. Chave inválida nunca
    derruba a execução: cai para Comunidade com um aviso, porque a varredura
    importa mais do que a cobrança.
    """
    hoje = hoje or date.today()
    aviso = ""

    bruta, origem = _chave_configurada(chave)
    if bruta:
        try:
            return validar_chave(bruta, hoje)
        except LicencaInvalida as erro:
            aviso = f"licença de {origem} ignorada: {erro}"

    edicao_de_teste, aviso_do_teste = _ler_teste(hoje)
    if edicao_de_teste is not None:
        if not aviso:
            return edicao_de_teste
        return Edicao(
            plano=edicao_de_teste.plano,
            expira_em=edicao_de_teste.expira_em,
            aviso=aviso,
        )

    return Edicao(plano=Plano.COMUNIDADE, aviso=aviso or aviso_do_teste)


def como_liberar(recurso: Recurso) -> str:
    """Mensagem mostrada quando alguém pede um recurso que o plano não cobre."""
    caminhos = [
        (f"teste grátis por {DIAS_DE_TESTE} dias:", "rtc-check --iniciar-teste"),
        ("já tem uma chave:", "rtc-check --licenca RTC2...."),
        ("planos e preços:", URL_PLANOS),
    ]
    largura = max(len(rotulo) for rotulo, _ in caminhos)
    return "\n".join(
        [
            f"'{DESCRICAO_DO_RECURSO[recurso]}' faz parte do plano "
            f"{NOME_DO_PLANO[PLANO_MINIMO[recurso]]}.",
            *(f"  {rotulo.ljust(largura)}  {valor}" for rotulo, valor in caminhos),
        ]
    )
