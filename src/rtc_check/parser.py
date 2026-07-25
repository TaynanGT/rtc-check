"""Leitura de XML de NF-e (modelo 55) e NFC-e (modelo 65).

Só toca em campos do layout 4.00, estáveis e públicos desde 2018. A detecção
dos grupos da Reforma Tributária é por *presença*, não por validação de schema
O XSD oficial é a fonte de verdade para conformidade estrutural.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

# Grupo criado pela NT 2025.002 (RTC) para detalhar IBS/CBS por item.
TAG_GRUPO_RTC = "gIBSCBS"
TAG_CLASS_TRIB = "cClassTrib"

CRT_REGIME_NORMAL = "3"


class XmlInvalido(Exception):
    """XML ilegível ou que não é uma NF-e."""


@dataclass
class Item:
    numero: str
    codigo: str
    descricao: str
    ncm: str
    cfop: str
    cean: str | None
    tem_grupo_rtc: bool
    tem_class_trib: bool


@dataclass
class NotaFiscal:
    arquivo: Path
    chave: str
    modelo: str
    numero: str
    emissao: str
    emitente_cnpj: str
    emitente_nome: str
    crt: str
    itens: list[Item] = field(default_factory=list)

    @property
    def em_escopo_agosto(self) -> bool:
        """Emitentes CRT=3 (Regime Normal) passam a ser rejeitados em 03/08/2026."""
        return self.crt == CRT_REGIME_NORMAL


def _texto(elemento: ElementTree.Element, caminho: str) -> str:
    achado = elemento.find(caminho, NS)
    return achado.text.strip() if achado is not None and achado.text else ""


def _tem_descendente(elemento: ElementTree.Element, nome_tag: str) -> bool:
    alvo = f"{{{NS['nfe']}}}{nome_tag}"
    return any(filho.tag == alvo for filho in elemento.iter())


def ler_nota(caminho: Path) -> NotaFiscal:
    """Lê um arquivo XML e devolve a nota. Levanta ``XmlInvalido`` se não der."""
    try:
        arvore = ElementTree.parse(caminho)
    except ElementTree.ParseError as erro:
        raise XmlInvalido(f"XML malformado: {erro}") from erro

    raiz = arvore.getroot()
    inf = raiz.find(".//nfe:infNFe", NS)
    if inf is None:
        raise XmlInvalido("não contém o elemento infNFe (não é uma NF-e)")

    chave = (inf.get("Id") or "").removeprefix("NFe")
    emit = inf.find("nfe:emit", NS)
    ide = inf.find("nfe:ide", NS)
    if emit is None or ide is None:
        raise XmlInvalido("faltam os grupos obrigatórios emit/ide")

    nota = NotaFiscal(
        arquivo=caminho,
        chave=chave,
        modelo=_texto(ide, "nfe:mod"),
        numero=_texto(ide, "nfe:nNF"),
        emissao=_texto(ide, "nfe:dhEmi") or _texto(ide, "nfe:dEmi"),
        emitente_cnpj=_texto(emit, "nfe:CNPJ") or _texto(emit, "nfe:CPF"),
        emitente_nome=_texto(emit, "nfe:xNome"),
        crt=_texto(emit, "nfe:CRT"),
    )

    for det in inf.findall("nfe:det", NS):
        prod = det.find("nfe:prod", NS)
        if prod is None:
            continue
        nota.itens.append(
            Item(
                numero=det.get("nItem", "?"),
                codigo=_texto(prod, "nfe:cProd"),
                descricao=_texto(prod, "nfe:xProd"),
                ncm=_texto(prod, "nfe:NCM"),
                cfop=_texto(prod, "nfe:CFOP"),
                cean=_texto(prod, "nfe:cEAN") or None,
                tem_grupo_rtc=_tem_descendente(det, TAG_GRUPO_RTC),
                tem_class_trib=_tem_descendente(det, TAG_CLASS_TRIB),
            )
        )

    return nota


def varrer_pasta(pasta: Path, recursivo: bool = True) -> list[Path]:
    """Lista os XMLs de uma pasta, ordenados para tornar a saída determinística."""
    padrao = "**/*.xml" if recursivo else "*.xml"
    return sorted(p for p in pasta.glob(padrao) if p.is_file())
