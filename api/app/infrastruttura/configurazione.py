from __future__ import annotations

import os
from dataclasses import dataclass

URL_DATABASE_PREDEFINITO = (
    "postgresql+asyncpg://civic_app:civic_app@localhost:55432/civic_test"
)


@dataclass(frozen=True, slots=True)
class ConfigurazioneDatabase:
    url_applicazione: str
    url_migratore: str


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
