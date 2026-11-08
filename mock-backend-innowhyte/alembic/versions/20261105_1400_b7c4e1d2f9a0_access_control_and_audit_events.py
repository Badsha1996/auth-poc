"""access control fields on users + append-only audit_events

Revision ID: b7c4e1d2f9a0
Revises: a323022fd3e2
Create Date: 2026-11-05 14:00:00

- users: auth_provider (identity-provider abstraction), email_verified, is_active, deactivated_at
- users: uniqueness is now (auth_provider, external_id) instead of external_id alone
- audit_events: security audit trail; a trigger blocks UPDATE, DELETE and TRUNCATE
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7c4e1d2f9a0"
down_revision: str | None = "a323022fd3e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users -------------------------------------------------------------------------------
    op.add_column(
        "users", sa.Column("auth_provider", sa.String(length=32), server_default="workos", nullable=False)
    )
    op.add_column(
        "users", sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column("users", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("users", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_index(op.f("ix_users_external_id"), table_name="users")
    op.create_unique_constraint(op.f("uq_users_auth_provider"), "users", ["auth_provider", "external_id"])

    # --- audit_events ------------------------------------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_external_id", sa.String(length=255), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'denied', 'failure')", name=op.f("ck_audit_events_outcome")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_occurred_at"), "audit_events", ["occurred_at"], unique=False)
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"], unique=False)
    op.create_index(op.f("ix_audit_events_target_id"), "audit_events", ["target_id"], unique=False)

    # Append-only: the application (and anyone with normal table privileges) can only INSERT.
    op.execute(
        """
        CREATE FUNCTION audit_events_block_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only: % is not allowed', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$;
        """
    )
    op.execute(
        "CREATE TRIGGER audit_events_no_update_delete BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION audit_events_block_mutation();"
    )
    op.execute(
        "CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_events_block_mutation();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events;")
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_update_delete ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS audit_events_block_mutation();")
    op.drop_index(op.f("ix_audit_events_target_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_action"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_occurred_at"), table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_constraint(op.f("uq_users_auth_provider"), "users", type_="unique")
    op.create_index(op.f("ix_users_external_id"), "users", ["external_id"], unique=True)
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "auth_provider")
