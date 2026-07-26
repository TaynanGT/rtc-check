"""Backend de vendas: assinatura de webhook, contrato do checkout e servidor."""

import hashlib
import hmac
import http.client
import json
import threading
import urllib.error
import urllib.request
from datetime import date, timedelta
from urllib.parse import urlparse

import pytest

from rtc_check import edicao as ed
from rtc_check import mercadopago as mp
from rtc_check import servidor_vendas as sv

SEGREDO = "segredo-de-teste"


def _assinatura(id_do_dado: str, id_requisicao: str, ts: str = "1690000000") -> str:
    manifesto = f"id:{id_do_dado.lower()};request-id:{id_requisicao};ts:{ts};"
    v1 = hmac.new(SEGREDO.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def _pagamento_aprovado(codigo_plano: str = "mensal", **extras):
    plano = mp.PLANOS_DE_VENDA[codigo_plano]
    base = {
        "status": "approved",
        "currency_id": "BRL",
        "transaction_amount": plano.preco,
        "metadata": {"rtc_check_plano": codigo_plano},
        "payer": {"email": "comprador@example.com"},
    }
    base.update(extras)
    return base


def test_assinatura_do_webhook_valida_e_invalida():
    cabecalho = _assinatura("12345", "req-1")
    assert mp.validar_assinatura_webhook(cabecalho, "12345", "req-1", SEGREDO)
    assert not mp.validar_assinatura_webhook(cabecalho, "99999", "req-1", SEGREDO)
    assert not mp.validar_assinatura_webhook(cabecalho, "12345", "req-2", SEGREDO)
    assert not mp.validar_assinatura_webhook(cabecalho, "12345", "req-1", "outro")
    assert not mp.validar_assinatura_webhook("lixo", "12345", "req-1", SEGREDO)
    assert not mp.validar_assinatura_webhook(cabecalho, "", "req-1", SEGREDO)
    assert not mp.validar_assinatura_webhook(cabecalho, "12345", "req-1", "")


def test_preferencia_carrega_preco_plano_e_urls():
    corpo = mp.corpo_da_preferencia(
        mp.PLANOS_DE_VENDA["anual"], "https://vendas.example/"
    )
    item = corpo["items"][0]
    assert item["unit_price"] == 1490.0
    assert item["currency_id"] == "BRL"
    assert corpo["metadata"]["rtc_check_plano"] == "anual"
    assert corpo["external_reference"] == "anual"
    assert corpo["notification_url"] == "https://vendas.example/webhook/mercadopago"
    assert corpo["back_urls"]["success"] == "https://vendas.example/obrigado"


def test_pagamento_aprovado_emite_licenca_valida_e_e_idempotente(tmp_path):
    hoje = date(2026, 7, 26)
    resultado = sv.processar_pagamento(
        "111",
        tmp_path,
        buscar_pagamento=lambda _id: _pagamento_aprovado("mensal"),
        hoje=hoje,
    )
    assert resultado.desfecho == sv.LICENCA_EMITIDA
    assert resultado.email_do_comprador == "comprador@example.com"

    edicao = ed.validar_chave(resultado.chave, hoje)
    assert edicao.plano is ed.Plano.ESCRITORIO
    assert edicao.titular == "comprador@example.com"
    assert edicao.expira_em == hoje + timedelta(days=33)

    registros = [
        json.loads(linha)
        for linha in (tmp_path / "vendas.jsonl").read_text().splitlines()
    ]
    assert registros[0]["evento"] == sv.LICENCA_EMITIDA
    assert registros[0]["chave"] == resultado.chave

    repetido = sv.processar_pagamento(
        "111",
        tmp_path,
        buscar_pagamento=lambda _id: pytest.fail("não deveria reconsultar"),
    )
    assert repetido.desfecho == sv.PAGAMENTO_DUPLICADO


def test_valor_errado_moeda_errada_e_plano_desconhecido_nao_emitem(tmp_path):
    casos = [
        _pagamento_aprovado("mensal", transaction_amount=1.0),
        _pagamento_aprovado("mensal", currency_id="USD"),
        _pagamento_aprovado("mensal", metadata={}, external_reference="hack"),
        _pagamento_aprovado("mensal", payer={}),
    ]
    for indice, pagamento in enumerate(casos):
        resultado = sv.processar_pagamento(
            f"20{indice}", tmp_path, buscar_pagamento=lambda _id, p=pagamento: p
        )
        assert resultado.desfecho == sv.PAGAMENTO_RECUSADO
        assert not resultado.chave


def test_pagamento_pendente_nao_registra_e_pode_aprovar_depois(tmp_path):
    pendente = sv.processar_pagamento(
        "333", tmp_path, buscar_pagamento=lambda _id: {"status": "pending"}
    )
    assert pendente.desfecho == sv.PAGAMENTO_IGNORADO
    assert not (tmp_path / "vendas.jsonl").exists()

    aprovado = sv.processar_pagamento(
        "333", tmp_path, buscar_pagamento=lambda _id: _pagamento_aprovado("anual")
    )
    assert aprovado.desfecho == sv.LICENCA_EMITIDA


def test_reembolso_e_cancelamento_sao_registrados(tmp_path):
    reembolso = sv.processar_pagamento(
        "444",
        tmp_path,
        buscar_pagamento=lambda _id: {"status": "refunded", "external_reference": "mensal"},
    )
    assert reembolso.desfecho == sv.REEMBOLSO_CONFIRMADO
    cancelado = sv.processar_pagamento(
        "555",
        tmp_path,
        buscar_pagamento=lambda _id: {"status": "cancelled", "external_reference": "mensal"},
    )
    assert cancelado.desfecho == sv.PAGAMENTO_CANCELADO
    eventos = [
        json.loads(linha)["evento"]
        for linha in (tmp_path / "vendas.jsonl").read_text().splitlines()
    ]
    assert eventos == [sv.REEMBOLSO_CONFIRMADO, sv.PAGAMENTO_CANCELADO]


def test_email_sem_smtp_configurado_fica_so_no_registro(tmp_path):
    config = sv.ConfigVendas(
        url_publica="https://vendas.example",
        segredo_webhook=SEGREDO,
        diretorio=tmp_path,
    )
    assert not sv.enviar_chave_por_email(config, "a@b.c", "RTC2.x.y", "mensal")


@pytest.fixture
def servidor(tmp_path, monkeypatch):
    monkeypatch.setattr(
        mp, "obter_pagamento", lambda _id: _pagamento_aprovado("mensal")
    )
    config = sv.ConfigVendas(
        url_publica="https://vendas.example",
        segredo_webhook=SEGREDO,
        diretorio=tmp_path / "vendas",
    )
    from http.server import ThreadingHTTPServer

    instancia = ThreadingHTTPServer(("127.0.0.1", 0), sv._handler(config))
    linha = threading.Thread(target=instancia.serve_forever, daemon=True)
    linha.start()
    yield f"http://127.0.0.1:{instancia.server_port}"
    instancia.shutdown()
    instancia.server_close()


def _post(url: str, cabecalhos: dict[str, str], corpo: bytes = b"{}"):
    requisicao = urllib.request.Request(url, data=corpo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(requisicao) as resposta:
            return resposta.status, json.loads(resposta.read().decode())
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read().decode())


def test_webhook_com_assinatura_valida_emite_licenca(servidor):
    status, dados = _post(
        f"{servidor}/webhook/mercadopago?data.id=777&type=payment",
        {
            "x-signature": _assinatura("777", "req-7"),
            "x-request-id": "req-7",
            "Content-Type": "application/json",
        },
    )
    assert status == 200
    assert dados["desfecho"] == sv.LICENCA_EMITIDA


def test_webhook_com_assinatura_invalida_recebe_401(servidor):
    status, dados = _post(
        f"{servidor}/webhook/mercadopago?data.id=888&type=payment",
        {"x-signature": "ts=1,v1=deadbeef", "x-request-id": "req-8"},
    )
    assert status == 401
    assert "assinatura" in dados["erro"]


def test_webhook_de_outro_topico_e_ignorado_sem_consultar_api(servidor, monkeypatch):
    monkeypatch.setattr(
        mp, "obter_pagamento", lambda _id: pytest.fail("não deveria consultar")
    )
    status, dados = _post(
        f"{servidor}/webhook/mercadopago?data.id=1&type=merchant_order", {}
    )
    assert status == 200
    assert dados["desfecho"] == sv.PAGAMENTO_IGNORADO


def test_carregar_config_exige_url_segredo_token_e_porta_smtp(monkeypatch, tmp_path):
    for variavel in (
        "RTC_CHECK_VENDAS_URL",
        "PAYMENT_WEBHOOK_SECRET",
        "PAYMENT_API_KEY",
        "SMTP_PORT",
        "RTC_CHECK_VENDAS_DIR",
    ):
        monkeypatch.delenv(variavel, raising=False)
    with pytest.raises(SystemExit, match="RTC_CHECK_VENDAS_URL"):
        sv.carregar_config()
    monkeypatch.setenv("RTC_CHECK_VENDAS_URL", "https://vendas.example/")
    with pytest.raises(SystemExit, match="PAYMENT_WEBHOOK_SECRET"):
        sv.carregar_config()
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", SEGREDO)
    with pytest.raises(SystemExit, match="PAYMENT_API_KEY"):
        sv.carregar_config()
    monkeypatch.setenv("PAYMENT_API_KEY", "APP_USR-teste")
    monkeypatch.setenv("SMTP_PORT", "não-numérica")
    with pytest.raises(SystemExit, match="SMTP_PORT"):
        sv.carregar_config()
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("RTC_CHECK_VENDAS_DIR", str(tmp_path / "vendas"))
    config = sv.carregar_config()
    assert config.url_publica == "https://vendas.example"
    assert config.segredo_webhook == SEGREDO

    monkeypatch.delenv("RTC_CHECK_VENDAS_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://rtc.onrender.com/")
    assert sv.carregar_config().url_publica == "https://rtc.onrender.com"


def test_chave_de_emissao_e_gerada_uma_vez_e_reaproveitada(monkeypatch, tmp_path):
    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA", raising=False)
    sv.garantir_chave_de_emissao(tmp_path)
    caminho = tmp_path / "emissor-ed25519.pem"
    assert caminho.exists()
    primeira = sv.chave_publica_do_emissor()

    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA", raising=False)
    sv.garantir_chave_de_emissao(tmp_path)
    assert sv.chave_publica_do_emissor() == primeira

    # Uma licença emitida com essa chave valida contra a pública anunciada.
    monkeypatch.setenv("RTC_CHECK_CHAVE_PUBLICA", primeira)
    chave = ed.gerar_chave(
        ed.Plano.ESCRITORIO, date.today() + timedelta(days=30), "Compradora"
    )
    assert ed.validar_chave(chave).titular == "Compradora"


def test_rota_da_chave_publica_anuncia_o_emissor(servidor):
    with urllib.request.urlopen(f"{servidor}/chave-publica") as resposta:
        dados = json.loads(resposta.read().decode())
    assert dados["chave_publica"]
    assert "CHAVE_PUBLICA_PADRAO" in dados["instrucao"]


def test_linha_ilegivel_no_registro_e_ignorada(tmp_path):
    (tmp_path / "vendas.jsonl").write_text(
        'não é json\n[1, 2]\n{"id_pagamento": "1"}\n', encoding="utf-8"
    )
    assert sv.ja_processado(tmp_path, "1")
    assert not sv.ja_processado(tmp_path, "2")


def test_email_com_smtp_configurado_carrega_a_chave(monkeypatch, tmp_path):
    envios = []

    class SMTPFalso:
        def __init__(self, host, porta, timeout=0):
            envios.append(("conexao", host, porta))

        def __enter__(self):
            return self

        def __exit__(self, *excecao):
            return False

        def login(self, usuario, senha):
            envios.append(("login", usuario))

        def send_message(self, mensagem):
            envios.append(("mensagem", mensagem))

    monkeypatch.setattr(sv.smtplib, "SMTP_SSL", SMTPFalso)
    config = sv.ConfigVendas(
        url_publica="https://vendas.example",
        segredo_webhook=SEGREDO,
        diretorio=tmp_path,
        smtp_host="smtp.example",
        smtp_usuario="vendas@example.com",
        smtp_senha="senha",
        remetente="RTC Check <vendas@example.com>",
    )
    assert sv.enviar_chave_por_email(config, "comprador@example.com", "RTC2.a.b", "anual")
    mensagem = next(item[1] for item in envios if item[0] == "mensagem")
    assert mensagem["To"] == "comprador@example.com"
    assert "RTC2.a.b" in mensagem.get_content()
    assert ("login", "vendas@example.com") in envios


class _RespostaFalsa:
    def __init__(self, corpo: bytes):
        self._corpo = corpo

    def read(self) -> bytes:
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *excecao):
        return False


