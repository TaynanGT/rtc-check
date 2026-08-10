# rtc-check

Auditoria local de prontidão da NF-e para a Reforma Tributária (IBS/CBS). CLI +
app desktop em Python 3.11+. O XML do cliente nunca sai da máquina dele.

## Comandos

```bash
uv pip install -e ".[dev]"      # ambiente
uv run pytest                   # testes (CI exige --cov-fail-under=90)
uv run pytest tests/test_rules.py -k nome_do_teste   # prefira o teste isolado
uv run ruff check .             # lint
uv run mypy                     # tipos (strict = true)
node --check src/rtc_check/web/app.js   # o JS da interface entra no CI
```

Antes de commitar, o mínimo é `ruff check .` + `mypy` + `pytest`. O CI roda ainda
matriz 3.11–3.14 em Linux/Windows/macOS, instalação limpa a partir do wheel,
`bandit`, `pip-audit` e um teste real de interface no Chromium.

## Contratos que não podem quebrar sem aviso

- **Exit codes do CLI** são API pública, verificados no job `instalacao-limpa` do
  CI: `0` varredura ok, `1` bloqueio encontrado, `2` nenhum XML analisado,
  `3` recurso pago sem plano. Mudar qualquer um é breaking change.
- **A interface visual precisa entrar no wheel**: `rtc_check/web/index.html`,
  `app.css` e `app.js`. Se mexer em `[tool.hatch.build]`, confira o job.
- **Cobertura mínima de 90%** — mudança de comportamento sem teste derruba o CI.

## Dados sensíveis

Nunca leia, copie para relatório, log ou commit: `.env`, `credentials/`, `*.pem`,
`*.key`, e principalmente `xmls/` e `acervo/` — são notas fiscais de cliente.
`.env.example` é público e serve de referência; os valores reais, não.
`src/rtc_check/mercadopago.py`, `checkout.py` e `servidor_vendas.py` tocam
pagamento e licenciamento: mudança ali pede o subagente `revisor`.

## Convenções

- Código, commits, comentários, mensagens de erro e docs em **português do Brasil**.
- Comentário explica *por quê*, não *o quê* — veja o padrão já usado em `ci.yml`.
- `ruff` com `line-length = 100` e regras `E,F,I,UP,B,SIM`; `mypy` em modo strict.
- Branch de trabalho e PR conforme `CONTRIBUTING.md`; PR usa
  `.github/pull_request_template.md`.

## Subagentes deste projeto

- `explorador` (haiku) — localizar código sem encher o contexto principal.
- `revisor` (sonnet) — revisar o diff em contexto limpo antes do commit.

Delegue busca ampla ao `explorador`: ele devolve `arquivo:linha` em vez de
despejar arquivos no contexto.
