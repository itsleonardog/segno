"""schema iniziale con ruoli, RLS e indici spaziali

Revision ID: 0001_schema_iniziale
Revises:
Create Date: 2026-11-17 00:00:00.000000

"""

from __future__ import annotations

import os
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_schema_iniziale"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUOLO_MIGRATORE = "civic_migrator"
RUOLO_APPLICAZIONE = "civic_app"

TIPI_ENUM: dict[str, tuple[str, ...]] = {
    "dispatch_mode": ("open311", "email", "open311_then_email"),
    "user_status": ("active", "suspended", "deletion_pending", "anonymized"),
    "report_status": ("open", "in_progress", "resolved", "closed"),
    "report_visibility": ("public", "hidden_by_moderation"),
    "report_dispatch_state": (
        "pending",
        "routed",
        "sent_open311",
        "sent_email",
        "failed",
        "out_of_jurisdiction",
    ),
    "actor_type": (
        "citizen",
        "municipality",
        "moderator",
        "system",
        "open311_sync",
    ),
    "dispatch_channel": ("open311", "email"),
    "dispatch_attempt_status": (
        "queued",
        "sending",
        "succeeded",
        "failed_permanent",
        "failed_retryable",
        "suppressed",
    ),
}

ORDINE_CREAZIONE = (
    "municipality",
    "category",
    "user",
    "municipality_service",
    "refresh_token",
    "email_verification_token",
    "password_reset_token",
    "report",
    "report_dispatch",
    "report_status_event",
    "outbox_event",
    "notification",
    "notification_preference",
    "audit_log",
)

TABELLE_CON_RLS = (
    "municipality_service",
    "report",
    "report_status_event",
    "report_dispatch",
    "outbox_event",
    "user",
    "refresh_token",
    "notification",
    "notification_preference",
    "audit_log",
)

CATEGORIE_BASE = (
    (
        "0192f3a0-0001-7000-8000-000000000001",
        "strade",
        '{"it": "Strade", "en": "Roads"}',
        "road",
        10,
    ),
    (
        "0192f3a0-0002-7000-8000-000000000002",
        "illuminazione",
        '{"it": "Illuminazione", "en": "Street lighting"}',
        "lightbulb",
        20,
    ),
    (
        "0192f3a0-0003-7000-8000-000000000003",
        "rifiuti",
        '{"it": "Rifiuti", "en": "Waste"}',
        "trash",
        30,
    ),
    (
        "0192f3a0-0004-7000-8000-000000000004",
        "altro",
        '{"it": "Altro", "en": "Other"}',
        "circle-help",
        40,
    ),
)


class Geography(sa.types.UserDefinedType):
    cache_ok = True

    def __init__(self, tipo_geometria: str) -> None:
        self.tipo_geometria = tipo_geometria

    def get_col_spec(self, **kw: object) -> str:
        return f"geography({self.tipo_geometria},4326)"


class Geometry(sa.types.UserDefinedType):
    cache_ok = True

    def __init__(self, tipo_geometria: str) -> None:
        self.tipo_geometria = tipo_geometria

    def get_col_spec(self, **kw: object) -> str:
        return f"geometry({self.tipo_geometria},4326)"


def _tipo_enum(nome: str) -> postgresql.ENUM:
    return postgresql.ENUM(*TIPI_ENUM[nome], name=nome, create_type=False)


