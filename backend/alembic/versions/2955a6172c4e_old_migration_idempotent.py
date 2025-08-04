from sqlalchemy import inspect, CHAR, Column
from alembic import op

def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c["name"] for c in insp.get_columns("provider_procedures")]
    if "provider_state" not in cols:
        op.add_column(
            "provider_procedures",
            Column("provider_state", CHAR(2))
        )

def downgrade():
    op.drop_column("provider_procedures", "provider_state")
    