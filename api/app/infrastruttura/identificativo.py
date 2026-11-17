from __future__ import annotations

import secrets
import time
import uuid

MASCHERA_TIMESTAMP_MS = (1 << 48) - 1
MASCHERA_RANDOM_A = (1 << 12) - 1
MASCHERA_RANDOM_B = (1 << 62) - 1


def genera_identificativo_uuid7() -> uuid.UUID:
    """Restituisce un UUID v7 ordinabile per il timestamp di creazione."""
    timestamp_ms = (time.time_ns() // 1_000_000) & MASCHERA_TIMESTAMP_MS
    valore = timestamp_ms << 80
    valore |= 0x7 << 76
    valore |= (secrets.randbits(12) & MASCHERA_RANDOM_A) << 64
    valore |= 0b10 << 62
    valore |= secrets.randbits(62) & MASCHERA_RANDOM_B
    return uuid.UUID(int=valore)
