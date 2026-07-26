import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rtc_check import edicao as ed


@pytest.fixture(autouse=True)
def config_isolada(tmp_path, monkeypatch):
    """Nenhum teste pode ver, gravar ou gastar a licença real da máquina."""
    monkeypatch.setenv("RTC_CHECK_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("RTC_CHECK_LICENCA", raising=False)
    monkeypatch.delenv("RTC_CHECK_ORIGEM_DA_CHAVE", raising=False)
    privada = Ed25519PrivateKey.generate()
    caminho = tmp_path / "emissor-ed25519.pem"
    caminho.write_bytes(
        privada.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    publica = privada.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    monkeypatch.setenv("RTC_CHECK_CHAVE_PRIVADA", str(caminho))
    monkeypatch.setenv("RTC_CHECK_CHAVE_PUBLICA", ed._b64_codificar(publica))


@pytest.fixture
def licenciado(monkeypatch):
    """Roda o teste num plano pago, como um cliente com chave válida."""
    from datetime import date, timedelta

    chave = ed.gerar_chave(
        ed.Plano.ESCRITORIO, date.today() + timedelta(days=30), "Teste Automatizado"
    )
    monkeypatch.setenv("RTC_CHECK_LICENCA", chave)
    return chave
