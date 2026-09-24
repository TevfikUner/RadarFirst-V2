"""ilk sema ucuslar ve edr_olcumleri

Bu, projenin BASELINE (temel) migration'idir -- models.py'deki Ucus ve
EdrOlcumu ORM modelleriyle birebir ayni semayi elle (autogenerate yerine)
tanimlar. Elle yazilmasinin sebebi: bu migration olusturuldugunda gercek
gelistirme veritabaninda (Turbulence-db) bu tablolar zaten
Base.metadata.create_all() ile onceden olusturulmustu -- autogenerate o
veritabanina karsi calistirilsaydi "fark yok" derdi (bos bir migration
uretirdi). Var olan veritabani, bu migration olusturulduktan sonra
'alembic stamp head' ile (CREATE calistirilmadan) bu revizyona isaretlendi.
Bu migration'i SIFIRDAN bir veritabaninda calistirmak (alembic upgrade head)
asagidaki tablolari dogru sekilde olusturur.

Revision ID: 64f50586f90c
Revises:
Create Date: 2026-09-24 19:50:18.750176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64f50586f90c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ucuslar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ucus_numarasi", sa.String(), nullable=False),
        sa.Column("tarih", sa.Date(), nullable=False),
        sa.Column("icao24", sa.String(), nullable=True),
        sa.Column("kalkis_havaalani", sa.String(), nullable=True),
        sa.Column("varis_havaalani", sa.String(), nullable=True),
        sa.Column("olusturulma_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("ucus_numarasi", "tarih", name="uq_ucus_numarasi_tarih"),
    )

    op.create_table(
        "edr_olcumleri",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ucus_id", sa.Integer(), sa.ForeignKey("ucuslar.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zaman", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enlem", sa.Float(), nullable=False),
        sa.Column("boylam", sa.Float(), nullable=False),
        sa.Column("ti1_indeksi", sa.Float(), nullable=True),
        sa.Column("edr_proxy", sa.Float(), nullable=True),
        sa.Column("richardson_sayisi", sa.Float(), nullable=True),
        sa.Column("dinamik_kararsizlik", sa.Boolean(), nullable=True),
        sa.Column("basinc_hpa", sa.Float(), nullable=True),
    )
    op.create_index("ix_edr_olcumleri_ucus_id", "edr_olcumleri", ["ucus_id"])
    op.create_index("ix_edr_olcumleri_zaman", "edr_olcumleri", ["zaman"])


def downgrade() -> None:
    op.drop_index("ix_edr_olcumleri_zaman", table_name="edr_olcumleri")
    op.drop_index("ix_edr_olcumleri_ucus_id", table_name="edr_olcumleri")
    op.drop_table("edr_olcumleri")
    op.drop_table("ucuslar")
