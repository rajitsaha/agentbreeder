"""Add prompt_versions table for prompt versioning (M6.2)

Revision ID: 005
Revises: 004
Create Date: 2026-03-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "prompt_id",
            UUID(as_uuid=True),
            sa.ForeignKey("prompts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_prompt_versions_prompt_id", "prompt_versions", ["prompt_id"])
    op.create_index("ix_prompt_versions_created_at", "prompt_versions", ["created_at"])
    op.create_index(
        "ix_prompt_versions_prompt_id_version",
        "prompt_versions",
        ["prompt_id", "version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_versions_prompt_id_version")
    op.drop_index("ix_prompt_versions_created_at")
    op.drop_index("ix_prompt_versions_prompt_id")
    op.drop_table("prompt_versions")
