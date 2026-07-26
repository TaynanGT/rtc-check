"""Regras de prontidão para o corte de 03/08/2026 (NT 2025.002-RTC)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from . import gtin
from .normativa import NORMATIVA_RTC
from .parser import Item, NotaFiscal
from .tabelas_rtc import (
    CCLASSTRIB_NFE,
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


# A edição em uso decide quais regras rodam. As regras RTC001-RTC007 tratam o
# corte da RTC e ficam gratuitas; NCM001 e GTIN001 são higiene de cadastro.
TODAS_AS_REGRAS = frozenset(
    {
        "RTC001",
        "RTC002",
        "RTC003",
        "RTC004",
        "RTC005",
        "RTC006",
        "RTC007",
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
            # cClassTrib vazio já é o RTC002; RTC006 trata só código preenchido
            # e inválido, para um defeito não render dois bloqueios.
            if (
                "RTC006" in ativas
                and item.tem_class_trib
                and item.cclass_trib not in CCLASSTRIB_NFE
            ):
                achados.append(
                    _achado(
                        Severidade.BLOQUEIO,
                        "RTC006",
                        f"cClassTrib '{item.cclass_trib}' não é vigente para NF-e "
                        "na tabela oficial v1.60 do IT 2025.002.",
                        nota,
                        item,
                        arquivo,
                    )
                )
            # Na tabela oficial, os 3 primeiros dígitos do cClassTrib são o
            # próprio CST; um par individualmente válido mas incoerente seria
            # rejeitado e passava aqui sem nenhum achado.
            if (
                "RTC007" in ativas
                and item.cst_ibscbs in CSTS_IBSCBS
                and item.cclass_trib in CCLASSTRIB_NFE
                and item.cclass_trib[:3] != item.cst_ibscbs
            ):
                achados.append(
                    _achado(
                        Severidade.BLOQUEIO,
                        "RTC007",
                        f"cClassTrib '{item.cclass_trib}' pertence ao CST "
                        f"{item.cclass_trib[:3]} na tabela oficial, incompatível "
                        f"com o CST {item.cst_ibscbs} informado no item.",
                        nota,
                        item,
                        arquivo,
                    )
                )
            if (
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
            if (
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
        # A NT 2017.001 impõe as mesmas exigências ao cEAN (unidade comercial)
        # e ao cEANTrib (unidade tributável); os dois são validados.
        campos_gtin: tuple[tuple[str, str | None], ...] = (
            ("cEAN", item.cean),
            ("cEANTrib", item.ceantrib),
        )
        for rotulo, valor_gtin in campos_gtin:
            if gtin.esta_vazio(valor_gtin):
                if nota.exige_literal_sem_gtin:
                    achados.append(
                        _achado(
                            Severidade.ALERTA,
                            "GTIN001",
                            f"{rotulo} vazio. No layout 4.00, produto sem código "
                            "de barras precisa do literal 'SEM GTIN'.",
                            nota,
                            item,
                            arquivo,
                        )
                    )
            else:
                valido, motivo = gtin.validar(valor_gtin)
                if not valido:
                    achados.append(
                        _achado(
                            Severidade.ALERTA,
                            "GTIN001",
                            motivo if rotulo == "cEAN" else f"{rotulo}: {motivo}",
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
