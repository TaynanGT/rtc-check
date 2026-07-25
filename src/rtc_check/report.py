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
class ResumoEmitente:
    """Recorte por CNPJ emitente, para quem audita mais de uma empresa."""

    cnpj: str
    nome: str = ""
    notas: int = 0
    notas_em_escopo: int = 0
    itens: int = 0
    bloqueios: int = 0
    alertas: int = 0
    skus: set[str] = field(default_factory=set)


@dataclass
class Resumo:
    arquivos_lidos: int = 0
    arquivos_invalidos: list[tuple[str, str]] = field(default_factory=list)
    notas_em_escopo: int = 0
    total_itens: int = 0
    por_severidade: Counter[str] = field(default_factory=Counter)
    grupos: list[GrupoSku] = field(default_factory=list)
    emitentes: dict[str, ResumoEmitente] = field(default_factory=dict)

    @property
    def skus_bloqueados(self) -> int:
        return sum(1 for g in self.grupos if g.severidade_max is Severidade.BLOQUEIO)

    @property
    def aprovado(self) -> bool:
        return self.por_severidade[Severidade.BLOQUEIO.value] == 0

    @property
    def emitentes_ordenados(self) -> list[ResumoEmitente]:
        return sorted(
            self.emitentes.values(), key=lambda e: (-e.bloqueios, -e.notas, e.cnpj)
        )


@dataclass
class Comparativo:
    """Diferença entre uma varredura anterior e a atual."""

    referencia: str
    bloqueios_antes: int = 0
    bloqueios_agora: int = 0
    novos: list[str] = field(default_factory=list)
    corrigidos: list[str] = field(default_factory=list)
    persistentes: list[str] = field(default_factory=list)

    @property
    def saldo(self) -> int:
        """Quanto o número de SKUs bloqueados andou. Negativo é progresso."""
        return len(self.novos) - len(self.corrigidos)


class RelatorioAnteriorInvalido(Exception):
    """O arquivo passado em --comparar não é um relatório JSON do RTC Check."""


def _skus_bloqueados(resumo: Resumo) -> set[str]:
    return {g.sku for g in resumo.grupos if g.severidade_max is Severidade.BLOQUEIO}


def comparar(resumo: Resumo, anterior: object, referencia: str) -> Comparativo:
    """Compara a varredura atual com um relatório JSON gerado antes."""
    if not isinstance(anterior, dict) or not isinstance(anterior.get("itens"), list):
        raise RelatorioAnteriorInvalido(
            "esperado um relatório gerado com --formato json"
        )

    antes = {
        str(item.get("sku"))
        for item in anterior["itens"]
        if isinstance(item, dict) and item.get("severidade") == Severidade.BLOQUEIO.value
    }
    agora = _skus_bloqueados(resumo)

    bloqueios_antes = anterior.get("bloqueios", 0)
    return Comparativo(
        referencia=referencia,
        bloqueios_antes=bloqueios_antes if isinstance(bloqueios_antes, int) else 0,
        bloqueios_agora=resumo.por_severidade[Severidade.BLOQUEIO.value],
        novos=sorted(agora - antes),
        corrigidos=sorted(antes - agora),
        persistentes=sorted(agora & antes),
    )


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


def _linhas_por_emitente(resumo: Resumo) -> list[str]:
    linhas = ["  Por emitente:", ""]
    for e in resumo.emitentes_ordenados:
        rotulo = f"{e.cnpj}  {e.nome[:36]}".strip()
        linhas.append(f"    {rotulo}")
        linhas.append(
            f"      {e.notas} nota(s), {e.itens} item(ns), "
            f"{e.bloqueios} bloqueio(s), {len(e.skus)} SKU(s) a corrigir"
        )
    linhas.append("")
    return linhas


def _linhas_do_comparativo(comp: Comparativo) -> list[str]:
    seta = "+" if comp.saldo > 0 else ""
    linhas = [
        f"  Comparativo com {comp.referencia}:",
        "",
        f"    Bloqueios ........ {comp.bloqueios_antes} -> {comp.bloqueios_agora}",
        f"    SKUs corrigidos .. {len(comp.corrigidos)}",
        f"    SKUs novos ....... {len(comp.novos)}",
        f"    SKUs pendentes ... {len(comp.persistentes)}",
        f"    Saldo de SKUs .... {seta}{comp.saldo}",
        "",
    ]
    if comp.novos:
        linhas.append("    Apareceram desde a última varredura:")
        linhas.extend(f"      + {sku}" for sku in comp.novos[:10])
        if len(comp.novos) > 10:
            linhas.append(f"      ... e mais {len(comp.novos) - 10}")
        linhas.append("")
    return linhas


