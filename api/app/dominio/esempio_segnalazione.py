from __future__ import annotations

from enum import StrEnum


class StatoSegnalazione(StrEnum):
    """Gli stati del ciclo di vita civico di una segnalazione."""

    APERTA = "open"
    IN_CORSO = "in_progress"
    RISOLTA = "resolved"
    CHIUSA = "closed"


type TransizioneStato = tuple[StatoSegnalazione, StatoSegnalazione]

# Chiusa è terminale; risolta può riaprirsi se il sopralluogo lo richiede.
TRANSAZIONI_AMMESSE: frozenset[TransizioneStato] = frozenset(
    {
        (StatoSegnalazione.APERTA, StatoSegnalazione.IN_CORSO),
        (StatoSegnalazione.IN_CORSO, StatoSegnalazione.RISOLTA),
        (StatoSegnalazione.RISOLTA, StatoSegnalazione.CHIUSA),
        (StatoSegnalazione.RISOLTA, StatoSegnalazione.IN_CORSO),
    }
)


class TransizioneNonAmmessa(Exception):  # noqa: N818
    """Segnala un passaggio di stato non previsto dal ciclo di vita."""

    def __init__(
        self,
        stato_precedente: StatoSegnalazione,
        stato_successivo: StatoSegnalazione,
    ) -> None:
        self.stato_precedente = stato_precedente
        self.stato_successivo = stato_successivo
        super().__init__(
            "La segnalazione non può passare "
            f"da {stato_precedente.value} a {stato_successivo.value}."
        )


def valida_transizione_stato(
    stato_precedente: StatoSegnalazione,
    stato_successivo: StatoSegnalazione,
) -> StatoSegnalazione:
    """Restituisce lo stato successivo o solleva TransizioneNonAmmessa."""
    if (stato_precedente, stato_successivo) not in TRANSAZIONI_AMMESSE:
        raise TransizioneNonAmmessa(stato_precedente, stato_successivo)
    return stato_successivo
