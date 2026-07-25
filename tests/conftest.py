import pytest

from rtc_check import edicao as ed


@pytest.fixture(autouse=True)
def config_isolada(tmp_path, monkeypatch):
    """Nenhum teste pode ver, gravar ou gastar a licença real da máquina."""
    monkeypatch.setenv("RTC_CHECK_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("RTC_CHECK_LICENCA", raising=False)
    monkeypatch.delenv("RTC_CHECK_CHAVE_VERIFICACAO", raising=False)


@pytest.fixture
def licenciado(monkeypatch):
    """Roda o teste num plano pago, como um cliente com chave válida."""
    from datetime import date, timedelta

    chave = ed.gerar_chave(
        ed.Plano.ESCRITORIO, date.today() + timedelta(days=30), "Teste Automatizado"
    )
    monkeypatch.setenv("RTC_CHECK_LICENCA", chave)
    return chave
