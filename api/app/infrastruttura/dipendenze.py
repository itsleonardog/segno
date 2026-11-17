from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncConnection

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
