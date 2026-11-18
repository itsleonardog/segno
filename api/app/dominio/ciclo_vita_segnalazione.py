from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.esempio_segnalazione import (
    StatoSegnalazione,
    TransizioneNonAmmessa,
)
from app.dominio.notifica import (
    CANALE_IN_APP,
    EVENTO_STATO_SEGNALAZIONE_CAMBIATO,
    TIPO_CAMBIO_STATO,
    componi_dedupe_key,
)
from app.dominio.segnalazione import Segnalazione
from app.infrastruttura import repository_notifiche, repository_segnalazioni
from app.infrastruttura.outbox import inserisci_evento_outbox

FINESTRA_MODIFICA_ORE = 24

# Le transizioni consentite all'operatore comunale: open -> in_progress ->
# resolved -> closed. Riaprire una segnalazione risolta è fuori da questo flusso.
TRANSAZIONI_OPERATORE: frozenset[tuple[StatoSegnalazione, StatoSegnalazione]] = (
    frozenset(
        {
            (StatoSegnalazione.APERTA, StatoSegnalazione.IN_CORSO),
            (StatoSegnalazione.IN_CORSO, StatoSegnalazione.RISOLTA),
            (StatoSegnalazione.RISOLTA, StatoSegnalazione.CHIUSA),
        }
    )
)


class ModificaScaduta(Exception):  # noqa: N818
    """Segnala una modifica richiesta oltre la finestra consentita."""


def valida_transizione_operatore(
    stato_precedente: StatoSegnalazione,
    stato_successivo: StatoSegnalazione,
) -> StatoSegnalazione:
    """Restituisce lo stato successivo o solleva TransizioneNonAmmessa."""
    if (stato_precedente, stato_successivo) not in TRANSAZIONI_OPERATORE:
        raise TransizioneNonAmmessa(stato_precedente, stato_successivo)
    return stato_successivo


def verifica_finestra_modifica(
    created_at: datetime,
    istante: datetime,
) -> None:
    """Solleva ModificaScaduta se la finestra di modifica è trascorsa."""
    if istante - created_at > timedelta(hours=FINESTRA_MODIFICA_ORE):
        raise ModificaScaduta("Il termine per modificare la segnalazione è trascorso.")


async def registra_cambio_stato(
    connessione: AsyncConnection,
    segnalazione: Segnalazione,
    stato_successivo: StatoSegnalazione,
    *,
    actor_type: str,
    actor_id: uuid.UUID | None,
    note_public: str | None,
) -> uuid.UUID | None:
    """Aggiorna lo stato, accoda l'evento e notifica l'autore della segnalazione."""
    stato_precedente = StatoSegnalazione(segnalazione.status)
    await repository_segnalazioni.aggiorna_stato(
        connessione,
        report_id=segnalazione.id,
        stato=stato_successivo.value,
    )
    evento_id = await repository_segnalazioni.inserisci_evento_stato(
        connessione,
        report_id=segnalazione.id,
        municipality_id=segnalazione.municipality_id,
        from_status=stato_precedente.value,
        to_status=stato_successivo.value,
        actor_type=actor_type,
        actor_id=actor_id,
        note_public=note_public,
        is_public=True,
    )
    if segnalazione.author_id is None:
        return None
    notifica_id = await repository_notifiche.inserisci_notifica(
        connessione,
        user_id=segnalazione.author_id,
        report_id=segnalazione.id,
        tipo=TIPO_CAMBIO_STATO,
        canale=CANALE_IN_APP,
        payload={
            "public_ref": segnalazione.public_ref,
            "from_status": stato_precedente.value,
            "to_status": stato_successivo.value,
            "note_public": note_public,
        },
        dedupe_key=componi_dedupe_key(evento_id),
    )
    await inserisci_evento_outbox(
        connessione,
        aggregate_type="report",
        aggregate_id=segnalazione.id,
        event_type=EVENTO_STATO_SEGNALAZIONE_CAMBIATO,
        payload={
            "notification_id": str(notifica_id),
            "report_id": str(segnalazione.id),
            "public_ref": segnalazione.public_ref,
            "from_status": stato_precedente.value,
            "to_status": stato_successivo.value,
            "note_public": note_public,
        },
        tenant_id=segnalazione.municipality_id,
    )
    return notifica_id
