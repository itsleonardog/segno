"""Endpoint di autenticazione e gestione delle sessioni.

access_scope='system' è confinato a questo modulo: registrazione, verifica
email, login, refresh e recupero password avvengono prima che esista un
user_id autenticato e devono poter cercare l'utente per email. Tutti gli altri
endpoint usano il contesto tenant con app.tenant_id=NULL e app.user_id valorizzato,
così le policy su user e refresh_token restano applicate.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.autenticazione import (
    DURATA_ACCESS_TOKEN_SECONDI,
    DURATA_TOKEN_RESET_ORE,
    DURATA_TOKEN_VERIFICA_ORE,
    ErroreRiusoToken,
    PasswordNonValida,
    TokenNonValido,
    crea_access_token,
    crea_refresh_token,
    genera_token_opaco,
    hash_password,
    hash_token_opaco,
    maschera_email,
    valida_password,
    valida_refresh_token,
    verifica_password,
)
from app.infrastruttura.cifratura_email import (
    EmailCipher,
    EmailNonValido,
    calcola_hash_lookup_email,
)
from app.infrastruttura.database import transazione_con_contesto
from app.infrastruttura.dipendenze import (
    get_cifrario_email,
    get_email_sender,
    get_pepper_lookup_email,
)
from app.infrastruttura.email_sender import EmailSender
from app.infrastruttura.errori import ErroreApi
from app.infrastruttura.middleware_auth import (
    connessione_tenant,
    get_utente_autenticato,
)
from app.infrastruttura.repository_autenticazione import (
    aggiorna_last_login,
    aggiorna_password_hash,
    consuma_token_reset,
    consuma_token_verifica,
    crea_token_reset,
    crea_token_verifica,
    crea_utente,
    invalida_token_reset_pendenti,
    lista_sessioni_attive,
    marca_email_verificata,
    registra_audit,
    revoca_famiglia,
    revoca_refresh_token,
    revoca_sessione,
    revoca_tutte_le_famiglie,
    rileva_conflitti_registrazione,
    trova_refresh_token_per_hash,
    trova_utente_per_email_lookup_hash,
)
from app.infrastruttura.repository_autenticazione import (
    crea_refresh_token as persisti_refresh_token,
)
from app.presentazione.schemi_auth import (
    RichiestaLogin,
    RichiestaLogout,
    RichiestaPasswordDimenticata,
    RichiestaRefresh,
    RichiestaRegistrazione,
    RichiestaResetPassword,
    RichiestaVerificaEmail,
    RispostaRegistrazione,
    RispostaSessione,
    RispostaToken,
)

router = APIRouter(prefix="/auth", tags=["autenticazione"])

URL_VERIFICA_EMAIL = "http://localhost:5173/verifica-email?token="
URL_RESET_PASSWORD = "http://localhost:5173/reimposta-password?token="

DETTAGLIO_CONFLITTO_REGISTRAZIONE = (
    "Non è stato possibile completare la registrazione: esiste già un account "
    "con i dati indicati."
)
DETTAGLIO_CREDENZIALI_NON_VALIDE = (
    "Email o password non corretti. Controlla i dati e riprova."
)
DETTAGLIO_ACCOUNT_NON_ATTIVO = (
    "L'account non è attivo. Contatta l'assistenza per ripristinare l'accesso."
)
DETTAGLIO_TOKEN_SESSIONE_NON_VALIDO = (
    "La sessione non è valida. Effettua di nuovo l'accesso."
)
DETTAGLIO_TOKEN_PASSWORD_NON_VALIDO = (
    "Il link per reimpostare la password non è valido o è scaduto. "
    "Richiedine uno nuovo."
)
DETTAGLIO_TOKEN_VERIFICA_NON_VALIDO = (
    "Il link di verifica non è valido o è scaduto. Richiedine uno nuovo."
)

AZIONE_AUDIT_RIUSO_REFRESH = "refresh_token_reuse"

# Verifica contro un hash reale anche quando l'utente non esiste: riduce la
# differenza di tempo osservabile tra email registrata e non registrata.
HASH_PASSWORD_FITTIZIO = hash_password("password-fittizia-non-utilizzabile-01")


async def _connessione_system(request: Request) -> AsyncIterator[AsyncConnection]:
    async with transazione_con_contesto(
        request.app.state.motore,
        scope="system",
    ) as connessione:
        yield connessione


ConnessioneSystem = Annotated[AsyncConnection, Depends(_connessione_system)]
ConnessioneTenant = Annotated[AsyncConnection, Depends(connessione_tenant)]
UtenteAutenticato = Annotated[uuid.UUID, Depends(get_utente_autenticato)]
CifrarioEmail = Annotated[EmailCipher, Depends(get_cifrario_email)]
PepperLookup = Annotated[bytes, Depends(get_pepper_lookup_email)]
InvioEmail = Annotated[EmailSender, Depends(get_email_sender)]


@router.post(
    "/register",
    response_model=RispostaRegistrazione,
    status_code=201,
)
async def registra(
    richiesta: RichiestaRegistrazione,
    connessione: ConnessioneSystem,
    cifrario: CifrarioEmail,
    pepper: PepperLookup,
    invio_email: InvioEmail,
) -> RispostaRegistrazione:
    _valida_password_utente(richiesta.password)
    lookup_hash = _calcola_lookup(richiesta.email, pepper)
    email_presente, nickname_presente = await rileva_conflitti_registrazione(
        connessione,
        lookup_hash=lookup_hash,
        nickname=richiesta.nickname,
    )
    if email_presente or nickname_presente:
        raise _conflitto_registrazione()

    email_enc, key_id = cifrario.cifra(str(richiesta.email))
    try:
        utente_id = await crea_utente(
            connessione,
            nickname=richiesta.nickname,
            email_enc=email_enc,
            email_key_id=key_id,
            email_lookup_hash=lookup_hash,
            password_hash=hash_password(richiesta.password),
            privacy_policy_version=richiesta.privacy_policy_version,
            tos_version=richiesta.tos_version,
        )
    except IntegrityError as errore:
        raise _conflitto_registrazione() from errore

    token_verifica = genera_token_opaco()
    await crea_token_verifica(
        connessione,
        user_id=utente_id,
        token_hash=hash_token_opaco(token_verifica),
        expires_at=datetime.now(UTC) + timedelta(hours=DURATA_TOKEN_VERIFICA_ORE),
    )
    invio_email.invia(
        str(richiesta.email),
        "Conferma il tuo indirizzo email",
        "Apri questo indirizzo per confermare la tua email: "
        f"{URL_VERIFICA_EMAIL}{token_verifica}",
    )
    return RispostaRegistrazione(
        id=utente_id,
        nickname=richiesta.nickname,
        email_masked=maschera_email(str(richiesta.email)),
        email_verified_at=None,
    )


@router.post("/verify-email", status_code=204)
async def verifica_email(
    richiesta: RichiestaVerificaEmail,
    connessione: ConnessioneSystem,
) -> Response:
    utente_id = await consuma_token_verifica(
        connessione,
        hash_token_opaco(richiesta.token),
    )
    if utente_id is None:
        raise _errore_token_non_valido(DETTAGLIO_TOKEN_VERIFICA_NON_VALIDO)
    await marca_email_verificata(connessione, utente_id)
    return Response(status_code=204)


@router.post("/login", response_model=RispostaToken)
async def login(
    richiesta: RichiestaLogin,
    request: Request,
    connessione: ConnessioneSystem,
    pepper: PepperLookup,
) -> RispostaToken:
    lookup_hash = _calcola_lookup(richiesta.email, pepper)
    utente = await trova_utente_per_email_lookup_hash(connessione, lookup_hash)
    hash_da_verificare = (
        utente.password_hash if utente is not None else HASH_PASSWORD_FITTIZIO
    )
    if utente is None or not verifica_password(richiesta.password, hash_da_verificare):
        raise _credenziali_non_valide()
    if utente.status != "active":
        raise _account_non_attivo()

    access_token = crea_access_token(utente.id)
    refresh_token, dati_refresh = crea_refresh_token(utente.id)
    await persisti_refresh_token(
        connessione,
        identificativo=dati_refresh.id,
        user_id=dati_refresh.user_id,
        family_id=dati_refresh.family_id,
        token_hash=dati_refresh.token_hash,
        expires_at=dati_refresh.expires_at,
        user_agent_summary=_riassumi_user_agent(request.headers.get("user-agent")),
    )
    await aggiorna_last_login(connessione, utente.id)
    return RispostaToken(
        access_token=access_token,
        expires_in=DURATA_ACCESS_TOKEN_SECONDI,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=RispostaToken)
async def rinnova_sessione(
    richiesta: RichiestaRefresh,
    request: Request,
) -> RispostaToken:
    dati_token = _valida_refresh_o_401(richiesta.refresh_token)
    risposta: RispostaToken | None = None
    riuso_rilevato = False

    # La transazione è aperta qui e non nella dependency: se il riuso viene
    # rilevato, la revoca della famiglia deve essere committata prima del 401.
    async with transazione_con_contesto(
        request.app.state.motore,
        scope="system",
    ) as connessione:
        riga = await trova_refresh_token_per_hash(
            connessione,
            dati_token.token_hash,
            blocca_riga=True,
        )
        if riga is None or riga.user_id != dati_token.user_id:
            raise _sessione_non_valida()
        if riga.revoked_at is not None:
            await revoca_famiglia(connessione, riga.family_id)
            await registra_audit(
                connessione,
                actor_type="system",
                actor_id=None,
                action=AZIONE_AUDIT_RIUSO_REFRESH,
                entity_type="refresh_token",
                entity_id=riga.id,
            )
            riuso_rilevato = True
        else:
            access_token = crea_access_token(riga.user_id)
            nuovo_token, nuovi_dati = crea_refresh_token(riga.user_id, riga.family_id)
            await persisti_refresh_token(
                connessione,
                identificativo=nuovi_dati.id,
                user_id=nuovi_dati.user_id,
                family_id=nuovi_dati.family_id,
                token_hash=nuovi_dati.token_hash,
                expires_at=nuovi_dati.expires_at,
                user_agent_summary=_riassumi_user_agent(
                    request.headers.get("user-agent")
                ),
            )
            await revoca_refresh_token(
                connessione,
                token_id=riga.id,
                replaced_by=nuovi_dati.id,
            )
            risposta = RispostaToken(
                access_token=access_token,
                expires_in=DURATA_ACCESS_TOKEN_SECONDI,
                refresh_token=nuovo_token,
            )

    if riuso_rilevato:
        raise ErroreRiusoToken("Il refresh token è già stato revocato.")
    if risposta is None:
        raise _sessione_non_valida()
    return risposta


@router.post("/logout", status_code=204)
async def logout(
    richiesta: RichiestaLogout,
    utente_id: UtenteAutenticato,
    connessione: ConnessioneTenant,
) -> Response:
    riga = await trova_refresh_token_per_hash(
        connessione,
        hash_token_opaco(richiesta.refresh_token),
    )
    if riga is not None and riga.user_id == utente_id:
        await revoca_refresh_token(connessione, token_id=riga.id)
    return Response(status_code=204)


@router.post("/logout-all", status_code=204)
async def logout_all(
    utente_id: UtenteAutenticato,
    connessione: ConnessioneTenant,
) -> Response:
    await revoca_tutte_le_famiglie(connessione, utente_id)
    return Response(status_code=204)


@router.post("/password/forgot", status_code=202)
async def password_dimenticata(
    richiesta: RichiestaPasswordDimenticata,
    connessione: ConnessioneSystem,
    pepper: PepperLookup,
    invio_email: InvioEmail,
) -> Response:
    lookup_hash = _calcola_lookup(richiesta.email, pepper)
    utente = await trova_utente_per_email_lookup_hash(connessione, lookup_hash)
    if utente is not None:
        token_reset = genera_token_opaco()
        await crea_token_reset(
            connessione,
            user_id=utente.id,
            token_hash=hash_token_opaco(token_reset),
            expires_at=datetime.now(UTC) + timedelta(hours=DURATA_TOKEN_RESET_ORE),
        )
        invio_email.invia(
            str(richiesta.email),
            "Reimposta la password",
            "Apri questo indirizzo per reimpostare la password: "
            f"{URL_RESET_PASSWORD}{token_reset}",
        )
    return Response(status_code=202)


@router.post("/password/reset", status_code=204)
async def reset_password(
    richiesta: RichiestaResetPassword,
    connessione: ConnessioneSystem,
) -> Response:
    utente_id = await consuma_token_reset(
        connessione,
        hash_token_opaco(richiesta.token),
    )
    if utente_id is None:
        raise _errore_token_non_valido(DETTAGLIO_TOKEN_PASSWORD_NON_VALIDO)
    _valida_password_utente(richiesta.new_password)
    await aggiorna_password_hash(
        connessione,
        user_id=utente_id,
        password_hash=hash_password(richiesta.new_password),
    )
    await revoca_tutte_le_famiglie(connessione, utente_id)
    await invalida_token_reset_pendenti(connessione, utente_id)
    return Response(status_code=204)


@router.get("/sessions", response_model=list[RispostaSessione])
async def sessioni(
    utente_id: UtenteAutenticato,
    connessione: ConnessioneTenant,
) -> list[RispostaSessione]:
    return [
        RispostaSessione(
            id=sessione.id,
            created_at=sessione.created_at,
            last_used_at=sessione.last_used_at,
            user_agent_summary=sessione.user_agent_summary,
        )
        for sessione in await lista_sessioni_attive(connessione, utente_id)
    ]


@router.delete("/sessions/{sessione_id}", status_code=204)
async def revoca_sessione_corrente(
    sessione_id: uuid.UUID,
    utente_id: UtenteAutenticato,
    connessione: ConnessioneTenant,
) -> Response:
    await revoca_sessione(
        connessione,
        user_id=utente_id,
        sessione_id=sessione_id,
    )
    return Response(status_code=204)


def _valida_password_utente(password: str) -> None:
    try:
        valida_password(password)
    except PasswordNonValida as errore:
        raise ErroreApi(
            status=400,
            titolo="Password non valida",
            dettaglio=str(errore),
        ) from errore


def _calcola_lookup(email: str, pepper: bytes) -> str:
    try:
        return calcola_hash_lookup_email(email, pepper)
    except EmailNonValido as errore:
        raise ErroreApi(
            status=422,
            titolo="Email non valida",
            dettaglio="L'indirizzo email non è valido. Controlla e riprova.",
        ) from errore


def _valida_refresh_o_401(token: str):
    try:
        return valida_refresh_token(token)
    except TokenNonValido as errore:
        raise _sessione_non_valida() from errore


def _conflitto_registrazione() -> ErroreApi:
    return ErroreApi(
        status=409,
        titolo="Registrazione non possibile",
        dettaglio=DETTAGLIO_CONFLITTO_REGISTRAZIONE,
    )


def _credenziali_non_valide() -> ErroreApi:
    return ErroreApi(
        status=401,
        titolo="Accesso non riuscito",
        dettaglio=DETTAGLIO_CREDENZIALI_NON_VALIDE,
    )


def _account_non_attivo() -> ErroreApi:
    return ErroreApi(
        status=403,
        titolo="Account non attivo",
        dettaglio=DETTAGLIO_ACCOUNT_NON_ATTIVO,
    )


def _sessione_non_valida() -> ErroreApi:
    return ErroreApi(
        status=401,
        titolo="Autenticazione richiesta",
        dettaglio=DETTAGLIO_TOKEN_SESSIONE_NON_VALIDO,
    )


def _errore_token_non_valido(dettaglio: str) -> ErroreApi:
    return ErroreApi(
        status=400,
        titolo="Token non valido",
        dettaglio=dettaglio,
    )


def _riassumi_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return " ".join(user_agent.split())[:120]
