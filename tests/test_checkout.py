from rtc_check.checkout import PROVEDOR_PADRAO, URL_CHECKOUT_PADRAO, carregar


def test_checkout_padrao_e_o_servidor_de_vendas(monkeypatch):
    monkeypatch.delenv("RTC_CHECK_CHECKOUT_URL", raising=False)
    monkeypatch.delenv("RTC_CHECK_PAYMENT_PROVIDER", raising=False)
    checkout = carregar()
    assert checkout.automatico
    assert checkout.url == URL_CHECKOUT_PADRAO
    assert checkout.provedor == PROVEDOR_PADRAO


def test_checkout_aceita_somente_https(monkeypatch):
    monkeypatch.setenv("RTC_CHECK_PAYMENT_PROVIDER", "Asaas")
    monkeypatch.setenv("RTC_CHECK_CHECKOUT_URL", "https://pagamentos.example/rtc")
    monkeypatch.setenv("RTC_CHECK_CHECKOUT_ALLOWED_HOSTS", "pagamentos.example")
    checkout = carregar()
    assert checkout.automatico
    assert checkout.provedor == "Asaas"
    assert checkout.url == "https://pagamentos.example/rtc"

    # URL não-HTTPS no ambiente nunca chega ao navegador: volta ao padrão.
    monkeypatch.setenv("RTC_CHECK_CHECKOUT_URL", "javascript:alert(1)")
    assert carregar().url == URL_CHECKOUT_PADRAO


def test_checkout_recusa_host_nao_permitido(monkeypatch):
    monkeypatch.setenv("RTC_CHECK_CHECKOUT_URL", "https://checkout-malicioso.example/rtc")
    monkeypatch.setenv("RTC_CHECK_CHECKOUT_ALLOWED_HOSTS", "pagamentos.example")
    # Host fora da lista permitida nunca chega ao navegador: cai no oficial.
    assert carregar().url == URL_CHECKOUT_PADRAO
