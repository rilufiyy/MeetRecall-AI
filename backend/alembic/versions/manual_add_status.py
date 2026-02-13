"""Add status column

Revision ID: manual_add_status
Revises: 
Create Date: 2024-02-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'manual_add_status'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add status column to meetings table
    # We use server_default to ensure existing rows get a value
    op.add_column('meetings', sa.Column('status', sa.String(), server_default='UPLOADED', nullable=True))
    
    # Optional: Update existing nulls if any (redundant with server_default but safe)
    op.execute("UPDATE meetings SET status = 'UPLOADED' WHERE status IS NULL")


def downgrade() -> None:
    op.drop_column('meetings', 'status')
