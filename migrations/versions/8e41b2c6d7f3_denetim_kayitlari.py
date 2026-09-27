"""denetim kayitlari

API'deki değiştirici isteklerin kim/ne/sonuç denetim kaydı (bkz. depo/denetim.py).

Revision ID: 8e41b2c6d7f3
Revises: 3c9d1e7a5b20
Create Date: 2026-09-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e41b2c6d7f3'
down_revision: Union[str, Sequence[str], None] = '3c9d1e7a5b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "denetim_kayitlari",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("zaman", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("kimlik", sa.String(64), nullable=False),
        sa.Column("rol", sa.String(16), nullable=True),
        sa.Column("yontem", sa.String(8), nullable=False),
        sa.Column("yol", sa.String(500), nullable=False),
        sa.Column("durum_kodu", sa.Integer(), nullable=False),
        sa.Column("istemci_ip", sa.String(64), nullable=True),
        sa.Column("sure_ms", sa.Integer(), nullable=False),
    )
    op.create_index("ix_denetim_kayitlari_zaman", "denetim_kayitlari", ["zaman"])


def downgrade() -> None:
    op.drop_index("ix_denetim_kayitlari_zaman", table_name="denetim_kayitlari")
    op.drop_table("denetim_kayitlari")
