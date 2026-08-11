#!/usr/bin/env python3
"""Hook PreToolUse: barra leitura de segredo em qualquer projeto.

As regras de `permissions.deny` cobrem a ferramenta Read, mas não cobrem
`cat .env` nem `type .env` pelo Bash — e é por aí que um segredo vaza sem
ninguém perceber. Este hook olha os dois caminhos.

Ele nunca responde "allow": quando não reconhece nada de sensível, sai calado e
deixa a decisão com as suas regras de permissão. Um hook que aprova por conta
própria desmontaria o resto da configuração.

Contrato: recebe o evento em JSON no stdin, devolve JSON no stdout.
https://code.claude.com/docs/en/hooks
"""

from __future__ import annotations

import json
import re
import sys

# Caminhos que nunca devem ser lidos. Casam com segmento de caminho, não com
# substring solta, senão `grep API_KEY src/` viraria falso positivo.
PADROES = [
    (r"(^|[/\\])\.env(\.local|\.production|\.prod|\.staging)?$", "arquivo .env"),
    (r"(^|[/\\])credentials([/\\]|$)", "diretório credentials/"),
    (r"(^|[/\\])\.ssh([/\\]|$)", "diretório .ssh/"),
    (r"(^|[/\\])\.aws([/\\]|$)", "diretório .aws/"),
    (r"\.(pem|key|p12|pfx|jks)$", "arquivo de chave privada"),
    (r"(^|[/\\])id_(rsa|dsa|ecdsa|ed25519)$", "chave SSH privada"),
    (r"(^|[/\\])\.credentials\.json$", "credencial do Claude Code"),
    (r"(^|[/\\])\.netrc$", "arquivo .netrc"),
]

# Exemplos versionados são públicos por definição e servem de referência.
LIBERADOS = re.compile(r"\.(example|sample|template|dist)$|\.env\.example", re.IGNORECASE)

COMPILADOS = [(re.compile(p, re.IGNORECASE), rotulo) for p, rotulo in PADROES]


def _classificar(texto: str) -> str | None:
    """Devolve o rótulo do segredo encontrado, ou None."""
    if not texto:
        return None
    if LIBERADOS.search(texto):
        return None
    for padrao, rotulo in COMPILADOS:
        if padrao.search(texto):
            return rotulo
    return None


def _alvos_do_comando(comando: str) -> list[str]:
    """Extrai de um comando de shell as palavras que parecem caminho.

    Sem isto, um comando como `echo "sem chave aqui"` casaria com o padrão de
    chave só pela palavra solta.
    """
    palavras = re.split(r"[\s;|&()<>]+", comando)
    return [p.strip("\"'") for p in palavras if p.strip("\"'")]


def main() -> int:
    try:
        evento = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Evento ilegível não é motivo para travar o trabalho de ninguém.
        return 0

    ferramenta = evento.get("tool_name", "")
    entrada = evento.get("tool_input") or {}
    achado = None

    if ferramenta in {"Read", "Edit", "Write", "NotebookEdit"}:
        caminho = entrada.get("file_path") or entrada.get("notebook_path") or ""
        achado = _classificar(str(caminho).replace("\\", "/"))

    elif ferramenta in {"Bash", "PowerShell"}:
        comando = str(entrada.get("command", ""))
        for alvo in _alvos_do_comando(comando):
            achado = _classificar(alvo.replace("\\", "/"))
            if achado:
                break

    elif ferramenta in {"Grep", "Glob"}:
        caminho = str(entrada.get("path", ""))
        achado = _classificar(caminho.replace("\\", "/"))

    if not achado:
        # Nada reconhecido: silêncio, e a decisão volta para as regras normais.
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Bloqueado pelo hook guarda-segredos: {achado}. "
                        "Segredo e credencial não entram no contexto, em log, em "
                        "relatório nem em commit. Se precisa saber o formato do "
                        "arquivo, leia o .example correspondente."
                    ),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
