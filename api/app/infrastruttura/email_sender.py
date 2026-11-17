from __future__ import annotations

import json
import logging
from typing import Protocol

logger = logging.getLogger(__name__)

AMBIENTE_DEV = "dev"


class EmailSender(Protocol):
    def invia(self, destinatario: str, oggetto: str, corpo: str) -> None:
        """Consegna un messaggio o lo registra secondo l'ambiente configurato."""
        ...


class LoggingEmailSender:
    """Stub di invio: in dev logga il contenuto, altrove segnala lo step futuro."""

    def __init__(self, ambiente: str) -> None:
        self._ambiente = ambiente

    def invia(self, destinatario: str, oggetto: str, corpo: str) -> None:
        if self._ambiente == AMBIENTE_DEV:
            # L'indirizzo del destinatario è PII e non finisce nei log: il corpo
            # contiene già URL e token necessari alla verifica manuale in dev.
            logger.info(
                "email_dev_inviata %s",
                json.dumps(
                    {"oggetto": oggetto, "corpo": corpo},
                    ensure_ascii=False,
                ),
            )
            return
        logger.warning("email_not_sent reason=stub_step_3 messaggio=email_non_inviata")
