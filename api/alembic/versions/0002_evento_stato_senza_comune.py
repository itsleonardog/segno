"""rende nullable il comune degli eventi di stato

Revision ID: 0002_evento_stato_senza_comune
Revises: 0001_schema_iniziale
Create Date: 2026-11-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_evento_stato_senza_comune"
down_revision: str | None = "0001_schema_iniziale"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "report_status_event",
        "municipality_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "report_status_event",
        "municipality_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
