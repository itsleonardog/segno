from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.dispatch import (
    CifrarioEmailDispatch,
    ErroreInvioEmailSegnalazione,
    EsitoElaborazione,
)
from app.dominio.notifica import (
    STATO_NOTIFICA_IGNORATA,
    STATO_NOTIFICA_INVIATA,
    InvioEmailNotifica,
    NotificaDaInviare,
    componi_contenuto_email_notifica,
    componi_url_pagina_segnalazione,
)
from app.infrastruttura import repository_notifiche

logger = logging.getLogger(__name__)

MESSAGGIO_PROVIDER_EMAIL_NON_DISPONIBILE = (
    "Invio email di aggiornamento all'autore non riuscito."
)


class ElaboratoreNotifiche:
    """Invia all'autore l'email di aggiornamento per un evento di stato."""

    def __init__(
        self,
        *,
        invio_email: InvioEmailNotifica,
        cifrario_email: CifrarioEmailDispatch,
        url_pubblica_base: str,
    ) -> None:
        self._invio_email = invio_email
        self._cifrario_email = cifrario_email
        self._url_pubblica_base = url_pubblica_base

    async def elabora_evento_cambio_stato(
        self,
        connessione: AsyncConnection,
        payload: Mapping[str, object],
    ) -> EsitoElaborazione:
        """Invia l'email descritta dall'evento e segna la notifica come inviata."""
        notifica_id = _uuid_da_payload(payload.get("notification_id"))
        if notifica_id is None:
            logger.warning(
                "notification_event_missing_id",
                extra={"event_payload_keys": sorted(payload.keys())},
            )
            return EsitoElaborazione(stato_dispatch=STATO_NOTIFICA_IGNORATA)
        notifica = await repository_notifiche.carica_notifica_da_inviare(
            connessione,
            notifica_id,
        )
        if notifica is None:
            logger.warning(
                "notification_event_target_missing",
                extra={"notification_id": str(notifica_id)},
            )
            return EsitoElaborazione(stato_dispatch=STATO_NOTIFICA_IGNORATA)
        if notifica.sent_at is not None:
            return EsitoElaborazione(stato_dispatch=STATO_NOTIFICA_INVIATA)
        contenuto = componi_contenuto_email_notifica(
            _riferimento_pubblico(notifica, payload),
            notifica.to_status,
            notifica.note_public,
            componi_url_pagina_segnalazione(
                self._url_pubblica_base,
                _riferimento_pubblico(notifica, payload),
            ),
        )
        destinatario = self._cifrario_email.decifra(
            notifica.email_enc,
            notifica.email_key_id,
        )
        try:
            self._invio_email.invia(
                destinatario,
                contenuto.oggetto,
                contenuto.corpo,
            )
        except (ErroreInvioEmailSegnalazione, OSError) as errore:
            logger.warning(
                "notification_email_failed",
                extra={
                    "notification_id": str(notifica.id),
                    "error_type": type(errore).__name__,
                },
            )
            return EsitoElaborazione(
                stato_dispatch=STATO_NOTIFICA_IGNORATA,
                richiede_ritentativo=True,
                messaggio_errore=MESSAGGIO_PROVIDER_EMAIL_NON_DISPONIBILE,
            )
        await repository_notifiche.marca_notifica_inviata(
            connessione,
            notifica.id,
        )
        logger.info(
            "notification_email_succeeded",
            extra={
                "notification_id": str(notifica.id),
                "report_id": str(notifica.report_id) if notifica.report_id else None,
            },
        )
        return EsitoElaborazione(stato_dispatch=STATO_NOTIFICA_INVIATA)


def _uuid_da_payload(valore: object) -> uuid.UUID | None:
    if not isinstance(valore, str):
        return None
    try:
        return uuid.UUID(valore)
    except ValueError:
        return None


def _riferimento_pubblico(
    notifica: NotificaDaInviare,
    payload: Mapping[str, object],
) -> str:
    if notifica.public_ref:
        return notifica.public_ref
    riferimento_payload = payload.get("public_ref")
    return (
        riferimento_payload
        if isinstance(riferimento_payload, str) and riferimento_payload
        else "segnalazione"
    )
