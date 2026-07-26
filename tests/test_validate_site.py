from pathlib import Path

from scripts.validate_site import validar


def test_site_publico_passa_no_auditor_estatico():
    raiz = Path(__file__).parents[1]
    assert validar(raiz / "site") == []
