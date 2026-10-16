"""kullanici geri bildirimleri

E7: önerinin yararlı/doğru olup olmadığına dair kişisel veri içermeyen kayıt.

Revision ID: a7c3e9f1b2d4
Revises: e9c1d4b7a2f6
Create Date: 2026-10-16 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c3e9f1b2d4"
down_revision: Union[str, Sequence[str], None] = "e9c1d4b7a2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kullanici_geri_bildirimleri",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("hedef_turu", sa.String(16), nullable=False),
        sa.Column("hedef_kimligi", sa.String(64), nullable=True),
        sa.Column("yararli_mi", sa.Boolean(), nullable=True),
        sa.Column("dogru_mu", sa.Boolean(), nullable=True),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column("rol", sa.String(16), nullable=False),
        sa.Column("yazilim_surumu", sa.String(32), nullable=True),
        sa.Column("olusturulma_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kullanici_geri_bildirimleri_hedef", "kullanici_geri_bildirimleri", ["hedef_turu", "olusturulma_zamani"]
    )


def downgrade() -> None:
    op.drop_index("ix_kullanici_geri_bildirimleri_hedef", table_name="kullanici_geri_bildirimleri")
    op.drop_table("kullanici_geri_bildirimleri")
