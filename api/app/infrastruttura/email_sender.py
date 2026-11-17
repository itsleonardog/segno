from __future__ import annotations

import json
import logging
from email.utils import make_msgid
from typing import Protocol

from app.dominio.dispatch import ContenutoEmail, ErroreInvioEmailSegnalazione
from app.infrastruttura.configurazione import MITTENTE_PREDEFINITO

logger = logging.getLogger(__name__)

AMBIENTE_DEV = "dev"


class EmailSender(Protocol):
    def invia(self, destinatario: str, oggetto: str, corpo: str) -> None:
        """Consegna un messaggio o lo registra secondo l'ambiente configurato."""
        ...

    def invia_segnalazione(
        self,
        destinatario: str,
        contenuto: ContenutoEmail,
    ) -> str:
        """Consegna la segnalazione al comune e restituisce il Message-ID."""
        ...


class LoggingEmailSender:
    """Stub di invio: in dev logga il contenuto, altrove segnala lo step futuro."""

    def __init__(
        self,
        ambiente: str,
        indirizzo_mittente: str = MITTENTE_PREDEFINITO,
    ) -> None:
        self._ambiente = ambiente
        self._indirizzo_mittente = indirizzo_mittente

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

    def invia_segnalazione(
        self,
        destinatario: str,
        contenuto: ContenutoEmail,
    ) -> str:
        message_id = make_msgid(domain=_dominio_mittente(self._indirizzo_mittente))
        if self._ambiente != AMBIENTE_DEV:
            logger.error(
                "dispatch_email_provider_not_configured",
                extra={"message_id": message_id},
            )
            raise ErroreInvioEmailSegnalazione(
                "Il provider email di dispatch non è ancora configurato."
            )
        # Mittente e destinatario sono PII e restano fuori dai log; il Message-ID
        # basta a correlare la risposta del comune in ambiente di sviluppo.
        logger.info(
            "dispatch_email_dev_inviata %s",
            json.dumps(
                {
                    "mittente": self._indirizzo_mittente,
                    "oggetto": contenuto.oggetto,
                    "message_id": message_id,
                },
                ensure_ascii=False,
            ),
        )
        return message_id


def _dominio_mittente(indirizzo_mittente: str) -> str:
    return indirizzo_mittente.rsplit("@", maxsplit=1)[-1]
