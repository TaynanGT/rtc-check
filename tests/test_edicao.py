from datetime import date, timedelta

import pytest

from rtc_check import edicao as ed

HOJE = date(2026, 7, 25)
DEPOIS = HOJE + timedelta(days=30)


def _chave(plano=ed.Plano.ESCRITORIO, expira=DEPOIS, titular="Loja do Zé Ltda"):
    return ed.gerar_chave(plano, expira, titular)


# --- chave de licença -------------------------------------------------------


def test_chave_valida_devolve_plano_e_titular():
    edicao = ed.validar_chave(_chave(), hoje=HOJE)
    assert edicao.plano is ed.Plano.ESCRITORIO
    assert edicao.titular == "Loja do Zé Ltda"
    assert edicao.expira_em == DEPOIS
    assert edicao.dias_restantes(HOJE) == 30


def test_chave_adulterada_e_recusada():
    chave = _chave()
    # troca o último caractere da assinatura
    adulterada = chave[:-2] + ("A" if chave[-2] != "A" else "B") + chave[-1]
    with pytest.raises(ed.LicencaInvalida, match="corrompida"):
        ed.validar_chave(adulterada, hoje=HOJE)


def test_carga_reescrita_nao_passa_sem_assinatura_nova():
    """Trocar o plano dentro da chave invalida a assinatura."""
    comunidade = _chave(plano=ed.Plano.COMUNIDADE)
    plataforma = _chave(plano=ed.Plano.PLATAFORMA)
    corpo = plataforma.split(".")[1]
    forjada = f"{ed.PREFIXO_CHAVE}.{corpo}.{comunidade.split('.')[2]}"
    with pytest.raises(ed.LicencaInvalida):
        ed.validar_chave(forjada, hoje=HOJE)


def test_chave_vencida_e_recusada():
    with pytest.raises(ed.LicencaInvalida, match="vencida"):
        ed.validar_chave(_chave(expira=HOJE - timedelta(days=1)), hoje=HOJE)


