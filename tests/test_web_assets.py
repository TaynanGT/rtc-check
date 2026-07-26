from pathlib import Path

WEB = Path(__file__).parents[1] / "src" / "rtc_check" / "web"


def test_interface_e_script_tem_os_controles_criticos_do_fluxo():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    script = (WEB / "app.js").read_text(encoding="utf-8")
    for identificador in (
        "rule-picker-content",
        "copy-diagnostic",
        "history-clear",
        "cancel-analysis",
        "feedback-title",
    ):
        assert f'id="{identificador}"' in html
    assert "selected-rule" in script
    assert "copy-diagnostic" in script
