from __future__ import annotations

import hmac
import os
from hashlib import sha256
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from email_validator import EmailNotValidError, validate_email

NONCE_BYTE = 12
KEY_ID_DEV = "dev-v1"


class EmailNonValido(ValueError):  # noqa: N818
    """Segnala un indirizzo email non valido per il lookup pseudonimo."""


class ChiaveEmailSconosciuta(ValueError):  # noqa: N818
    """Segnala un key_id non gestito dal cifrario configurato."""


class EmailNonDecifrabile(ValueError):  # noqa: N818
    """Segnala un ciphertext che non può essere decifrato con la chiave indicata."""


class EmailCipher(Protocol):
    @property
    def key_id_corrente(self) -> str: ...

    def cifra(self, email: str) -> tuple[bytes, str]:
        """Restituisce il ciphertext e il key_id della chiave usata."""
        ...

    def decifra(self, ciphertext: bytes, key_id: str) -> str:
        """Restituisce l'email in chiaro o solleva un errore di decifratura."""
        ...


class CifrarioEmailEnvelope:
    """Implementazione dev di envelope encryption con AES-256-GCM e KEK unica."""

    def __init__(self, chiave: bytes, key_id: str = KEY_ID_DEV) -> None:
        if len(chiave) != 32:
            raise ValueError("La KEK deve essere di 32 byte per AES-256-GCM.")
        self._aead = AESGCM(chiave)
        self._key_id = key_id

    @property
    def key_id_corrente(self) -> str:
        return self._key_id

    def cifra(self, email: str) -> tuple[bytes, str]:
        nonce = os.urandom(NONCE_BYTE)
        ciphertext = self._aead.encrypt(
            nonce,
            email.encode("utf-8"),
            self._key_id.encode("utf-8"),
        )
        return nonce + ciphertext, self._key_id

    def decifra(self, ciphertext: bytes, key_id: str) -> str:
        if key_id != self._key_id:
            raise ChiaveEmailSconosciuta(f"Key id non gestito: {key_id}.")
        nonce, contenuto = ciphertext[:NONCE_BYTE], ciphertext[NONCE_BYTE:]
        try:
            chiaro = self._aead.decrypt(
                nonce,
                contenuto,
                key_id.encode("utf-8"),
            )
        except InvalidTag as errore:
            raise EmailNonDecifrabile(
                "Il ciphertext non è integro o la chiave non corrisponde."
            ) from errore
        return chiaro.decode("utf-8")


def calcola_hash_lookup_email(email: str, pepper: bytes) -> str:
    """Restituisce l'HMAC-SHA256 esadecimale dell'email normalizzata."""
    email_normalizzata = _normalizza_email(email)
    return hmac.new(
        pepper,
        email_normalizzata.encode("utf-8"),
        sha256,
    ).hexdigest()


def _normalizza_email(email: str) -> str:
    valore = email.strip().lower()
    try:
        validate_email(valore, check_deliverability=False)
    except EmailNotValidError as errore:
        raise EmailNonValido(
            "L'indirizzo email non è valido. Controlla e riprova."
        ) from errore
    return valore
