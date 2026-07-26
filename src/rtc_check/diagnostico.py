"""Diagnóstico local, copiável e sem dados fiscais."""

from __future__ import annotations

import platform
from typing import Any

from . import __version__
from .catalogo import COBERTURA, catalogo_json, dias_desde_snapshot
from .limites import MAX_REQUISICAO, MAX_XML, MAX_XMLS, MAX_ZIP_DESCOMPACTADO
from .normativa import NORMATIVA_RTC


def dados() -> dict[str, Any]:
    """Retorna somente versão, limites e capacidades; nunca caminhos ou XMLs."""
    return {
        "produto": "RTC Check",
        "versao": __version__,
        "python": platform.python_version(),
        "sistema": platform.system(),
        "arquitetura": platform.machine(),
        "privacidade": {
            "rede": "somente 127.0.0.1 na interface Desktop",
            "telemetria": False,
            "xmls_incluidos": False,
        },
        "limites": {
            "requisicao_bytes": MAX_REQUISICAO,
            "xml_bytes": MAX_XML,
            "xmls_por_lote": MAX_XMLS,
            "zip_descompactado_bytes": MAX_ZIP_DESCOMPACTADO,
        },
        "normativa": NORMATIVA_RTC.como_json(),
        "idade_snapshot_dias": dias_desde_snapshot(),
        "regras_catalogadas": len(catalogo_json()),
        "cobertura": COBERTURA,
    }
