"""Backend de vendas: assinatura de webhook, contrato do checkout e servidor."""

import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.request
from datetime import date, timedelta

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


def test_pagina_de_planos_e_saude(servidor):
    with urllib.request.urlopen(f"{servidor}/saude") as resposta:
        assert json.loads(resposta.read().decode()) == {"ok": True}
    with urllib.request.urlopen(f"{servidor}/") as resposta:
        pagina = resposta.read().decode()
    assert "/comprar/mensal" in pagina
    assert "R$ 1.490" in pagina
