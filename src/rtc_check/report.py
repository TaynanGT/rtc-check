"""Agregação dos achados e geração de relatórios (texto, JSON, CSV, HTML).

A agregação é por SKU de propósito: a correção acontece uma vez no cadastro do
produto, não uma vez por nota. Um SKU quebrado em 4.000 notas é *um* item de
trabalho, não quatro mil.
"""

from __future__ import annotations

import csv
import html
import io
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from .rules import Achado, Severidade, dias_ate_corte


@dataclass
class GrupoSku:
    sku: str
    descricao: str
    ncm: str
    codigos: set[str] = field(default_factory=set)
    mensagens: dict[str, str] = field(default_factory=dict)
    severidade_max: Severidade = Severidade.INFO
    ocorrencias: int = 0
    arquivos: set[str] = field(default_factory=set)


@dataclass
class Resumo:
    arquivos_lidos: int = 0
    arquivos_invalidos: list[tuple[str, str]] = field(default_factory=list)
    notas_em_escopo: int = 0
    total_itens: int = 0
    por_severidade: Counter[str] = field(default_factory=Counter)
    grupos: list[GrupoSku] = field(default_factory=list)

    @property
    def skus_bloqueados(self) -> int:
        return sum(1 for g in self.grupos if g.severidade_max is Severidade.BLOQUEIO)

    @property
    def aprovado(self) -> bool:
        return self.por_severidade[Severidade.BLOQUEIO.value] == 0


_ORDEM = {Severidade.BLOQUEIO: 0, Severidade.ALERTA: 1, Severidade.INFO: 2}


def agregar(achados: list[Achado]) -> list[GrupoSku]:
    mapa: dict[str, GrupoSku] = {}
    for a in achados:
        chave = a.sku or f"(sem código) {a.descricao[:30]}"
        grupo = mapa.get(chave)
        if grupo is None:
            grupo = GrupoSku(sku=chave, descricao=a.descricao, ncm=a.ncm)
            mapa[chave] = grupo
        grupo.codigos.add(a.codigo)
        grupo.mensagens.setdefault(a.codigo, a.mensagem)
        grupo.ocorrencias += 1
        grupo.arquivos.add(a.arquivo)
        if _ORDEM[a.severidade] < _ORDEM[grupo.severidade_max]:
            grupo.severidade_max = a.severidade

    return sorted(
        mapa.values(),
        key=lambda g: (_ORDEM[g.severidade_max], -g.ocorrencias, g.sku),
    )


def formatar_texto(resumo: Resumo, hoje: date | None = None) -> str:
    dias = dias_ate_corte(hoje)
    linhas = [
        "",
        "  RTC Check — prontidão para a Reforma Tributária",
        "  " + "-" * 52,
        f"  Corte da obrigatoriedade (CRT=3): 03/08/2026  ({dias} dias)",
        "",
        f"  XMLs lidos ............... {resumo.arquivos_lidos}",
        f"  Notas em escopo (CRT=3) .. {resumo.notas_em_escopo}",
        f"  Itens analisados ......... {resumo.total_itens}",
        "",
        f"  Bloqueios ................ {resumo.por_severidade[Severidade.BLOQUEIO.value]}",
        f"  Alertas .................. {resumo.por_severidade[Severidade.ALERTA.value]}",
        f"  SKUs a corrigir .......... {resumo.skus_bloqueados}",
        "",
    ]

    if resumo.arquivos_invalidos:
        linhas.append(f"  {len(resumo.arquivos_invalidos)} arquivo(s) ilegível(is):")
        for nome, motivo in resumo.arquivos_invalidos[:5]:
            linhas.append(f"    - {nome}: {motivo}")
        if len(resumo.arquivos_invalidos) > 5:
            linhas.append(f"    ... e mais {len(resumo.arquivos_invalidos) - 5}")
        linhas.append("")

    bloqueios = [g for g in resumo.grupos if g.severidade_max is Severidade.BLOQUEIO]
    if bloqueios:
        linhas.append("  SKUs que serão rejeitados a partir de 03/08:")
        linhas.append("")
        for g in bloqueios[:20]:
            linhas.append(f"    {g.sku}  ({g.ocorrencias}x em {len(g.arquivos)} nota(s))")
            linhas.append(f"      {g.descricao[:64]}")
            for codigo in sorted(g.codigos):
                linhas.append(f"      [{codigo}] {g.mensagens[codigo]}")
            linhas.append("")
        if len(bloqueios) > 20:
            linhas.append(
                f"    ... e mais {len(bloqueios) - 20} SKU(s). "
                "Veja o relatório completo."
            )
            linhas.append("")

    if resumo.aprovado:
        linhas.append("  Nenhum bloqueio encontrado neste acervo.")
        linhas.append("")

    return "\n".join(linhas)


