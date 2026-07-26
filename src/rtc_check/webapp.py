"""Aplicação visual local do RTC Check.

O navegador é somente a interface. O servidor escuta exclusivamente em
127.0.0.1, usa um token aleatório por sessão e apaga os uploads ao terminar a
análise. Nenhum XML é transmitido para a Internet.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
import threading
import webbrowser
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import __version__
from . import edicao as ed
from .checkout import PRECO_ANUAL_BR, PRECO_MENSAL_BR
from .checkout import carregar as carregar_checkout
from .cli import AnaliseCancelada, analisar
from .normativa import NORMATIVA_RTC
from .report import Resumo, formatar_csv, formatar_html, formatar_json
from .rules import Severidade

MAX_REQUISICAO = 64 * 1024 * 1024
MAX_XML = 25 * 1024 * 1024
MAX_XMLS = 20_000
MAX_ZIP_DESCOMPACTADO = 500 * 1024 * 1024
COR_PADRAO = "#0f766e"
ARQUIVOS_WEB = Path(__file__).with_name("web")


class EntradaInvalida(ValueError):
    """Upload ou parâmetro que não pode ser processado com segurança."""


@dataclass(frozen=True)
class RelatorioEmMemoria:
    resumo: Resumo
    edicao: ed.Edicao
    demo: bool
    criado_em: datetime = field(default_factory=datetime.now)


@dataclass
class AnaliseEmAndamento:
    """Estado mínimo de uma análise assíncrona, sempre mantido apenas em memória."""

    identificador: str
    cancelar: threading.Event = field(default_factory=threading.Event, repr=False)
    etapa: str = "preparando"
    mensagem: str = "Preparando o lote localmente."
    processados: int = 0
    total: int = 0
    resultado_id: str | None = None
    erro: str | None = None
    concluida: bool = False
    criado_em: datetime = field(default_factory=datetime.now)


@dataclass
class EstadoApp:
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    relatorios: dict[str, RelatorioEmMemoria] = field(default_factory=dict)
    analises: dict[str, AnaliseEmAndamento] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def guardar(self, resumo: Resumo, edicao_atual: ed.Edicao, *, demo: bool) -> str:
        identificador = secrets.token_urlsafe(18)
        with self._lock:
            self.relatorios[identificador] = RelatorioEmMemoria(
                resumo=resumo,
                edicao=edicao_atual,
                demo=demo,
            )
            if len(self.relatorios) > 20:
                mais_antigo = min(
                    self.relatorios,
                    key=lambda chave: self.relatorios[chave].criado_em,
                )
                self.relatorios.pop(mais_antigo, None)
        return identificador

    def iniciar_analise(self) -> AnaliseEmAndamento:
        analise = AnaliseEmAndamento(identificador=secrets.token_urlsafe(18))
        with self._lock:
            self.analises[analise.identificador] = analise
            if len(self.analises) > 20:
                mais_antiga = min(self.analises, key=lambda chave: self.analises[chave].criado_em)
                self.analises.pop(mais_antiga, None)
        return analise

    def obter_analise(self, identificador: str) -> AnaliseEmAndamento | None:
        with self._lock:
            return self.analises.get(identificador)

    def cancelar_analise(self, identificador: str) -> AnaliseEmAndamento | None:
        analise = self.obter_analise(identificador)
        if analise and not analise.concluida:
            analise.cancelar.set()
            analise.mensagem = "Cancelamento solicitado; descartando o lote local."
        return analise

    def cancelar_todas(self) -> None:
        with self._lock:
            for analise in self.analises.values():
                analise.cancelar.set()


def _serializar_andamento(analise: AnaliseEmAndamento, estado: EstadoApp) -> dict[str, Any]:
    dados: dict[str, Any] = {
        "id": analise.identificador,
        "etapa": analise.etapa,
        "mensagem": analise.mensagem,
        "processados": analise.processados,
        "total": analise.total,
        "concluida": analise.concluida,
        "cancelamento_solicitado": analise.cancelar.is_set(),
    }
    if analise.erro:
        dados["erro"] = analise.erro
    if analise.resultado_id:
        salvo = estado.relatorios.get(analise.resultado_id)
        if salvo:
            dados["resultado"] = _serializar_resultado(
                salvo.resumo, salvo.edicao, analise.resultado_id, demo=salvo.demo
            )
    return dados


def _pontuacao(resumo: Resumo) -> int:
    """Indicador operacional, não uma nota fiscal ou jurídica."""
    if resumo.total_itens == 0:
        return 100 if not resumo.arquivos_invalidos else 0
    bloqueios = resumo.skus_bloqueados
    alertas = sum(
        1 for grupo in resumo.grupos if grupo.severidade_max is Severidade.ALERTA
    )
    penalidade = min(1.0, (bloqueios + alertas * 0.25) / resumo.total_itens)
    return max(0, round(100 * (1 - penalidade)))


def _acao_por_codigo(codigo: str) -> str:
    acoes = {
        "RTC001": "Parametrize o ERP para gerar o grupo IBSCBS nos itens em escopo.",
        "RTC002": "Preencha cClassTrib conforme o tratamento tributário da operação.",
        "RTC003": "Substitua o CST IBS/CBS por um código vigente na tabela oficial.",
        "RTC004": "Inclua o grupo gIBSCBS exigido pelo CST informado.",
        "RTC005": "Remova gIBSCBS ou ajuste o CST incompatível.",
        "RTC006": "Revise o cClassTrib na tabela vigente para NF-e modelo 55.",
        "NCM001": "Corrija o NCM para oito dígitos antes de reenviar ao cadastro.",
        "GTIN001": "Corrija o GTIN ou use SEM GTIN quando o layout permitir.",
    }
    return acoes.get(codigo, "Revise o cadastro e confirme a correção no validador oficial.")


def _ordenar_codigos(codigos: set[str]) -> list[str]:
    prioridade = {
        "RTC001": 0,
        "RTC002": 1,
        "RTC003": 2,
        "RTC004": 3,
        "RTC005": 4,
        "RTC006": 5,
        "NCM001": 6,
        "GTIN001": 7,
    }
    return sorted(codigos, key=lambda codigo: (prioridade.get(codigo, 99), codigo))


def _serializar_resultado(
    resumo: Resumo,
    edicao_atual: ed.Edicao,
    identificador: str,
    *,
    demo: bool,
) -> dict[str, Any]:
    limite = len(resumo.grupos) if demo else edicao_atual.limite_de_skus
    grupos = resumo.grupos[:limite]
    pode_exportar = demo or edicao_atual.tem(ed.Recurso.FORMATO_HTML)
    return {
        "id": identificador,
        "demo": demo,
        "pontuacao": _pontuacao(resumo),
        "aprovado": resumo.aprovado,
        "arquivos_lidos": resumo.arquivos_lidos,
        "arquivos_invalidos": [
            {"arquivo": nome, "motivo": motivo}
            for nome, motivo in resumo.arquivos_invalidos[:20]
        ],
        "total_arquivos_invalidos": len(resumo.arquivos_invalidos),
        "notas_em_escopo": resumo.notas_em_escopo,
        "total_itens": resumo.total_itens,
        "bloqueios": resumo.por_severidade[Severidade.BLOQUEIO.value],
        "alertas": resumo.por_severidade[Severidade.ALERTA.value],
        "skus_a_corrigir": resumo.skus_bloqueados,
        "total_grupos": len(resumo.grupos),
        "grupos_ocultos": max(0, len(resumo.grupos) - len(grupos)),
        "pode_exportar": pode_exportar,
        "itens": [
            {
                "sku": grupo.sku,
                "descricao": grupo.descricao,
                "ncm": grupo.ncm,
                "emitente": grupo.emitente_documento,
                "severidade": grupo.severidade_max.value,
                "codigos": _ordenar_codigos(grupo.codigos),
                "mensagens": [
                    {
                        "codigo": codigo,
                        "mensagem": grupo.mensagens[codigo],
                        "acao": _acao_por_codigo(codigo),
                    }
                    for codigo in _ordenar_codigos(grupo.codigos)
                ],
                "ocorrencias": grupo.ocorrencias,
                "notas_afetadas": len(grupo.arquivos),
            }
            for grupo in grupos
        ],
        "emitentes": [
            {
                "cnpj": emitente.cnpj,
                "nome": emitente.nome,
                "notas": emitente.notas,
                "itens": emitente.itens,
                "bloqueios": emitente.bloqueios,
                "skus": len(emitente.skus),
            }
            for emitente in resumo.emitentes_ordenados
        ],
    }


def _status() -> dict[str, Any]:
    atual = ed.resolver()
    checkout = carregar_checkout()
    return {
        "versao": __version__,
        "plano": atual.nome,
        "pago": atual.pago,
        "em_teste": atual.plano is ed.Plano.TESTE,
        "licenciado": atual.plano in {ed.Plano.ESCRITORIO, ed.Plano.PLATAFORMA},
        "dias_restantes": atual.dias_restantes(),
        "aviso": atual.aviso,
        "checkout": {
            "provedor": checkout.provedor,
            "url": checkout.url,
            "automatico": checkout.automatico,
            "preco_mensal": PRECO_MENSAL_BR,
            "preco_anual": PRECO_ANUAL_BR,
        },
        "normativa": NORMATIVA_RTC.como_json(),
        "privacidade": {
            "servidor": "127.0.0.1",
            "telemetria": False,
            "retencao_upload": "apagado ao terminar a análise",
        },
    }


def _nome_seguro(nome: str, indice: int) -> str:
    base = Path(nome.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .")
    return f"{indice:05d}-{base or 'nota.xml'}"


def _salvar_xmls_do_upload(partes: list[tuple[str, bytes]], destino: Path) -> int:
    gravados = 0
    total_descompactado = 0
    for nome, conteudo in partes:
        sufixo = Path(nome).suffix.lower()
        if sufixo == ".xml":
            if len(conteudo) > MAX_XML:
                raise EntradaInvalida(f"{nome}: XML maior que 25 MB")
            gravados += 1
            if gravados > MAX_XMLS:
                raise EntradaInvalida("o lote ultrapassa 20.000 XMLs")
            (destino / _nome_seguro(nome, gravados)).write_bytes(conteudo)
            continue
        if sufixo != ".zip":
            continue
        try:
            arquivo_zip = zipfile.ZipFile(BytesIO(conteudo))
        except zipfile.BadZipFile as erro:
            raise EntradaInvalida(f"{nome}: ZIP inválido") from erro
        with arquivo_zip:
            for membro in arquivo_zip.infolist():
                if membro.is_dir() or Path(membro.filename).suffix.lower() != ".xml":
                    continue
                if membro.file_size > MAX_XML:
                    raise EntradaInvalida(f"{membro.filename}: XML maior que 25 MB")
                if total_descompactado + membro.file_size > MAX_ZIP_DESCOMPACTADO:
                    raise EntradaInvalida("ZIP ultrapassa 500 MB descompactados")
                gravados += 1
                if gravados > MAX_XMLS:
                    raise EntradaInvalida("o lote ultrapassa 20.000 XMLs")
                try:
                    with arquivo_zip.open(membro) as origem:
                        dados = origem.read(MAX_XML + 1)
                except (RuntimeError, NotImplementedError, zipfile.BadZipFile) as erro:
                    raise EntradaInvalida(
                        f"{membro.filename}: XML do ZIP não pôde ser lido"
                    ) from erro
                if len(dados) > MAX_XML:
                    raise EntradaInvalida(f"{membro.filename}: XML maior que 25 MB")
                total_descompactado += len(dados)
                if total_descompactado > MAX_ZIP_DESCOMPACTADO:
                    raise EntradaInvalida("ZIP ultrapassa 500 MB descompactados")
                (destino / _nome_seguro(membro.filename, gravados)).write_bytes(dados)
    if not gravados:
        raise EntradaInvalida("selecione pelo menos um arquivo XML ou ZIP com XMLs")
    return gravados


def _partes_multipart(content_type: str, corpo: bytes) -> list[tuple[str, bytes]]:
    cabecalho = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    )
    mensagem = BytesParser(policy=default).parsebytes(cabecalho + corpo)
    if not mensagem.is_multipart():
        raise EntradaInvalida("envio multipart inválido")
    partes: list[tuple[str, bytes]] = []
    for parte in mensagem.iter_parts():
        nome = parte.get_filename()
        if not nome:
            continue
        conteudo = parte.get_payload(decode=True)
        if isinstance(conteudo, bytes):
            partes.append((nome, conteudo))
    return partes


def _criar_demo(destino: Path) -> None:
    xml_risco = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe>
<infNFe Id="NFe35260712345678000199550010000000011000000017" versao="4.00">
<ide><mod>55</mod><nNF>101</nNF><dhEmi>2026-07-20T09:15:00-03:00</dhEmi><tpNF>1</tpNF></ide>
<emit><CNPJ>12345678000199</CNPJ><xNome>INDÚSTRIA DEMONSTRAÇÃO LTDA</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>SKU-1001</cProd><cEAN>7891234567895</cEAN>
<xProd>CHAPA DE AÇO GALVANIZADO</xProd><NCM>72104900</NCM></prod>
<imposto><ICMS><ICMS00><CST>00</CST></ICMS00></ICMS></imposto></det>
<det nItem="2"><prod><cProd>SKU-2002</cProd><cEAN></cEAN>
<xProd>PERFIL DOBRADO SOB MEDIDA</xProd><NCM>7308400</NCM></prod>
<imposto><ICMS><ICMS00><CST>00</CST></ICMS00></ICMS></imposto></det>
</infNFe></NFe></nfeProc>"""
    xml_ok = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe>
