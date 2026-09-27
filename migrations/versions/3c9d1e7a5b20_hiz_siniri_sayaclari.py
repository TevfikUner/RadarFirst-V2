"""hiz siniri sayaclari

Süreçler/kopyalar arası paylaşılan API hız sınırı (bkz. depo/hiz_siniri.py).

Revision ID: 3c9d1e7a5b20
Revises: f83780f8a3bf
Create Date: 2026-09-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c9d1e7a5b20'
down_revision: Union[str, Sequence[str], None] = 'f83780f8a3bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hiz_siniri_sayaclari",
        sa.Column("anahtar", sa.String(200), primary_key=True),
        sa.Column("pencere_baslangic", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("sayi", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("hiz_siniri_sayaclari")
