"""Interface de linha de comando do RTC Check."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from . import __version__
from . import edicao as ed
from .parser import XmlInvalido, ler_nota, varrer_pasta
from .report import (
    Comparativo,
    RelatorioAnteriorInvalido,
    Resumo,
    agregar,
    comparar,
    formatar_csv,
    formatar_html,
    formatar_json,
    formatar_texto,
)
from .rules import Severidade, avaliar_nota

FORMATOS = ("texto", "json", "csv", "html")

RECURSO_DO_FORMATO = {
    "json": ed.Recurso.FORMATO_JSON,
    "csv": ed.Recurso.FORMATO_CSV,
    "html": ed.Recurso.FORMATO_HTML,
}

# Códigos de saída: 0 tudo certo, 1 há bloqueio (com --falhar-em-bloqueio),
# 2 erro de uso, 3 recurso fora do plano em uso.
SAIDA_FORA_DO_PLANO = 3


class AnaliseCancelada(Exception):
    """Interrompe uma análise local solicitada pela interface visual."""

RODAPE_COMUNIDADE = """
  Plano Comunidade. Estão liberados neste relatório: a varredura completa,
  a contagem de bloqueios e os primeiros SKUs da fila.

  Fora do plano: lista completa de SKUs, exportação em JSON/CSV/HTML,
  gravação em arquivo, portão de CI, regras de NCM e GTIN, quebra por CNPJ
  e comparativo entre execuções.

  Teste tudo por 14 dias, sem cadastro:  rtc-check --iniciar-teste
