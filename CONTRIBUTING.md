# Contribuindo

## Ambiente

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest && uv run ruff check . && uv run mypy
```

Os três precisam passar antes do push. O CI roda em Windows, Linux e macOS,
nas versões 3.11 a 3.13 do Python.

## Regra nova

Cada regra vive em `src/rtc_check/rules.py` e precisa de:

1. Um código estável (`RTC003`, `NCM002`, ...). Código publicado não muda de
   significado, porque cliente coloca isso em planilha isso em planilha e em filtro de CI.
2. Severidade honesta: `BLOQUEIO` é só para o que realmente faz o SEFAZ
   rejeitar a nota. Inflacionar bloqueio destrói a confiança no relatório.
3. Uma fixture em `tests/fixtures/` que dispara a regra, e outra parecida que
   **não** dispara. A segunda é a que pega falso positivo.
4. Linha nova na tabela do README e no CHANGELOG.

## Fixtures

Use CNPJ e chave de acesso fictícios. Nunca commite XML de empresa real.
o `.gitignore` ajuda, mas ele não substitui conferir o `git diff`.

## Claude Code

`.claude/settings.json` e `CLAUDE.md` já vêm no repositório e valem para quem
clona: permissões dos comandos do projeto, bloqueio de leitura em `.env`,
`credentials/`, `xmls/` e `acervo/`, e dois subagentes (`explorador`, `revisor`).

Para aplicar a mesma configuração nos seus **outros** projetos, em nível de
usuário:

```bash
./scripts/aplicar-config-claude.sh --ver   # mostra o que seria escrito
./scripts/aplicar-config-claude.sh         # mescla em ~/.claude/settings.json
```

O script faz backup do seu `settings.json` atual e mescla em vez de sobrescrever.
