from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.autenticazione import maschera_email
from app.infrastruttura.cifratura_email import EmailCipher
from app.infrastruttura.dipendenze import get_cifrario_email
from app.infrastruttura.errori import ErroreApi
from app.infrastruttura.middleware_auth import (
    connessione_tenant,
    get_utente_autenticato,
)
from app.infrastruttura.repository_autenticazione import (
    UtentePersistito,
    aggiorna_locale,
    aggiorna_nickname,
    trova_utente_per_id,
)
from app.presentazione.schemi_auth import (
    RichiestaAggiornamentoMe,
    RispostaMe,
)

router = APIRouter(tags=["profilo"])

DETTAGLIO_NICKNAME_DUPLICATO = "Il nickname scelto è già in uso. Scegline un altro."
DETTAGLIO_PROFILO_NON_DISPONIBILE = (
    "Il profilo non è disponibile. Effettua di nuovo l'accesso."
)

ConnessioneTenant = Annotated[AsyncConnection, Depends(connessione_tenant)]
UtenteAutenticato = Annotated[uuid.UUID, Depends(get_utente_autenticato)]
CifrarioEmail = Annotated[EmailCipher, Depends(get_cifrario_email)]


@router.get("/me", response_model=RispostaMe)
async def leggi_profilo(
    utente_id: UtenteAutenticato,
    connessione: ConnessioneTenant,
    cifrario: CifrarioEmail,
) -> RispostaMe:
    utente = await _carica_utente(connessione, utente_id)
    return _risposta_me(utente, cifrario)


@router.patch("/me", response_model=RispostaMe)
async def aggiorna_profilo(
    richiesta: RichiestaAggiornamentoMe,
    utente_id: UtenteAutenticato,
    connessione: ConnessioneTenant,
    cifrario: CifrarioEmail,
) -> RispostaMe:
    if richiesta.nickname is not None:
        try:
            await aggiorna_nickname(
                connessione,
                user_id=utente_id,
                nickname=richiesta.nickname,
            )
        except IntegrityError as errore:
            raise ErroreApi(
                status=409,
                titolo="Nickname non disponibile",
                dettaglio=DETTAGLIO_NICKNAME_DUPLICATO,
            ) from errore
    if richiesta.locale is not None:
        await aggiorna_locale(
            connessione,
            user_id=utente_id,
            locale=richiesta.locale,
        )
    utente = await _carica_utente(connessione, utente_id)
    return _risposta_me(utente, cifrario)


async def _carica_utente(
    connessione: AsyncConnection,
    utente_id: uuid.UUID,
) -> UtentePersistito:
    utente = await trova_utente_per_id(connessione, utente_id)
    if utente is None:
        raise ErroreApi(
            status=401,
            titolo="Autenticazione richiesta",
            dettaglio=DETTAGLIO_PROFILO_NON_DISPONIBILE,
        )
    return utente


def _risposta_me(utente: UtentePersistito, cifrario: EmailCipher) -> RispostaMe:
    email = cifrario.decifra(utente.email_enc, utente.email_key_id)
    return RispostaMe(
        id=utente.id,
        nickname=utente.nickname,
        email_masked=maschera_email(email),
        email_verified_at=utente.email_verified_at,
        status=utente.status,
        created_at=utente.created_at,
        last_login_at=utente.last_login_at,
        locale=utente.locale,
        privacy_policy_version=utente.privacy_policy_version,
        tos_version=utente.tos_version,
    )
