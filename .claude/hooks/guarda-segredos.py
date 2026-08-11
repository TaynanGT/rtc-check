#!/usr/bin/env python3
"""Hook PreToolUse: sinaliza acesso a segredo em qualquer projeto.

As regras de `permissions.deny` cobrem a ferramenta Read, mas não cobrem
`cat .env` nem `type .env` pelo Bash — e é por aí que um segredo vaza sem
ninguém perceber. Este hook olha os dois caminhos.

MODO decide o que ele faz ao reconhecer um caminho sensível:

- `avisar` (atual): injeta um aviso junto do resultado da ferramenta e deixa
  passar. A varredura é por palavra, então ela também enxerga texto que apenas
  cita o caminho — uma query de ferramenta, o corpo de uma mensagem de commit.
  Avisando, esses casos custam uma linha de ruído em vez de travar o trabalho.
- `barrar`: nega a chamada. Protege de fato contra leitura por shell, ao preço
  de barrar também quem só citou o caminho.

Trocar de modo é trocar esta constante. Em qualquer um dos dois, as regras de
`permissions.deny` continuam valendo por conta própria sobre a ferramenta Read.

Ele nunca responde "allow": aprovar por conta própria passaria por cima das
regras de permissão do usuário, inclusive as que este hook não conhece.

Contrato: recebe o evento em JSON no stdin, devolve JSON no stdout.
https://code.claude.com/docs/en/hooks
"""

from __future__ import annotations

import json
import re
import sys

MODO = "avisar"  # "avisar" ou "barrar"

# Caminhos sensíveis. Casam com segmento de caminho, não com substring solta,
# senão `grep API_KEY src/` viraria alarme.
PADROES = [
    (r"(^|[/\\])\.env(\.local|\.production|\.prod|\.staging)?$", "arquivo .env"),
    (r"(^|[/\\])credentials([/\\]|$)", "diretório de credencial"),
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
    """Divide um comando de shell nas palavras que podem ser caminho."""
    palavras = re.split(r"[\s;|&()<>]+", comando)
    return [p.strip("\"'") for p in palavras if p.strip("\"'")]


def _achado(evento: dict[str, object]) -> str | None:
    ferramenta = evento.get("tool_name", "")
    entrada = evento.get("tool_input") or {}
    if not isinstance(entrada, dict):
        return None

    if ferramenta in {"Read", "Edit", "Write", "NotebookEdit"}:
        caminho = entrada.get("file_path") or entrada.get("notebook_path") or ""
        return _classificar(str(caminho).replace("\\", "/"))

    if ferramenta in {"Bash", "PowerShell"}:
        comando = str(entrada.get("command", ""))
        for alvo in _alvos_do_comando(comando):
            rotulo = _classificar(alvo.replace("\\", "/"))
            if rotulo:
                return rotulo
        return None

    if ferramenta in {"Grep", "Glob"}:
        return _classificar(str(entrada.get("path", "")).replace("\\", "/"))

    return None


def main() -> int:
    try:
        evento = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Evento ilegível não é motivo para travar o trabalho de ninguém.
        return 0

    if not isinstance(evento, dict):
        return 0

    rotulo = _achado(evento)
    if not rotulo:
        # Nada reconhecido: silêncio, e a decisão volta para as regras normais.
        return 0

    saida: dict[str, object] = {"hookEventName": "PreToolUse"}

    if MODO == "barrar":
        saida["permissionDecision"] = "deny"
        saida["permissionDecisionReason"] = (
            f"Bloqueado pelo hook guarda-segredos: {rotulo}. Segredo e credencial "
            "não entram no contexto, em log, em relatório nem em commit. Se "
            "precisa saber o formato do arquivo, leia o .example correspondente."
        )
    else:
        saida["additionalContext"] = (
            f"Aviso do hook guarda-segredos: esta chamada menciona {rotulo}. "
            "Se ela realmente lê o arquivo, não traga o conteúdo para o contexto, "
            "log, relatório nem commit — use o .example correspondente para saber "
            "o formato. Se ela apenas cita o caminho num texto, siga normalmente."
        )

    print(json.dumps({"hookSpecificOutput": saida}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
