"""sanal pirepler

M6: ADS-B izinden seyir fazı irtifa sapması olayları (bkz. fizik/sanal_pirep.py).

Revision ID: e2b6c8d4a1f9
Revises: d1f8a2c6e4b7
Create Date: 2026-10-01 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2b6c8d4a1f9"
down_revision: Union[str, Sequence[str], None] = "d1f8a2c6e4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sanal_pirepler",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ucak", sa.String(16), nullable=False),
        sa.Column("icao24", sa.String(8), nullable=True),
        sa.Column("ucus_numarasi", sa.String(16), nullable=True),
        sa.Column("kaynak", sa.String(16), nullable=False),
        sa.Column("zaman", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baslangic", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bitis", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enlem", sa.Float(), nullable=False),
        sa.Column("boylam", sa.Float(), nullable=False),
        sa.Column("seviye_ft", sa.Float(), nullable=False),
        sa.Column("sapma_ft", sa.Float(), nullable=False),
        sa.Column("maks_dikey_hiz_ftdk", sa.Float(), nullable=True),
        sa.Column("sure_sn", sa.Float(), nullable=False),
        sa.Column("irtifa_kaynagi", sa.String(8), nullable=True),
        sa.Column("ucak_sayisi", sa.Integer(), server_default="1", nullable=False),
        sa.Column("bildirim_zamani", sa.DateTime(timezone=True), nullable=True),
        sa.Column("olusturulma_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ucak", "zaman", name="uq_sanal_pirepler_ucak_zaman"),
    )
    op.create_index("ix_sanal_pirepler_zaman", "sanal_pirepler", ["zaman"])


def downgrade() -> None:
    op.drop_index("ix_sanal_pirepler_zaman", table_name="sanal_pirepler")
    op.drop_table("sanal_pirepler")