def formatar_texto(
    resumo: Resumo,
    hoje: date | None = None,
    *,
    limite: int = 20,
    rodape: str = "",
    por_cnpj: bool = False,
    comparativo: Comparativo | None = None,
) -> str:
    dias = dias_ate_corte(hoje)
    linhas = [
        "",
        "  RTC Check | prontidão para a Reforma Tributária",
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

    if por_cnpj and resumo.emitentes:
        linhas.extend(_linhas_por_emitente(resumo))

    bloqueios = [g for g in resumo.grupos if g.severidade_max is Severidade.BLOQUEIO]
    if bloqueios:
        linhas.append("  SKUs que serão rejeitados a partir de 03/08:")
        linhas.append("")
        for g in bloqueios[:limite]:
            linhas.append(f"    {g.sku}  ({g.ocorrencias}x em {len(g.arquivos)} nota(s))")
            linhas.append(f"      {g.descricao[:64]}")
            for codigo in sorted(g.codigos):
                linhas.append(f"      [{codigo}] {g.mensagens[codigo]}")
            linhas.append("")
        if len(bloqueios) > limite:
            linhas.append(
                f"    ... e mais {len(bloqueios) - limite} SKU(s). "
                "Veja o relatório completo."
            )
            linhas.append("")

    if resumo.aprovado:
        linhas.append("  Nenhum bloqueio encontrado neste acervo.")
        linhas.append("")

    if comparativo is not None:
        linhas.extend(_linhas_do_comparativo(comparativo))

    if rodape:
        linhas.append(rodape.rstrip("\n"))
        linhas.append("")

    return "\n".join(linhas)


def formatar_json(
    resumo: Resumo,
    *,
    por_cnpj: bool = False,
    comparativo: Comparativo | None = None,
) -> str:
    extras: dict[str, object] = {}
    if por_cnpj:
        extras["emitentes"] = [
            {
                "cnpj": e.cnpj,
                "nome": e.nome,
                "notas": e.notas,
                "notas_em_escopo": e.notas_em_escopo,
                "itens": e.itens,
                "bloqueios": e.bloqueios,
                "alertas": e.alertas,
                "skus_a_corrigir": len(e.skus),
            }
            for e in resumo.emitentes_ordenados
        ]
    if comparativo is not None:
        extras["comparativo"] = {
            "referencia": comparativo.referencia,
            "bloqueios_antes": comparativo.bloqueios_antes,
            "bloqueios_agora": comparativo.bloqueios_agora,
            "skus_novos": comparativo.novos,
            "skus_corrigidos": comparativo.corrigidos,
            "skus_pendentes": comparativo.persistentes,
            "saldo": comparativo.saldo,
        }

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
            **extras,
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
h2{font-size:1.15rem;margin:2rem 0 .75rem;font-weight:640}
ul{margin:.25rem 0 1rem 1.1rem;font-size:.875rem}
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


def _bloco_emitentes_html(resumo: Resumo) -> str:
    e = html.escape
    if not resumo.emitentes:
        return ""
    linhas = "".join(
        f"<tr><td><code>{e(em.cnpj)}</code></td><td>{e(em.nome[:60])}</td>"
        f"<td>{em.notas}</td><td>{em.itens}</td><td>{em.bloqueios}</td>"
        f"<td>{len(em.skus)}</td></tr>"
        for em in resumo.emitentes_ordenados
    )
    return (
        '<h2>Por emitente</h2><div class="tw"><table><thead><tr><th>CNPJ</th>'
        "<th>Emitente</th><th>Notas</th><th>Itens</th><th>Bloqueios</th>"
        f"<th>SKUs a corrigir</th></tr></thead><tbody>{linhas}</tbody></table></div>"
    )


def _bloco_comparativo_html(comp: Comparativo) -> str:
    e = html.escape
    novos = "".join(f"<li><code>{e(sku)}</code></li>" for sku in comp.novos[:20])
    lista = f"<p>Apareceram desde a última varredura:</p><ul>{novos}</ul>" if novos else ""
    return (
        f"<h2>Comparativo com {e(comp.referencia)}</h2>"
        f'<div class="cards">'
        f'<div class="card"><div class="n">{comp.bloqueios_antes}</div>'
        f'<div class="l">Bloqueios antes</div></div>'
        f'<div class="card"><div class="n">{comp.bloqueios_agora}</div>'
        f'<div class="l">Bloqueios agora</div></div>'
        f'<div class="card ok"><div class="n">{len(comp.corrigidos)}</div>'
        f'<div class="l">SKUs corrigidos</div></div>'
        f'<div class="card {"bad" if comp.novos else "ok"}"><div class="n">'
        f'{len(comp.novos)}</div><div class="l">SKUs novos</div></div>'
        f"</div>{lista}"
    )


def formatar_html(
    resumo: Resumo,
    hoje: date | None = None,
    *,
    por_cnpj: bool = False,
    comparativo: Comparativo | None = None,
) -> str:
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

    secoes = ""
    if por_cnpj:
        secoes += _bloco_emitentes_html(resumo)
    if comparativo is not None:
        secoes += _bloco_comparativo_html(comparativo)

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RTC Check: relatório de prontidão</title><style>{_CSS}</style></head>
<body><div class="wrap">
<h1>Prontidão para a Reforma Tributária</h1>
<p class="sub">Corte da obrigatoriedade para emitentes CRT=3:
<strong>03/08/2026</strong>, faltam {dias} dias.</p>
<div class="cards">{cards}</div>
{secoes}
<div class="tw"><table>
<thead><tr><th>SKU</th><th>Produto / achados</th><th>NCM</th>
<th>Severidade</th><th>Ocorrências</th><th>Notas</th></tr></thead>
<tbody>{corpo}</tbody></table></div>
<footer>Gerado localmente pelo RTC Check. Nenhum dado saiu desta máquina.<br>
Conferência de estrutura; a fonte de verdade para conformidade de schema é o
validador oficial do SEFAZ.</footer>
</div></body></html>"""
