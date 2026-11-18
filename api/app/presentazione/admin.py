from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dominio.dispatch import EVENTO_DISPATCH_RITENTATIVO
from app.dominio.esempio_segnalazione import StatoSegnalazione
from app.dominio.segnalazione import Segnalazione
from app.infrastruttura import repository_amministrazione, repository_segnalazioni
from app.infrastruttura.dipendenze import ContestoOperatore, contesto_operatore
from app.infrastruttura.errori import ErroreApi
from app.infrastruttura.outbox import inserisci_evento_outbox
from app.presentazione.schemi_admin import (
    EventoStatoAmministrazioneRisposta,
    NotaInternaRisposta,
    RichiestaNotaInterna,
    RispostaDettaglioAmministrazione,
    RispostaElencoAmministrazione,
    RispostaElencoFallimenti,
    RispostaFallimentoDispatch,
    RispostaRiprogrammazioneDispatch,
    TentativoDispatchRisposta,
)
from app.presentazione.schemi_segnalazioni import RispostaSegnalazione

router = APIRouter(tags=["amministrazione"])

ContestoOperatoreDep = Annotated[ContestoOperatore, Depends(contesto_operatore)]
LIMITE_FALLIMENTI_PREDEFINITO = 50


@router.get(
    "/admin/reports",
    response_model=RispostaElencoAmministrazione,
)
async def elenca_report_amministrazione(
    contesto: ContestoOperatoreDep,
    status: StatoSegnalazione | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RispostaElencoAmministrazione:
    segnalazioni = await repository_segnalazioni.elenca_segnalazioni_amministrazione(
        contesto.connessione,
        municipality_id=contesto.municipality_id,
        stato=status.value if status is not None else None,
        cursore=_uuid_da_cursore(cursor),
        limite=limit + 1,
    )
    ha_altre_pagine = len(segnalazioni) > limit
    pagina = segnalazioni[:limit]
    return RispostaElencoAmministrazione(
        items=[_risposta_segnalazione(voce) for voce in pagina],
        next_cursor=(str(pagina[-1].id) if ha_altre_pagine and pagina else None),
    )


@router.get(
    "/admin/reports/{report_id}",
    response_model=RispostaDettaglioAmministrazione,
)
async def leggi_report_amministrazione(
    report_id: uuid.UUID,
    contesto: ContestoOperatoreDep,
) -> RispostaDettaglioAmministrazione:
    segnalazione = await _carica_segnalazione_del_comune(contesto, report_id)
    eventi = await repository_amministrazione.elenca_eventi_stato_completi(
        contesto.connessione,
        report_id,
    )
    tentativi = await repository_amministrazione.elenca_tentativi_dispatch(
        contesto.connessione,
        report_id,
    )
    note = await repository_amministrazione.elenca_note_interne(
        contesto.connessione,
        report_id,
    )
    return RispostaDettaglioAmministrazione(
        **_risposta_segnalazione(segnalazione).model_dump(),
        status_events=[_risposta_evento(evento) for evento in eventi],
        dispatch_history=[_risposta_tentativo(tentativo) for tentativo in tentativi],
        internal_notes=[_risposta_nota(nota) for nota in note],
    )


@router.post(
    "/admin/reports/{report_id}/comments",
    response_model=NotaInternaRisposta,
    status_code=201,
)
async def aggiungi_nota_interna(
    report_id: uuid.UUID,
    richiesta: RichiestaNotaInterna,
    contesto: ContestoOperatoreDep,
) -> NotaInternaRisposta:
    await _carica_segnalazione_del_comune(contesto, report_id)
    nota = await repository_amministrazione.inserisci_nota_interna(
        contesto.connessione,
        report_id=report_id,
        municipality_id=contesto.municipality_id,
        author_id=contesto.utente_id,
        body=richiesta.body.strip(),
    )
    return _risposta_nota(nota)


@router.get(
    "/admin/dispatch-failures",
    response_model=RispostaElencoFallimenti,
)
async def elenca_fallimenti_dispatch(
    contesto: ContestoOperatoreDep,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = LIMITE_FALLIMENTI_PREDEFINITO,
) -> RispostaElencoFallimenti:
    fallimenti = await repository_amministrazione.elenca_fallimenti_permanenti(
        contesto.connessione,
        municipality_id=contesto.municipality_id,
        limite=limit,
    )
    return RispostaElencoFallimenti(
        items=[
            RispostaFallimentoDispatch(
                report_id=fallimento.report_id,
                public_ref=fallimento.public_ref,
                title=fallimento.title,
                dispatch=_risposta_tentativo(fallimento.dispatch),
            )
            for fallimento in fallimenti
        ]
    )


@router.post(
    "/admin/reports/{report_id}/dispatch/retry",
    response_model=RispostaRiprogrammazioneDispatch,
    status_code=202,
)
async def riprogramma_dispatch(
    report_id: uuid.UUID,
    contesto: ContestoOperatoreDep,
) -> RispostaRiprogrammazioneDispatch:
    segnalazione = await _carica_segnalazione_del_comune(contesto, report_id)
    event_id = await inserisci_evento_outbox(
        contesto.connessione,
        aggregate_type="report",
        aggregate_id=segnalazione.id,
        event_type=EVENTO_DISPATCH_RITENTATIVO,
        payload={
            "report_id": str(segnalazione.id),
            "public_ref": segnalazione.public_ref,
        },
        tenant_id=contesto.municipality_id,
    )
    return RispostaRiprogrammazioneDispatch(event_id=event_id)


async def _carica_segnalazione_del_comune(
    contesto: ContestoOperatore,
    report_id: uuid.UUID,
) -> Segnalazione:
    segnalazione = await repository_segnalazioni.carica_segnalazione_per_id(
        contesto.connessione,
        report_id,
    )
    if (
        segnalazione is None
        or segnalazione.municipality_id != contesto.municipality_id
        or segnalazione.visibility == "hidden_by_moderation"
    ):
        raise ErroreApi(
            status=404,
            titolo="Segnalazione non trovata",
            dettaglio="La segnalazione richiesta non appartiene al tuo comune.",
        )
    return segnalazione


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


def _risposta_evento(
    evento: repository_amministrazione.EventoStatoAmministrazione,
) -> EventoStatoAmministrazioneRisposta:
    return EventoStatoAmministrazioneRisposta(
        id=evento.id,
        from_status=evento.from_status,
        to_status=evento.to_status,
        actor_type=evento.actor_type,
        note_public=evento.note_public,
        is_public=evento.is_public,
        created_at=evento.created_at,
    )


def _risposta_tentativo(
    tentativo: repository_amministrazione.TentativoDispatch,
) -> TentativoDispatchRisposta:
    return TentativoDispatchRisposta(
        id=tentativo.id,
        channel=tentativo.channel,
        attempt_no=tentativo.attempt_no,
        status=tentativo.status,
        provider_request_id=tentativo.provider_request_id,
        http_status=tentativo.http_status,
        error_code=tentativo.error_code,
        error_detail_redacted=tentativo.error_detail_redacted,
        next_attempt_at=tentativo.next_attempt_at,
        succeeded_at=tentativo.succeeded_at,
        created_at=tentativo.created_at,
    )


def _risposta_nota(
    nota: repository_amministrazione.NotaInterna,
) -> NotaInternaRisposta:
    return NotaInternaRisposta(
        id=nota.id,
        author_id=nota.author_id,
        body=nota.body,
        created_at=nota.created_at,
    )


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