<infNFe Id="NFe35260712345678000199550010000000021000000024" versao="4.00">
<ide><mod>55</mod><nNF>102</nNF><dhEmi>2026-07-21T14:02:00-03:00</dhEmi><tpNF>1</tpNF></ide>
<emit><CNPJ>12345678000199</CNPJ><xNome>INDÚSTRIA DEMONSTRAÇÃO LTDA</xNome><CRT>3</CRT></emit>
<det nItem="1"><prod><cProd>SKU-3003</cProd><cEAN>SEM GTIN</cEAN>
<xProd>PRODUTO JÁ PARAMETRIZADO</xProd><NCM>72104900</NCM></prod><imposto>
<IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib><gIBSCBS>
<vBC>100.00</vBC><gIBSUF><pIBSUF>0.1</pIBSUF><vIBSUF>0.10</vIBSUF></gIBSUF>
<gCBS><pCBS>0.9</pCBS><vCBS>0.90</vCBS></gCBS></gIBSCBS></IBSCBS>
</imposto></det></infNFe></NFe></nfeProc>"""
    (destino / "demonstracao-com-risco.xml").write_text(xml_risco, encoding="utf-8")
    (destino / "demonstracao-conforme.xml").write_text(xml_ok, encoding="utf-8")


def _validar_marca(valor: str | None) -> str:
    marca = (valor or "RTC Check").strip()[:60]
    return marca or "RTC Check"


def _validar_cor(valor: str | None) -> str:
    cor = (valor or COR_PADRAO).strip()
    return cor if re.fullmatch(r"#[0-9A-Fa-f]{6}", cor) else COR_PADRAO


def _handler(estado: EstadoApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "RTCCheckLocal/1.0"

        def log_message(self, formato: str, *args: object) -> None:
            # Não registrar nomes de arquivos, parâmetros ou conteúdo fiscal.
            if len(args) > 1 and str(args[1]) >= "400":
                super().log_message(formato, *args)

        def _cabecalhos_seguranca(self, tipo: str, tamanho: int) -> None:
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(tamanho))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; "
                "style-src 'self'; script-src 'self'; connect-src 'self'; "
                "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )

        def _enviar(
            self,
            corpo: bytes,
            tipo: str,
            status: HTTPStatus = HTTPStatus.OK,
            *,
            download: str | None = None,
        ) -> None:
            self.send_response(status)
            self._cabecalhos_seguranca(tipo, len(corpo))
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{download}"')
            self.end_headers()
            self.wfile.write(corpo)

        def _json(
            self,
            dados: object,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            self._enviar(
                json.dumps(dados, ensure_ascii=False).encode(),
                "application/json; charset=utf-8",
                status,
            )

        def _autorizado(self) -> bool:
            recebido = self.headers.get("X-RTC-Token", "")
            return secrets.compare_digest(recebido, estado.token)

        def _host_valido(self) -> bool:
            try:
                host = (
                    urlparse(f"//{self.headers.get('Host', '')}").hostname or ""
                ).lower()
            except ValueError:
                return False
            return host in {"127.0.0.1", "::1", "localhost"}

        def _exigir_host_local(self) -> bool:
            if self._host_valido():
                return True
            self._json({"erro": "host local inválido"}, HTTPStatus.FORBIDDEN)
            return False

        def _exigir_token(self) -> bool:
            if self._autorizado():
                return True
            self._json({"erro": "sessão local inválida"}, HTTPStatus.FORBIDDEN)
            return False

        def _corpo(self) -> bytes:
            try:
                tamanho = int(self.headers.get("Content-Length", "0"))
            except ValueError as erro:
                raise EntradaInvalida("tamanho da requisição inválido") from erro
            if tamanho <= 0 or tamanho > MAX_REQUISICAO:
                raise EntradaInvalida("requisição vazia ou maior que 64 MB")
            return self.rfile.read(tamanho)

        def do_GET(self) -> None:  # noqa: N802
            if not self._exigir_host_local():
                return
            caminho = urlparse(self.path).path
            if caminho == "/":
                pagina = (ARQUIVOS_WEB / "index.html").read_text(encoding="utf-8")
                pagina = pagina.replace("{{RTC_TOKEN}}", estado.token)
                self._enviar(pagina.encode(), "text/html; charset=utf-8")
                return
            if caminho in {"/app.css", "/app.js"}:
                nome = caminho.removeprefix("/")
                tipo = "text/css; charset=utf-8" if nome.endswith(".css") else (
                    "text/javascript; charset=utf-8"
                )
                self._enviar((ARQUIVOS_WEB / nome).read_bytes(), tipo)
                return
            if caminho == "/api/status":
                if self._exigir_token():
                    self._json(_status())
                return
            if caminho.startswith("/api/analises/"):
                partes = caminho.strip("/").split("/")
                if len(partes) != 3:
                    self._json({"erro": "consulta de análise inválida"}, HTTPStatus.NOT_FOUND)
                    return
                if not self._exigir_token():
                    return
                analise = estado.obter_analise(partes[2])
                if analise is None:
                    self._json(
                        {"erro": "análise expirada; execute novamente"},
                        HTTPStatus.NOT_FOUND,
                    )
                    return
                self._json(_serializar_andamento(analise, estado))
                return
            self._json({"erro": "recurso não encontrado"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            if not self._exigir_host_local() or not self._exigir_token():
                return
            caminho = urlparse(self.path).path
            try:
                if caminho == "/api/demo":
                    self._analisar_demo()
                elif caminho == "/api/analisar":
                    self._analisar_upload()
                elif caminho.startswith("/api/analises/") and caminho.endswith("/cancelar"):
                    self._cancelar_analise(caminho)
                elif caminho == "/api/teste":
                    self._iniciar_teste()
                elif caminho == "/api/licenca":
                    self._ativar_licenca()
                elif caminho == "/api/encerrar":
                    self._encerrar()
                elif caminho.startswith("/api/exportar/"):
                    self._exportar(caminho)
                elif caminho.startswith("/api/atualizar/"):
                    self._atualizar_resultado(caminho)
                else:
                    self._json({"erro": "recurso não encontrado"}, HTTPStatus.NOT_FOUND)
            except EntradaInvalida as erro:
                self._json({"erro": str(erro)}, HTTPStatus.BAD_REQUEST)
            except (OSError, ValueError) as erro:
                self._json(
                    {"erro": f"não foi possível concluir: {erro}"},
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                )

        def _concluir_analise(
            self,
            resumo: Resumo,
            edicao_atual: ed.Edicao,
            *,
            demo: bool,
        ) -> None:
            identificador = estado.guardar(resumo, edicao_atual, demo=demo)
            self._json(
                _serializar_resultado(
                    resumo,
                    edicao_atual,
                    identificador,
                    demo=demo,
                )
            )

        def _analisar_demo(self) -> None:
            with tempfile.TemporaryDirectory(prefix="rtc-check-demo-") as pasta:
                destino = Path(pasta)
                _criar_demo(destino)
                atual = ed.resolver()
                regras_demo = ed.Edicao(plano=ed.Plano.ESCRITORIO).regras_ativas
                resumo = analisar(destino, regras=regras_demo)
            self._concluir_analise(resumo, atual, demo=True)

        def _analisar_upload(self) -> None:
            tipo = self.headers.get("Content-Type", "")
            if not tipo.lower().startswith("multipart/form-data"):
                raise EntradaInvalida("use o seletor de XML ou ZIP da interface")
            partes = _partes_multipart(tipo, self._corpo())
            analise = estado.iniciar_analise()

            def executar_em_segundo_plano() -> None:
                try:
                    with tempfile.TemporaryDirectory(prefix="rtc-check-upload-") as pasta:
                        destino = Path(pasta)
                        analise.etapa = "preparando"
                        analise.mensagem = "Conferindo e preparando os XMLs neste PC."
                        _salvar_xmls_do_upload(partes, destino)
                        if analise.cancelar.is_set():
                            raise AnaliseCancelada()
                        analise.etapa = "analisando"
                        analise.mensagem = "Lendo XMLs e agrupando produtos."
                        atual = ed.resolver()

                        def atualizar_progresso(processados: int, total: int) -> None:
                            analise.processados = processados
                            analise.total = total
                            analise.mensagem = (
                                f"Analisando XML {processados:,} de {total:,}."
                                .replace(",", ".")
                            )

                        resumo = analisar(
                            destino,
                            regras=atual.regras_ativas,
                            progresso=atualizar_progresso,
                            cancelar=analise.cancelar.is_set,
                        )
                    analise.etapa = "finalizando"
                    analise.mensagem = "Organizando a fila de correção."
                    analise.resultado_id = estado.guardar(resumo, atual, demo=False)
                    analise.concluida = True
                except AnaliseCancelada:
                    analise.etapa = "cancelada"
                    analise.mensagem = "Análise cancelada. Os arquivos temporários foram apagados."
                    analise.concluida = True
                except (OSError, ValueError, EntradaInvalida) as erro:
                    analise.etapa = "erro"
                    analise.erro = f"não foi possível concluir: {erro}"
                    analise.concluida = True

            threading.Thread(target=executar_em_segundo_plano, daemon=True).start()
            self._json(_serializar_andamento(analise, estado), HTTPStatus.ACCEPTED)

        def _cancelar_analise(self, caminho: str) -> None:
            partes = caminho.strip("/").split("/")
            if len(partes) != 4:
                raise EntradaInvalida("cancelamento de análise inválido")
            analise = estado.cancelar_analise(partes[2])
            if analise is None:
                self._json({"erro": "análise expirada; execute novamente"}, HTTPStatus.NOT_FOUND)
                return
            self._json(_serializar_andamento(analise, estado))

        def _iniciar_teste(self) -> None:
            try:
                atual = ed.iniciar_teste()
            except ed.TesteIndisponivel as erro:
                raise EntradaInvalida(str(erro)) from erro
            self._json(
                {
                    "mensagem": f"Teste liberado até {atual.expira_em:%d/%m/%Y}.",
                    "status": _status(),
                }
            )

        def _ativar_licenca(self) -> None:
            try:
                dados = json.loads(self._corpo())
                chave = str(dados["chave"])
                atual = ed.salvar_licenca(chave)
            except (json.JSONDecodeError, KeyError, ed.LicencaInvalida) as erro:
                raise EntradaInvalida(f"chave recusada: {erro}") from erro
            self._json(
                {
                    "mensagem": f"Plano {atual.nome} ativado para {atual.titular}.",
                    "status": _status(),
                }
            )

        def _encerrar(self) -> None:
            estado.cancelar_todas()
            self._json({"mensagem": "RTC Check encerrado com segurança."})
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def _atualizar_resultado(self, caminho: str) -> None:
            partes = caminho.strip("/").split("/")
            if len(partes) != 3:
                raise EntradaInvalida("atualização de resultado inválida")
            salvo = estado.relatorios.get(partes[2])
            if salvo is None:
                raise EntradaInvalida("análise expirada; execute novamente")
            atual = ed.resolver()
            if not salvo.demo and salvo.edicao.regras_ativas != atual.regras_ativas:
                self._json(
                    {
                        "erro": (
                            "o plano mudou e este resultado não contém todas as regras; "
                            "selecione o lote novamente"
                        )
                    },
                    HTTPStatus.CONFLICT,
                )
                return
            self._json(
                _serializar_resultado(
                    salvo.resumo,
                    atual,
                    partes[2],
                    demo=salvo.demo,
                )
            )

        def _exportar(self, caminho: str) -> None:
            partes = caminho.strip("/").split("/")
            if len(partes) != 4:
                raise EntradaInvalida("exportação inválida")
            _, _, identificador, formato = partes
            salvo = estado.relatorios.get(identificador)
            if salvo is None:
                raise EntradaInvalida("análise expirada; execute novamente")
            atual = ed.resolver()
            liberado = salvo.demo or atual.tem(ed.Recurso.FORMATO_HTML)
            if not liberado:
                self._json(
                    {
                        "erro": "exportações fazem parte do plano Escritório",
                        "como_liberar": "Teste grátis: rtc-check --iniciar-teste",
                    },
                    HTTPStatus.PAYMENT_REQUIRED,
                )
                return
            if not salvo.demo and salvo.edicao.regras_ativas != atual.regras_ativas:
                self._json(
                    {
                        "erro": (
                            "o plano mudou e esta exportação ficaria incompleta; "
                            "selecione o lote novamente"
                        )
                    },
                    HTTPStatus.CONFLICT,
                )
                return
            marca = _validar_marca(self.headers.get("X-RTC-Brand"))
            cor = _validar_cor(self.headers.get("X-RTC-Color"))
            if formato == "html":
                conteudo = formatar_html(
                    salvo.resumo,
                    por_cnpj=True,
                    marca=marca,
                    cor=cor,
                ).encode()
                self._enviar(
                    conteudo,
                    "text/html; charset=utf-8",
                    download="prontidao-rtc.html",
                )
            elif formato == "csv":
                conteudo = ("\ufeff" + formatar_csv(salvo.resumo)).encode("utf-8")
                self._enviar(
                    conteudo,
                    "text/csv; charset=utf-8",
                    download="fila-de-correcao.csv",
                )
            elif formato == "json":
                conteudo = formatar_json(salvo.resumo, por_cnpj=True).encode()
                self._enviar(
                    conteudo,
                    "application/json; charset=utf-8",
                    download="auditoria-rtc.json",
                )
            else:
                raise EntradaInvalida("formato de exportação desconhecido")

    return Handler


def executar(*, porta: int = 0, abrir_navegador: bool = True) -> int:
    """Inicia a interface local e bloqueia até Ctrl+C."""
    estado = EstadoApp()
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), _handler(estado))
    endereco = f"http://127.0.0.1:{servidor.server_port}/"
    print(f"RTC Check Desktop {__version__}: {endereco}")
    print("Os XMLs permanecem neste computador. Pressione Ctrl+C para encerrar.")
    if abrir_navegador:
        threading.Timer(0.35, webbrowser.open, args=(endereco,)).start()
    try:
        servidor.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nRTC Check encerrado.")
    finally:
        servidor.server_close()
    return 0


def main() -> int:
    try:
        porta = int(os.environ.get("RTC_CHECK_PORTA", "0"))
    except ValueError as erro:
        raise SystemExit("RTC_CHECK_PORTA precisa ser um número entre 0 e 65535") from erro
    if not 0 <= porta <= 65535:
        raise SystemExit("RTC_CHECK_PORTA precisa estar entre 0 e 65535")
    sem_navegador = os.environ.get("RTC_CHECK_SEM_NAVEGADOR") == "1"
    return executar(porta=porta, abrir_navegador=not sem_navegador)


if __name__ == "__main__":
    raise SystemExit(main())
