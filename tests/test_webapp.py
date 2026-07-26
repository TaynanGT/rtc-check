import json
import threading
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

import pytest

from rtc_check import webapp
from rtc_check.cli import analisar
from rtc_check.edicao import Edicao, Plano
from rtc_check.report import Resumo

FIXTURES = Path(__file__).parent / "fixtures"


def _multipart(arquivos: list[tuple[str, bytes]]) -> tuple[str, bytes]:
    limite = "----rtc-check-test-boundary"
    partes = []
    for nome, conteudo in arquivos:
        partes.extend(
            [
                f"--{limite}\r\n".encode(),
                (
                    'Content-Disposition: form-data; name="arquivos"; '
                    f'filename="{nome}"\r\n'
                ).encode(),
                b"Content-Type: application/octet-stream\r\n\r\n",
                conteudo,
                b"\r\n",
            ]
        )
    partes.append(f"--{limite}--\r\n".encode())
    return f"multipart/form-data; boundary={limite}", b"".join(partes)


@pytest.fixture
def app_local(tmp_path, monkeypatch):
    monkeypatch.setenv("RTC_CHECK_HOME", str(tmp_path / "config"))
    estado = webapp.EstadoApp(token="token-de-teste")
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), webapp._handler(estado))
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{servidor.server_port}", estado
    servidor.shutdown()
    servidor.server_close()
    thread.join(timeout=2)


def _request(
    base: str,
    path: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    token: bool = True,
    headers: dict[str, str] | None = None,
):
    cabecalhos = dict(headers or {})
    if token:
        cabecalhos["X-RTC-Token"] = "token-de-teste"
    requisicao = urllib.request.Request(
        base + path,
        data=body,
        method=method,
        headers=cabecalhos,
    )
    try:
        resposta = urllib.request.urlopen(requisicao, timeout=5)
    except urllib.error.HTTPError as erro:
        return erro.code, erro.headers, erro.read()
    with resposta:
        return resposta.status, resposta.headers, resposta.read()


def test_pontuacao_e_acoes():
    vazio = Resumo()
    assert webapp._pontuacao(vazio) == 100
    vazio.arquivos_invalidos.append(("a.xml", "inválido"))
    assert webapp._pontuacao(vazio) == 0

    resumo = Resumo(total_itens=10)
    resumo = analisar(FIXTURES)
    assert 0 <= webapp._pontuacao(resumo) < 100
    assert "ERP" in webapp._acao_por_codigo("RTC001")
    assert "validador oficial" in webapp._acao_por_codigo("DESCONHECIDA")
    assert webapp._ordenar_codigos({"GTIN001", "RTC001", "NCM001"}) == [
        "RTC001",
        "NCM001",
        "GTIN001",
    ]


def test_serializacao_respeita_limite_gratuito():
    resumo = analisar(FIXTURES)
    dados = webapp._serializar_resultado(
        resumo,
        Edicao(plano=Plano.COMUNIDADE),
        "id",
        demo=False,
    )
    assert dados["id"] == "id"
    assert len(dados["itens"]) <= 5
    assert not dados["pode_exportar"]
    assert dados["itens"][0]["mensagens"][0]["acao"]

    demo = webapp._serializar_resultado(
        resumo,
        Edicao(plano=Plano.COMUNIDADE),
        "demo",
        demo=True,
    )
    assert len(demo["itens"]) == len(resumo.grupos)
    assert demo["pode_exportar"]


def test_estado_descarta_relatorio_mais_antigo():
    estado = webapp.EstadoApp()
    for _ in range(22):
        estado.guardar(Resumo(), Edicao(), demo=True)
    assert len(estado.relatorios) == 20


def test_validacao_de_marca_cor_e_nome():
    assert webapp._validar_marca("  Escritório X  ") == "Escritório X"
    assert webapp._validar_marca("") == "RTC Check"
    assert webapp._validar_cor("#12aBcD") == "#12aBcD"
    assert webapp._validar_cor("red") == webapp.COR_PADRAO
    assert webapp._nome_seguro("../../<nota>.xml", 2) == "00002-_nota_.xml"


def test_upload_xml_zip_e_formatos_ignorados(tmp_path):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as arquivo:
        arquivo.writestr("sub/pasta/segunda.xml", "<NFe/>")
        arquivo.writestr("ignorar.txt", "não")
    total = webapp._salvar_xmls_do_upload(
        [
            ("primeira.xml", b"<NFe/>"),
            ("lote.zip", buffer.getvalue()),
            ("foto.png", b"x"),
        ],
        tmp_path,
    )
    assert total == 2
    assert len(list(tmp_path.glob("*.xml"))) == 2


def test_upload_recusa_entrada_invalida(tmp_path, monkeypatch):
    with pytest.raises(webapp.EntradaInvalida, match="pelo menos um"):
        webapp._salvar_xmls_do_upload([("x.txt", b"x")], tmp_path)
    with pytest.raises(webapp.EntradaInvalida, match="ZIP inválido"):
        webapp._salvar_xmls_do_upload([("x.zip", b"ruim")], tmp_path)

    monkeypatch.setattr(webapp, "MAX_XML", 3)
    with pytest.raises(webapp.EntradaInvalida, match="maior"):
        webapp._salvar_xmls_do_upload([("x.xml", b"1234")], tmp_path)


def test_parser_multipart():
    tipo, corpo = _multipart([("nota.xml", b"<NFe/>")])
    assert webapp._partes_multipart(tipo, corpo) == [("nota.xml", b"<NFe/>")]
    with pytest.raises(webapp.EntradaInvalida):
        webapp._partes_multipart("text/plain", b"sem multipart")


