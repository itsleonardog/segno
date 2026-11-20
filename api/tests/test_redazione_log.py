from __future__ import annotations

from app.infrastruttura.logging_sicuro import redigi_messaggio

MESSAGGIO_CON_PII = (
    "invio a mario.rossi@example.com con token=abcdef123456 "
    "e coordinate lat=45.123456 lng=9.987654"
)


def test_redazione_rimuove_email_token_e_coordinate() -> None:
    redatto = redigi_messaggio(MESSAGGIO_CON_PII)

    assert "mario.rossi@example.com" not in redatto
    assert "abcdef123456" not in redatto
    assert "45.12" in redatto
    assert "45.123456" not in redatto
    assert "9.99" in redatto
    assert "9.987654" not in redatto
