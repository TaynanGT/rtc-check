"""Referência normativa usada pelo RTC Check.

Este módulo torna explícita a fotografia regulatória usada pela versão do
programa. A data e a versão não substituem o validador oficial: servem para
que um relatório possa ser auditado e reproduzido depois de uma atualização
da RTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ReferenciaNormativa:
    documento: str
    versao: str
    publicada_em: date
    fonte: str
    corte_obrigatoriedade: date
    tabela_documento: str
    tabela_versao: str
    tabela_publicada_em: date
    fonte_tabela: str

    @property
    def rotulo(self) -> str:
        return f"{self.documento} v{self.versao}"

    def como_json(self) -> dict[str, str]:
        return {
            "documento": self.documento,
            "versao": self.versao,
            "publicada_em": self.publicada_em.isoformat(),
            "fonte": self.fonte,
            "corte_obrigatoriedade": self.corte_obrigatoriedade.isoformat(),
            "tabela_documento": self.tabela_documento,
            "tabela_versao": self.tabela_versao,
            "tabela_publicada_em": self.tabela_publicada_em.isoformat(),
            "fonte_tabela": self.fonte_tabela,
        }


# Atualize esta referência junto com as regras e as fixtures quando o portal
# oficial publicar nova versão da RTC. Fonte consultada em 25/07/2026.
NORMATIVA_RTC = ReferenciaNormativa(
    documento="Nota Técnica 2025.002-RTC",
    versao="1.50",
    publicada_em=date(2026, 6, 1),
    fonte="https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=pD4YrecPV6s%3D",
    corte_obrigatoriedade=date(2026, 8, 3),
    tabela_documento="Informe Técnico 2025.002",
    tabela_versao="1.60",
    tabela_publicada_em=date(2026, 6, 23),
    fonte_tabela=(
        "https://www.nfe.fazenda.gov.br/portal/"
        "exibirArquivo.aspx?conteudo=jxTMMQeEVM8%3D"
    ),
)
