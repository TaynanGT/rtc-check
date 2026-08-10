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
# `permissions.allow` e `.deny` são concatenados e deduplicados, para não descartar
# permissões que você já tinha aprovado.
TEMPORARIO="$(mktemp)"
jq -s '
  .[0] as $atual | .[1] as $novo |
  ($atual * $novo)
  | .env = (($atual.env // {}) + ($novo.env // {}))
  | .permissions.allow = ((($atual.permissions.allow // []) + ($novo.permissions.allow // [])) | unique)
  | .permissions.deny  = ((($atual.permissions.deny  // []) + ($novo.permissions.deny  // [])) | unique)
' "$DESTINO" "$ORIGEM" > "$TEMPORARIO"

mv "$TEMPORARIO" "$DESTINO"

echo "config de usuário aplicada em: $DESTINO"
echo
echo "confira dentro do Claude Code com:  /config    e   /permissions"
echo "para voltar atrás, restaure o backup mostrado acima."
