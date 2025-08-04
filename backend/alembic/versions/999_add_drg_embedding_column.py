"""add embedding column to drg_procedures

Revision ID: 999_add_drg_embedding_column
Revises: 
Create Date: 2025-08-04
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '999_add_drg_embedding_column'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Add 1536-dim pgvector column to drg_procedures if not present"""
    with op.batch_alter_table("drg_procedures") as batch_op:
        batch_op.add_column(sa.Column("embedding", Vector(1536)))


def downgrade() -> None:
    with op.batch_alter_table("drg_procedures") as batch_op:
        batch_op.drop_column("embedding")
