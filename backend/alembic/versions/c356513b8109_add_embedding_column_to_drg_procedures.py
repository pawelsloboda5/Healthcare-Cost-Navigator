"""add_embedding_column_to_drg_procedures

Revision ID: c356513b8109
Revises: 624858ae931f
Create Date: 2025-07-25 18:25:28.395537

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'c356513b8109'
down_revision: Union[str, None] = '624858ae931f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add embedding column to drg_procedures table
    op.add_column('drg_procedures', sa.Column('embedding', Vector(1536), nullable=True))


def downgrade() -> None:
    # Remove embedding column from drg_procedures table
    op.drop_column('drg_procedures', 'embedding')