def formatar_json(resumo: Resumo) -> str:
    return json.dumps(
        {
            "corte": "2026-08-03",
            "arquivos_lidos": resumo.arquivos_lidos,
            "arquivos_invalidos": [
                {"arquivo": n, "motivo": m} for n, m in resumo.arquivos_invalidos
            ],
            "notas_em_escopo": resumo.notas_em_escopo,
            "total_itens": resumo.total_itens,
            "bloqueios": resumo.por_severidade[Severidade.BLOQUEIO.value],
            "alertas": resumo.por_severidade[Severidade.ALERTA.value],
            "skus_a_corrigir": resumo.skus_bloqueados,
            "itens": [
                {
                    "sku": g.sku,
                    "descricao": g.descricao,
                    "ncm": g.ncm,
                    "severidade": g.severidade_max.value,
                    "codigos": sorted(g.codigos),
                    "mensagens": g.mensagens,
                    "ocorrencias": g.ocorrencias,
                    "notas_afetadas": len(g.arquivos),
                }
                for g in resumo.grupos
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def formatar_csv(resumo: Resumo) -> str:
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", lineterminator="\n")
    escritor.writerow(
        ["sku", "descricao", "ncm", "severidade", "codigos", "ocorrencias",
         "notas_afetadas", "mensagens"]
    )
    for g in resumo.grupos:
        escritor.writerow([
            g.sku, g.descricao, g.ncm, g.severidade_max.value,
            "|".join(sorted(g.codigos)), g.ocorrencias, len(g.arquivos),
            " / ".join(g.mensagens[c] for c in sorted(g.codigos)),
        ])
    return buffer.getvalue()


_CSS = """
*{box-sizing:border-box}body{margin:0;padding:2rem 1.5rem;font:15px/1.6 -apple-system,
"Segoe UI",system-ui,sans-serif;color:#18181b;background:#fafafa}
.wrap{max-width:1000px;margin:0 auto}h1{font-size:1.5rem;margin:0 0 .25rem}
.sub{color:#71717a;margin:0 0 2rem;font-size:.9rem}
.cards{display:grid;gap:.75rem;margin-bottom:2rem;
grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.card{background:#fff;border:1px solid #e4e4e7;border-radius:8px;padding:1rem}
.card .n{font-size:1.75rem;font-weight:650;letter-spacing:-.02em}
.card .l{color:#71717a;font-size:.8rem;margin-top:.15rem}
.card.bad .n{color:#dc2626}.card.warn .n{color:#d97706}.card.ok .n{color:#16a34a}
.tw{overflow-x:auto;background:#fff;border:1px solid #e4e4e7;border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:.875rem}
th{text-align:left;padding:.6rem .75rem;background:#f4f4f5;font-weight:600;
border-bottom:1px solid #e4e4e7;white-space:nowrap}
td{padding:.6rem .75rem;border-bottom:1px solid #f4f4f5;vertical-align:top}
tr:last-child td{border-bottom:0}
.tag{display:inline-block;padding:.1rem .45rem;border-radius:4px;font-size:.75rem;font-weight:600}
.tag.bloqueio{background:#fee2e2;color:#991b1b}.tag.alerta{background:#fef3c7;color:#92400e}
.tag.info{background:#e0e7ff;color:#3730a3}
code{font:.8rem ui-monospace,Consolas,monospace;background:#f4f4f5;
padding:.05rem .3rem;border-radius:3px}
.msg{color:#52525b;font-size:.8rem;margin-top:.2rem}
footer{margin-top:2rem;color:#a1a1aa;font-size:.8rem}
"""


def formatar_html(resumo: Resumo, hoje: date | None = None) -> str:
    e = html.escape
    dias = dias_ate_corte(hoje)
    b = resumo.por_severidade[Severidade.BLOQUEIO.value]
    a = resumo.por_severidade[Severidade.ALERTA.value]

    linhas = []
    for g in resumo.grupos:
        msgs = "".join(
            f'<div class="msg"><code>{e(c)}</code> {e(g.mensagens[c])}</div>'
            for c in sorted(g.codigos)
        )
        linhas.append(
            f"<tr><td><code>{e(g.sku)}</code></td>"
            f"<td>{e(g.descricao[:70])}{msgs}</td>"
            f"<td><code>{e(g.ncm)}</code></td>"
            f'<td><span class="tag {g.severidade_max.value}">'
            f"{g.severidade_max.value}</span></td>"
            f"<td>{g.ocorrencias}</td><td>{len(g.arquivos)}</td></tr>"
        )

    corpo = "".join(linhas) or '<tr><td colspan="6">Nenhum achado.</td></tr>'

    cartoes = [
        ("", resumo.arquivos_lidos, "XMLs lidos"),
        ("", resumo.notas_em_escopo, "Notas em escopo"),
        ("", resumo.total_itens, "Itens analisados"),
        ("bad" if b else "ok", b, "Bloqueios"),
        ("warn" if a else "ok", a, "Alertas"),
        ("bad" if resumo.skus_bloqueados else "ok", resumo.skus_bloqueados, "SKUs a corrigir"),
    ]
    cards = "".join(
        f'<div class="card {classe}"><div class="n">{valor}</div>'
        f'<div class="l">{rotulo}</div></div>'
        for classe, valor, rotulo in cartoes
    )

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RTC Check — relatório de prontidão</title><style>{_CSS}</style></head>
<body><div class="wrap">
<h1>Prontidão para a Reforma Tributária</h1>
<p class="sub">Corte da obrigatoriedade para emitentes CRT=3:
<strong>03/08/2026</strong> — faltam {dias} dias.</p>
<div class="cards">{cards}</div>
<div class="tw"><table>
<thead><tr><th>SKU</th><th>Produto / achados</th><th>NCM</th>
<th>Severidade</th><th>Ocorrências</th><th>Notas</th></tr></thead>
<tbody>{corpo}</tbody></table></div>
<footer>Gerado localmente pelo RTC Check. Nenhum dado saiu desta máquina.<br>
Conferência de estrutura; a fonte de verdade para conformidade de schema é o
validador oficial do SEFAZ.</footer>
</div></body></html>"""
