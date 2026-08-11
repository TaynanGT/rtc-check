"""Testes do hook guarda-segredos.

O hook é a única cobertura sobre leitura de segredo por comando de shell — a
regra de permissão só alcança a ferramenta Read. Ele também falha em silêncio:
quando o regex deixa de casar, nada acontece, nenhum erro aparece, e a cobertura
some sem ninguém perceber. Isso pede teste.

Os casos de "deve ficar calado" importam tanto quanto os de "deve sinalizar".
Um hook barulhento enche o contexto de aviso irrelevante até ninguém mais ler
nenhum deles.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "guarda-segredos.py"


def _rodar(evento: dict[str, Any]) -> dict[str, Any] | None:
    """Executa o hook e devolve o `hookSpecificOutput`, ou None se saiu calado."""
    resultado = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(evento),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resultado.returncode == 0, f"hook saiu com {resultado.returncode}: {resultado.stderr}"
    if not resultado.stdout.strip():
        return None
    saida: dict[str, Any] = json.loads(resultado.stdout)["hookSpecificOutput"]
    return saida


def _sinalizou(evento: dict[str, Any]) -> bool:
    return _rodar(evento) is not None


def _leitura(caminho: str, ferramenta: str = "Read") -> dict[str, Any]:
    return {"tool_name": ferramenta, "tool_input": {"file_path": caminho}}


def _shell(comando: str) -> dict[str, Any]:
    return {"tool_name": "Bash", "tool_input": {"command": comando}}


@pytest.mark.parametrize(
    "evento",
    [
        pytest.param(_leitura("/proj/.env"), id="env-na-raiz"),
        pytest.param(_leitura("/proj/.env.production"), id="env-de-producao"),
        pytest.param(_leitura("/proj/credentials/mp.json"), id="dir-credencial"),
        pytest.param(_leitura("/home/u/.ssh/id_rsa"), id="chave-ssh"),
        pytest.param(_leitura("/home/u/.aws/credentials"), id="credencial-aws"),
        pytest.param(_leitura("/proj/certs/servidor.pem"), id="certificado"),
        pytest.param(_leitura("/proj/chave.key"), id="chave-privada"),
        pytest.param(_leitura("/home/u/.netrc"), id="netrc"),
        pytest.param(_leitura("C:\\proj\\.env"), id="caminho-windows"),
        pytest.param(_leitura("/proj/.env", "Write"), id="escrita-sobre-env"),
        pytest.param(_leitura("/proj/.env", "Edit"), id="edicao-de-env"),
        pytest.param(_shell("cat .env"), id="shell-cat"),
        pytest.param(_shell("ls && cat /proj/.env | head -5"), id="shell-encadeado"),
        pytest.param(_shell("base64 /home/u/.ssh/id_ed25519"), id="shell-base64-chave"),
        pytest.param({"tool_name": "Grep", "tool_input": {"path": "/home/u/.ssh"}}, id="grep-ssh"),
    ],
)
def test_sinaliza_acesso_a_segredo(evento: dict[str, Any]) -> None:
    saida = _rodar(evento)
    assert saida is not None, "o hook não viu um caminho sensível"
    assert "additionalContext" in saida, "no modo avisar o sinal é o aviso de contexto"


@pytest.mark.parametrize(
    "evento",
    [
        pytest.param(_leitura("/proj/.env.example"), id="exemplo-versionado"),
        pytest.param(_leitura("/proj/.env.sample"), id="sample-versionado"),
        pytest.param(_leitura("/proj/src/cli.py"), id="codigo-comum"),
        pytest.param(_leitura("/proj/monkey.py"), id="nome-que-contem-key"),
        pytest.param(_leitura("/proj/docs/turkey.md"), id="outro-nome-com-key"),
        pytest.param(_shell("grep -rn API_KEY src/"), id="busca-por-nome-de-variavel"),
        pytest.param(_shell("uv run pytest -q"), id="rodar-testes"),
        pytest.param(_shell("echo a chave primaria da tabela"), id="prosa-com-a-palavra-chave"),
        pytest.param(_leitura("/proj/tests/fixtures/conforme_crt3.xml"), id="fixture-de-teste"),
    ],
)
def test_fica_calado_no_que_e_legitimo(evento: dict[str, Any]) -> None:
    assert not _sinalizou(evento), "o hook alarmou sobre trabalho legítimo"


@pytest.mark.parametrize(
    "evento",
    [
        pytest.param(_shell("jq -r '.env | keys[]' settings.json"), id="query-de-ferramenta"),
        pytest.param(_shell('git commit -m "trata melhor o arquivo .env"'), id="mensagem-commit"),
    ],
)
def test_nao_trava_comando_que_apenas_cita_o_caminho(evento: dict[str, Any]) -> None:
    """A varredura é por palavra, então texto que cita um caminho também casa.

    Foi por isso que o modo virou `avisar`: nestes dois casos reais o hook
    chegou a barrar um commit e uma consulta de configuração. Avisar custa uma
    linha de ruído; barrar custava o trabalho.
    """
    saida = _rodar(evento)
    assert saida is not None, "estes casos casam mesmo — o ponto é que não travam"
    assert "permissionDecision" not in saida, "citar um caminho não pode bloquear a chamada"


def test_evento_ilegivel_nao_trava_o_trabalho() -> None:
    resultado = subprocess.run(
        [sys.executable, str(HOOK)],
        input="isto nao e json",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resultado.returncode == 0
    assert not resultado.stdout.strip()


def test_nunca_responde_allow() -> None:
    """O hook não aprova nada.

    Se respondesse "allow", passaria por cima das regras de permissão do próprio
    usuário — inclusive as que ele não conhece.
    """
    for evento in [_leitura("/proj/src/cli.py"), _leitura("/proj/.env"), _shell("rm -rf /")]:
        saida = _rodar(evento)
        if saida is not None:
            assert saida.get("permissionDecision") != "allow"


def _carregar_modulo() -> Any:
    especificacao = importlib.util.spec_from_file_location("guarda_segredos", HOOK)
    assert especificacao and especificacao.loader
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


def test_modo_barrar_continua_funcionando(monkeypatch: pytest.MonkeyPatch) -> None:
    """O modo estrito é uma constante; trocar de ideia não pode exigir reescrita."""
    modulo = _carregar_modulo()
    monkeypatch.setattr(modulo, "MODO", "barrar")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_leitura("/proj/.env"))))

    saidas: list[str] = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: saidas.append(str(a[0])))

    assert modulo.main() == 0
    decisao = json.loads(saidas[0])["hookSpecificOutput"]
    assert decisao["permissionDecision"] == "deny"
    assert "guarda-segredos" in decisao["permissionDecisionReason"]
