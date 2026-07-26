from pathlib import Path

RAIZ = Path(__file__).parents[1]


def test_landing_reflete_produto_atual_e_contato_privado_configuravel():
    pagina = (RAIZ / "site" / "index.html").read_text(encoding="utf-8")
    configuracao = (RAIZ / "site" / "lead-config.js").read_text(encoding="utf-8")

    assert "RTC006" in pagina
    assert "v0.3.1" in pagina
    assert "151 passando" not in pagina
    assert "issues/new?template=comercial" not in pagina
    assert 'id="lead-form"' in pagina
    assert "RTC_CHECK_LEADS_ENDPOINT" in pagina
    assert 'RTC_CHECK_LEADS_ENDPOINT = ""' in configuracao


def test_landing_oferece_demo_rastreabilidade_e_trilhas_comerciais():
    pagina = (RAIZ / "site" / "index.html").read_text(encoding="utf-8")

    assert 'id="demo"' in pagina
    assert "NT 2025.002-RTC v1.50" in pagina
    assert "Escritórios e times fiscais" in pagina
    assert "ERP e parceiros de implantação" in pagina
