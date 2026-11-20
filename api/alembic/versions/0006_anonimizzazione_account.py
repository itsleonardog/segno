"""rende anonimizzabile l'account e indicizza la retention delle notifiche

Revision ID: 0006_anonimizzazione_account
Revises: 0005_operatore_notifiche
Create Date: 2026-11-20 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_anonimizzazione_account"
down_revision: str | None = "0005_operatore_notifiche"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLONNE_ANONIMIZZABILI: dict[str, sa.types.TypeEngine] = {
    "email_enc": postgresql.BYTEA(),
    "email_key_id": sa.Text(),
    "email_lookup_hash": sa.Text(),
    "password_hash": sa.Text(),
}


def upgrade() -> None:
    # L'account anonimizzato non conserva recapiti né credenziali: i campi
    # diventano NULL e il vincolo di unicità sull'email resta valido perché
    # PostgreSQL considera distinti i valori NULL.
    for nome_colonna, tipo in COLONNE_ANONIMIZZABILI.items():
        op.alter_column(
            "user",
            nome_colonna,
            existing_type=tipo,
            nullable=True,
        )
    op.create_index(
        "ix_notification_read_at",
        "notification",
        ["read_at"],
        postgresql_where=sa.text("read_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notification_read_at", table_name="notification")
    for nome_colonna, tipo in COLONNE_ANONIMIZZABILI.items():
        op.alter_column(
            "user",
            nome_colonna,
            existing_type=tipo,
            nullable=False,
        )
