"""Teste de volume: um acervo real tem dezenas de milhares de notas.

Não é benchmark rigoroso. É uma trava contra regressão acidental de ordem de
grandeza (um O(n²) escondido na agregação, por exemplo).
"""

from __future__ import annotations

import time
import tracemalloc

from rtc_check.cli import analisar

NOTAS = 2000
ITENS_POR_NOTA = 5

# Folgas largas de propósito: o teste roda em CI compartilhada e lenta.
TETO_SEGUNDOS = 30.0
TETO_MB = 300.0


def _gerar_acervo(pasta, quantidade: int) -> None:
    for n in range(quantidade):
        itens = "".join(
            f'<det nItem="{i}"><prod><cProd>SKU-{i:03d}</cProd>'
            f"<cEAN>SEM GTIN</cEAN><xProd>PRODUTO {i}</xProd>"
            f"<NCM>72104900</NCM><CFOP>5102</CFOP></prod></det>"
            for i in range(1, ITENS_POR_NOTA + 1)
        )
        (pasta / f"nf{n:05d}.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
            f'<infNFe Id="NFe{n}" versao="4.00">'
            f"<ide><mod>55</mod><nNF>{n}</nNF></ide>"
            "<emit><CNPJ>1</CNPJ><xNome>T</xNome><CRT>3</CRT></emit>"
            f"{itens}</infNFe></NFe>",
            encoding="utf-8",
        )


def test_acervo_grande_em_tempo_e_memoria_aceitaveis(tmp_path):
    _gerar_acervo(tmp_path, NOTAS)

    tracemalloc.start()
    inicio = time.perf_counter()
    resumo = analisar(tmp_path)
    duracao = time.perf_counter() - inicio
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    pico_mb = pico / 1_048_576

    assert resumo.arquivos_lidos == NOTAS
    assert resumo.total_itens == NOTAS * ITENS_POR_NOTA

    # A agregação precisa colapsar 10.000 achados em 5 SKUs distintos.
    assert resumo.skus_bloqueados == ITENS_POR_NOTA

    assert duracao < TETO_SEGUNDOS, f"levou {duracao:.1f}s (teto {TETO_SEGUNDOS}s)"
    assert pico_mb < TETO_MB, f"pico de {pico_mb:.0f}MB (teto {TETO_MB}MB)"

    print(f"\n  {NOTAS} notas / {resumo.total_itens} itens: "
          f"{duracao:.2f}s, pico {pico_mb:.0f}MB")
