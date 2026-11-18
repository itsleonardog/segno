from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.ciclo_vita_segnalazione import (
    ModificaScaduta,
    registra_cambio_stato,
    valida_transizione_operatore,
    verifica_finestra_modifica,
)
from app.dominio.creazione_segnalazione import (
    CategoriaNonValida,
)
from app.dominio.creazione_segnalazione import (
    crea_segnalazione as crea_segnalazione_dominio,
)
from app.dominio.esempio_segnalazione import (
    StatoSegnalazione,
    TransizioneNonAmmessa,
)
from app.dominio.geografia import CoordinateNonValide
from app.dominio.segnalazione import (
    DatiNuovaSegnalazione,
    EventoStatoSegnalazione,
    Segnalazione,
)
from app.infrastruttura import repository_segnalazioni
from app.infrastruttura.dipendenze import (
    connessione_piattaforma,
    connessione_pubblica,
)
from app.infrastruttura.errori import ErroreApi
from app.infrastruttura.idempotenza import (
    ChiaveIdempotenzaInConflitto,
    ElaborazioneIdempotenteInCorso,
    avvia_idempotenza,
    calcola_hash_richiesta,
    completa_idempotenza,
)
from app.infrastruttura.middleware_auth import get_utente_autenticato
from app.presentazione.schemi_segnalazioni import (
    EventoStatoPubblico,
    RichiestaCambioStato,
    RichiestaCreazioneSegnalazione,
    RichiestaModificaSegnalazione,
    RispostaDettaglioSegnalazione,
    RispostaElencoSegnalazioni,
    RispostaSegnalazione,
)

router = APIRouter(tags=["segnalazioni"])

ENDPOINT_CREAZIONE_SEGNALAZIONE = "/v1/reports"
LUNGHEZZA_MASSIMA_CHIAVE_IDEMPOTENZA = 255
NOTA_MODIFICA_SEGNALAZIONE = "La segnalazione è stata modificata dall'autore."

ConnessionePubblica = Annotated[AsyncConnection, Depends(connessione_pubblica)]
ConnessionePiattaforma = Annotated[
    AsyncConnection,
    Depends(connessione_piattaforma),
]
UtenteAutenticato = Annotated[uuid.UUID, Depends(get_utente_autenticato)]


@router.post(
    "/reports",
    response_model=RispostaSegnalazione,
    status_code=201,
)
async def crea_segnalazione(
    richiesta: RichiestaCreazioneSegnalazione,
    utente_id: UtenteAutenticato,
    connessione: ConnessionePiattaforma,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
) -> JSONResponse:
    chiave = _valida_chiave_idempotenza(idempotency_key)
    impronta = calcola_hash_richiesta(richiesta.model_dump(mode="json"))
    try:
        esito_idempotenza = await avvia_idempotenza(
            connessione,
            utente_id=utente_id,
            endpoint=ENDPOINT_CREAZIONE_SEGNALAZIONE,
            chiave=chiave,
            request_hash=impronta,
        )
    except ChiaveIdempotenzaInConflitto as errore:
        raise _chiave_idempotenza_in_conflitto() from errore
    except ElaborazioneIdempotenteInCorso as errore:
        raise _idempotenza_in_corso() from errore

    if esito_idempotenza.risposta_salvata is not None:
        risposta_salvata = esito_idempotenza.risposta_salvata
        return JSONResponse(
            status_code=risposta_salvata.status,
            content=dict(risposta_salvata.corpo),
        )
    if esito_idempotenza.record_id is None:
        raise _idempotenza_in_corso()

    segnalazione = await _crea_segnalazione(connessione, utente_id, richiesta)
    corpo = _risposta_segnalazione(segnalazione).model_dump(mode="json")
    await completa_idempotenza(
        connessione,
        record_id=esito_idempotenza.record_id,
        status=201,
        corpo=corpo,
    )
    return JSONResponse(status_code=201, content=corpo)


