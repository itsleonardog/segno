"""associa gli operatori a un comune e aggiunge le note interne

Revision ID: 0005_operatore_notifiche
Revises: 0004_ruolo_operatore
Create Date: 2026-11-18 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_operatore_notifiche"
down_revision: str | None = "0004_ruolo_operatore"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUOLO_MIGRATORE = "civic_migrator"
RUOLO_APPLICAZIONE = "civic_app"


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("municipality_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_municipality",
        "user",
        "municipality",
        ["municipality_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_user_municipality_id", "user", ["municipality_id"])
    op.create_table(
        "report_internal_note",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report.id"],
            name="fk_report_internal_note_report",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["municipality_id"],
            ["municipality.id"],
            name="fk_report_internal_note_municipality",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["user.id"],
            name="fk_report_internal_note_author",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_internal_note"),
    )
    op.create_index(
        "ix_report_internal_note_report_created_at",
        "report_internal_note",
        ["report_id", "created_at"],
    )
    _assegna_privilegi()
    _abilita_rls()


def downgrade() -> None:
    op.drop_index(
        "ix_report_internal_note_report_created_at",
        table_name="report_internal_note",
    )
    op.drop_table("report_internal_note")
    op.drop_index("ix_user_municipality_id", table_name="user")
    op.drop_constraint("fk_user_municipality", "user", type_="foreignkey")
    op.drop_column("user", "municipality_id")


def _assegna_privilegi() -> None:
    op.execute(f"ALTER TABLE report_internal_note OWNER TO {RUOLO_MIGRATORE}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE report_internal_note "
        f"TO {RUOLO_APPLICAZIONE}"
    )


def _abilita_rls() -> None:
    op.execute("ALTER TABLE report_internal_note ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY report_internal_note_accesso_tenant
        ON report_internal_note
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (
            app_access_scope() = 'tenant'
            AND municipality_id = app_tenant_id()
        )
        WITH CHECK (
            app_access_scope() = 'tenant'
            AND municipality_id = app_tenant_id()
        )
        """)
    op.execute(f"""
        CREATE POLICY report_internal_note_accesso_piattaforma
        ON report_internal_note
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (app_access_scope() IN ('platform', 'system'))
        WITH CHECK (app_access_scope() IN ('platform', 'system'))
        """)
