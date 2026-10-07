"""add password hashes to users

Revision ID: 7f1a2c3d4e5f
Revises: 4b2a91c7d0e3
"""
from alembic import op
import sqlalchemy as sa


revision = "7f1a2c3d4e5f"
down_revision = "4b2a91c7d0e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("password_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "password_hash")