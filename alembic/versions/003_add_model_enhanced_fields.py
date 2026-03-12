"""Add enhanced fields to models table

Revision ID: 003
Revises: 002
Create Date: 2026-03-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("models", sa.Column("context_window", sa.Integer(), nullable=True))
    op.add_column("models", sa.Column("max_output_tokens", sa.Integer(), nullable=True))
    op.add_column("models", sa.Column("input_price_per_million", sa.Float(), nullable=True))
    op.add_column("models", sa.Column("output_price_per_million", sa.Float(), nullable=True))
    op.add_column("models", sa.Column("capabilities", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("models", "capabilities")
    op.drop_column("models", "output_price_per_million")
    op.drop_column("models", "input_price_per_million")
    op.drop_column("models", "max_output_tokens")
    op.drop_column("models", "context_window")
