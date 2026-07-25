"""Fotografia das tabelas oficiais usadas pelas regras da RTC.

As constantes abaixo vêm dos documentos vigentes no Portal Nacional da NF-e.
Elas ficam embutidas para manter a execução 100% local e sem dependências.
Ao atualizar uma tabela, atualize também a referência normativa e os testes.
"""

from __future__ import annotations

# Tabela de Classificação Tributária do IBS e CBS, IT 2025.002 v1.60,
# publicada em 23/06/2026. Coluna ``ind_gIBSCBS`` da aba CST.
CSTS_EXIGEM_GIBSCBS = frozenset(
    {"000", "010", "011", "200", "220", "221", "222", "510", "515", "550", "830"}
)
CSTS_PROIBEM_GIBSCBS = frozenset(
    {"400", "410", "620", "800", "810", "811", "820"}
)
CSTS_IBSCBS = CSTS_EXIGEM_GIBSCBS | CSTS_PROIBEM_GIBSCBS

# Tabela de códigos de combustíveis sujeitos à tributação monofásica,
# publicada em 05/12/2025 (Informe Técnico 2023.003 v1.08). A UB12-10 usa
# essa lista para dispensar o grupo pai IBSCBS quando cProdANP estiver nela.
CPROD_ANP_MONOFASICOS = frozenset(
    {
        "210203001",
        "210203003",
        "210203004",
        "210203005",
        "320101001",
        "320101002",
        "320102001",
        "320102002",
        "320102003",
        "320102005",
        "320103001",
        "320103002",
        "320103003",
        "320201001",
        "320301001",
        "320301002",
        "420101004",
        "420101005",
        "420102004",
        "420102005",
        "420105001",
        "420107001",
        "420201001",
        "420201003",
        "420301002",
        "810102001",
        "810102003",
        "810102004",
        "820101001",
        "820101003",
        "820101011",
        "820101012",
        "820101013",
        "820101025",
        "820101026",
        "820101027",
        "820101030",
        "820101032",
        "820101033",
        "820101034",
    }
)
