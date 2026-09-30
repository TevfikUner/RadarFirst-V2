"""ml ornekleri

ML eğitim örnekleri: seyir irtifasındaki IEM PIREP'leri ve ERA5 özellikleri
(bkz. ml/ml_veri_hatti.py).

Revision ID: c4e7a1d9b3f2
Revises: a7c3e91f0b24
Create Date: 2026-09-30 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c4e7a1d9b3f2"
down_revision: Union[str, Sequence[str], None] = "a7c3e91f0b24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ml_ornekleri",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pirep_anahtari", sa.String(96), nullable=False),
        sa.Column("kaynak", sa.String(16), nullable=False),
        sa.Column("zaman", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enlem", sa.Float(), nullable=False),
        sa.Column("boylam", sa.Float(), nullable=False),
        sa.Column("irtifa_ft", sa.Float(), nullable=False),
        sa.Column("sinif", sa.Integer(), nullable=False),
        sa.Column("durum", sa.String(16), server_default="bekliyor", nullable=False),
        sa.Column("ozellikler", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("deneme_sayisi", sa.Integer(), server_default="0", nullable=False),
        sa.Column("son_hata", sa.Text(), nullable=True),
        sa.Column("olusturulma_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("guncellenme_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pirep_anahtari", name="uq_ml_ornekleri_pirep_anahtari"),
    )
    op.create_index("ix_ml_ornekleri_durum_zaman", "ml_ornekleri", ["durum", "zaman"])


def downgrade() -> None:
    op.drop_index("ix_ml_ornekleri_durum_zaman", table_name="ml_ornekleri")
    op.drop_table("ml_ornekleri")
