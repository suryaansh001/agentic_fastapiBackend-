"""agentRun subagent parent/child columns

Revision ID: 4b2a91c7d0e3
Revises: 10cef88f7583
Create Date: 2026-10-07 09:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b2a91c7d0e3'
down_revision: Union[str, None] = '10cef88f7583'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'agentRun',
        sa.Column('parent_run_id', sa.String(), nullable=True),
    )
    op.add_column(
        'agentRun',
        sa.Column('child_run_ids', sa.JSON(), nullable=True),
    )
    op.create_index(
        'ix_agentRun_parent_run_id',
        'agentRun',
        ['parent_run_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_agentRun_parent_run_id', table_name='agentRun')
    op.drop_column('agentRun', 'child_run_ids')
    op.drop_column('agentRun', 'parent_run_id')
