#!/usr/bin/env bash
# Aplica a configuração de nível de usuário do Claude Code em ~/.claude/settings.json.
#
# O settings.json do projeto (.claude/settings.json) já vale para quem clona este
# repositório. Este script é para a outra metade: valer em TODOS os projetos da
# máquina, inclusive os que não têm .claude/ nenhum.
#
# Uso:
#   ./scripts/aplicar-config-claude.sh          # aplica (faz backup do que existir)
#   ./scripts/aplicar-config-claude.sh --ver    # só mostra o que seria escrito
#
# Requer: jq (para mesclar sem apagar o que você já tem).

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGEM="$RAIZ/.claude/settings.global.example.json"
DESTINO="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"

if [ ! -f "$ORIGEM" ]; then
  echo "erro: não encontrei $ORIGEM" >&2
  exit 1
fi

if [ "${1:-}" = "--ver" ]; then
  cat "$ORIGEM"
  exit 0
fi

if ! command -v jq > /dev/null 2>&1; then
  echo "erro: este script precisa do jq para mesclar sem apagar sua config atual." >&2
  echo "      instale o jq, ou copie o arquivo à mão:" >&2
  echo "      cp '$ORIGEM' '$DESTINO'" >&2
  exit 1
fi

mkdir -p "$(dirname "$DESTINO")"

if [ -f "$DESTINO" ]; then
  BACKUP="$DESTINO.backup-$(date +%Y%m%d-%H%M%S)"
  cp "$DESTINO" "$BACKUP"
  echo "backup da config anterior: $BACKUP"
else
  echo '{}' > "$DESTINO"
fi

# Mescla profunda: o que já existia é preservado, as chaves novas entram por cima.
# O `*` do jq só funde objeto; array ele substitui. Por isso `permissions.allow`,
# `.deny` e cada evento de `hooks` são concatenados à mão — sem isso, instalar o
# guarda de segredos apagaria os hooks que você já tivesse configurado.
TEMPORARIO="$(mktemp)"
jq -s '
  .[0] as $atual | .[1] as $novo |
  ($atual * $novo)
  | .env = (($atual.env // {}) + ($novo.env // {}))
  | .permissions.allow = ((($atual.permissions.allow // []) + ($novo.permissions.allow // [])) | unique)
  | .permissions.deny  = ((($atual.permissions.deny  // []) + ($novo.permissions.deny  // [])) | unique)
  | .hooks = (
      (($atual.hooks // {}) * ($novo.hooks // {}))
      | with_entries(
          .key as $evento
          | .value = (
              ((($atual.hooks // {})[$evento]) // [])
              + ((($novo.hooks // {})[$evento]) // [])
              | unique
            )
        )
    )
' "$DESTINO" "$ORIGEM" > "$TEMPORARIO"

mv "$TEMPORARIO" "$DESTINO"

echo "config de usuário aplicada em: $DESTINO"

# O CLAUDE.md global é prosa, não JSON: mesclar automaticamente misturaria regras
# de dois autores sem ninguém conferir. Só instala quando não existe nada lá.
MEMORIA_ORIGEM="$RAIZ/.claude/CLAUDE.global.example.md"
MEMORIA_DESTINO="$(dirname "$DESTINO")/CLAUDE.md"

if [ -f "$MEMORIA_ORIGEM" ]; then
  if [ ! -f "$MEMORIA_DESTINO" ] || cmp -s "$MEMORIA_ORIGEM" "$MEMORIA_DESTINO"; then
    cp "$MEMORIA_ORIGEM" "$MEMORIA_DESTINO"
    echo "instruções globais instaladas em: $MEMORIA_DESTINO"
  else
    cp "$MEMORIA_ORIGEM" "$MEMORIA_DESTINO.novo"
    echo
    echo "você já tem um $MEMORIA_DESTINO — não sobrescrevi."
    echo "a versão nova ficou em $MEMORIA_DESTINO.novo; compare com:"
    echo "    diff '$MEMORIA_DESTINO' '$MEMORIA_DESTINO.novo'"
  fi
fi

# Subagentes de nível de usuário valem em todos os projetos. Só entram aqui os
# genéricos: os que citam arquivo ou regra deste repositório ficam no projeto,
# onde o escopo de projeto tem precedência sobre o de usuário de qualquer forma.
AGENTES_ORIGEM="$RAIZ/.claude/agents.global"
AGENTES_DESTINO="$(dirname "$DESTINO")/agents"

if [ -d "$AGENTES_ORIGEM" ]; then
  mkdir -p "$AGENTES_DESTINO"
  for agente in "$AGENTES_ORIGEM"/*.md; do
    [ -e "$agente" ] || continue
    nome="$(basename "$agente")"
    if [ -f "$AGENTES_DESTINO/$nome" ] && ! cmp -s "$agente" "$AGENTES_DESTINO/$nome"; then
      cp "$agente" "$AGENTES_DESTINO/$nome.novo"
      echo "subagente $nome já existe e difere; versão nova em $nome.novo"
    else
      cp "$agente" "$AGENTES_DESTINO/$nome"
      echo "subagente global instalado: $AGENTES_DESTINO/$nome"
    fi
  done
fi

# O hook precisa existir no disco e ser executável antes de a config apontar
# para ele; um comando de hook que não roda falha em silêncio.
HOOKS_ORIGEM="$RAIZ/.claude/hooks"
HOOKS_DESTINO="$(dirname "$DESTINO")/hooks"

if [ -d "$HOOKS_ORIGEM" ]; then
  mkdir -p "$HOOKS_DESTINO"
  for gancho in "$HOOKS_ORIGEM"/*; do
    [ -e "$gancho" ] || continue
    cp "$gancho" "$HOOKS_DESTINO/"
    chmod +x "$HOOKS_DESTINO/$(basename "$gancho")"
    echo "hook instalado: $HOOKS_DESTINO/$(basename "$gancho")"
  done
fi

echo
echo "confira dentro do Claude Code com:  /config  /permissions  /memory  /agents  /hooks"
echo "para voltar atrás, restaure o backup mostrado acima."
echo
# O ultracode é session-only por definição: a chave não é lida de settings.json.
# A única forma de "sempre ligado" é o lançamento sempre pedir por ele.
cat <<'FIM'
Ultracode não tem forma persistente — a chave não é lida de settings.json.
Para que toda sessão já comece com ele, coloque no seu ~/.bashrc ou ~/.zshrc:

    alias claude='claude --effort ultracode'

Dentro de uma sessão já aberta, use /effort ultracode.
Sem alias, o padrão desta config é effort xhigh, que é o nível que o
ultracode envia ao modelo — muda só a orquestração de workflows.
FIM
