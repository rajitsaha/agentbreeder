"""Add litellm_key_refs table for virtual key metadata.

Revision ID: 012
Revises: 011
Create Date: 2026-04-24
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: str = "011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "litellm_key_refs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key_alias", sa.String(255), unique=True, nullable=False),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("litellm_key_id", sa.String(255), nullable=True),
        sa.Column(
            "scope_type",
            sa.Enum(
                "org",
                "team",
                "user",
                "agent",
                "service_principal",
                name="keyscopetype",
            ),
            nullable=False,
        ),
        sa.Column("scope_id", sa.String(255), nullable=False),
        sa.Column("team_id", sa.String(100), nullable=True),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("allowed_models", sa.JSON, nullable=True),
        sa.Column("max_budget", sa.Float, nullable=True),
        sa.Column(
            "budget_duration",
            sa.Enum("daily", "weekly", "monthly", name="budgetduration"),
            nullable=True,
        ),
        sa.Column("tpm_limit", sa.Integer, nullable=True),
        sa.Column("rpm_limit", sa.Integer, nullable=True),
        sa.Column("tags", sa.JSON, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_litellm_key_refs_key_alias", "litellm_key_refs", ["key_alias"])
    op.create_index(
        "ix_litellm_key_refs_scope", "litellm_key_refs", ["scope_type", "scope_id"]
    )
    op.create_index("ix_litellm_key_refs_team", "litellm_key_refs", ["team_id"])
    op.create_index("ix_litellm_key_refs_agent", "litellm_key_refs", ["agent_name"])


def downgrade() -> None:
    op.drop_index("ix_litellm_key_refs_agent", "litellm_key_refs")
    op.drop_index("ix_litellm_key_refs_team", "litellm_key_refs")
    op.drop_index("ix_litellm_key_refs_scope", "litellm_key_refs")
    op.drop_index("ix_litellm_key_refs_key_alias", "litellm_key_refs")
    op.drop_table("litellm_key_refs")
    op.execute("DROP TYPE IF EXISTS keyscopetype")
    op.execute("DROP TYPE IF EXISTS budgetduration")
