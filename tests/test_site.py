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
    assert "navigator.clipboard" not in pagina
    assert 'name="site"' in pagina
    assert 'id="lead-news"' in pagina


def test_landing_oferece_demo_rastreabilidade_e_trilhas_comerciais():
    pagina = (RAIZ / "site" / "index.html").read_text(encoding="utf-8")

    assert 'id="demo"' in pagina
    assert "NT 2025.002-RTC v1.50" in pagina
    assert "Escritórios e times fiscais" in pagina
    assert "ERP e parceiros de implantação" in pagina


def test_landing_publica_confianca_calculadora_e_descoberta():
    pagina = (RAIZ / "site" / "index.html").read_text(encoding="utf-8")
    assert 'id="calculadora"' in pagina
    assert 'href="privacy.html"' in pagina
    assert 'href="terms.html"' in pagina
    assert 'href="status.html"' in pagina
    assert "Não é promessa de economia" in pagina
    for nome in ("privacy.html", "terms.html", "status.html", "robots.txt", "sitemap.xml"):
        assert (RAIZ / "site" / nome).is_file()


def test_paginas_de_confianca_nao_prometem_cobertura_total():
    privacidade = (RAIZ / "site" / "privacy.html").read_text(encoding="utf-8")
    termos = (RAIZ / "site" / "terms.html").read_text(encoding="utf-8")
    status = (RAIZ / "site" / "status.html").read_text(encoding="utf-8")
    assert "não possui telemetria" in privacidade
    assert "revisão jurídica" in privacidade
    assert "Não transmite" in termos
    assert "fora do escopo atual" in status