@router.get("/reports", response_model=RispostaElencoSegnalazioni)
async def elenca_segnalazioni(
    connessione: ConnessionePubblica,
    lat_min: Annotated[float | None, Query(ge=-90.0, le=90.0)] = None,
    lat_max: Annotated[float | None, Query(ge=-90.0, le=90.0)] = None,
    lng_min: Annotated[float | None, Query(ge=-180.0, le=180.0)] = None,
    lng_max: Annotated[float | None, Query(ge=-180.0, le=180.0)] = None,
    category: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    status: StatoSegnalazione | None = None,
    municipality_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RispostaElencoSegnalazioni:
    filtri = _componi_filtri(
        lat_min=lat_min,
        lat_max=lat_max,
        lng_min=lng_min,
        lng_max=lng_max,
        category=category,
        status=status,
        municipality_id=municipality_id,
    )
    pagine = await repository_segnalazioni.elenca_segnalazioni_pubbliche(
        connessione,
        filtri=filtri,
        cursore=_uuid_da_cursore(cursor),
        limite=limit + 1,
    )
    ha_altre_pagine = len(pagine) > limit
    segnalazioni = pagine[:limit]
    return RispostaElencoSegnalazioni(
        items=[_risposta_segnalazione(voce) for voce in segnalazioni],
        next_cursor=(
            str(segnalazioni[-1].id) if ha_altre_pagine and segnalazioni else None
        ),
    )


@router.get(
    "/reports/{report_id}/status-events",
    response_model=list[EventoStatoPubblico],
)
async def leggi_eventi_stato(
    report_id: uuid.UUID,
    connessione: ConnessionePubblica,
) -> list[EventoStatoPubblico]:
    segnalazione = await repository_segnalazioni.carica_segnalazione_per_id(
        connessione,
        report_id,
    )
    if segnalazione is None:
        raise _segnalazione_non_trovata()
    eventi = await repository_segnalazioni.elenca_eventi_pubblici(
        connessione,
        report_id,
    )
    return [_risposta_evento(evento) for evento in eventi]


@router.get(
    "/reports/{public_ref}",
    response_model=RispostaDettaglioSegnalazione,
)
async def leggi_segnalazione(
    public_ref: str,
    connessione: ConnessionePubblica,
) -> RispostaDettaglioSegnalazione:
    segnalazione = await repository_segnalazioni.carica_segnalazione_per_public_ref(
        connessione,
        public_ref,
    )
    if segnalazione is None:
        raise _segnalazione_non_trovata()
    eventi = await repository_segnalazioni.elenca_eventi_pubblici(
        connessione,
        segnalazione.id,
    )
    risposta = _risposta_segnalazione(segnalazione)
    return RispostaDettaglioSegnalazione(
        **risposta.model_dump(),
        status_events=[_risposta_evento(evento) for evento in eventi],
    )


@router.patch("/reports/{report_id}", response_model=RispostaSegnalazione)
async def modifica_segnalazione(
    report_id: uuid.UUID,
    richiesta: RichiestaModificaSegnalazione,
    utente_id: UtenteAutenticato,
    connessione: ConnessionePiattaforma,
) -> RispostaSegnalazione:
    if not _ha_campi_modificati(richiesta):
        raise _nessuna_modifica()
    segnalazione = await _carica_segnalazione_modificabile(
        connessione,
        report_id,
        utente_id,
    )
    if richiesta.category_id is not None:
        await _verifica_categoria(connessione, richiesta.category_id)
    await repository_segnalazioni.aggiorna_contenuti(
        connessione,
        report_id=report_id,
        title=richiesta.title,
        description=richiesta.description,
        category_id=richiesta.category_id,
    )
    await repository_segnalazioni.inserisci_evento_stato(
        connessione,
        report_id=report_id,
        municipality_id=segnalazione.municipality_id,
        from_status=segnalazione.status,
        to_status=segnalazione.status,
        actor_type="citizen",
        actor_id=utente_id,
        note_public=NOTA_MODIFICA_SEGNALAZIONE,
        is_public=True,
    )
    aggiornata = await _ricarica_segnalazione(connessione, report_id)
    return _risposta_segnalazione(aggiornata)


@router.patch("/reports/{report_id}/status", response_model=RispostaSegnalazione)
async def cambia_stato_segnalazione(
    report_id: uuid.UUID,
    richiesta: RichiestaCambioStato,
    utente_id: UtenteAutenticato,
    connessione: ConnessionePiattaforma,
) -> RispostaSegnalazione:
    if not await repository_segnalazioni.utente_e_operatore(connessione, utente_id):
        raise _operatore_richiesto()
    segnalazione = await _ricarica_segnalazione(connessione, report_id)
    stato_precedente = StatoSegnalazione(segnalazione.status)
    _valida_transizione(stato_precedente, richiesta.status)
    await registra_cambio_stato(
        connessione,
        segnalazione,
        richiesta.status,
        actor_type="municipality",
        actor_id=utente_id,
        note_public=richiesta.note_public,
    )
    aggiornata = await _ricarica_segnalazione(connessione, report_id)
    return _risposta_segnalazione(aggiornata)


async def _crea_segnalazione(
    connessione: AsyncConnection,
    utente_id: uuid.UUID,
    richiesta: RichiestaCreazioneSegnalazione,
) -> Segnalazione:
    dati = DatiNuovaSegnalazione(
        title=richiesta.title,
        description=richiesta.description,
        category_id=richiesta.category_id,
        lat=richiesta.lat,
        lng=richiesta.lng,
        address_text=richiesta.address_text,
        photo_url=richiesta.photo_url,
    )
    try:
        return await crea_segnalazione_dominio(connessione, utente_id, dati)
    except CategoriaNonValida as errore:
        raise _categoria_non_valida() from errore
    except CoordinateNonValide as errore:
        raise _coordinate_non_valide() from errore


async def _carica_segnalazione_modificabile(
    connessione: AsyncConnection,
    report_id: uuid.UUID,
    utente_id: uuid.UUID,
) -> Segnalazione:
    segnalazione = await _ricarica_segnalazione(connessione, report_id)
    if segnalazione.author_id != utente_id:
        raise _modifica_non_consentita()
    if segnalazione.status != StatoSegnalazione.APERTA.value:
        raise _segnalazione_non_modificabile()
    try:
        verifica_finestra_modifica(segnalazione.created_at, datetime.now(UTC))
    except ModificaScaduta as errore:
        raise _modifica_scaduta() from errore
    return segnalazione


async def _ricarica_segnalazione(
    connessione: AsyncConnection,
    report_id: uuid.UUID,
) -> Segnalazione:
    segnalazione = await repository_segnalazioni.carica_segnalazione_per_id(
        connessione,
        report_id,
    )
    if segnalazione is None:
        raise _segnalazione_non_trovata()
    return segnalazione


async def _verifica_categoria(
    connessione: AsyncConnection,
    category_id: uuid.UUID,
) -> None:
    if not await repository_segnalazioni.categoria_e_attiva(
        connessione,
        category_id,
    ):
        raise _categoria_non_valida()


def _valida_transizione(
    stato_precedente: StatoSegnalazione,
    stato_successivo: StatoSegnalazione,
) -> None:
    try:
        valida_transizione_operatore(stato_precedente, stato_successivo)
    except TransizioneNonAmmessa as errore:
        raise _transizione_non_ammessa() from errore


def _componi_filtri(
    *,
    lat_min: float | None,
    lat_max: float | None,
    lng_min: float | None,
    lng_max: float | None,
    category: str | None,
    status: StatoSegnalazione | None,
    municipality_id: uuid.UUID | None,
) -> repository_segnalazioni.FiltriElencoSegnalazioni:
    _valida_riquadro(lat_min, lat_max, lng_min, lng_max)
    return repository_segnalazioni.FiltriElencoSegnalazioni(
        lat_min=lat_min,
        lat_max=lat_max,
        lng_min=lng_min,
        lng_max=lng_max,
        category=category,
        status=status.value if status is not None else None,
        municipality_id=municipality_id,
    )


def _valida_riquadro(
    lat_min: float | None,
    lat_max: float | None,
    lng_min: float | None,
    lng_max: float | None,
) -> None:
    valori = (lat_min, lat_max, lng_min, lng_max)
    if not any(valore is not None for valore in valori):
        return
    if not all(valore is not None for valore in valori):
        raise ErroreApi(
            status=422,
            titolo="Riquadro incompleto",
            dettaglio=(
                "Per filtrare per area indica lat_min, lat_max, lng_min e lng_max."
            ),
        )
    if lat_min > lat_max or lng_min > lng_max:
        raise ErroreApi(
            status=422,
            titolo="Riquadro non valido",
            dettaglio="I limiti del riquadro non sono coerenti. Correggili e riprova.",
        )


def _valida_chiave_idempotenza(chiave: str | None) -> str:
    if chiave is None or not chiave.strip():
        raise ErroreApi(
            status=400,
            titolo="Idempotenza richiesta",
            dettaglio=("Per creare una segnalazione invia l'header Idempotency-Key."),
        )
    chiave_normalizzata = chiave.strip()
    if len(chiave_normalizzata) > LUNGHEZZA_MASSIMA_CHIAVE_IDEMPOTENZA:
        raise ErroreApi(
            status=400,
            titolo="Idempotenza non valida",
            dettaglio=(
                "La chiave di idempotenza è troppo lunga. " "Usa una chiave più corta."
            ),
        )
    return chiave_normalizzata


def _uuid_da_cursore(cursore: str | None) -> uuid.UUID | None:
    if cursore is None:
        return None
    try:
        return uuid.UUID(cursore)
    except ValueError as errore:
        raise ErroreApi(
            status=422,
            titolo="Cursore non valido",
            dettaglio=(
                "Il cursore di paginazione non è valido. " "Riparti dalla prima pagina."
            ),
        ) from errore


def _ha_campi_modificati(richiesta: RichiestaModificaSegnalazione) -> bool:
    return (
        richiesta.title is not None
        or richiesta.description is not None
        or richiesta.category_id is not None
    )


def _risposta_segnalazione(segnalazione: Segnalazione) -> RispostaSegnalazione:
    return RispostaSegnalazione(
        id=segnalazione.id,
        public_ref=segnalazione.public_ref,
        municipality_id=segnalazione.municipality_id,
        author_id=segnalazione.author_id,
        category_id=segnalazione.category_id,
        title=segnalazione.title,
        description=segnalazione.description,
        lat=segnalazione.lat,
        lng=segnalazione.lng,
        address_text=segnalazione.address_text,
        status=segnalazione.status,
        visibility=segnalazione.visibility,
        dispatch_state=segnalazione.dispatch_state,
        boundary_ambiguous=segnalazione.boundary_ambiguous,
        created_at=segnalazione.created_at,
    )


def _risposta_evento(evento: EventoStatoSegnalazione) -> EventoStatoPubblico:
    return EventoStatoPubblico(
        id=evento.id,
        from_status=evento.from_status,
        to_status=evento.to_status,
        actor_type=evento.actor_type,
        note_public=evento.note_public,
        created_at=evento.created_at,
    )


def _segnalazione_non_trovata() -> ErroreApi:
    return ErroreApi(
        status=404,
        titolo="Segnalazione non trovata",
        dettaglio="La segnalazione richiesta non esiste o non è pubblica.",
    )


def _modifica_non_consentita() -> ErroreApi:
    return ErroreApi(
        status=403,
        titolo="Modifica non consentita",
        dettaglio="Puoi modificare solo le segnalazioni che hai creato.",
    )


def _segnalazione_non_modificabile() -> ErroreApi:
    return ErroreApi(
        status=409,
        titolo="Segnalazione non modificabile",
        dettaglio=("La segnalazione può essere modificata solo mentre è aperta."),
    )


def _modifica_scaduta() -> ErroreApi:
    return ErroreApi(
        status=400,
        titolo="Modifica scaduta",
        dettaglio="Il termine per modificare la segnalazione è trascorso.",
    )


def _nessuna_modifica() -> ErroreApi:
    return ErroreApi(
        status=400,
        titolo="Nessuna modifica",
        dettaglio="Indica almeno un campo da modificare.",
    )


def _categoria_non_valida() -> ErroreApi:
    return ErroreApi(
        status=422,
        titolo="Categoria non valida",
        dettaglio="La categoria scelta non è disponibile. Scegline un'altra.",
    )


def _coordinate_non_valide() -> ErroreApi:
    return ErroreApi(
        status=422,
        titolo="Coordinate non valide",
        dettaglio="Le coordinate indicate non sono valide. Controllale e riprova.",
    )


def _operatore_richiesto() -> ErroreApi:
    return ErroreApi(
        status=403,
        titolo="Operazione non consentita",
        dettaglio=(
            "Solo un operatore comunale può cambiare lo stato della segnalazione."
        ),
    )


def _transizione_non_ammessa() -> ErroreApi:
    return ErroreApi(
        status=400,
        titolo="Cambio di stato non ammesso",
        dettaglio="La segnalazione non può passare allo stato richiesto.",
    )


def _chiave_idempotenza_in_conflitto() -> ErroreApi:
    return ErroreApi(
        status=409,
        titolo="Chiave di idempotenza già usata",
        dettaglio=(
            "La chiave di idempotenza è già stata usata con dati diversi. "
            "Usane una nuova per questa richiesta."
        ),
    )


def _idempotenza_in_corso() -> ErroreApi:
    return ErroreApi(
        status=409,
        titolo="Richiesta in elaborazione",
        dettaglio=(
            "Una richiesta con questa chiave è ancora in elaborazione. "
            "Riprova tra qualche istante."
        ),
    )
