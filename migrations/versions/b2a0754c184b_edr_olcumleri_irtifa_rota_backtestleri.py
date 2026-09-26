"""edr olcumleri irtifa, rota backtestleri

Revision ID: b2a0754c184b
Revises: 9ad326d01cac
Create Date: 2026-09-26 15:22:42.146203

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2a0754c184b'
down_revision: Union[str, Sequence[str], None] = '9ad326d01cac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("edr_olcumleri", sa.Column("irtifa_m", sa.Float(), nullable=True))

    metrik = []
    for rota in ("gercek", "buyuk_daire", "optimize"):
        metrik += [
            sa.Column(f"{rota}_mesafe_km", sa.Float(), nullable=False),
            sa.Column(f"{rota}_sure_dk", sa.Float(), nullable=False),
            sa.Column(f"{rota}_riskli_oran", sa.Float(), nullable=True),
            sa.Column(f"{rota}_sigmet_ihlali", sa.Integer(), nullable=False),
        ]
    op.create_table(
        "rota_backtestleri",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ucus_id", sa.Integer(), sa.ForeignKey("ucuslar.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ucak_modeli", sa.String(8), nullable=False),
        sa.Column("seyir_irtifasi_ft", sa.Float(), nullable=False),
        sa.Column("veri_kaynagi", sa.String(24), nullable=False),
        sa.Column("kacinma_stratejisi", sa.String(16), nullable=False),
        sa.Column("guvenli_rota_bulundu_mu", sa.Boolean(), nullable=False),
        *metrik,
        sa.Column("olusturulma_zamani", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("ucus_id", name="uq_rota_backtestleri_ucus_id"),
    )


def downgrade() -> None:
    op.drop_table("rota_backtestleri")
    op.drop_column("edr_olcumleri", "irtifa_m")
