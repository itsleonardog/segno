from __future__ import annotations

import uuid

from pydantic import BaseModel


class CategoriaRisposta(BaseModel):
    id: uuid.UUID
    slug: str
    name_i18n: dict[str, str]
    icon: str | None
