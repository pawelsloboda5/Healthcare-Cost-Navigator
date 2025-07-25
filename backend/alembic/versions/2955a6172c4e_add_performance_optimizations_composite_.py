"""Add performance optimizations - composite index and denormalized state

Revision ID: 2955a6172c4e
Revises: 
Create Date: 2025-07-25 17:33:49.579917

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2955a6172c4e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add provider_state column to provider_procedures for denormalization
    op.add_column('provider_procedures', sa.Column('provider_state', sa.CHAR(2), nullable=True))
    
    # Populate the new column with data from providers table
    op.execute("""
        UPDATE provider_procedures pp 
        SET provider_state = p.provider_state 
        FROM providers p 
        WHERE p.provider_id = pp.provider_id
    """)
    
    # Add composite covering index for optimal query performance
    # This index covers the JOIN condition and includes the aggregated column
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_pp_state_drg_cost_inc
        ON provider_procedures (drg_code, provider_id)
        INCLUDE (average_covered_charges)
    """)
    
    # Add index on the new provider_state column for direct filtering
    op.create_index('idx_pp_provider_state', 'provider_procedures', ['provider_state'])
    
    # Create trigger to keep provider_state in sync with providers table
    op.execute("""
        CREATE OR REPLACE FUNCTION trg_sync_provider_state() RETURNS trigger AS $$
        BEGIN
            NEW.provider_state := (
                SELECT provider_state 
                FROM providers 
                WHERE provider_id = NEW.provider_id
            );
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER provider_state_sync_trigger
        BEFORE INSERT OR UPDATE OF provider_id
        ON provider_procedures
        FOR EACH ROW EXECUTE FUNCTION trg_sync_provider_state();
    """)


def downgrade() -> None:
    # Drop the trigger and function
    op.execute("DROP TRIGGER IF EXISTS provider_state_sync_trigger ON provider_procedures")
    op.execute("DROP FUNCTION IF EXISTS trg_sync_provider_state()")
    
    # Drop indexes
    op.drop_index('idx_pp_provider_state', 'provider_procedures')
    op.execute("DROP INDEX IF EXISTS idx_pp_state_drg_cost_inc")
    
    # Drop the denormalized column
    op.drop_column('provider_procedures', 'provider_state')
