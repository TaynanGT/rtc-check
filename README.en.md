# RTC Check

[![CI](https://github.com/TaynanGT/rtc-check/actions/workflows/ci.yml/badge.svg)](https://github.com/TaynanGT/rtc-check/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20to%203.14-blue.svg)](pyproject.toml)

**[Project page](https://taynangt.github.io/rtc-check/)** · **[Português](README.md)**

**Find product XML patterns that may cause rejection from August 3rd onward.**

Brazil's tax reform (Reforma Tributária) adds IBS and CBS fields to the electronic
invoice (NF-e). From **2026-08-03**, rule UB12-10 rejects an NF-e issued by a
company under the regular tax regime (`CRT=3`) without the parent `IBSCBS`
group, when the rule applies.

Understanding the rule is the easy part. The hard part is knowing **which of your
thousands of SKUs are out of compliance** — and that answer is already sitting in the
XML archive on your disk. RTC Check scans it and returns the list of SKUs that need
work, grouped by product and sorted by impact.

```
  RTC Check | prontidão para a Reforma Tributária
  ----------------------------------------------------
  Corte da obrigatoriedade (CRT=3): 03/08/2026  (9 dias)

  XMLs lidos ............... 4127
  Notas em escopo (CRT=3) .. 3980
  Itens analisados ......... 21544

  Bloqueios ................ 8102
  Alertas .................. 341
  SKUs a corrigir .......... 214
```

214 work items, not 8,102. You fix the product record once.

> The tool's interface and reports are in Brazilian Portuguese, because that is the
> language of the invoices, of the tax rule and of the people who fix the records.
> This page exists so you can evaluate the project before installing it.

## Runs on your machine. Full stop.

No XML leaves your computer. There is no account, external server, or telemetry.
The visual app uses a temporary server restricted to `127.0.0.1`; browser uploads
are processed on the same PC and removed after each analysis. `defusedxml` protects
the parser and `cryptography` verifies signed licenses.

The scan and the text report above are **free forever, no sign-up**. Exporting,
automating and comparing runs are part of the paid plans, with a
[14-day free trial](#plans) unlocked by a local command.

## Install

```bash
pip install "rtc-check @ git+https://github.com/TaynanGT/rtc-check.git"
```

Or without installing anything permanent:

```bash
uvx --from git+https://github.com/TaynanGT/rtc-check.git rtc-check ./xmls
```

In production, pin a version instead of tracking `main`: append the release tag to
the URL, as in `...rtc-check.git@v0.4.1`. Available tags are listed under
[releases](https://github.com/TaynanGT/rtc-check/releases).

Requires Python 3.11+. Tested on Windows, Linux and macOS, from 3.11 to 3.14.

## Usage

```bash
rtc-check ./folder-with-xmls          # free
rtc-check --iniciar-teste             # start the 14-day trial
rtc-check ./xmls -f html -o report.html
rtc-check ./xmls --falhar-em-bloqueio # fail a CI build on blockers
rtc-check ./xmls --por-cnpj           # break down by issuing company
rtc-check ./xmls --comparar last-week.json
rtc-check --plano                     # show the current edition
```

Exit codes: `0` clean, `1` blockers found (with `--falhar-em-bloqueio`), `2` usage
error, `3` the requested feature is not in the current plan.

## Plans

| | Community | Office | Platform |
|---|---|---|---|
| **Price** | R$ 0, forever | R$ 149/month or R$ 1,490/year | contact us |
| Unlimited local scanning | yes | yes | yes |
| Cut-off rules (`RTC001` to `RTC006`) | yes | yes | yes |
| Blocker and SKU counts | yes | yes | yes |
| Full SKU list | first 5 | full | full |
| Product-record rules (`NCM001`, `GTIN001`) | no | yes | yes |
| JSON, CSV and HTML export | no | yes | yes |
| Write to file, CI gate | no | yes | yes |
| Per-CNPJ breakdown, run comparison | no | yes | yes |
| Rule updates | via GitHub | signed package, the day the NT ships | same |
| Support | public issues | email, 1 business day | contract |
| Redistribution license | no | no | yes |

The free plan is not bait: it fully answers the question that brought you here, which is
*"does my current XML pattern pose a rejection risk in August?"*. What you pay
for is the work that comes after the answer.

## What it checks

| Code | Severity | Check | Plan |
|---|---|---|---|
| `RTC001` | blocker | parent `IBSCBS` missing when UB12-10 applies | free |
| `RTC002` | blocker | `IBSCBS` present but without `cClassTrib` | free |
| `RTC003` | blocker | IBS/CBS CST missing or absent from the official table | free |
| `RTC004` | blocker | CST requires `gIBSCBS`, but the group is missing | free |
| `RTC005` | blocker | CST forbids `gIBSCBS`, but the group is present | free |
| `RTC006` | blocker | `cClassTrib` is not current for NF-e in the official table | free |
| `NCM001` | blocker | NCM missing or not 8 digits | paid |
| `GTIN001` | warning | invalid GS1 check digit or malformed GTIN | paid |

The report records the exact regulatory snapshot: Technical Note
2025.002-RTC v1.50 and the CST/cClassTrib table from Technical Report
2025.002 v1.60. Historical findings are conditional: they represent risk if
the same emission pattern continues after the cut-off.

Issuers under Simples Nacional (`CRT=1` and `2`) never produce an RTC blocker: their
transition follows a different rule and is not part of the August cut-off. A false
positive is worse than a missing check — it is what makes people stop reading the report.

## What it is not

It is not a schema validator and does not try to be. The
[official SEFAZ-RS validator](https://dfe-portal.svrs.rs.gov.br/Cff/ValidadorRtcNfe) is
the source of truth for structural conformance, and it is free. The difference is scope:
the official one validates *one invoice at a time*. RTC Check scans the whole archive and
tells you where to look; then you confirm the fixed invoice in the official validator.

## Development

```bash
git clone https://github.com/TaynanGT/rtc-check && cd rtc-check
uv venv && uv pip install -e ".[dev]"
uv run pytest          # tests
uv run ruff check .    # lint
uv run mypy            # types
```

## License

AGPL-3.0-or-later. Internal use in your company, including commercial use, is allowed.
Embedding RTC Check in a closed-source product, or offering it as a service without
publishing your modifications, requires a commercial license — see
[COMMERCIAL.md](COMMERCIAL.md).

An honest note about the plans: the code is open, so the feature gating lives in this
repository and anyone can remove it. That is known and will not change. A subscription
does not buy access to the binary; it buys the rule updated the day the technical note
ships, support with a deadline, and the right to redistribute.
