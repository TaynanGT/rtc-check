import json
from pathlib import Path

RAIZ = Path(__file__).parents[1]


def test_webhook_contract_is_explicit_and_closed():
    schema = json.loads((RAIZ / "docs" / "webhook-event.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]["event_type"]["enum"]) == {
        "checkout_iniciado",
        "pagamento_confirmado",
        "licenca_emitida",
        "pagamento_cancelado",
        "reembolso_confirmado",
    }
    assert "coupon_code" in schema["properties"]


def test_signing_script_never_falls_back_to_unsigned_success():
    script = (RAIZ / "scripts" / "Sign-Windows.ps1").read_text(encoding="utf-8")
    assert "Set-AuthenticodeSignature" in script
    assert 'Status -ne "Valid"' in script
    assert "Nenhum certificado Authenticode" in script