"""


def analisar(
    pasta: Path,
    recursivo: bool = True,
    regras: frozenset[str] | None = None,
    progresso: Callable[[int, int], None] | None = None,
    cancelar: Callable[[], bool] | None = None,
) -> Resumo:
    resumo = Resumo()
    achados = []
    caminhos = list(varrer_pasta(pasta, recursivo))
    total = len(caminhos)

    for indice, caminho in enumerate(caminhos, start=1):
        if cancelar and cancelar():
            raise AnaliseCancelada()
        try:
            arquivo_relativo = caminho.relative_to(pasta).as_posix()
        except ValueError:
            arquivo_relativo = caminho.name
        resumo.arquivos_lidos += 1
        try:
            nota = ler_nota(caminho)
        except XmlInvalido as erro:
            resumo.arquivos_invalidos.append((arquivo_relativo, str(erro)))
            if progresso:
                progresso(indice, total)
            continue

        emitente = resumo.registrar_emitente(nota.emitente_cnpj, nota.emitente_nome)
        if nota.em_escopo_agosto:
            resumo.notas_em_escopo += 1
        resumo.total_itens += len(nota.itens)

        emitente.notas += 1
        emitente.notas_em_escopo += int(nota.em_escopo_agosto)
        emitente.itens += len(nota.itens)

        for achado in avaliar_nota(
            nota, regras=regras, arquivo=arquivo_relativo
        ):
            achados.append(achado)
            resumo.por_severidade[achado.severidade.value] += 1
            if achado.severidade is Severidade.BLOQUEIO:
                emitente.bloqueios += 1
                emitente.skus.add(achado.sku)
            elif achado.severidade is Severidade.ALERTA:
                emitente.alertas += 1
        if progresso:
            progresso(indice, total)

    resumo.grupos = agregar(achados)
    return resumo


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rtc-check",
        description=(
            "Varre um acervo de XMLs de NF-e e aponta riscos de rejeição ligados "
            "à Reforma Tributária a partir de 03/08/2026. "
            "Roda 100%% local: nenhum arquivo sai da máquina."
        ),
        epilog=(
            "A varredura e o relatório de texto são gratuitos para sempre. "
            "Exportação, portão de CI, regras de cadastro, quebra por CNPJ e "
            "comparativo fazem parte dos planos pagos, com 14 dias de teste "
            f"grátis: rtc-check --iniciar-teste ({ed.URL_PLANOS})"
        ),
    )
    p.add_argument("pasta", type=Path, nargs="?", help="pasta com os arquivos .xml")
    p.add_argument("-f", "--formato", choices=FORMATOS, default="texto")
    p.add_argument("-o", "--saida", type=Path, help="grava em arquivo em vez do stdout")
    p.add_argument("--sem-recursao", action="store_true", help="não entra em subpastas")
    p.add_argument(
        "--app",
        action="store_true",
        help="abre a interface visual local no navegador",
    )
    p.add_argument(
        "--sem-navegador",
        action="store_true",
        help="com --app, inicia o servidor sem abrir o navegador",
    )
    p.add_argument(
        "--porta",
        type=int,
        default=0,
        help="porta local da interface; 0 escolhe uma porta livre",
    )
    p.add_argument(
        "--falhar-em-bloqueio",
        action="store_true",
        help="sai com código 1 se houver bloqueios (útil em CI)",
    )
    p.add_argument(
        "--por-cnpj",
        action="store_true",
        help="quebra o resultado por emitente",
    )
    p.add_argument(
        "--comparar",
        type=Path,
        metavar="RELATORIO.json",
        help="compara com um relatório JSON gerado antes",
    )

    planos = p.add_argument_group("plano e licença")
    planos.add_argument("--licenca", metavar="CHAVE", help="ativa uma chave de licença")
    planos.add_argument(
        "--iniciar-teste",
        action="store_true",
        help=f"libera {ed.DIAS_DE_TESTE} dias de teste grátis nesta máquina",
    )
    planos.add_argument(
        "--plano",
        action="store_true",
        help="mostra o plano em uso e o que está liberado",
    )

    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _texto_do_plano(edicao: ed.Edicao, hoje: date | None = None) -> str:
    linhas = ["", f"  RTC Check {__version__} | plano {edicao.nome}"]
    if edicao.titular:
        linhas.append(f"  Licenciado para {edicao.titular}")
    if edicao.expira_em is not None:
        dias = edicao.dias_restantes(hoje)
        linhas.append(f"  Válido até {edicao.expira_em:%d/%m/%Y} ({dias} dia(s))")
    linhas.append("")

    linhas.append("  Liberado:")
    linhas.extend(
        f"    [x] {ed.DESCRICAO_DO_RECURSO[r]}" for r in edicao.recursos_liberados
    )
    bloqueados = edicao.recursos_bloqueados
    if bloqueados:
        linhas.append("")
        linhas.append("  Fora do plano:")
        linhas.extend(f"    [ ] {ed.DESCRICAO_DO_RECURSO[r]}" for r in bloqueados)
        linhas.append("")
        linhas.append("  Teste grátis:  rtc-check --iniciar-teste")
        linhas.append(f"  Planos:        {ed.URL_PLANOS}")
    linhas.append("")
    return "\n".join(linhas)


def _exigir(edicao: ed.Edicao, recurso: ed.Recurso) -> str:
    """Devolve a mensagem de bloqueio, ou string vazia se o plano cobre."""
    if edicao.tem(recurso):
        return ""
    return f"erro: {ed.como_liberar(recurso)}"


def _recursos_pedidos(args: argparse.Namespace) -> list[ed.Recurso]:
    pedidos = []
    formato = RECURSO_DO_FORMATO.get(args.formato)
    if formato is not None:
        pedidos.append(formato)
    if args.saida:
        pedidos.append(ed.Recurso.SAIDA_ARQUIVO)
    if args.falhar_em_bloqueio:
        pedidos.append(ed.Recurso.PORTAO_CI)
    if args.por_cnpj:
        pedidos.append(ed.Recurso.POR_CNPJ)
    if args.comparar:
        pedidos.append(ed.Recurso.COMPARATIVO)
    return pedidos


def _ativar_licenca(chave: str) -> int:
    try:
        edicao = ed.salvar_licenca(chave)
    except ed.LicencaInvalida as erro:
        print(f"erro: chave recusada: {erro}", file=sys.stderr)
        return 2
    except OSError as erro:
        print(f"erro: não consegui gravar a licença: {erro}", file=sys.stderr)
        return 2
    print(f"licença do plano {edicao.nome} ativada.")
    print(_texto_do_plano(edicao))
    return 0


def _iniciar_teste() -> int:
    try:
        edicao = ed.iniciar_teste()
    except ed.TesteIndisponivel as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    except OSError as erro:
        print(f"erro: não consegui registrar o teste: {erro}", file=sys.stderr)
        return 2
    print(f"teste grátis liberado até {edicao.expira_em:%d/%m/%Y}.")
    print(_texto_do_plano(edicao))
    return 0


def _carregar_comparativo(caminho: Path, resumo: Resumo) -> Comparativo:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return comparar(resumo, dados, caminho.name)


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    if args.app:
        if not 0 <= args.porta <= 65535:
            print("erro: --porta precisa estar entre 0 e 65535", file=sys.stderr)
            return 2
        from .webapp import executar

        return executar(porta=args.porta, abrir_navegador=not args.sem_navegador)

    if args.licenca and not args.pasta:
        return _ativar_licenca(args.licenca)
    if args.iniciar_teste:
        return _iniciar_teste()

    edicao = ed.resolver(args.licenca)
    if edicao.aviso:
        print(f"aviso: {edicao.aviso}", file=sys.stderr)

    if args.plano:
        print(_texto_do_plano(edicao))
        return 0

    if args.pasta is None:
        print("erro: informe a pasta com os XMLs (rtc-check --help)", file=sys.stderr)
        return 2
    if not args.pasta.exists():
        print(f"erro: pasta não encontrada: {args.pasta}", file=sys.stderr)
        return 2
    if not args.pasta.is_dir():
        print(f"erro: não é uma pasta: {args.pasta}", file=sys.stderr)
        return 2

    for recurso in _recursos_pedidos(args):
        impedimento = _exigir(edicao, recurso)
        if impedimento:
            print(impedimento, file=sys.stderr)
            return SAIDA_FORA_DO_PLANO

    resumo = analisar(
        args.pasta, recursivo=not args.sem_recursao, regras=edicao.regras_ativas
    )

    comparativo = None
    if args.comparar:
        try:
            comparativo = _carregar_comparativo(args.comparar, resumo)
        except (OSError, json.JSONDecodeError, RelatorioAnteriorInvalido) as erro:
            print(f"erro: não consegui ler {args.comparar}: {erro}", file=sys.stderr)
            return 2

    if args.formato == "texto":
        saida = formatar_texto(
            resumo,
            limite=edicao.limite_de_skus,
            rodape="" if edicao.pago else RODAPE_COMUNIDADE,
            por_cnpj=args.por_cnpj,
            comparativo=comparativo,
        )
    elif args.formato == "json":
        saida = formatar_json(resumo, por_cnpj=args.por_cnpj, comparativo=comparativo)
    elif args.formato == "csv":
        saida = formatar_csv(resumo)
    else:
        saida = formatar_html(resumo, por_cnpj=args.por_cnpj, comparativo=comparativo)

    if args.saida:
        args.saida.write_text(saida, encoding="utf-8")
        print(f"relatório gravado em {args.saida}", file=sys.stderr)
    else:
        print(saida)

    if args.falhar_em_bloqueio and resumo.por_severidade[Severidade.BLOQUEIO.value]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
