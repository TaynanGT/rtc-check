from datetime import date

from rtc_check.catalogo import COBERTURA, REGRAS, catalogo_json, dias_desde_snapshot, regra
from rtc_check.rules import TODAS_AS_REGRAS


def test_catalogo_cobre_todas_as_regras_ativas():
    assert set(REGRAS) == set(TODAS_AS_REGRAS)
    assert {item["codigo"] for item in catalogo_json()} == set(TODAS_AS_REGRAS)
    assert all(item["fonte"].startswith("https://") for item in catalogo_json())


def test_catalogo_expoe_acao_e_limites():
    rtc = regra("RTC001")
    assert rtc
    assert rtc.rejeicao == "1115"
    assert rtc.responsavel
    assert regra("desconhecida") is None
    assert "NFS-e, CT-e e eventos fiscais" in COBERTURA["fora_de_escopo"]


def test_idade_do_snapshot_e_deterministica():
    assert dias_desde_snapshot(date(2026, 7, 26)) == 33
