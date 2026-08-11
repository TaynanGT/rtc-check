"""Testes do hook guarda-segredos.

O hook é a única barreira que cobre leitura de segredo por comando de shell — a
regra de permissão só alcança a ferramenta Read. Sem teste, uma edição
descuidada no regex derruba essa barreira sem ninguém perceber, porque o hook
falha em silêncio: ele simplesmente deixa passar.

Os casos de "deve passar" importam tanto quanto os de "deve barrar". Um hook que
bloqueia trabalho legítimo é desinstalado pela primeira pessoa que ele atrapalha,
e aí não protege mais nada.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "guarda-segredos.py"


def _rodar(evento: dict[str, object]) -> dict[str, object] | None:
    """Executa o hook e devolve a decisão, ou None quando ele sai calado."""
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
    return json.loads(resultado.stdout)


def _barrou(evento: dict[str, object]) -> bool:
    saida = _rodar(evento)
    if saida is None:
        return False
    return saida["hookSpecificOutput"]["permissionDecision"] == "deny"


def _leitura(caminho: str, ferramenta: str = "Read") -> dict[str, object]:
    return {"tool_name": ferramenta, "tool_input": {"file_path": caminho}}


def _shell(comando: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": comando}}


@pytest.mark.parametrize(
    "evento",
    [
        pytest.param(_leitura("/proj/.env"), id="env-na-raiz"),
        pytest.param(_leitura("/proj/.env.production"), id="env-de-producao"),
        pytest.param(_leitura("/proj/credenciais/../credentials/mp.json"), id="dir-credential"),
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
        pytest.param(
            {"tool_name": "Grep", "tool_input": {"path": "/home/u/.ssh"}}, id="grep-em-ssh"
        ),
    ],
)
def test_barra_acesso_a_segredo(evento: dict[str, object]) -> None:
    assert _barrou(evento), "o hook deixou passar um caminho sensível"


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
def test_deixa_passar_o_que_e_legitimo(evento: dict[str, object]) -> None:
    assert not _barrou(evento), "o hook barrou trabalho legítimo"


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
    """O hook opina apenas para barrar.

    Se ele respondesse "allow", passaria por cima das regras de permissão do
    próprio usuário — inclusive as que ele não conhece.
    """
    eventos = [
        _leitura("/proj/src/cli.py"),
        _leitura("/proj/.env"),
        _shell("rm -rf /"),
    ]
    for evento in eventos:
        saida = _rodar(evento)
        if saida is not None:
            decisao = saida["hookSpecificOutput"]["permissionDecision"]
            assert decisao == "deny", f"hook respondeu {decisao!r}, e só deveria saber negar"


@pytest.mark.xfail(
    reason="varredura por palavra também enxerga texto que apenas cita o caminho",
    strict=False,
)
@pytest.mark.parametrize(
    "evento",
    [
        pytest.param(_shell("jq -r '.env | keys[]' settings.json"), id="query-jq"),
        pytest.param(_shell('git commit -m "trata melhor o arquivo .env"'), id="mensagem-commit"),
    ],
)
def test_falsos_positivos_conhecidos(evento: dict[str, object]) -> None:
    assert not _barrou(evento)
