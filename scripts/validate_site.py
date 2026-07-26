"""Validação estática mínima e sem rede da landing do GitHub Pages."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


class AuditorHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.titulos = 0
        self.imagens_sem_alt: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        dados = dict(attrs)
        if identificador := dados.get("id"):
            if identificador in self.ids:
                raise ValueError(f"id duplicado: {identificador}")
            self.ids.add(identificador)
        if tag == "a" and dados.get("href"):
            self.links.append(dados["href"] or "")
        if tag == "title":
            self.titulos += 1
        if tag == "img" and "alt" not in dados:
            self.imagens_sem_alt.append(dados.get("src") or "(sem src)")


def validar(site: Path) -> list[str]:
    erros: list[str] = []
    for pagina in sorted(site.glob("*.html")):
        auditor = AuditorHTML()
        try:
            auditor.feed(pagina.read_text(encoding="utf-8"))
        except (UnicodeError, ValueError) as erro:
            erros.append(f"{pagina.name}: {erro}")
            continue
        if auditor.titulos != 1:
            erros.append(f"{pagina.name}: esperado um title, veio {auditor.titulos}")
        for imagem in auditor.imagens_sem_alt:
            erros.append(f"{pagina.name}: imagem sem alt: {imagem}")
        for href in auditor.links:
            parsed = urlparse(href)
            if parsed.scheme or href.startswith(("#", "mailto:", "tel:")):
                continue
            destino = site / parsed.path
            if parsed.path and not destino.exists():
                erros.append(f"{pagina.name}: link local inexistente: {href}")
    return erros


def main() -> int:
    raiz = Path(__file__).resolve().parents[1]
    erros = validar(raiz / "site")
    if erros:
        print("\n".join(erros), file=sys.stderr)
        return 1
    print("Landing validada: HTML, IDs, imagens e links locais.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
