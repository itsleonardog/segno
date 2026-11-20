from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.autenticazione import maschera_email, verifica_password
from app.dominio.gdpr import (
    AZIONE_AUDIT_ACCOUNT_ANONIMIZZATO,
    EsportazioneUtente,
    ProfiloEsportato,
)
from app.infrastruttura import repository_gdpr
from app.infrastruttura.cifratura_email import EmailCipher
from app.infrastruttura.dipendenze import connessione_piattaforma, get_cifrario_email
from app.infrastruttura.errori import ErroreApi
from app.infrastruttura.middleware_auth import (
    connessione_tenant,
    get_utente_autenticato,
)
from app.infrastruttura.repository_autenticazione import (
    UtentePersistito,
    aggiorna_locale,
    aggiorna_nickname,
    registra_audit,
    revoca_tutte_le_famiglie,
    trova_utente_per_id,
)
from app.presentazione.schemi_auth import (
    RichiestaAggiornamentoMe,
    RichiestaCancellazioneAccount,
    RispostaMe,
)

router = APIRouter(tags=["profilo"])

DETTAGLIO_NICKNAME_DUPLICATO = "Il nickname scelto è già in uso. Scegline un altro."
DETTAGLIO_PROFILO_NON_DISPONIBILE = (
    "Il profilo non è disponibile. Effettua di nuovo l'accesso."
)
DETTAGLIO_PASSWORD_NON_CORRETTA = (
    "La password indicata non è corretta. Riprova per confermare la cancellazione."
)
EMAIL_NON_DISPONIBILE = "email non disponibile"
NOME_FILE_ESPORTAZIONE = "segno-dati-personali.json"

ConnessioneTenant = Annotated[AsyncConnection, Depends(connessione_tenant)]
ConnessionePiattaforma = Annotated[
    AsyncConnection,
    Depends(connessione_piattaforma),
]
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


@router.get("/me/export")
async def esporta_dati(
    utente_id: UtenteAutenticato,
    connessione: ConnessionePiattaforma,
    cifrario: CifrarioEmail,
) -> Response:
    utente = await _carica_utente(connessione, utente_id)
    esportazione = EsportazioneUtente(
        generata_il=datetime.now(UTC),
        profilo=_profilo_esportato(utente, cifrario),
        segnalazioni=tuple(
            await repository_gdpr.elenca_segnalazioni_autore(connessione, utente_id)
        ),
        eventi=tuple(
            await repository_gdpr.elenca_eventi_autore(connessione, utente_id)
        ),
        notifiche=tuple(
            await repository_gdpr.elenca_notifiche_autore(connessione, utente_id)
        ),
    )
    corpo = json.dumps(esportazione.come_dizionario(), ensure_ascii=False)
    return Response(
        content=corpo,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{NOME_FILE_ESPORTAZIONE}"'
        },
    )


@router.delete("/me", status_code=204)
async def cancella_account(
    richiesta: RichiestaCancellazioneAccount,
    utente_id: UtenteAutenticato,
    connessione: ConnessionePiattaforma,
) -> Response:
    utente = await _carica_utente(connessione, utente_id)
    if utente.password_hash is None or not verifica_password(
        richiesta.password,
        utente.password_hash,
    ):
        raise ErroreApi(
            status=403,
            titolo="Password non corretta",
            dettaglio=DETTAGLIO_PASSWORD_NON_CORRETTA,
        )
    await repository_gdpr.anonimizza_utente(connessione, utente_id)
    await repository_gdpr.azzera_riferimenti_autore(connessione, utente_id)
    await repository_gdpr.invalida_token_pendenti(connessione, utente_id)
    await revoca_tutte_le_famiglie(connessione, utente_id)
    await registra_audit(
        connessione,
        actor_type="citizen",
        actor_id=utente_id,
        action=AZIONE_AUDIT_ACCOUNT_ANONIMIZZATO,
        entity_type="user",
        entity_id=utente_id,
    )
    return Response(status_code=204)


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
    email = _email_in_chiaro(utente, cifrario)
    return RispostaMe(
        id=utente.id,
        nickname=utente.nickname,
        email_masked=(
            maschera_email(email) if email is not None else EMAIL_NON_DISPONIBILE
        ),
        email_verified_at=utente.email_verified_at,
        status=utente.status,
        created_at=utente.created_at,
        last_login_at=utente.last_login_at,
        locale=utente.locale,
        privacy_policy_version=utente.privacy_policy_version,
        tos_version=utente.tos_version,
        is_operatore=utente.is_operatore,
        municipality_id=utente.municipality_id,
    )


def _profilo_esportato(
    utente: UtentePersistito,
    cifrario: EmailCipher,
) -> ProfiloEsportato:
    return ProfiloEsportato(
        id=utente.id,
        nickname=utente.nickname,
        email=_email_in_chiaro(utente, cifrario),
        status=utente.status,
        email_verified_at=utente.email_verified_at,
        created_at=utente.created_at,
        last_login_at=utente.last_login_at,
        locale=utente.locale,
        privacy_policy_version=utente.privacy_policy_version,
        tos_version=utente.tos_version,
        is_operatore=utente.is_operatore,
        municipality_id=utente.municipality_id,
    )


def _email_in_chiaro(
    utente: UtentePersistito,
    cifrario: EmailCipher,
) -> str | None:
    if utente.email_enc is None or utente.email_key_id is None:
        return None
    return cifrario.decifra(utente.email_enc, utente.email_key_id)