def _timestamp(nome: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        nome,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.func.now(),
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    _crea_ruoli()
    _crea_tipi_enum()
    _crea_funzioni_contesto()
    _crea_tabelle()
    _crea_indici()
    _semina_categorie()
    _assegna_proprieta_e_privilegi()
    _abilita_rls_e_policy()


def downgrade() -> None:
    for tabella in reversed(ORDINE_CREAZIONE):
        op.drop_table(tabella)
    op.execute("DROP FUNCTION IF EXISTS app_access_scope()")
    op.execute("DROP FUNCTION IF EXISTS app_user_id()")
    op.execute("DROP FUNCTION IF EXISTS app_tenant_id()")
    for nome_tipo in reversed(tuple(TIPI_ENUM)):
        op.execute(f"DROP TYPE IF EXISTS {nome_tipo}")


def _crea_ruoli() -> None:
    ruoli = (
        (RUOLO_MIGRATORE, "CIVIC_MIGRATOR_PASSWORD", "BYPASSRLS"),
        (RUOLO_APPLICAZIONE, "CIVIC_APP_PASSWORD", "NOBYPASSRLS"),
    )
    for nome_ruolo, variabile_password, bypass_rls in ruoli:
        ruolo_esistente = op.get_bind().execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :nome_ruolo"),
            {"nome_ruolo": nome_ruolo},
        )
        if ruolo_esistente.scalar() is not None:
            continue
        password = os.environ.get(variabile_password) or nome_ruolo
        password_letterale = password.replace("'", "''")
        op.execute(
            f"CREATE ROLE {nome_ruolo} LOGIN {bypass_rls} "
            f"NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
            f"PASSWORD '{password_letterale}'"
        )


def _crea_tipi_enum() -> None:
    for nome_tipo, valori in TIPI_ENUM.items():
        postgresql.ENUM(*valori, name=nome_tipo).create(op.get_bind(), checkfirst=True)


