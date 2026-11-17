from __future__ import annotations

import base64
import binascii
import hashlib
import os
from dataclasses import dataclass

URL_DATABASE_PREDEFINITO = (
    "postgresql+asyncpg://civic_app:civic_app@localhost:55432/civic_test"
)

AMBIENTE_PREDEFINITO = "dev"
SEGRETO_JWT_PREDEFINITO = "civic-dev-jwt-secret-change-me-0123456789"

# In dev la KEK e il pepper sono derivati da costanti note: il materiale di
# chiave reale arriva dal KMS in Fase 5 e non deve mai essere versionato.
CHIAVE_CIFRATURA_PREDEFINITA = base64.b64encode(
    hashlib.sha256(b"civic-dev-email-kek").digest()
).decode("ascii")
PEPPER_LOOKUP_PREDEFINITO = base64.b64encode(
    hashlib.sha256(b"civic-dev-lookup-pepper").digest()
).decode("ascii")

LUNGHEZZA_MINIMA_SEGRETO = 32


@dataclass(frozen=True, slots=True)
class ConfigurazioneDatabase:
    url_applicazione: str
    url_migratore: str


@dataclass(frozen=True, slots=True)
class ConfigurazioneSicurezza:
    ambiente: str
    segreto_jwt: str
    chiave_cifratura_base64: str
    pepper_lookup_base64: str


def leggi_configurazione_database() -> ConfigurazioneDatabase:
    """Restituisce le URL di connessione per l'applicazione e le migrazioni."""
    return ConfigurazioneDatabase(
        url_applicazione=os.environ.get(
            "CIVIC_DATABASE_URL_APP", URL_DATABASE_PREDEFINITO
        ),
        url_migratore=os.environ.get(
            "CIVIC_DATABASE_URL",
            "postgresql+asyncpg://civic_migrator:civic_migrator@localhost:55432/civic_test",
        ),
    )


def leggi_configurazione_sicurezza() -> ConfigurazioneSicurezza:
    """Restituisce la configurazione di cifratura, hashing e firma dei token."""
    return ConfigurazioneSicurezza(
        ambiente=os.environ.get("CIVIC_ENV", AMBIENTE_PREDEFINITO),
        segreto_jwt=os.environ.get("CIVIC_JWT_SECRET", SEGRETO_JWT_PREDEFINITO),
        chiave_cifratura_base64=os.environ.get(
            "CIVIC_EMAIL_KEK", CHIAVE_CIFRATURA_PREDEFINITA
        ),
        pepper_lookup_base64=os.environ.get(
            "CIVIC_EMAIL_LOOKUP_PEPPER", PEPPER_LOOKUP_PREDEFINITO
        ),
    )


def decodifica_segreto_base64(valore: str, nome: str) -> bytes:
    """Restituisce il segreto decodificato o solleva ValueError se non è valido."""
    try:
        contenuto = base64.b64decode(valore, validate=True)
    except (binascii.Error, ValueError) as errore:
        raise ValueError(f"Il segreto {nome} non è base64 valido.") from errore
    if len(contenuto) < LUNGHEZZA_MINIMA_SEGRETO:
        raise ValueError(
            f"Il segreto {nome} deve contenere almeno {LUNGHEZZA_MINIMA_SEGRETO} byte."
        )
    return contenuto
