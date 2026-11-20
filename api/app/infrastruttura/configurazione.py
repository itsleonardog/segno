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

URL_PUBBLICA_PREDEFINITA = "https://segnalazioni.example"
MITTENTE_PREDEFINITO = "segnalazioni@segno.example"
PAUSA_WORKER_PREDEFINITA_SECONDI = 5.0
INTERVALLO_SINCRONIZZAZIONE_OPEN311_PREDEFINITO_SECONDI = 300.0
INTERVALLO_RETENTION_PREDEFINITO_SECONDI = 86400.0
PREFISSO_SEGRETO_OPEN311_PREDEFINITO = "CIVIC_OPEN311_KEY_"
ORIGINI_CORS_PREDEFINITE = "http://localhost:3000"

LIMITE_LOGIN_PREDEFINITO = 5
LIMITE_REGISTRAZIONE_PREDEFINITO = 5
LIMITE_SEGNALAZIONI_PREDEFINITO = 3
LIMITE_GEOCODING_PREDEFINITO = 10

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


@dataclass(frozen=True, slots=True)
class ConfigurazioneDispatch:
    url_pubblica_base: str
    indirizzo_mittente: str
    pausa_worker_secondi: float
    intervallo_sincronizzazione_open311_secondi: float
    intervallo_retention_secondi: float
    prefisso_segreto_open311: str


@dataclass(frozen=True, slots=True)
class ConfigurazioneRateLimit:
    login_per_minuto: int
    registrazione_per_minuto: int
    segnalazioni_per_minuto: int
    geocoding_per_minuto: int


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


def leggi_configurazione_dispatch() -> ConfigurazioneDispatch:
    """Restituisce i parametri del dispatch e del worker di relay."""
    return ConfigurazioneDispatch(
        url_pubblica_base=os.environ.get(
            "CIVIC_URL_PUBBLICA_BASE", URL_PUBBLICA_PREDEFINITA
        ),
        indirizzo_mittente=os.environ.get("CIVIC_EMAIL_MITTENTE", MITTENTE_PREDEFINITO),
        pausa_worker_secondi=float(
            os.environ.get(
                "CIVIC_WORKER_PAUSA_SECONDI",
                str(PAUSA_WORKER_PREDEFINITA_SECONDI),
            )
        ),
        intervallo_sincronizzazione_open311_secondi=float(
            os.environ.get(
                "CIVIC_OPEN311_SYNC_SECONDI",
                str(INTERVALLO_SINCRONIZZAZIONE_OPEN311_PREDEFINITO_SECONDI),
            )
        ),
        intervallo_retention_secondi=float(
            os.environ.get(
                "CIVIC_RETENTION_SECONDI",
                str(INTERVALLO_RETENTION_PREDEFINITO_SECONDI),
            )
        ),
        prefisso_segreto_open311=os.environ.get(
            "CIVIC_OPEN311_KEY_PREFISSO", PREFISSO_SEGRETO_OPEN311_PREDEFINITO
        ),
    )


def leggi_configurazione_rate_limit() -> ConfigurazioneRateLimit:
    """Restituisce i limiti di frequenza applicati dal middleware."""
    return ConfigurazioneRateLimit(
        login_per_minuto=int(
            os.environ.get("CIVIC_RATE_LIMIT_LOGIN", str(LIMITE_LOGIN_PREDEFINITO))
        ),
        registrazione_per_minuto=int(
            os.environ.get(
                "CIVIC_RATE_LIMIT_REGISTRAZIONE",
                str(LIMITE_REGISTRAZIONE_PREDEFINITO),
            )
        ),
        segnalazioni_per_minuto=int(
            os.environ.get(
                "CIVIC_RATE_LIMIT_SEGNALAZIONI",
                str(LIMITE_SEGNALAZIONI_PREDEFINITO),
            )
        ),
        geocoding_per_minuto=int(
            os.environ.get(
                "CIVIC_RATE_LIMIT_GEOCODING",
                str(LIMITE_GEOCODING_PREDEFINITO),
            )
        ),
    )


def leggi_origini_consentite() -> tuple[str, ...]:
    """Restituisce le origini ammesse per le richieste provenienti dal browser."""
    valore = os.environ.get("CIVIC_CORS_ORIGINS", ORIGINI_CORS_PREDEFINITE)
    return tuple(origine.strip() for origine in valore.split(",") if origine.strip())


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