def _crea_funzioni_contesto() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION app_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
        $$
        """)
    op.execute("""
        CREATE OR REPLACE FUNCTION app_user_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
        $$
        """)
    op.execute("""
        CREATE OR REPLACE FUNCTION app_access_scope() RETURNS text
        LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.access_scope', true), '')
        $$
        """)


def _crea_tabelle() -> None:
    op.create_table(
        "municipality",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("istat_code", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("boundary", Geography("MultiPolygon"), nullable=False),
        sa.Column("boundary_source", sa.Text(), nullable=True),
        sa.Column("boundary_version", sa.Text(), nullable=True),
        sa.Column("boundary_imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("boundary_checksum", sa.Text(), nullable=True),
        sa.Column("dispatch_mode", _tipo_enum("dispatch_mode"), nullable=False),
        sa.Column("open311_endpoint_url", sa.Text(), nullable=True),
        sa.Column("open311_jurisdiction_id", sa.Text(), nullable=True),
        sa.Column("open311_api_key_ref", sa.Text(), nullable=True),
        sa.Column("coverage_bbox", Geometry("Polygon"), nullable=True),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.PrimaryKeyConstraint("id", name="pk_municipality"),
        sa.UniqueConstraint("slug", name="uq_municipality_slug"),
        sa.UniqueConstraint("istat_code", name="uq_municipality_istat_code"),
    )

    op.create_table(
        "category",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name_i18n", postgresql.JSONB(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "requires_photo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("default_sla_days", sa.Integer(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["category.id"],
            name="fk_category_parent",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_category"),
        sa.UniqueConstraint("slug", name="uq_category_slug"),
    )

    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nickname", sa.Text(), nullable=False),
        sa.Column("nickname_normalized", sa.Text(), nullable=False),
        sa.Column("email_enc", postgresql.BYTEA(), nullable=False),
        sa.Column("email_key_id", sa.Text(), nullable=False),
        sa.Column("email_lookup_hash", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "locale",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'it'"),
        ),
        sa.Column(
            "status",
            _tipo_enum("user_status"),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        _timestamp("created_at"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("privacy_policy_version", sa.Text(), nullable=False),
        sa.Column("tos_version", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user"),
        sa.UniqueConstraint("email_lookup_hash", name="uq_user_email_lookup_hash"),
    )

    op.create_table(
        "municipality_service",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("open311_service_code", sa.Text(), nullable=True),
        sa.Column("open311_extra_fields", postgresql.JSONB(), nullable=True),
        sa.Column("fallback_email_enc", postgresql.BYTEA(), nullable=True),
        sa.Column(
            "fallback_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("sla_days", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["municipality_id"],
            ["municipality.id"],
            name="fk_municipality_service_municipality",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name="fk_municipality_service_category",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_municipality_service"),
        sa.UniqueConstraint(
            "municipality_id",
            "category_id",
            name="uq_municipality_service_municipality_category",
        ),
    )

    op.create_table(
        "refresh_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.Column("ip_hash", sa.Text(), nullable=True),
        sa.Column("user_agent_hash", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_refresh_token_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["refresh_token.id"],
            name="fk_refresh_token_replaced_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_token"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_token_hash"),
    )

    op.create_table(
        "email_verification_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_email_verification_token_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_email_verification_token"),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_email_verification_token_token_hash",
        ),
    )

    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_password_reset_token_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_reset_token"),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_password_reset_token_token_hash",
        ),
    )

    op.create_table(
        "report",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_ref", sa.Text(), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=True),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", Geography("Point"), nullable=False),
        sa.Column("location_accuracy_m", sa.Float(), nullable=True),
        sa.Column("address_label", sa.Text(), nullable=True),
        sa.Column(
            "status",
            _tipo_enum("report_status"),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "visibility",
            _tipo_enum("report_visibility"),
            nullable=False,
            server_default=sa.text("'public'"),
        ),
        sa.Column(
            "dispatch_state",
            _tipo_enum("report_dispatch_state"),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "boundary_ambiguous",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "jurisdiction_resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.CheckConstraint(
            "public_ref ~ '^CR-[0-9]{4}-[0-9]{6}$'",
            name="ck_report_public_ref_formato",
        ),
        sa.ForeignKeyConstraint(
            ["municipality_id"],
            ["municipality.id"],
            name="fk_report_municipality",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["user.id"],
            name="fk_report_author",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name="fk_report_category",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report"),
        sa.UniqueConstraint("public_ref", name="uq_report_public_ref"),
    )

    op.create_table(
        "report_dispatch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        sa.Column("channel", _tipo_enum("dispatch_channel"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _tipo_enum("dispatch_attempt_status"),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("provider_request_id", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_detail_redacted", sa.Text(), nullable=True),
        sa.Column("request_fingerprint", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp("created_at"),
        sa.CheckConstraint("attempt_no > 0", name="ck_report_dispatch_attempt_no"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report.id"],
            name="fk_report_dispatch_report",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["municipality_id"],
            ["municipality.id"],
            name="fk_report_dispatch_municipality",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_dispatch"),
        sa.UniqueConstraint(
            "report_id",
            "channel",
            "attempt_no",
            name="uq_report_dispatch_report_channel_attempt",
        ),
    )

    op.create_table(
        "report_status_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=True),
        sa.Column("from_status", _tipo_enum("report_status"), nullable=True),
        sa.Column("to_status", _tipo_enum("report_status"), nullable=False),
        sa.Column("actor_type", _tipo_enum("actor_type"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("note_public", sa.Text(), nullable=True),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("source_dispatch_id", sa.Uuid(), nullable=True),
        _timestamp("created_at"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report.id"],
            name="fk_report_status_event_report",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["municipality_id"],
            ["municipality.id"],
            name="fk_report_status_event_municipality",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_status_event"),
    )

    op.create_table(
        "outbox_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        _timestamp("created_at"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_event"),
    )

    op.create_table(
        "notification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        _timestamp("created_at"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_notification_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report.id"],
            name="fk_notification_report",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification"),
        sa.UniqueConstraint("dedupe_key", name="uq_notification_dedupe_key"),
    )

    op.create_table(
        "notification_preference",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_notification_preference_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_preference"),
        sa.UniqueConstraint(
            "user_id",
            "type",
            "channel",
            name="uq_notification_preference_user_type_channel",
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("ip_hash", sa.Text(), nullable=True),
        _timestamp("created_at"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )


def _crea_indici() -> None:
    op.create_index(
        "ix_municipality_boundary_gist",
        "municipality",
        ["boundary"],
        postgresql_using="gist",
    )
    op.create_index(
        "ux_user_nickname_normalizzato",
        "user",
        [sa.text("lower(nickname)")],
        unique=True,
    )
    op.create_index("ix_refresh_token_user_id", "refresh_token", ["user_id"])
    op.create_index("ix_refresh_token_family_id", "refresh_token", ["family_id"])
    op.create_index(
        "ix_email_verification_token_user_id",
        "email_verification_token",
        ["user_id"],
    )
    op.create_index(
        "ix_password_reset_token_user_id",
        "password_reset_token",
        ["user_id"],
    )
    op.create_index(
        "ix_report_location_gist",
        "report",
        ["location"],
        postgresql_using="gist",
    )
    op.create_index(
        "ix_report_municipality_status_created_at",
        "report",
        ["municipality_id", "status", "created_at"],
    )
    op.create_index("ix_report_status", "report", ["status"])
    op.create_index("ix_report_category_id", "report", ["category_id"])
    op.create_index("ix_report_author_id", "report", ["author_id"])
    op.create_index(
        "ix_report_status_event_report_created_at",
        "report_status_event",
        ["report_id", "created_at"],
    )
    op.create_index(
        "ix_report_status_event_municipality_id",
        "report_status_event",
        ["municipality_id"],
    )
    op.create_index(
        "ix_report_dispatch_municipality_id",
        "report_dispatch",
        ["municipality_id"],
    )
    op.create_index(
        "ix_report_dispatch_next_attempt_at",
        "report_dispatch",
        ["next_attempt_at"],
    )
    op.create_index("ix_outbox_event_tenant_id", "outbox_event", ["tenant_id"])
    op.create_index(
        "ix_outbox_event_non_processati",
        "outbox_event",
        ["processed_at", "id"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.create_index("ix_notification_user_id", "notification", ["user_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def _semina_categorie() -> None:
    for identificativo, slug, nome_i18n, icona, ordine in CATEGORIE_BASE:
        op.execute(
            sa.text("""
                INSERT INTO category (
                    id, slug, name_i18n, icon, is_active, requires_photo, sort_order
                )
                VALUES (
                    CAST(:identificativo AS uuid),
                    :slug,
                    CAST(:nome_i18n AS jsonb),
                    :icona,
                    true,
                    false,
                    :ordine
                )
                ON CONFLICT (slug) DO NOTHING
                """).bindparams(
                identificativo=identificativo,
                slug=slug,
                nome_i18n=nome_i18n,
                icona=icona,
                ordine=ordine,
            )
        )


def _assegna_proprieta_e_privilegi() -> None:
    for tabella in ORDINE_CREAZIONE:
        op.execute(f'ALTER TABLE "{tabella}" OWNER TO {RUOLO_MIGRATORE}')
    for funzione in ("app_tenant_id()", "app_user_id()", "app_access_scope()"):
        op.execute(f"ALTER FUNCTION {funzione} OWNER TO {RUOLO_MIGRATORE}")

    op.execute(f"GRANT USAGE ON SCHEMA public TO {RUOLO_APPLICAZIONE}")
    for tabella in ORDINE_CREAZIONE:
        op.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{tabella}" '
            f"TO {RUOLO_APPLICAZIONE}"
        )
    op.execute(
        f"REVOKE UPDATE, DELETE ON TABLE report_status_event "
        f"FROM {RUOLO_APPLICAZIONE}"
    )


def _abilita_rls_e_policy() -> None:
    for tabella in TABELLE_CON_RLS:
        op.execute(f'ALTER TABLE "{tabella}" ENABLE ROW LEVEL SECURITY')

    _policy_report()
    _policy_municipality_service()
    _policy_report_status_event()
    _policy_report_dispatch()
    _policy_outbox_event()
    _policy_tabelle_utente()
    _policy_audit_log()


def _policy_report() -> None:
    op.execute(f"""
        CREATE POLICY report_accesso_tenant ON report
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
        CREATE POLICY report_lettura_pubblica ON report
        FOR SELECT TO {RUOLO_APPLICAZIONE}
        USING (
            app_access_scope() = 'public'
            AND visibility = 'public'
            AND deleted_at IS NULL
        )
        """)
    op.execute(f"""
        CREATE POLICY report_accesso_piattaforma ON report
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (app_access_scope() IN ('platform', 'system'))
        WITH CHECK (app_access_scope() IN ('platform', 'system'))
        """)


def _policy_municipality_service() -> None:
    op.execute(f"""
        CREATE POLICY municipality_service_accesso_tenant ON municipality_service
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
        CREATE POLICY municipality_service_accesso_piattaforma
        ON municipality_service
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (app_access_scope() IN ('platform', 'system'))
        WITH CHECK (app_access_scope() IN ('platform', 'system'))
        """)


def _policy_report_status_event() -> None:
    op.execute(f"""
        CREATE POLICY report_status_event_accesso_tenant ON report_status_event
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
        CREATE POLICY report_status_event_lettura_pubblica ON report_status_event
        FOR SELECT TO {RUOLO_APPLICAZIONE}
        USING (
            app_access_scope() = 'public'
            AND is_public = true
        )
        """)
    op.execute(f"""
        CREATE POLICY report_status_event_accesso_piattaforma
        ON report_status_event
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (app_access_scope() IN ('platform', 'system'))
        WITH CHECK (app_access_scope() IN ('platform', 'system'))
        """)


def _policy_report_dispatch() -> None:
    op.execute(f"""
        CREATE POLICY report_dispatch_accesso_tenant ON report_dispatch
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
        CREATE POLICY report_dispatch_accesso_piattaforma ON report_dispatch
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (app_access_scope() IN ('platform', 'system'))
        WITH CHECK (app_access_scope() IN ('platform', 'system'))
        """)


def _policy_outbox_event() -> None:
    op.execute(f"""
        CREATE POLICY outbox_event_accesso_tenant ON outbox_event
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (
            app_access_scope() = 'tenant'
            AND tenant_id = app_tenant_id()
        )
        WITH CHECK (
            app_access_scope() = 'tenant'
            AND tenant_id = app_tenant_id()
        )
        """)
    op.execute(f"""
        CREATE POLICY outbox_event_accesso_piattaforma ON outbox_event
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (app_access_scope() IN ('platform', 'system'))
        WITH CHECK (app_access_scope() IN ('platform', 'system'))
        """)


def _policy_tabelle_utente() -> None:
    op.execute(f"""
        CREATE POLICY utente_accesso_proprio ON "user"
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (id = app_user_id())
        WITH CHECK (id = app_user_id())
        """)
    op.execute(f"""
        CREATE POLICY utente_accesso_piattaforma ON "user"
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (app_access_scope() IN ('platform', 'system'))
        WITH CHECK (app_access_scope() IN ('platform', 'system'))
        """)

    for tabella in ("refresh_token", "notification", "notification_preference"):
        op.execute(f"""
            CREATE POLICY {tabella}_accesso_proprio ON "{tabella}"
            FOR ALL TO {RUOLO_APPLICAZIONE}
            USING (user_id = app_user_id())
            WITH CHECK (user_id = app_user_id())
            """)
        op.execute(f"""
            CREATE POLICY {tabella}_accesso_piattaforma ON "{tabella}"
            FOR ALL TO {RUOLO_APPLICAZIONE}
            USING (app_access_scope() IN ('platform', 'system'))
            WITH CHECK (app_access_scope() IN ('platform', 'system'))
            """)


def _policy_audit_log() -> None:
    op.execute(f"""
        CREATE POLICY audit_log_accesso_piattaforma ON audit_log
        FOR ALL TO {RUOLO_APPLICAZIONE}
        USING (app_access_scope() IN ('platform', 'system'))
        WITH CHECK (app_access_scope() IN ('platform', 'system'))
        """)