def test_demo_cria_acervo_analisavel(tmp_path):
    webapp._criar_demo(tmp_path)
    resumo = analisar(tmp_path)
    assert resumo.arquivos_lidos == 2
    assert resumo.total_itens == 3
    assert resumo.skus_bloqueados >= 1


def test_http_entrega_interface_status_e_seguranca(app_local):
    base, _ = app_local
    status, headers, body = _request(base, "/", token=False)
    assert status == 200
    assert b"RTC Check Desktop" in body
    assert b"token-de-teste" in body
    assert headers["Content-Security-Policy"].startswith("default-src")

    assert _request(base, "/app.css", token=False)[0] == 200
    assert _request(base, "/app.js", token=False)[0] == 200
    assert _request(base, "/nao-existe", token=False)[0] == 404
    assert _request(base, "/api/status", token=False)[0] == 403

    status, _, body = _request(base, "/api/status")
    dados = json.loads(body)
    assert status == 200
    assert dados["privacidade"]["telemetria"] is False
    assert dados["plano"] == "Comunidade"

    assert _request(
        base,
        "/",
        token=False,
        headers={"Host": "site-malicioso.example"},
    )[0] == 403


def test_http_demo_e_todos_os_downloads(app_local):
    base, _ = app_local
    status, _, body = _request(base, "/api/demo", method="POST", body=b"{}")
    assert status == 200
    resultado = json.loads(body)
    assert resultado["demo"]
    assert resultado["itens"]

    for formato, trecho in (
        ("html", b"Minha Contabilidade"),
        ("csv", b"sku;descricao"),
        ("json", b'"itens"'),
    ):
        status, headers, conteudo = _request(
            base,
            f"/api/exportar/{resultado['id']}/{formato}",
            method="POST",
            body=b"{}",
            headers={
                "X-RTC-Brand": "Minha Contabilidade",
                "X-RTC-Color": "#123456",
            },
        )
        assert status == 200
        assert trecho in conteudo
        assert "attachment" in headers["Content-Disposition"]


def test_http_upload_real_e_bloqueia_exportacao_no_comunidade(app_local):
    base, _ = app_local
    tipo, corpo = _multipart(
        [("nota.xml", (FIXTURES / "legado_crt3.xml").read_bytes())]
    )
    status, _, body = _request(
        base,
        "/api/analisar",
        method="POST",
        body=corpo,
        headers={"Content-Type": tipo},
    )
    assert status == 200
    resultado = json.loads(body)
    assert not resultado["demo"]
    assert resultado["arquivos_lidos"] == 1

    status, _, body = _request(
        base,
        f"/api/exportar/{resultado['id']}/csv",
        method="POST",
        body=b"{}",
    )
    assert status == 402
    assert "Escritório" in json.loads(body)["erro"]


def test_http_trata_erros_e_ativa_teste(app_local):
    base, _ = app_local
    assert _request(base, "/api/qualquer", method="POST", body=b"{}")[0] == 404
    assert _request(base, "/api/analisar", method="POST", body=b"{}")[0] == 400
    assert _request(
        base,
        "/api/licenca",
        method="POST",
        body=b'{"chave":"invalida"}',
        headers={"Content-Type": "application/json"},
    )[0] == 400

    status, _, body = _request(base, "/api/teste", method="POST", body=b"{}")
    assert status == 200
    assert json.loads(body)["status"]["plano"] == "Teste grátis"
    assert _request(base, "/api/teste", method="POST", body=b"{}")[0] == 400


def test_http_recusa_relatorio_expirado_e_formato_desconhecido(app_local):
    base, _ = app_local
    assert _request(
        base,
        "/api/exportar/inexistente/csv",
        method="POST",
        body=b"{}",
    )[0] == 400

    _, _, body = _request(base, "/api/demo", method="POST", body=b"{}")
    identificador = json.loads(body)["id"]
    assert _request(
        base,
        f"/api/exportar/{identificador}/pdf",
        method="POST",
        body=b"{}",
    )[0] == 400


def test_executar_sem_navegador(monkeypatch, capsys):
    class ServidorFalso:
        server_port = 45678

        def __init__(self, endereco, handler):
            assert endereco == ("127.0.0.1", 0)
            assert handler

        def serve_forever(self, poll_interval):
            assert poll_interval == 0.25
            raise KeyboardInterrupt

        def server_close(self):
            pass

    monkeypatch.setattr(webapp, "ThreadingHTTPServer", ServidorFalso)
    assert webapp.executar(abrir_navegador=False) == 0
    assert "127.0.0.1:45678" in capsys.readouterr().out


def test_main_le_configuracao_do_executavel(monkeypatch):
    recebido = {}

    def executar_falso(*, porta, abrir_navegador):
        recebido.update(porta=porta, abrir_navegador=abrir_navegador)
        return 0

    monkeypatch.setenv("RTC_CHECK_PORTA", "43210")
    monkeypatch.setenv("RTC_CHECK_SEM_NAVEGADOR", "1")
    monkeypatch.setattr(webapp, "executar", executar_falso)
    assert webapp.main() == 0
    assert recebido == {"porta": 43210, "abrir_navegador": False}

    monkeypatch.setenv("RTC_CHECK_PORTA", "invalida")
    with pytest.raises(SystemExit, match="número"):
        webapp.main()
    monkeypatch.setenv("RTC_CHECK_PORTA", "70000")
    with pytest.raises(SystemExit, match="entre"):
        webapp.main()
