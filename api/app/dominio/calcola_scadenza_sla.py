from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Protocol

GIORNI_SETTIMANA_LAVORATIVI = frozenset({0, 1, 2, 3, 4})


class SegnalazioneConSla(Protocol):
    """Espone gli istanti e il flag SLA che il calcolo richiede alla segnalazione."""

    @property
    def istante_creazione(self) -> datetime: ...

    @property
    def scadenza_sla(self) -> datetime | None: ...

    @property
    def is_scaduta(self) -> bool: ...


class IstanteSenzaFusoOrario(ValueError):  # noqa: N818
    """Segnala un istante privo di fuso orario, contrario alla convenzione UTC."""


class GiorniLavorativiNonValidi(ValueError):  # noqa: N818
    """Segnala un numero di giorni lavorativi inferiore a uno."""


class ScadenzaSlaNonCalcolata(Exception):  # noqa: N818
    """Segnala una segnalazione senza scadenza SLA, da calcolare prima."""


def calcola_scadenza_sla(
    segnalazione: SegnalazioneConSla,
    giorni_lavorativi: int,
) -> datetime:
    """Restituisce la scadenza della SLA contando solo i giorni lavorativi."""
    if giorni_lavorativi < 1:
        raise GiorniLavorativiNonValidi(
            "I giorni lavorativi della SLA devono essere almeno uno."
        )
    istante_scadenza = _istante_con_fuso(segnalazione.istante_creazione)
    giorni_da_contare = giorni_lavorativi
    # Il giorno di apertura non si conta: la SLA decorre dal primo giorno
    # lavorativo successivo, coerentemente con il calcolo per comune.
    while giorni_da_contare > 0:
        istante_scadenza += timedelta(days=1)
        if istante_scadenza.weekday() in GIORNI_SETTIMANA_LAVORATIVI:
            giorni_da_contare -= 1
    return istante_scadenza


def marca_come_scaduta[SegnalazioneSlaT: SegnalazioneConSla](
    segnalazione: SegnalazioneSlaT,
    istante_riferimento: datetime,
) -> SegnalazioneSlaT:
    """Restituisce la segnalazione con is_scaduta aggiornato alla scadenza SLA."""
    if segnalazione.scadenza_sla is None:
        raise ScadenzaSlaNonCalcolata(
            "La scadenza della SLA va calcolata prima di marcare la segnalazione."
        )
    istante_riferimento = _istante_con_fuso(istante_riferimento)
    # Alla scadenza esatta la SLA è già violata: il comune aveva fino a lì.
    is_scaduta = istante_riferimento >= segnalazione.scadenza_sla
    if is_scaduta == segnalazione.is_scaduta:
        return segnalazione
    return replace(segnalazione, is_scaduta=is_scaduta)


def _istante_con_fuso(istante: datetime) -> datetime:
    if istante.tzinfo is None:
        raise IstanteSenzaFusoOrario(
            "L'istante deve avere un fuso orario esplicito, UTC nel database."
        )
    return istante
