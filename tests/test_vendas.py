"""Backend de vendas: assinatura de webhook, contrato do checkout e servidor."""

import hashlib
import hmac
import http.client
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
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
        buscar_pagamento=lambda _id: _pagamento_aprovado("mensal"),
    )
    assert repetido.desfecho == sv.PAGAMENTO_DUPLICADO


def test_reembolso_depois_da_venda_e_registrado_uma_unica_vez(tmp_path):
    venda = sv.processar_pagamento(
        "777", tmp_path, buscar_pagamento=lambda _id: _pagamento_aprovado("mensal")
    )
    assert venda.desfecho == sv.LICENCA_EMITIDA

    reembolso = sv.processar_pagamento(
        "777",
        tmp_path,
        buscar_pagamento=lambda _id: {"status": "refunded", "external_reference": "mensal"},
    )
    assert reembolso.desfecho == sv.REEMBOLSO_CONFIRMADO

    eventos = sv.eventos_registrados(tmp_path, "777")
    assert eventos == {sv.LICENCA_EMITIDA, sv.REEMBOLSO_CONFIRMADO}

    repetido = sv.processar_pagamento(
        "777",
        tmp_path,
        buscar_pagamento=lambda _id: {"status": "refunded", "external_reference": "mensal"},
    )
    assert repetido.desfecho == sv.PAGAMENTO_DUPLICADO


def test_pagamento_de_ambiente_de_teste_nao_emite(tmp_path, monkeypatch):
    monkeypatch.delenv("RTC_CHECK_PERMITIR_SANDBOX", raising=False)
    resultado = sv.processar_pagamento(
        "778",
        tmp_path,
        buscar_pagamento=lambda _id: _pagamento_aprovado("mensal", live_mode=False),
    )
    assert resultado.desfecho == sv.PAGAMENTO_RECUSADO
    assert "ambiente de teste" in resultado.detalhe

    # Homologação opta explicitamente por aceitar pagamentos de sandbox.
    monkeypatch.setenv("RTC_CHECK_PERMITIR_SANDBOX", "1")
    homologado = sv.processar_pagamento(
        "779",
        tmp_path,
        buscar_pagamento=lambda _id: _pagamento_aprovado("mensal", live_mode=False),
    )
    assert homologado.desfecho == sv.LICENCA_EMITIDA


def test_chave_privada_configurada_invalida_derruba_o_boot(monkeypatch, tmp_path):
    monkeypatch.setenv("RTC_CHECK_CHAVE_PRIVADA", str(tmp_path / "nao-existe.pem"))
    with pytest.raises(SystemExit, match="RTC_CHECK_CHAVE_PRIVADA inválida"):
        sv.garantir_chave_de_emissao(tmp_path)


