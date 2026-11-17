from __future__ import annotations

from app.infrastruttura.cifratura_email import (
    CifrarioEmailEnvelope,
    calcola_hash_lookup_email,
)
from app.infrastruttura.configurazione import (
    decodifica_segreto_base64,
    leggi_configurazione_sicurezza,
)

EMAIL_DI_PROVA = "Mario.Rossi@Example.com"


def _cifrario() -> CifrarioEmailEnvelope:
    configurazione = leggi_configurazione_sicurezza()
    chiave = decodifica_segreto_base64(
        configurazione.chiave_cifratura_base64,
        "CIVIC_EMAIL_KEK",
    )
    return CifrarioEmailEnvelope(chiave)


def _pepper() -> bytes:
    configurazione = leggi_configurazione_sicurezza()
    return decodifica_segreto_base64(
        configurazione.pepper_lookup_base64,
        "CIVIC_EMAIL_LOOKUP_PEPPER",
    )


def test_email_cipher_roundtrip() -> None:
    cifrario = _cifrario()

    primo_ciphertext, primo_key_id = cifrario.cifra(EMAIL_DI_PROVA)
    secondo_ciphertext, secondo_key_id = cifrario.cifra(EMAIL_DI_PROVA)

    assert cifrario.decifra(primo_ciphertext, primo_key_id) == EMAIL_DI_PROVA
    assert primo_key_id == secondo_key_id == "dev-v1"
    assert primo_ciphertext != secondo_ciphertext


def test_email_lookup_hash_deterministico() -> None:
    pepper = _pepper()

    primo_hash = calcola_hash_lookup_email("  Mario.Rossi@Example.com ", pepper)
    secondo_hash = calcola_hash_lookup_email("mario.rossi@example.com", pepper)

    assert primo_hash == secondo_hash
    assert len(primo_hash) == 64
    assert "mario" not in primo_hash.lower()
    assert "@" not in primo_hash
