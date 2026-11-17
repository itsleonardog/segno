from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from app.dominio.dispatch import VoceConfigurazioneDispatch

DURATA_PREDEFINITA_SECONDI = 60.0

ChiaveConfigurazione = tuple[uuid.UUID, uuid.UUID]
VoceInCache = tuple[float, VoceConfigurazioneDispatch]


class CacheConfigurazioneDispatch:
    """Cache in memoria con TTL breve per comune e categoria."""

    def __init__(
        self,
        durata_secondi: float = DURATA_PREDEFINITA_SECONDI,
        orologio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._durata_secondi = durata_secondi
        self._orologio = orologio
        self._voci: dict[ChiaveConfigurazione, VoceInCache] = {}

    def leggi(
        self,
        municipality_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> VoceConfigurazioneDispatch | None:
        chiave = (municipality_id, category_id)
        voce = self._voci.get(chiave)
        if voce is None:
            return None
        istante_scadenza, configurazione = voce
        if self._orologio() >= istante_scadenza:
            self._voci.pop(chiave, None)
            return None
        return configurazione

    def scrivi(
        self,
        municipality_id: uuid.UUID,
        category_id: uuid.UUID,
        voce: VoceConfigurazioneDispatch,
    ) -> None:
        self._voci[(municipality_id, category_id)] = (
            self._orologio() + self._durata_secondi,
            voce,
        )

    def invalida_comune(self, municipality_id: uuid.UUID) -> None:
        """Rimuove tutte le configurazioni del comune dopo una scrittura."""
        chiavi = [chiave for chiave in self._voci if chiave[0] == municipality_id]
        for chiave in chiavi:
            self._voci.pop(chiave, None)


cache_configurazione_dispatch = CacheConfigurazioneDispatch()
