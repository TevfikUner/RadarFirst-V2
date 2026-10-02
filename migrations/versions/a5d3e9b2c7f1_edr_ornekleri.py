"""edr ornekleri

M1: MADIS uçak EDR gözlemleri ve ERA5 özellikleri (bkz. ml/edr_eslestirme.py).

Revision ID: a5d3e9b2c7f1
Revises: f4a9c2e7b1d3
Create Date: 2026-10-02 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a5d3e9b2c7f1"
down_revision: Union[str, Sequence[str], None] = "f4a9c2e7b1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "edr_ornekleri",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("gozlem_anahtari", sa.String(96), nullable=False),
        sa.Column("kaynak", sa.String(16), nullable=False),
        sa.Column("zaman", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enlem", sa.Float(), nullable=False),
        sa.Column("boylam", sa.Float(), nullable=False),
        sa.Column("irtifa_ft", sa.Float(), nullable=False),
        sa.Column("max_edr", sa.Float(), nullable=False),
        sa.Column("med_edr", sa.Float(), nullable=False),
        sa.Column("edr_sinifi", sa.Integer(), nullable=False),
        sa.Column("kalite", sa.String(4), nullable=True),
        sa.Column("ml_ornek_id", sa.BigInteger(), nullable=True),
        sa.Column("ozellikler", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("olusturulma_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gozlem_anahtari", name="uq_edr_ornekleri_gozlem_anahtari"),
    )
    op.create_index("ix_edr_ornekleri_zaman", "edr_ornekleri", ["zaman"])


def downgrade() -> None:
    op.drop_index("ix_edr_ornekleri_zaman", table_name="edr_ornekleri")
    op.drop_table("edr_ornekleri")