def test_criar_preferencia_usa_o_token_e_devolve_init_point(monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "APP_USR-teste")
    capturadas = []

    def urlopen_falso(requisicao, timeout=0):
        capturadas.append(requisicao)
        return _RespostaFalsa(
            json.dumps({"init_point": "https://mp.example/checkout"}).encode()
        )

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_falso)
    url = mp.criar_preferencia(mp.PLANOS_DE_VENDA["mensal"], "https://vendas.example")
    assert url == "https://mp.example/checkout"
    requisicao = capturadas[0]
    assert requisicao.get_header("Authorization") == "Bearer APP_USR-teste"
    assert requisicao.get_header("X-idempotency-key")


def test_api_sem_token_com_erro_http_ou_resposta_estranha(monkeypatch):
    monkeypatch.delenv("PAYMENT_API_KEY", raising=False)
    with pytest.raises(mp.ErroMercadoPago, match="PAYMENT_API_KEY"):
        mp.token_de_acesso()

    monkeypatch.setenv("PAYMENT_API_KEY", "APP_USR-teste")
    with pytest.raises(mp.ErroMercadoPago, match="id de pagamento"):
        mp.obter_pagamento("não-numérico")

    def http_401(requisicao, timeout=0):
        raise urllib.error.HTTPError(requisicao.full_url, 401, "unauthorized", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", http_401)
    with pytest.raises(mp.ErroMercadoPago, match="HTTP 401"):
        mp.obter_pagamento("123")

    def rede_fora(requisicao, timeout=0):
        raise urllib.error.URLError("sem rede")

    monkeypatch.setattr(urllib.request, "urlopen", rede_fora)
    with pytest.raises(mp.ErroMercadoPago, match="falha ao falar"):
        mp.obter_pagamento("123")

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda r, timeout=0: _RespostaFalsa(b"[1, 2]")
    )
    with pytest.raises(mp.ErroMercadoPago, match="resposta inesperada"):
        mp.obter_pagamento("123")

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda r, timeout=0: _RespostaFalsa(b"{}")
    )
    with pytest.raises(mp.ErroMercadoPago, match="init_point"):
        mp.criar_preferencia(mp.PLANOS_DE_VENDA["anual"], "https://vendas.example")


