"""add buy_date column to trades table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-20

"""
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS buy_date DATE")


def downgrade() -> None:
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS buy_date")
