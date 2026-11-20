"""Redazione di dati personali e coordinate nei log applicativi."""

from __future__ import annotations

import logging
import re

SOSTITUZIONE_EMAIL = "[email-redatta]"
SOSTITUZIONE_TOKEN = "[token-redatto]"
CIFRE_COORDINATA_NEI_LOG = 2

PATTERN_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PATTERN_TOKEN = re.compile(
    r"(?i)\b(access_token|refresh_token|bearer|token)\b"
    r"(\s*[=:]\s*|\s+)"
    r"([A-Za-z0-9._\-]{8,})"
)
PATTERN_COORDINATA = re.compile(
    r"(?i)\b(lat|latitudine|latitude|lng|lon|longitudine|longitude)\b"
    r"(\s*[=:]\s*)"
    r"(-?\d+\.\d+)"
)


class RedattoreLog(logging.Filter):
    """Rimuove email, token e coordinate precise dal messaggio del record."""

    def filter(self, record: logging.LogRecord) -> bool:
        messaggio = record.getMessage()
        redatto = redigi_messaggio(messaggio)
        if redatto != messaggio:
            record.msg = redatto
            record.args = ()
        return True


def redigi_messaggio(messaggio: str) -> str:
    """Restituisce il messaggio senza email, token e coordinate precise."""
    redatto = PATTERN_TOKEN.sub(_token_redatto, messaggio)
    redatto = PATTERN_EMAIL.sub(SOSTITUZIONE_EMAIL, redatto)
    return PATTERN_COORDINATA.sub(_coordinata_arrotondata, redatto)


def installa_redazione_log() -> None:
    """Collega il filtro agli handler già configurati sulla radice dei logger."""
    for gestore in logging.getLogger().handlers:
        if any(isinstance(filtro, RedattoreLog) for filtro in gestore.filters):
            continue
        gestore.addFilter(RedattoreLog())


def _token_redatto(corrispondenza: re.Match[str]) -> str:
    return f"{corrispondenza.group(1)}{corrispondenza.group(2)}{SOSTITUZIONE_TOKEN}"


def _coordinata_arrotondata(corrispondenza: re.Match[str]) -> str:
    valore = round(float(corrispondenza.group(3)), CIFRE_COORDINATA_NEI_LOG)
    return f"{corrispondenza.group(1)}{corrispondenza.group(2)}{valore:.2f}"
