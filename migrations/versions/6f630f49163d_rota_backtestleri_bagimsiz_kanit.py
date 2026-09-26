"""rota backtestleri bagimsiz kanit

Revision ID: 6f630f49163d
Revises: e5b39618c49e
Create Date: 2026-09-26 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6f630f49163d'
down_revision: Union[str, Sequence[str], None] = 'e5b39618c49e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KOLONLAR = [
    f"{rota}_{metrik}"
    for rota in ("gercek", "buyuk_daire", "optimize")
    for metrik in ("turb_sigmet", "pirep_raporu", "mog_pirep")
]


def upgrade() -> None:
    op.add_column(
        "rota_backtestleri", sa.Column("kanit_kaynaklari", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    for kolon in _KOLONLAR:
        op.add_column("rota_backtestleri", sa.Column(kolon, sa.Integer(), nullable=True))


def downgrade() -> None:
    for kolon in reversed(_KOLONLAR):
        op.drop_column("rota_backtestleri", kolon)
    op.drop_column("rota_backtestleri", "kanit_kaynaklari")
