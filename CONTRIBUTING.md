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

A config de usuário liga mensagens entre sessões e Remote Control. Se elas não
aparecerem, procure por `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`,
`DISABLE_TELEMETRY`, `DO_NOT_TRACK` ou `DISABLE_GROWTHBOOK` no seu shell: cada uma
delas desliga a avaliação de feature flag de que os dois recursos dependem, e o
sintoma é o recurso simplesmente não existir, sem erro.

### Esforço e ultracode

O padrão de sessão é `effortLevel: xhigh`. A variável `CLAUDE_CODE_EFFORT_LEVEL`
é deliberadamente **não** definida: ela tem precedência sobre tudo, e defini-la
anula o campo `effort` do frontmatter de cada subagente — que é justamente como
`explorador`, `revisor` e `revisor-pagamento` rodam em níveis diferentes.

Ultracode não é persistível: a chave não é lida de `settings.json` e nem
`effortLevel` nem `CLAUDE_CODE_EFFORT_LEVEL` aceitam o valor. Use
`claude --effort ultracode` no lançamento, ou `/effort ultracode` na sessão. Ele
envia `xhigh` ao modelo e acrescenta a orquestração de workflows; sessões com
ultracode ativo também ficam isentas do limite de subagentes simultâneos.

O `revisor` roda em `medium` de propósito, não por economia: nos níveis baixo e
médio a revisão só relata o que tem mais confiança, e nos altos ela amplia a
cobertura ao custo de falso positivo. Para um revisor pré-commit, precisão vale
mais que abrangência — quem quiser a varredura ampla usa `/code-review`.

Ressalva conhecida: o `effort` do frontmatter é respeitado quando o subagente é
despachado pela ferramenta Task, que é o caminho normal. Há relato de que ele é
ignorado no caminho `--agent` e descartado em agent teams, enquanto o `model`
passa nos três. A falha é silenciosa, então não conte com o `effort` nesses dois
casos.