def test_licenca_do_emissor_anterior_continua_valida(monkeypatch, tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from rtc_check import edicao as ed_modulo

    # A instalação confia na chave nova (padrão) e na anterior; uma licença
    # assinada pelo emissor antigo precisa continuar validando.
    antiga = Ed25519PrivateKey.generate()
    caminho = tmp_path / "emissor-antigo.pem"
    caminho.write_bytes(
        antiga.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    publica_antiga = ed._b64_codificar(
        antiga.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    monkeypatch.delenv("RTC_CHECK_CHAVE_PUBLICA", raising=False)
    monkeypatch.setattr(ed_modulo, "CHAVES_PUBLICAS_ANTERIORES", (publica_antiga,))
    chave = ed.gerar_chave(
        ed.Plano.ESCRITORIO,
        date.today() + timedelta(days=10),
        "Cliente Antigo",
        caminho_chave_privada=str(caminho),
    )
    assert ed.validar_chave(chave).titular == "Cliente Antigo"


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
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RTC_CHECK_VENDAS_DIR", "vendas-do-teste")
    config = sv.carregar_config()
    assert config.url_publica == "https://vendas.example"
    assert config.segredo_webhook == SEGREDO
    assert config.diretorio == tmp_path / "vendas-do-teste"

    monkeypatch.delenv("RTC_CHECK_VENDAS_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://rtc.onrender.com/")
    assert sv.carregar_config().url_publica == "https://rtc.onrender.com"


def test_diretorio_de_dados_valida_relativo_e_absoluto(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RTC_CHECK_VENDAS_DIR", "../fora-do-projeto")
    with pytest.raises(SystemExit, match="RTC_CHECK_VENDAS_DIR"):
        sv._diretorio_de_dados()

    monkeypatch.setenv("RTC_CHECK_VENDAS_DIR", "vendas/sub/../dados")
    assert sv._diretorio_de_dados() == Path(os.getcwd()) / "vendas" / "dados"

    if os.name == "posix":
        monkeypatch.setenv("RTC_CHECK_VENDAS_DIR", "/var/dados-rtc-check")
        assert sv._diretorio_de_dados() == Path("/var/dados-rtc-check")

        # No Windows 3.13+, "/etc/..." nem é absoluto: cai no ramo relativo
        # e é igualmente recusado, então o caso vale só para POSIX.
        monkeypatch.setenv("RTC_CHECK_VENDAS_DIR", "/etc/area-do-sistema")
        with pytest.raises(SystemExit, match="absoluto"):
            sv._diretorio_de_dados()


def test_chave_privada_do_ambiente_e_materializada_no_disco(monkeypatch, tmp_path):
    # O conftest grava o PEM do emissor de teste neste caminho fixo.
    pem = (tmp_path / "emissor-ed25519.pem").read_text(encoding="utf-8")
    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA", raising=False)
    monkeypatch.setenv("RTC_CHECK_CHAVE_PRIVADA_PEM", pem)
    sv.garantir_chave_de_emissao(tmp_path)
    assert (tmp_path / "emissor-ed25519.pem").exists()
    # A mesma chave do ambiente segue emitindo: a pública configurada confere.
    chave = ed.gerar_chave(
        ed.Plano.ESCRITORIO, date.today() + timedelta(days=30), "Ambiente"
    )
    assert ed.validar_chave(chave).titular == "Ambiente"


def test_pem_achatado_pelo_campo_de_ambiente_e_reconstruido(monkeypatch, tmp_path):
    pem = (tmp_path / "emissor-ed25519.pem").read_text(encoding="utf-8")
    achatado = " ".join(pem.split())
    assert "\n" not in achatado
    publica_original = sv.chave_publica_do_emissor()

    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA", raising=False)
    monkeypatch.setenv("RTC_CHECK_CHAVE_PRIVADA_PEM", achatado)
    sv.garantir_chave_de_emissao(tmp_path / "dados")
    assert sv.chave_publica_do_emissor() == publica_original
    assert os.environ["RTC_CHECK_ORIGEM_DA_CHAVE"] == "ambiente"


def test_pem_invalido_no_ambiente_e_ignorado_com_aviso(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA", raising=False)
    monkeypatch.setenv("RTC_CHECK_CHAVE_PRIVADA_PEM", "trocar-depois")
    dados = tmp_path / "dados"
    sv.garantir_chave_de_emissao(dados)
    aviso = capsys.readouterr().err
    assert "não contém um PEM Ed25519 válido" in aviso
    assert "marcador BEGIN AUSENTE" in aviso
    # Uma chave real foi gerada no lugar do placeholder.
    assert "BEGIN PRIVATE KEY" in (dados / "emissor-ed25519.pem").read_text()
    assert sv.chave_publica_do_emissor()
    assert os.environ["RTC_CHECK_ORIGEM_DA_CHAVE"] == "disco-local"


def test_pem_aparece_no_log_em_hospedagem_sem_disco(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA", raising=False)
    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA_PEM", raising=False)
    monkeypatch.setenv("RENDER", "true")
    sv.garantir_chave_de_emissao(tmp_path / "dados")
    saida = capsys.readouterr().err
    assert "RTC_CHECK_CHAVE_PRIVADA_PEM" in saida
    assert "BEGIN PRIVATE KEY" in saida


def test_chave_de_emissao_e_gerada_uma_vez_e_reaproveitada(monkeypatch, tmp_path):
    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA", raising=False)
    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA_PEM", raising=False)
    dados = tmp_path / "dados"
    sv.garantir_chave_de_emissao(dados)
    assert (dados / "emissor-ed25519.pem").exists()
    primeira = sv.chave_publica_do_emissor()

    monkeypatch.delenv("RTC_CHECK_CHAVE_PRIVADA", raising=False)
    sv.garantir_chave_de_emissao(dados)
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
        'não é json\n[1, 2]\n{"id_pagamento": "1", "evento": "licenca_emitida"}\n',
        encoding="utf-8",
    )
    assert sv.eventos_registrados(tmp_path, "1") == {sv.LICENCA_EMITIDA}
    assert sv.eventos_registrados(tmp_path, "2") == set()


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
    assert sv.enviar_chave_por_email(
        config, "comprador@example.com", "RTC2.a.b", "anual", "2027-07-26", "170606"
    )
    mensagem = next(item[1] for item in envios if item[0] == "mensagem")
    assert mensagem["To"] == "comprador@example.com"
    assert mensagem["Bcc"] == "vendas@example.com"
    corpo = mensagem.get_content()
    assert "RTC2.a.b" in corpo
    assert "válida até 26/07/2027" in corpo
    assert "pagamento Mercado Pago 170606" in corpo
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
    assert "%%MENSAGEM%%" not in pagina

    with urllib.request.urlopen(
        f"{servidor}/obrigado?collection_status=pending"
    ) as resposta:
        pendente = resposta.read().decode()
    assert "aguardando compensação" in pendente


def test_head_responde_para_monitores(servidor):
    endereco = urlparse(servidor)
    conexao = http.client.HTTPConnection(endereco.hostname, endereco.port)
    try:
        conexao.request("HEAD", "/saude")
        assert conexao.getresponse().status == 200
    finally:
        conexao.close()


def test_limite_de_compras_por_minuto(servidor, monkeypatch):
    monkeypatch.setattr(
        mp, "criar_preferencia", lambda plano, url: "https://mp.example/pref"
    )
    ultimos = [
        _get_sem_seguir_redirect(servidor, "/comprar/mensal")[0]
        for _ in range(sv.LIMITE_DE_COMPRAS_POR_MINUTO + 1)
    ]
    assert ultimos[0] == 303
    assert ultimos[-1] == 429


def test_pagina_de_planos_e_saude(servidor):
    with urllib.request.urlopen(f"{servidor}/saude") as resposta:
        saude = json.loads(resposta.read().decode())
    assert saude["ok"] is True
    assert saude["chave_fixada_no_ambiente"] is False
    with urllib.request.urlopen(f"{servidor}/") as resposta:
        pagina = resposta.read().decode()
    assert "/comprar/mensal" in pagina
    assert "R$ 1.490" in pagina


def test_cors_liberado_so_nas_rotas_publicas(servidor):
    # A página de status do site lê estas duas rotas do navegador.
    for caminho in ("/saude", "/chave-publica"):
        with urllib.request.urlopen(f"{servidor}{caminho}") as resposta:
            assert resposta.headers["Access-Control-Allow-Origin"] == "*", caminho
    # A página de vendas e o webhook não expõem CORS.
    with urllib.request.urlopen(f"{servidor}/") as resposta:
        assert resposta.headers.get("Access-Control-Allow-Origin") is None


def test_preflight_options_responde_as_rotas_publicas(servidor):
    endereco = urlparse(servidor)
    conexao = http.client.HTTPConnection(endereco.hostname, endereco.port)
    try:
        conexao.request("OPTIONS", "/saude")
        resposta = conexao.getresponse()
        resposta.read()
        assert resposta.status == 204
        assert resposta.getheader("Access-Control-Allow-Origin") == "*"

        conexao.request("OPTIONS", "/webhook/mercadopago")
        recusada = conexao.getresponse()
        recusada.read()
        assert recusada.status == 404
    finally:
        conexao.close()
