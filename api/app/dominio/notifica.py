from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.dominio.dispatch import ContenutoEmail
from app.dominio.esempio_segnalazione import StatoSegnalazione

TIPO_CAMBIO_STATO = "status_changed"
CANALE_IN_APP = "inapp"
EVENTO_STATO_SEGNALAZIONE_CAMBIATO = "report.status_changed"
STATO_NOTIFICA_INVIATA = "notification_sent"
STATO_NOTIFICA_IGNORATA = "ignored"

ETICHETTE_STATO_UTENTE: dict[str, str] = {
    StatoSegnalazione.APERTA.value: "Aperta",
    StatoSegnalazione.IN_CORSO.value: "In corso",
    StatoSegnalazione.RISOLTA.value: "Risolta",
    StatoSegnalazione.CHIUSA.value: "Chiusa",
}


class NotificaNonTrovata(Exception):  # noqa: N818
    """Segnala un evento notifica che punta a una notifica inesistente."""


class InvioEmailNotifica(Protocol):
    def invia(self, destinatario: str, oggetto: str, corpo: str) -> None:
        """Consegna una notifica all'autore della segnalazione."""
        ...


@dataclass(frozen=True, slots=True)
class Notifica:
    id: uuid.UUID
    user_id: uuid.UUID
    report_id: uuid.UUID | None
    tipo: str
    canale: str
    payload: Mapping[str, object]
    read_at: datetime | None
    sent_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NotificaDaInviare:
    id: uuid.UUID
    user_id: uuid.UUID
    report_id: uuid.UUID | None
    public_ref: str | None
    to_status: str | None
    note_public: str | None
    email_enc: bytes
    email_key_id: str
    sent_at: datetime | None


def componi_dedupe_key(evento_id: uuid.UUID) -> str:
    """Restituisce la chiave idempotente della notifica di cambio stato."""
    return f"{TIPO_CAMBIO_STATO}:{evento_id}"


def componi_url_pagina_segnalazione(
    url_pubblica_base: str,
    public_ref: str,
) -> str:
    """Restituisce il link alla pagina pubblica della segnalazione."""
    return f"{url_pubblica_base.rstrip('/')}/reports/{public_ref}"


def componi_contenuto_email_notifica(
    public_ref: str,
    to_status: str | None,
    note_public: str | None,
    url_pubblica: str,
) -> ContenutoEmail:
    """Restituisce oggetto e corpo dell'email di aggiornamento all'autore."""
    etichetta = ETICHETTE_STATO_UTENTE.get(
        to_status or "",
        "Aggiornata",
    )
    righe = [
        f"La segnalazione {public_ref} è ora nello stato: {etichetta}.",
        f"Puoi seguirla qui: {url_pubblica}",
    ]
    if note_public:
        righe.append(f"Nota del comune: {note_public}")
    return ContenutoEmail(
        oggetto=f"Aggiornamento sulla segnalazione {public_ref}",
        corpo="\n".join(righe),
    )
