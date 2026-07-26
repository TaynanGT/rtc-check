from rtc_check.checkout import URL_COMPRA_ASSISTIDA, carregar


def test_checkout_cai_para_compra_assistida(monkeypatch):
    monkeypatch.delenv("RTC_CHECK_CHECKOUT_URL", raising=False)
    checkout = carregar()
    assert not checkout.automatico
    assert checkout.url == URL_COMPRA_ASSISTIDA


def test_checkout_aceita_somente_https(monkeypatch):
    monkeypatch.setenv("RTC_CHECK_PAYMENT_PROVIDER", "Asaas")
    monkeypatch.setenv("RTC_CHECK_CHECKOUT_URL", "https://pagamentos.example/rtc")
    monkeypatch.setenv("RTC_CHECK_CHECKOUT_ALLOWED_HOSTS", "pagamentos.example")
    checkout = carregar()
    assert checkout.automatico
    assert checkout.provedor == "Asaas"

    monkeypatch.setenv("RTC_CHECK_CHECKOUT_URL", "javascript:alert(1)")
    assert not carregar().automatico


def test_checkout_recusa_host_nao_permitido(monkeypatch):
    monkeypatch.setenv("RTC_CHECK_CHECKOUT_URL", "https://checkout-malicioso.example/rtc")
    monkeypatch.setenv("RTC_CHECK_CHECKOUT_ALLOWED_HOSTS", "pagamentos.example")
    assert not carregar().automatico
