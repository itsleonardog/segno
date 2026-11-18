from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncConnection

from app.infrastruttura import repository_autenticazione
from app.infrastruttura.cifratura_email import (
    CifrarioEmailEnvelope,
    EmailCipher,
)
from app.infrastruttura.configurazione import (
    decodifica_segreto_base64,
    leggi_configurazione_dispatch,
    leggi_configurazione_sicurezza,
)
from app.infrastruttura.database import transazione_con_contesto
from app.infrastruttura.email_sender import EmailSender, LoggingEmailSender
from app.infrastruttura.errori import ErroreApi
from app.infrastruttura.middleware_auth import get_utente_autenticato

NOME_SEGRETO_KEK = "CIVIC_EMAIL_KEK"
NOME_SEGRETO_PEPPER = "CIVIC_EMAIL_LOOKUP_PEPPER"


def get_cifrario_email() -> EmailCipher:
    configurazione = leggi_configurazione_sicurezza()
    chiave = decodifica_segreto_base64(
        configurazione.chiave_cifratura_base64,
        NOME_SEGRETO_KEK,
    )
    return CifrarioEmailEnvelope(chiave)


def get_pepper_lookup_email() -> bytes:
    configurazione = leggi_configurazione_sicurezza()
    return decodifica_segreto_base64(
        configurazione.pepper_lookup_base64,
        NOME_SEGRETO_PEPPER,
    )


def get_email_sender() -> EmailSender:
    configurazione = leggi_configurazione_sicurezza()
    configurazione_dispatch = leggi_configurazione_dispatch()
    return LoggingEmailSender(
        ambiente=configurazione.ambiente,
        indirizzo_mittente=configurazione_dispatch.indirizzo_mittente,
    )


@dataclass(frozen=True, slots=True)
class ContestoOperatore:
    connessione: AsyncConnection
    utente_id: uuid.UUID
    municipality_id: uuid.UUID


async def connessione_pubblica(
    request: Request,
) -> AsyncIterator[AsyncConnection]:
    """Apre una transazione in scope pubblico per le letture anonime."""
    async with transazione_con_contesto(
        request.app.state.motore,
        scope="public",
    ) as connessione:
        yield connessione


async def connessione_piattaforma(
    request: Request,
) -> AsyncIterator[AsyncConnection]:
    """Apre una transazione in scope piattaforma per la scrittura delle segnalazioni."""
    # La risoluzione interroga il registro globale dei comuni e una segnalazione
    # fuori copertura ha municipality_id NULL: l'autorizzazione resta verificata
    # sull'utente autenticato prima di ogni scrittura.
    async with transazione_con_contesto(
        request.app.state.motore,
        scope="platform",
    ) as connessione:
        yield connessione


async def contesto_operatore(
    request: Request,
) -> AsyncIterator[ContestoOperatore]:
    """Apre una transazione amministrativa solo per operatori con un comune."""
    utente_id = get_utente_autenticato(request)
    async with transazione_con_contesto(
        request.app.state.motore,
        scope="platform",
        user_id=str(utente_id),
    ) as connessione:
        utente = await repository_autenticazione.trova_utente_per_id(
            connessione,
            utente_id,
        )
        if utente is None or not utente.is_operatore:
            raise ErroreApi(
                status=403,
                titolo="Operazione non consentita",
                dettaglio=(
                    "Questa area è riservata agli operatori comunali. "
                    "Effettua l'accesso con un account operatore."
                ),
            )
        if utente.municipality_id is None:
            raise ErroreApi(
                status=403,
                titolo="Comune non associato",
                dettaglio=(
                    "L'account operatore non è associato a un comune. "
                    "Chiedi di completare la configurazione."
                ),
            )
        yield ContestoOperatore(
            connessione=connessione,
            utente_id=utente_id,
            municipality_id=utente.municipality_id,
        )
