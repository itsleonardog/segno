"""aggiunge il ruolo operatore e il supporto all'idempotenza

Revision ID: 0004_ruolo_operatore
Revises: 0003_metadati_sessione
Create Date: 2026-11-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_ruolo_operatore"
down_revision: str | None = "0003_metadati_sessione"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUOLO_MIGRATORE = "civic_migrator"
RUOLO_APPLICAZIONE = "civic_app"
SEQUENZA_PUBLIC_REF = "seq_report_public_ref"


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "is_operatore",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(f"CREATE SEQUENCE IF NOT EXISTS {SEQUENZA_PUBLIC_REF}")
    op.create_table(
        "idempotency_record",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["user.id"],
            name="fk_idempotency_record_actor",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_record"),
        sa.UniqueConstraint(
            "actor_id",
            "endpoint",
            "idempotency_key",
            name="uq_idempotency_record_actor_endpoint_key",
        ),
    )
    op.create_index(
        "ix_idempotency_record_expires_at",
        "idempotency_record",
        ["expires_at"],
    )
    _assegna_privilegi()
    _abilita_rls()


def downgrade() -> None:
    op.drop_index(
        "ix_idempotency_record_expires_at",
        table_name="idempotency_record",
    )
    op.drop_table("idempotency_record")
    op.execute(f"DROP SEQUENCE IF EXISTS {SEQUENZA_PUBLIC_REF}")
    op.drop_column("user", "is_operatore")


def _assegna_privilegi() -> None:
    op.execute(f"ALTER TABLE idempotency_record OWNER TO {RUOLO_MIGRATORE}")
    op.execute(f"ALTER SEQUENCE {SEQUENZA_PUBLIC_REF} OWNER TO {RUOLO_MIGRATORE}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE idempotency_record "
        f"TO {RUOLO_APPLICAZIONE}"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON SEQUENCE {SEQUENZA_PUBLIC_REF} "
        f"TO {RUOLO_APPLICAZIONE}"
    )


def _abilita_rls() -> None:
    op.execute("ALTER TABLE idempotency_record ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY idempotency_record_accesso_proprio ON idempotency_record
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (actor_id = app_user_id())
        WITH CHECK (actor_id = app_user_id())
        """)
    op.execute(f"""
        CREATE POLICY idempotency_record_accesso_piattaforma ON idempotency_record
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (app_access_scope() IN ('platform', 'system'))
        WITH CHECK (app_access_scope() IN ('platform', 'system'))
        """)
