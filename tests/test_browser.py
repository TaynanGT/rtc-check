import threading
from http.server import ThreadingHTTPServer

import pytest

from rtc_check import webapp

playwright = pytest.importorskip("playwright.sync_api")


@pytest.mark.browser
def test_fluxo_visual_demo_acessivel(tmp_path, monkeypatch):
    monkeypatch.setenv("RTC_CHECK_HOME", str(tmp_path / "config"))
    estado = webapp.EstadoApp(token="token-browser")
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), webapp._handler(estado))
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{servidor.server_port}"
    try:
        with playwright.sync_playwright() as runtime:
            navegador = runtime.chromium.launch()
            pagina = navegador.new_page(viewport={"width": 1280, "height": 900})
            erros: list[str] = []
            pagina.on(
                "console",
                lambda msg: erros.append(msg.text) if msg.type == "error" else None,
            )
            pagina.goto(base)
            pagina.get_by_role("button", name="Ver demonstração").click()
            pagina.get_by_role("heading", name="Sua fila de correção").wait_for()
            assert pagina.locator("#metrics .metric").count() == 5
            assert pagina.locator("#result-rows tr").count() >= 1
            pagina.get_by_role("button", name="Ajuda").click()
            assert pagina.get_by_role("heading", name="Como tirar valor da análise").is_visible()
            pagina.keyboard.press("Escape")
            pagina.get_by_role("button", name="Personalizar").click()
            assert not pagina.get_by_label(
                "Permitir métricas das últimas análises neste navegador (opt-in)"
            ).is_checked()
            pagina.get_by_label("Usar contraste alto nesta interface").check()
            pagina.get_by_role("button", name="Salvar").click()
            assert "high-contrast" in pagina.locator("body").get_attribute("class")
            assert not erros
            navegador.close()
    finally:
        servidor.shutdown()
        servidor.server_close()
        thread.join(timeout=2)
