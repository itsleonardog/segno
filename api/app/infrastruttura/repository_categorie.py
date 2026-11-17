from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class CategoriaAttiva:
    id: uuid.UUID
    slug: str
    name_i18n: dict[str, str]
    icon: str | None


async def elenca_categorie_attive(
    connessione: AsyncConnection,
) -> list[CategoriaAttiva]:
    """Restituisce le categorie attive ordinate per posizione di visualizzazione."""
    esito = await connessione.execute(text("""
            SELECT id, slug, name_i18n, icon
            FROM category
            WHERE is_active = true
            ORDER BY sort_order ASC, slug ASC
            """))
    return [
        CategoriaAttiva(
            id=riga["id"],
            slug=riga["slug"],
            name_i18n=dict(riga["name_i18n"]),
            icon=riga["icon"],
        )
        for riga in esito.mappings().all()
    ]
