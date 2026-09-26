"""analiz gorevleri, sigmetler, hava durumu kupleri

Revision ID: 9ad326d01cac
Revises: 64f50586f90c
Create Date: 2026-09-26 14:41:47.896610

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9ad326d01cac'
down_revision: Union[str, Sequence[str], None] = '64f50586f90c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analiz_gorevleri",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tur", sa.String(16), nullable=False),
        sa.Column("durum", sa.String(16), nullable=False),
        sa.Column("ucus_numarasi", sa.String(), nullable=True),
        sa.Column("tarih", sa.String(10), nullable=True),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column("ozet", postgresql.JSONB(), nullable=True),
        sa.Column("olusturulma_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("guncellenme_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_analiz_gorevleri_durum_olusturulma", "analiz_gorevleri", ["durum", "olusturulma_zamani"])

    op.create_table(
        "sigmetler",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("dis_kimlik", sa.String(64), nullable=False),
        sa.Column("kaynak", sa.String(16), nullable=False),
        sa.Column("fir_kodu", sa.String(16), nullable=True),
        sa.Column("seri_no", sa.String(16), nullable=True),
        sa.Column("tehlike", sa.String(16), nullable=False),
        sa.Column("niteleyici", sa.String(16), nullable=True),
        sa.Column("gecerlilik_baslangic", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gecerlilik_bitis", sa.DateTime(timezone=True), nullable=False),
        sa.Column("taban_ft", sa.Integer(), nullable=True),
        sa.Column("tavan_ft", sa.Integer(), nullable=True),
        sa.Column("poligon", postgresql.JSONB(), nullable=False),
        sa.Column("enlem_min", sa.Float(), nullable=False),
        sa.Column("enlem_maks", sa.Float(), nullable=False),
        sa.Column("boylam_min", sa.Float(), nullable=False),
        sa.Column("boylam_maks", sa.Float(), nullable=False),
        sa.Column("ham_metin", sa.Text(), nullable=True),
        sa.Column("alinma_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("dis_kimlik", name="uq_sigmetler_dis_kimlik"),
    )
    op.create_index("ix_sigmetler_gecerlilik", "sigmetler", ["gecerlilik_baslangic", "gecerlilik_bitis"])
    op.create_index("ix_sigmetler_kutu", "sigmetler", ["enlem_min", "enlem_maks", "boylam_min", "boylam_maks"])

    op.create_table(
        "hava_durumu_kupleri",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kaynak", sa.String(16), nullable=False),
        sa.Column("model_calisma_zamani", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gecerlilik_baslangic", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gecerlilik_bitis", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enlem_min", sa.Float(), nullable=False),
        sa.Column("enlem_maks", sa.Float(), nullable=False),
        sa.Column("boylam_min", sa.Float(), nullable=False),
        sa.Column("boylam_maks", sa.Float(), nullable=False),
        sa.Column("basinc_seviyeleri_hpa", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("dosya_yolu", sa.String(), nullable=False),
        sa.Column("durum", sa.String(16), nullable=False),
        sa.Column("boyut_bayt", sa.BigInteger(), nullable=True),
        sa.Column("olusturulma_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("dosya_yolu", name="uq_hava_durumu_kupleri_dosya_yolu"),
    )
    op.create_index(
        "ix_hava_durumu_kupleri_gecerlilik", "hava_durumu_kupleri", ["gecerlilik_baslangic", "gecerlilik_bitis"]
    )


def downgrade() -> None:
    op.drop_index("ix_hava_durumu_kupleri_gecerlilik", table_name="hava_durumu_kupleri")
    op.drop_table("hava_durumu_kupleri")
    op.drop_index("ix_sigmetler_kutu", table_name="sigmetler")
    op.drop_index("ix_sigmetler_gecerlilik", table_name="sigmetler")
    op.drop_table("sigmetler")
    op.drop_index("ix_analiz_gorevleri_durum_olusturulma", table_name="analiz_gorevleri")
    op.drop_table("analiz_gorevleri")
