"""Add created_by (owner email FK) to all registry asset tables.

Revision ID: 014
Revises: 013
Create Date: 2026-04-24

Phase 1 RBAC (issue #128): adds a nullable created_by VARCHAR(255) column to
every registry asset table so that every resource can be attributed to the user
who created it. The column is nullable to avoid breaking existing rows. A future
migration (Phase 2) can backfill and make it non-nullable once the application
is writing the field consistently.

Tables patched:
  agents, tools, models, prompts, knowledge_bases, mcp_servers
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: str = "013"
branch_labels = None
depends_on = None

# Tables that need a created_by column
_ASSET_TABLES = [
    "agents",
    "tools",
    "models",
    "prompts",
    "knowledge_bases",
    "mcp_servers",
]


def upgrade() -> None:
    for table in _ASSET_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "created_by",
                    sa.String(255),
                    nullable=True,
                )
            )
            batch_op.create_index(
                f"ix_{table}_created_by",
                ["created_by"],
            )


def downgrade() -> None:
    for table in _ASSET_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_created_by")
            batch_op.drop_column("created_by")
