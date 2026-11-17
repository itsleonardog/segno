from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RADICE_API = Path(__file__).resolve().parents[1]

URL_AMMINISTRATORE = os.environ.get(
    "CIVIC_TEST_ADMIN_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:55432/civic_test",
)
URL_APPLICAZIONE = os.environ.get(
    "CIVIC_TEST_APP_URL",
    "postgresql+asyncpg://civic_app:civic_app@localhost:55432/civic_test",
)
PASSWORD_APPLICAZIONE = os.environ.get("CIVIC_APP_PASSWORD", "civic_app")
PASSWORD_MIGRATORE = os.environ.get("CIVIC_MIGRATOR_PASSWORD", "civic_migrator")

RUOLO_MIGRATORE = "civic_migrator"
RUOLO_APPLICAZIONE = "civic_app"


def esegui_alembic(argomenti: tuple[str, ...], url_database: str) -> None:
    ambiente = {
        **os.environ,
        "CIVIC_DATABASE_URL": url_database,
        "CIVIC_APP_PASSWORD": PASSWORD_APPLICAZIONE,
        "CIVIC_MIGRATOR_PASSWORD": PASSWORD_MIGRATORE,
    }
    esito = subprocess.run(
        [sys.executable, "-m", "alembic", *argomenti],
        cwd=RADICE_API,
        env=ambiente,
        capture_output=True,
        text=True,
    )
    assert esito.returncode == 0, esito.stderr
