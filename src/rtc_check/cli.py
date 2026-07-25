"""Interface de linha de comando do RTC Check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .parser import XmlInvalido, ler_nota, varrer_pasta
from .report import Resumo, agregar, formatar_csv, formatar_html, formatar_json, formatar_texto
from .rules import Severidade, avaliar_nota

FORMATOS = ("texto", "json", "csv", "html")


def analisar(pasta: Path, recursivo: bool = True) -> Resumo:
    resumo = Resumo()
    achados = []

    for caminho in varrer_pasta(pasta, recursivo):
        try:
            arquivo_relativo = caminho.relative_to(pasta).as_posix()
        except ValueError:
            arquivo_relativo = caminho.name
        resumo.arquivos_lidos += 1
        try:
            nota = ler_nota(caminho)
        except XmlInvalido as erro:
            resumo.arquivos_invalidos.append((arquivo_relativo, str(erro)))
            continue

        resumo.registrar_emitente(nota.emitente_cnpj, nota.emitente_nome)
        if nota.em_escopo_agosto:
            resumo.notas_em_escopo += 1
        resumo.total_itens += len(nota.itens)

        for achado in avaliar_nota(nota, arquivo_relativo):
            achados.append(achado)
            resumo.por_severidade[achado.severidade.value] += 1

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
    )
    p.add_argument("pasta", type=Path, help="pasta com os arquivos .xml")
    p.add_argument("-f", "--formato", choices=FORMATOS, default="texto")
    p.add_argument("-o", "--saida", type=Path, help="grava em arquivo em vez do stdout")
    p.add_argument("--sem-recursao", action="store_true", help="não entra em subpastas")
    p.add_argument(
        "--falhar-em-bloqueio",
        action="store_true",
        help="sai com código 1 se houver bloqueios (útil em CI)",
    )
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    if not args.pasta.exists():
        print(f"erro: pasta não encontrada: {args.pasta}", file=sys.stderr)
        return 2
    if not args.pasta.is_dir():
        print(f"erro: não é uma pasta: {args.pasta}", file=sys.stderr)
        return 2

    resumo = analisar(args.pasta, recursivo=not args.sem_recursao)

    if resumo.tem_multiplos_emitentes:
        documentos = ", ".join(resumo.documentos_emitentes)
        print(
            "erro: o plano Comunidade aceita um emitente por execução. "
            f"Foram encontrados: {documentos}. Separe os XMLs por emitente antes de rodar.",
            file=sys.stderr,
        )
        return 2

    saida = {
        "texto": formatar_texto,
        "json": formatar_json,
        "csv": formatar_csv,
        "html": formatar_html,
    }[args.formato](resumo)

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
