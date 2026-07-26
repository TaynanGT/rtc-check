"""Catálogo explicável e versionado das verificações do RTC Check."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

from .normativa import NORMATIVA_RTC

StatusRegra = Literal["oficial_ativa", "oficial_futura", "higiene_cadastral"]
ConfiancaRegra = Literal["deterministica", "orientativa"]


@dataclass(frozen=True)
class RegraCatalogo:
    codigo: str
    titulo: str
    campo: str
    referencia: str
    rejeicao: str | None
    impacto: str
    acao: str
    responsavel: str
    status: StatusRegra
    confianca: ConfiancaRegra
    fonte: str

    def como_json(self) -> dict[str, str | None]:
        return asdict(self)


REGRAS: dict[str, RegraCatalogo] = {
    "RTC001": RegraCatalogo(
        codigo="RTC001",
        titulo="Grupo IBS/CBS ausente",
        campo="det/imposto/IBSCBS",
        referencia="UB12-10",
        rejeicao="1115",
        impacto="A NF-e em escopo pode ser rejeitada a partir do corte operacional.",
        acao="Parametrize o ERP para gerar o grupo IBSCBS nos itens em escopo.",
        responsavel="ERP / cadastro fiscal",
        status="oficial_futura",
        confianca="deterministica",
        fonte=NORMATIVA_RTC.fonte,
    ),
    "RTC002": RegraCatalogo(
        codigo="RTC002",
        titulo="Classificação tributária ausente",
        campo="det/imposto/IBSCBS/cClassTrib",
        referencia="Layout 1-1",
        rejeicao=None,
        impacto="O item não informa o tratamento tributário exigido pelo novo leiaute.",
        acao="Preencha cClassTrib conforme o tratamento tributário da operação.",
        responsavel="Fiscal / cadastro tributário",
        status="oficial_ativa",
        confianca="deterministica",
        fonte=NORMATIVA_RTC.fonte,
    ),
    "RTC003": RegraCatalogo(
        codigo="RTC003",
        titulo="CST IBS/CBS inexistente",
        campo="det/imposto/IBSCBS/CST",
        referencia="UB13-10",
        rejeicao=None,
        impacto="O código não pertence à tabela oficial usada por esta versão.",
        acao="Substitua o CST IBS/CBS por um código vigente na tabela oficial.",
        responsavel="Fiscal / ERP",
        status="oficial_ativa",
        confianca="deterministica",
        fonte=NORMATIVA_RTC.fonte_tabela,
    ),
    "RTC004": RegraCatalogo(
        codigo="RTC004",
        titulo="Detalhamento IBS/CBS obrigatório ausente",
        campo="det/imposto/IBSCBS/gIBSCBS",
        referencia="UB13-30",
        rejeicao="1022",
        impacto="O CST exige o detalhamento, mas o grupo não foi informado.",
        acao="Inclua o grupo gIBSCBS exigido pelo CST informado.",
        responsavel="ERP / motor tributário",
        status="oficial_ativa",
        confianca="deterministica",
        fonte=NORMATIVA_RTC.fonte,
    ),
    "RTC005": RegraCatalogo(
        codigo="RTC005",
        titulo="Detalhamento IBS/CBS incompatível",
        campo="det/imposto/IBSCBS/gIBSCBS",
        referencia="UB13-20",
        rejeicao="1021",
        impacto="O CST proíbe o detalhamento presente no XML.",
        acao="Remova gIBSCBS ou ajuste o CST incompatível.",
        responsavel="ERP / motor tributário",
        status="oficial_ativa",
        confianca="deterministica",
        fonte=NORMATIVA_RTC.fonte,
    ),
    "RTC006": RegraCatalogo(
        codigo="RTC006",
        titulo="cClassTrib fora da tabela vigente",
        campo="det/imposto/IBSCBS/cClassTrib",
        referencia="IT 2025.002",
        rejeicao=None,
        impacto="A classificação não é válida para NF-e no snapshot oficial embarcado.",
        acao="Revise o cClassTrib na tabela vigente para NF-e modelo 55.",
        responsavel="Fiscal / cadastro tributário",
        status="oficial_ativa",
        confianca="deterministica",
        fonte=NORMATIVA_RTC.fonte_tabela,
    ),
    "NCM001": RegraCatalogo(
        codigo="NCM001",
        titulo="NCM inválido",
        campo="det/prod/NCM",
        referencia="Leiaute NF-e 4.00",
        rejeicao=None,
        impacto="O cadastro usa NCM ausente ou fora do formato de oito dígitos.",
        acao="Corrija o NCM para oito dígitos antes de reenviar ao cadastro.",
        responsavel="Cadastro de produtos",
        status="higiene_cadastral",
        confianca="deterministica",
        fonte=NORMATIVA_RTC.fonte,
    ),
    "GTIN001": RegraCatalogo(
        codigo="GTIN001",
        titulo="GTIN ausente ou inconsistente",
        campo="det/prod/cEAN",
        referencia="Leiaute NF-e 4.00",
        rejeicao=None,
        impacto="O código de barras não atende ao formato ou ao dígito verificador.",
        acao="Corrija o GTIN ou use SEM GTIN quando o leiaute permitir.",
        responsavel="Cadastro de produtos",
        status="higiene_cadastral",
        confianca="orientativa",
        fonte=NORMATIVA_RTC.fonte,
    ),
}


COBERTURA = {
    "documentos": ["NF-e modelo 55"],
    "layouts": ["3.10 (triagem de legado)", "4.00"],
    "regimes": ["CRT=3 no corte RTC", "higiene cadastral para demais notas"],
    "incluido": [
        "presença e coerência básica de IBSCBS",
        "CST IBS/CBS",
        "cClassTrib",
        "gIBSCBS",
        "NCM",
        "GTIN",
    ],
    "fora_de_escopo": [
        "cálculo integral de tributos",
        "assinatura ou transmissão de NF-e",
        "parecer jurídico ou contábil",
        "NFS-e, CT-e e eventos fiscais",
    ],
}


def catalogo_json() -> list[dict[str, str | None]]:
    return [REGRAS[codigo].como_json() for codigo in sorted(REGRAS)]


def regra(codigo: str) -> RegraCatalogo | None:
    return REGRAS.get(codigo)


def dias_desde_snapshot(hoje: date | None = None) -> int:
    return ((hoje or date.today()) - NORMATIVA_RTC.tabela_publicada_em).days

