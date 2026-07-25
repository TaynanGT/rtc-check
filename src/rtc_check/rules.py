"""Regras de prontidão para o corte de 03/08/2026 (NT 2025.002 - RTC).

Cada regra devolve achados por item. O foco é responder uma pergunta só:
*quais SKUs precisam de ação antes da data?*
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from . import gtin
from .parser import Item, NotaFiscal

# Data em que o SEFAZ passa a rejeitar NF-e sem IBS/CBS para CRT=3.
CORTE_OBRIGATORIEDADE = date(2026, 8, 3)


class Severidade(StrEnum):
    BLOQUEIO = "bloqueio"  # rejeita a nota depois do corte
    ALERTA = "alerta"  # não rejeita, mas gera risco fiscal
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

    @property
    def chave_sku(self) -> tuple[str, str]:
        return (self.sku, self.codigo)


def _achado(
    sev: Severidade, codigo: str, mensagem: str, nota: NotaFiscal, item: Item
) -> Achado:
    return Achado(
        severidade=sev,
        codigo=codigo,
        mensagem=mensagem,
        sku=item.codigo,
        descricao=item.descricao,
        ncm=item.ncm,
        arquivo=nota.arquivo.name,
    )


# Todas as regras conhecidas. A edição em uso decide quais rodam: RTC001 e
# RTC002 são o corte de agosto e ficam sempre ativas; NCM001 e GTIN001 são
# higiene de cadastro e entram nos planos pagos.
TODAS_AS_REGRAS = frozenset({"RTC001", "RTC002", "NCM001", "GTIN001"})


def avaliar_item(
    nota: NotaFiscal, item: Item, regras: frozenset[str] | None = None
) -> list[Achado]:
    ativas = TODAS_AS_REGRAS if regras is None else regras
    achados: list[Achado] = []

    if nota.em_escopo_agosto:
        if not item.tem_grupo_rtc:
            if "RTC001" in ativas:
                achados.append(
                    _achado(
                        Severidade.BLOQUEIO,
                        "RTC001",
                        "Item sem o grupo gIBSCBS. Emitente CRT=3 passa a ter a nota "
                        "rejeitada a partir de 03/08/2026.",
                        nota,
                        item,
                    )
                )
        elif not item.tem_class_trib and "RTC002" in ativas:
            achados.append(
                _achado(
                    Severidade.BLOQUEIO,
                    "RTC002",
                    "Grupo gIBSCBS presente mas sem cClassTrib. O código de "
                    "classificação tributária é obrigatório por item.",
                    nota,
                    item,
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
            )
        )

    if "GTIN001" in ativas:
        if gtin.esta_vazio(item.cean):
            # Antes do layout 4.00 nao existia o literal "SEM GTIN": cEAN vazio era
            # a forma correta de declarar produto sem codigo de barras. Cobrar o
            # literal numa nota antiga e falso positivo, e falso positivo derruba a
            # confianca no relatorio inteiro.
            if nota.exige_literal_sem_gtin:
                achados.append(
                    _achado(
                        Severidade.ALERTA,
                        "GTIN001",
                        "cEAN vazio. No layout 4.00, produto sem código de barras "
                        "precisa do literal 'SEM GTIN'.",
                        nota,
                        item,
                    )
                )
        else:
            valido, motivo = gtin.validar(item.cean)
            if not valido:
                achados.append(
                    _achado(Severidade.ALERTA, "GTIN001", motivo, nota, item)
                )

    return achados


def avaliar_nota(nota: NotaFiscal, regras: frozenset[str] | None = None) -> list[Achado]:
    achados: list[Achado] = []
    for item in nota.itens:
        achados.extend(avaliar_item(nota, item, regras))
    return achados


def dias_ate_corte(hoje: date | None = None) -> int:
    return (CORTE_OBRIGATORIEDADE - (hoje or date.today())).days