def test_chave_com_outra_chave_publica_nao_abre_a_instalacao(monkeypatch):
    """Só a chave pública correspondente confere a assinatura Ed25519."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    chave_publica = _chave()
    outra = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    monkeypatch.setenv("RTC_CHECK_CHAVE_PUBLICA", ed._b64_codificar(outra))
    with pytest.raises(ed.LicencaInvalida):
        ed.validar_chave(chave_publica, hoje=HOJE)


def test_formato_desconhecido_e_recusado():
    for lixo in ["", "abc", "RTC1-xxx", "OUTRO-AAAA-BBBB"]:
        with pytest.raises(ed.LicencaInvalida):
            ed.validar_chave(lixo, hoje=HOJE)


# --- recursos por plano -----------------------------------------------------


def test_comunidade_tem_a_varredura_e_o_relatorio_de_texto():
    comunidade = ed.Edicao()
    assert comunidade.tem(ed.Recurso.VARREDURA)
    assert comunidade.tem(ed.Recurso.RELATORIO_TEXTO)
    assert not comunidade.pago


def test_comunidade_nao_tem_exportacao_nem_ci():
    comunidade = ed.Edicao()
    for recurso in (
        ed.Recurso.FORMATO_JSON,
        ed.Recurso.FORMATO_CSV,
        ed.Recurso.FORMATO_HTML,
        ed.Recurso.SAIDA_ARQUIVO,
        ed.Recurso.PORTAO_CI,
        ed.Recurso.POR_CNPJ,
        ed.Recurso.COMPARATIVO,
        ed.Recurso.LISTA_COMPLETA,
    ):
        assert not comunidade.tem(recurso), recurso


def test_a_maior_parte_dos_recursos_e_paga():
    """Regra de produto: o gratuito resolve o essencial, o resto é pago."""
    comunidade = ed.Edicao()
    assert len(comunidade.recursos_bloqueados) > len(comunidade.recursos_liberados)


def test_teste_gratis_libera_o_mesmo_que_escritorio():
    teste = ed.Edicao(plano=ed.Plano.TESTE)
    escritorio = ed.Edicao(plano=ed.Plano.ESCRITORIO)
    assert teste.recursos_liberados == escritorio.recursos_liberados
    assert not teste.recursos_bloqueados


def test_regras_de_cadastro_so_no_plano_pago():
    regras_rtc = {"RTC001", "RTC002", "RTC003", "RTC004", "RTC005", "RTC006"}
    assert set(ed.Edicao().regras_ativas) == regras_rtc
    pago = ed.Edicao(plano=ed.Plano.ESCRITORIO).regras_ativas
    assert regras_rtc | {"NCM001", "GTIN001"} == set(pago)


def test_limite_de_skus_do_relatorio_de_texto():
    assert ed.Edicao().limite_de_skus == ed.LIMITE_GRATUITO_DE_SKUS
    assert ed.Edicao(plano=ed.Plano.TESTE).limite_de_skus == ed.LIMITE_PAGO_DE_SKUS


# --- teste grátis -----------------------------------------------------------


def test_teste_gratis_dura_quatorze_dias():
    edicao = ed.iniciar_teste(hoje=HOJE)
    assert edicao.plano is ed.Plano.TESTE
    assert edicao.expira_em == HOJE + timedelta(days=ed.DIAS_DE_TESTE)


def test_teste_gratis_nao_pode_ser_reiniciado():
    ed.iniciar_teste(hoje=HOJE)
    with pytest.raises(ed.TesteIndisponivel):
        ed.iniciar_teste(hoje=HOJE)

    # nem depois de vencer
    with pytest.raises(ed.TesteIndisponivel, match="já foi usado"):
        ed.iniciar_teste(hoje=HOJE + timedelta(days=90))


def test_teste_vencido_volta_para_comunidade_com_aviso():
    ed.iniciar_teste(hoje=HOJE)
    edicao = ed.resolver(hoje=HOJE + timedelta(days=30))
    assert edicao.plano is ed.Plano.COMUNIDADE
    assert "venceu" in edicao.aviso


def test_teste_em_andamento_vale_enquanto_dura():
    ed.iniciar_teste(hoje=HOJE)
    edicao = ed.resolver(hoje=HOJE + timedelta(days=13))
    assert edicao.plano is ed.Plano.TESTE


# --- resolução da edição ----------------------------------------------------


def test_sem_nada_configurado_e_comunidade():
    assert ed.resolver(hoje=HOJE).plano is ed.Plano.COMUNIDADE


def test_licenca_do_ambiente_e_usada(monkeypatch):
    monkeypatch.setenv("RTC_CHECK_LICENCA", _chave())
    assert ed.resolver(hoje=HOJE).plano is ed.Plano.ESCRITORIO


def test_licenca_da_linha_de_comando_ganha_do_ambiente(monkeypatch):
    monkeypatch.setenv("RTC_CHECK_LICENCA", _chave(plano=ed.Plano.ESCRITORIO))
    edicao = ed.resolver(_chave(plano=ed.Plano.PLATAFORMA), hoje=HOJE)
    assert edicao.plano is ed.Plano.PLATAFORMA


def test_licenca_salva_vale_nas_proximas_execucoes():
    ed.salvar_licenca(_chave(), hoje=HOJE)
    assert ed.resolver(hoje=HOJE).plano is ed.Plano.ESCRITORIO


def test_chave_invalida_nao_derruba_a_execucao(monkeypatch):
    """A varredura importa mais que a cobrança: cai para Comunidade com aviso."""
    monkeypatch.setenv("RTC_CHECK_LICENCA", "RTC1-LIXO-0000")
    edicao = ed.resolver(hoje=HOJE)
    assert edicao.plano is ed.Plano.COMUNIDADE
    assert "ignorada" in edicao.aviso


def test_registro_de_teste_corrompido_nao_derruba_a_execucao():
    arquivo = ed.diretorio_de_config() / "teste.json"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("{isso não é json", encoding="utf-8")
    edicao = ed.resolver(hoje=HOJE)
    assert edicao.plano is ed.Plano.COMUNIDADE
    assert edicao.aviso


def test_mensagem_de_upsell_diz_o_plano_e_o_caminho():
    mensagem = ed.como_liberar(ed.Recurso.FORMATO_CSV)
    assert "Escritório" in mensagem
    assert "--iniciar-teste" in mensagem
    assert ed.URL_PLANOS in mensagem
