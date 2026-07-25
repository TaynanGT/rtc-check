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

# cClassTrib vigente em 25/07/2026 para NF-e (modelo 55), extraído da tabela
# oficial online do IT 2025.002 v1.60. Classes de outros DF-e não valem para NF-e.
CCLASSTRIB_NFE = frozenset(
    {
        "000001", "000003", "000004", "000005", "200002", "200003", "200004",
        "200005", "200006", "200007", "200008", "200009", "200010", "200011",
        "200012", "200013", "200014", "200015", "200020", "200022", "200023",
        "200024", "200030", "200031", "200032", "200033", "200034", "200035",
        "200036", "200038", "200039", "200043", "200047", "200053", "200054",
        "410001", "410002", "410003", "410004", "410005", "410006", "410007",
        "410008", "410009", "410012", "410013", "410014", "410016", "410017",
        "410019", "410020", "410026", "410027", "410029", "410030", "410031",
        "410035", "410999", "510001", "515001", "550001", "550003", "550004",
        "550005", "550006", "550007", "550008", "550009", "550010", "550011",
        "550012", "550013", "550014", "550015", "550016", "550017", "550018",
        "550019", "550020", "550021", "550022", "550023", "620001", "620002",
        "620003", "620004", "620005", "620006", "620007", "800001", "800002",
        "810001", "811001", "811002", "811003", "830001",
    }
)

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
