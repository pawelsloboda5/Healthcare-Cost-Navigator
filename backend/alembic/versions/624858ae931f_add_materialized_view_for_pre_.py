"""Add materialized view for pre-aggregated state costs

Revision ID: 624858ae931f
Revises: 2955a6172c4e
Create Date: 2025-07-25 17:34:26.511958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '624858ae931f'
down_revision: Union[str, None] = '2955a6172c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create materialized view for pre-aggregated state-level procedure costs
    # This enables sub-5ms queries for "most expensive procedures by state"
    op.execute("""
        CREATE MATERIALIZED VIEW mv_state_drg_avg_cost AS
        SELECT 
            pp.provider_state,
            d.drg_code,
            d.drg_description,
            AVG(pp.average_covered_charges) AS avg_cost,
            COUNT(*) AS provider_count,
            MIN(pp.average_covered_charges) AS min_cost,
            MAX(pp.average_covered_charges) AS max_cost
        FROM provider_procedures pp
        JOIN drg_procedures d ON pp.drg_code = d.drg_code
        WHERE pp.provider_state IS NOT NULL
        GROUP BY pp.provider_state, d.drg_code, d.drg_description;
    """)
    
    # Create unique index for fast lookups
    op.execute("""
        CREATE UNIQUE INDEX mv_state_drg_pk
        ON mv_state_drg_avg_cost (provider_state, drg_code);
    """)
    
    # Create index for ordering by cost
    op.execute("""
        CREATE INDEX mv_state_drg_cost_desc
        ON mv_state_drg_avg_cost (provider_state, avg_cost DESC);
    """)
    
    # Initial population of the materialized view
    op.execute("REFRESH MATERIALIZED VIEW mv_state_drg_avg_cost;")


def downgrade() -> None:
    # Drop the materialized view and its indexes
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_state_drg_avg_cost CASCADE;")