def _get_sem_seguir_redirect(base: str, caminho: str):
    endereco = urlparse(base)
    conexao = http.client.HTTPConnection(endereco.hostname, endereco.port)
    try:
        conexao.request("GET", caminho)
        resposta = conexao.getresponse()
        return resposta.status, dict(resposta.getheaders()), resposta.read()
    finally:
        conexao.close()


def test_comprar_redireciona_para_o_checkout_hospedado(servidor, monkeypatch):
    monkeypatch.setattr(
        mp, "criar_preferencia", lambda plano, url: f"https://mp.example/{plano.codigo}"
    )
    status, cabecalhos, _ = _get_sem_seguir_redirect(servidor, "/comprar/mensal")
    assert status == 303
    assert cabecalhos["Location"] == "https://mp.example/mensal"


def test_comprar_plano_desconhecido_e_rota_errada_dao_404(servidor):
    status, _, _ = _get_sem_seguir_redirect(servidor, "/comprar/vitalicio")
    assert status == 404
    status, _, _ = _get_sem_seguir_redirect(servidor, "/nada")
    assert status == 404
    status, dados = _post(f"{servidor}/outro-webhook", {})
    assert status == 404
    assert "erro" in dados


def test_comprar_com_api_indisponivel_da_502(servidor, monkeypatch):
    def indisponivel(plano, url):
        raise mp.ErroMercadoPago("api fora do ar")

    monkeypatch.setattr(mp, "criar_preferencia", indisponivel)
    status, _, corpo = _get_sem_seguir_redirect(servidor, "/comprar/anual")
    assert status == 502
    assert "indispon" in corpo.decode()


def test_webhook_com_api_indisponivel_devolve_500_para_reenvio(servidor, monkeypatch):
    def indisponivel(_id):
        raise mp.ErroMercadoPago("api fora do ar")

    monkeypatch.setattr(mp, "obter_pagamento", indisponivel)
    status, dados = _post(
        f"{servidor}/webhook/mercadopago?data.id=999&type=payment",
        {"x-signature": _assinatura("999", "req-9"), "x-request-id": "req-9"},
    )
    assert status == 500
    assert "consultado" in dados["erro"]


def test_pagina_de_obrigado_orienta_a_ativacao(servidor):
    with urllib.request.urlopen(f"{servidor}/obrigado") as resposta:
        pagina = resposta.read().decode()
    assert "rtc-check --licenca" in pagina


def test_pagina_de_planos_e_saude(servidor):
    with urllib.request.urlopen(f"{servidor}/saude") as resposta:
        assert json.loads(resposta.read().decode()) == {"ok": True}
    with urllib.request.urlopen(f"{servidor}/") as resposta:
        pagina = resposta.read().decode()
    assert "/comprar/mensal" in pagina
    assert "R$ 1.490" in pagina
