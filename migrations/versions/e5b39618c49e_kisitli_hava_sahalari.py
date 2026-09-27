"""kisitli hava sahalari

Revision ID: e5b39618c49e
Revises: 2aa66ec79c21
Create Date: 2026-09-26 22:50:41.767703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5b39618c49e'
down_revision: Union[str, Sequence[str], None] = '2aa66ec79c21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kisitli_hava_sahalari",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dis_kimlik", sa.String(128), nullable=False),
        sa.Column("kaynak", sa.String(32), nullable=False),
        sa.Column("ad", sa.String(), nullable=False),
        sa.Column("tur", sa.String(16), nullable=False),
        sa.Column("taban_ft", sa.Integer(), nullable=True),
        sa.Column("tavan_ft", sa.Integer(), nullable=True),
        sa.Column("gecerlilik_baslangic", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gecerlilik_bitis", sa.DateTime(timezone=True), nullable=True),
        sa.Column("poligon", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enlem_min", sa.Float(), nullable=False),
        sa.Column("enlem_maks", sa.Float(), nullable=False),
        sa.Column("boylam_min", sa.Float(), nullable=False),
        sa.Column("boylam_maks", sa.Float(), nullable=False),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column("guncellenme_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("dis_kimlik", name="uq_kisitli_hava_sahalari_dis_kimlik"),
    )
    op.create_index(
        "ix_kisitli_hava_sahalari_kutu",
        "kisitli_hava_sahalari",
        ["enlem_min", "enlem_maks", "boylam_min", "boylam_maks"],
    )


def downgrade() -> None:
    op.drop_index("ix_kisitli_hava_sahalari_kutu", table_name="kisitli_hava_sahalari")
    op.drop_table("kisitli_hava_sahalari")
