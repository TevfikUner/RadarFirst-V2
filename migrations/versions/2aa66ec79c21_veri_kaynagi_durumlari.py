"""veri kaynagi durumlari

Revision ID: 2aa66ec79c21
Revises: b2a0754c184b
Create Date: 2026-09-26 22:37:59.644106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '2aa66ec79c21'
down_revision: Union[str, Sequence[str], None] = 'b2a0754c184b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "veri_kaynagi_durumlari",
        sa.Column("kaynak", sa.String(32), primary_key=True),
        sa.Column("son_deneme_zamani", sa.DateTime(timezone=True), nullable=False),
        sa.Column("son_basari_zamani", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ardisik_hata_sayisi", sa.Integer(), server_default="0", nullable=False),
        sa.Column("son_hata", sa.Text(), nullable=True),
        sa.Column("son_ozet", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("veri_kaynagi_durumlari")
