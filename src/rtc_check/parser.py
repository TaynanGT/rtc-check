"""Leitura de XML de NF-e (modelo 55) e NFC-e (modelo 65).

Só toca em campos do layout 4.00, estáveis e públicos desde 2018. A detecção
dos grupos da Reforma Tributária é por *presença*, não por validação de schema
O XSD oficial é a fonte de verdade para conformidade estrutural.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

CRT_REGIME_NORMAL = "3"

# O literal "SEM GTIN" para produto sem codigo de barras so existe a partir do
# layout 4.00 (NT 2016.002). Em 2.00 e 3.xx, cEAN vazio era a forma correta de
# dizer a mesma coisa, entao cobrar o literal ali e falso positivo.
LAYOUT_COM_SEM_GTIN = "4.00"


class _ElementoXml(Protocol):
    text: str | None

    def find(
        self,
        path: str,
        namespaces: dict[str, str] | None = None,
    ) -> _ElementoXml | None: ...


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
    cprod_anp: str
    tem_ibscbs: bool
    cst_ibscbs: str
    cclass_trib: str
    tem_gibscbs: bool

    @property
    def tem_grupo_rtc(self) -> bool:
        """Alias legado: antes da v0.2.0, o grupo RTC significava gIBSCBS."""
        return self.tem_gibscbs

    @property
    def tem_class_trib(self) -> bool:
        return bool(self.cclass_trib)


@dataclass
class NotaFiscal:
    arquivo: Path
    chave: str
    versao: str
    modelo: str
    numero: str
    emissao: str
    emitente_cnpj: str
    emitente_nome: str
    crt: str
    finalidade: str
    tipo_nota_debito: str
    chaves_referenciadas: tuple[str, ...]
    itens: list[Item] = field(default_factory=list)

    @property
    def em_escopo_agosto(self) -> bool:
        """Emitentes CRT=3 (Regime Normal) passam a ser rejeitados em 03/08/2026."""
        return self.crt == CRT_REGIME_NORMAL

    @property
    def exige_literal_sem_gtin(self) -> bool:
        """Só o layout 4.00 em diante conhece o literal ``SEM GTIN``."""
        return self.versao >= LAYOUT_COM_SEM_GTIN

    @property
    def referencia_nfe_anterior_2026(self) -> bool:
        """Exceção 1 da UB12-10 para devolução/complementar."""
        if self.finalidade not in {"2", "4"}:
            return False
        for chave in self.chaves_referenciadas:
            if len(chave) == 44 and chave.isdigit():
                ano = 2000 + int(chave[2:4])
                if ano < 2026:
                    return True
        return False


def _texto(elemento: _ElementoXml, caminho: str) -> str:
    achado = elemento.find(caminho, NS)
    return achado.text.strip() if achado is not None and achado.text else ""


def ler_nota(caminho: Path) -> NotaFiscal:
    """Lê um arquivo XML e devolve a nota. Levanta ``XmlInvalido`` se não der."""
    try:
        arvore = ElementTree.parse(caminho)
    except DefusedXmlException as erro:
        raise XmlInvalido(f"XML inseguro: {erro}") from erro
    except ElementTree.ParseError as erro:
        raise XmlInvalido(f"XML malformado: {erro}") from erro
    except OSError as erro:
        motivo = erro.strerror or str(erro)
        raise XmlInvalido(f"não foi possível ler o arquivo: {motivo}") from erro

    raiz = arvore.getroot()
    if raiz is None:
        raise XmlInvalido("XML vazio")
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
        versao=inf.get("versao", ""),
        modelo=_texto(ide, "nfe:mod"),
        numero=_texto(ide, "nfe:nNF"),
        emissao=_texto(ide, "nfe:dhEmi") or _texto(ide, "nfe:dEmi"),
        emitente_cnpj=_texto(emit, "nfe:CNPJ") or _texto(emit, "nfe:CPF"),
        emitente_nome=_texto(emit, "nfe:xNome"),
        crt=_texto(emit, "nfe:CRT"),
        finalidade=_texto(ide, "nfe:finNFe"),
        tipo_nota_debito=_texto(ide, "nfe:tpNFDebito"),
        chaves_referenciadas=tuple(
            texto
            for ref in ide.findall("nfe:NFref/nfe:refNFe", NS)
            if (texto := (ref.text or "").strip())
        ),
    )

    for det in inf.findall("nfe:det", NS):
        prod = det.find("nfe:prod", NS)
        if prod is None:
            continue
        ibscbs = det.find("nfe:imposto/nfe:IBSCBS", NS)
        nota.itens.append(
            Item(
                numero=det.get("nItem", "?"),
                codigo=_texto(prod, "nfe:cProd"),
                descricao=_texto(prod, "nfe:xProd"),
                ncm=_texto(prod, "nfe:NCM"),
                cfop=_texto(prod, "nfe:CFOP"),
                cean=_texto(prod, "nfe:cEAN") or None,
                cprod_anp=_texto(prod, "nfe:comb/nfe:cProdANP"),
                tem_ibscbs=ibscbs is not None,
                cst_ibscbs=_texto(ibscbs, "nfe:CST") if ibscbs is not None else "",
                cclass_trib=(
                    _texto(ibscbs, "nfe:cClassTrib") if ibscbs is not None else ""
                ),
                tem_gibscbs=(
                    ibscbs.find("nfe:gIBSCBS", NS) is not None
                    if ibscbs is not None
                    else False
                ),
            )
        )

    return nota


def varrer_pasta(pasta: Path, recursivo: bool = True) -> list[Path]:
    """Lista os XMLs de uma pasta, ordenados para tornar a saída determinística."""
    padrao = "**/*.xml" if recursivo else "*.xml"
    return sorted(p for p in pasta.glob(padrao) if p.is_file())
