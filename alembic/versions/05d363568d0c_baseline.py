"""baseline

Revision ID: 05d363568d0c
Revises:
Create Date: 2026-10-06

"""
import os
import sys
from logging.config import fileConfig

from alembic import op

# Make the project root importable when alembic loads this file.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database.session import Base  # noqa: E402
import app.database.models  # noqa: F401,E402  (registers every table on Base.metadata)

# revision identifiers, used by Alembic.
revision = "05d363568d0c"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Baseline: create the full schema from the ORM metadata.
    # create_all resolves table dependency ordering (including circular
    # FKs such as agentDefinition <-> agentVersion) which a flat
    # op.create_table sequence cannot express.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
