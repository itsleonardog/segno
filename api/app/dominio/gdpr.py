"""Modello dell'esportazione dei dati personali e dell'anonimizzazione."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

PREFISSO_UTENTE_CANCELLATO = "UtenteCancellato_"
LUNGHEZZA_SUFFISSO_ANONIMO = 8
AZIONE_AUDIT_ACCOUNT_ANONIMIZZATO = "account_anonymized"


def componi_nickname_anonimo(utente_id: uuid.UUID) -> str:
    """Restituisce il nickname pseudonimo assegnato all'account anonimizzato."""
    return f"{PREFISSO_UTENTE_CANCELLATO}{utente_id.hex[:LUNGHEZZA_SUFFISSO_ANONIMO]}"


@dataclass(frozen=True, slots=True)
class ProfiloEsportato:
    id: uuid.UUID
    nickname: str
    email: str | None
    status: str
    email_verified_at: datetime | None
    created_at: datetime
    last_login_at: datetime | None
    locale: str
    privacy_policy_version: str
    tos_version: str
    is_operatore: bool
    municipality_id: uuid.UUID | None

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "nickname": self.nickname,
            "email": self.email,
            "status": self.status,
            "email_verified_at": _data_iso(self.email_verified_at),
            "created_at": _data_iso(self.created_at),
            "last_login_at": _data_iso(self.last_login_at),
            "locale": self.locale,
            "privacy_policy_version": self.privacy_policy_version,
            "tos_version": self.tos_version,
            "is_operatore": self.is_operatore,
            "municipality_id": (
                str(self.municipality_id) if self.municipality_id else None
            ),
        }


@dataclass(frozen=True, slots=True)
class SegnalazioneEsportata:
    id: uuid.UUID
    public_ref: str
    title: str
    description: str
    category_id: uuid.UUID
    municipality_id: uuid.UUID | None
    status: str
    visibility: str
    dispatch_state: str
    lat: float
    lng: float
    address_text: str | None
    created_at: datetime

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "public_ref": self.public_ref,
            "title": self.title,
            "description": self.description,
            "category_id": str(self.category_id),
            "municipality_id": (
                str(self.municipality_id) if self.municipality_id else None
            ),
            "status": self.status,
            "visibility": self.visibility,
            "dispatch_state": self.dispatch_state,
            "lat": self.lat,
            "lng": self.lng,
            "address_text": self.address_text,
            "created_at": _data_iso(self.created_at),
        }


@dataclass(frozen=True, slots=True)
class EventoEsportato:
    id: uuid.UUID
    report_id: uuid.UUID
    to_status: str
    note_public: str | None
    created_at: datetime

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "report_id": str(self.report_id),
            "to_status": self.to_status,
            "note_public": self.note_public,
            "created_at": _data_iso(self.created_at),
        }


@dataclass(frozen=True, slots=True)
class NotificaEsportata:
    id: uuid.UUID
    report_id: uuid.UUID | None
    tipo: str
    canale: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "report_id": str(self.report_id) if self.report_id else None,
            "type": self.tipo,
            "channel": self.canale,
            "payload": dict(self.payload),
            "read_at": _data_iso(self.read_at),
            "created_at": _data_iso(self.created_at),
        }


@dataclass(frozen=True, slots=True)
class EsportazioneUtente:
    generata_il: datetime
    profilo: ProfiloEsportato
    segnalazioni: tuple[SegnalazioneEsportata, ...]
    eventi: tuple[EventoEsportato, ...]
    notifiche: tuple[NotificaEsportata, ...]

    def come_dizionario(self) -> dict[str, Any]:
        """Restituisce l'esportazione serializzabile in JSON."""
        return {
            "formato": "segno.esportazione_utente",
            "versione": 1,
            "generata_il": _data_iso(self.generata_il),
            "profilo": self.profilo.come_dizionario(),
            "segnalazioni": [
                segnalazione.come_dizionario() for segnalazione in self.segnalazioni
            ],
            "eventi_segnalazioni": [evento.come_dizionario() for evento in self.eventi],
            "notifiche": [notifica.come_dizionario() for notifica in self.notifiche],
        }


def _data_iso(valore: datetime | None) -> str | None:
    return valore.isoformat() if valore is not None else None
