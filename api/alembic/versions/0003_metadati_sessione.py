"""aggiunge i metadati di sessione al refresh token

Revision ID: 0003_metadati_sessione
Revises: 0002_evento_stato_senza_comune
Create Date: 2026-11-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_metadati_sessione"
down_revision: str | None = "0002_evento_stato_senza_comune"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "refresh_token",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "refresh_token",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "refresh_token",
        sa.Column("user_agent_summary", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("refresh_token", "user_agent_summary")
    op.drop_column("refresh_token", "last_used_at")
    op.drop_column("refresh_token", "created_at")
