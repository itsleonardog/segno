from __future__ import annotations

from datetime import datetime, timedelta

from app.dominio.esempio_segnalazione import (
    StatoSegnalazione,
    TransizioneNonAmmessa,
)

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
