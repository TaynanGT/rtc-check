"""Regras de prontidão para o corte de 03/08/2026 (NT 2025.002-RTC)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from . import gtin
from .normativa import NORMATIVA_RTC
from .parser import Item, NotaFiscal
from .tabelas_rtc import (
    CPROD_ANP_MONOFASICOS,
    CSTS_EXIGEM_GIBSCBS,
    CSTS_IBSCBS,
    CSTS_PROIBEM_GIBSCBS,
)

# Mantido como alias público para consumidores que já importam a constante.
CORTE_OBRIGATORIEDADE = NORMATIVA_RTC.corte_obrigatoriedade


class Severidade(StrEnum):
    BLOQUEIO = "bloqueio"
    ALERTA = "alerta"
    INFO = "info"


@dataclass(frozen=True)
class Achado:
    severidade: Severidade
    codigo: str
    mensagem: str
    sku: str
    descricao: str
    ncm: str
    arquivo: str
    emitente_documento: str

    @property
    def chave_sku(self) -> tuple[str, str, str]:
        return (self.emitente_documento, self.sku, self.codigo)


def _achado(
    sev: Severidade,
    codigo: str,
    mensagem: str,
    nota: NotaFiscal,
    item: Item,
    arquivo: str | None = None,
) -> Achado:
    return Achado(
        severidade=sev,
        codigo=codigo,
        mensagem=mensagem,
        sku=item.codigo,
        descricao=item.descricao,
        ncm=item.ncm,
        arquivo=arquivo or nota.arquivo.name,
        emitente_documento=nota.emitente_cnpj,
    )


# A edição em uso decide quais regras rodam. As regras RTC001-RTC005 tratam o
# corte da RTC e ficam gratuitas; NCM001 e GTIN001 são higiene de cadastro.
TODAS_AS_REGRAS = frozenset(
    {
        "RTC001",
        "RTC002",
        "RTC003",
        "RTC004",
        "RTC005",
        "NCM001",
        "GTIN001",
    }
)


def avaliar_item(
    nota: NotaFiscal,
    item: Item,
    regras: frozenset[str] | None = None,
    arquivo: str | None = None,
) -> list[Achado]:
    ativas = TODAS_AS_REGRAS if regras is None else regras
    achados: list[Achado] = []

    if nota.em_escopo_agosto:
        excecao_ub12 = (
            nota.referencia_nfe_anterior_2026
            or item.cprod_anp in CPROD_ANP_MONOFASICOS
        )
        if (
            "RTC001" in ativas
            and not item.tem_ibscbs
            and not excecao_ub12
        ):
            achados.append(
                _achado(
                    Severidade.BLOQUEIO,
                    "RTC001",
                    "Item sem o grupo pai IBSCBS exigido pela UB12-10. Se esse "
                    "padrão continuar, uma NF-e CRT=3 emitida a partir de "
                    "03/08/2026 será rejeitada (1115).",
                    nota,
                    item,
                    arquivo,
                )
            )
        elif item.tem_ibscbs:
            if "RTC002" in ativas and not item.tem_class_trib:
                achados.append(
                    _achado(
                        Severidade.BLOQUEIO,
                        "RTC002",
                        "Grupo IBSCBS presente sem cClassTrib, campo 1-1 no "
                        "layout da NT 2025.002-RTC.",
                        nota,
                        item,
                        arquivo,
                    )
                )
            if "RTC003" in ativas and item.cst_ibscbs not in CSTS_IBSCBS:
                valor = item.cst_ibscbs or "(vazio)"
                achados.append(
                    _achado(
                        Severidade.BLOQUEIO,
                        "RTC003",
                        f"CST do IBS/CBS '{valor}' inexistente na tabela oficial "
                        "v1.60 (UB13-10).",
                        nota,
                        item,
                        arquivo,
                    )
                )
            elif (
                "RTC004" in ativas
                and item.cst_ibscbs in CSTS_EXIGEM_GIBSCBS
                and not item.tem_gibscbs
                and nota.tipo_nota_debito != "07"
            ):
                achados.append(
                    _achado(
                        Severidade.BLOQUEIO,
                        "RTC004",
                        f"CST {item.cst_ibscbs} exige gIBSCBS, mas o grupo não "
                        "foi informado (UB13-30, rejeição 1022).",
                        nota,
                        item,
                        arquivo,
                    )
                )
            elif (
                "RTC005" in ativas
                and item.cst_ibscbs in CSTS_PROIBEM_GIBSCBS
                and item.tem_gibscbs
            ):
                achados.append(
                    _achado(
                        Severidade.BLOQUEIO,
                        "RTC005",
                        f"CST {item.cst_ibscbs} proíbe gIBSCBS, mas o grupo foi "
                        "informado (UB13-20, rejeição 1021).",
                        nota,
                        item,
                        arquivo,
                    )
                )

    if "NCM001" in ativas and (
        not item.ncm or len(item.ncm) != 8 or not item.ncm.isdigit()
    ):
        achados.append(
            _achado(
                Severidade.BLOQUEIO,
                "NCM001",
                f"NCM '{item.ncm or '(vazio)'}' inválido: esperado 8 dígitos "
                "numéricos.",
                nota,
                item,
                arquivo,
            )
        )

    if "GTIN001" in ativas:
        if gtin.esta_vazio(item.cean):
            if nota.exige_literal_sem_gtin:
                achados.append(
                    _achado(
                        Severidade.ALERTA,
                        "GTIN001",
                        "cEAN vazio. No layout 4.00, produto sem código de barras "
                        "precisa do literal 'SEM GTIN'.",
                        nota,
                        item,
                        arquivo,
                    )
                )
        else:
            valido, motivo = gtin.validar(item.cean)
            if not valido:
                achados.append(
                    _achado(
                        Severidade.ALERTA,
                        "GTIN001",
                        motivo,
                        nota,
                        item,
                        arquivo,
                    )
                )

    return achados


def avaliar_nota(
    nota: NotaFiscal,
    regras: frozenset[str] | None = None,
    arquivo: str | None = None,
) -> list[Achado]:
    achados: list[Achado] = []
    for item in nota.itens:
        achados.extend(avaliar_item(nota, item, regras, arquivo))
    return achados


def dias_ate_corte(hoje: date | None = None) -> int:
    return (CORTE_OBRIGATORIEDADE - (hoje or date.today())).days
