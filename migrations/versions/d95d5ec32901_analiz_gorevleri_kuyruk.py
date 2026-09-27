"""analiz gorevleri kuyruk

Revision ID: d95d5ec32901
Revises: 6f630f49163d
Create Date: 2026-09-26 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd95d5ec32901'
down_revision: Union[str, Sequence[str], None] = '6f630f49163d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analiz_gorevleri", sa.Column("parametreler", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("analiz_gorevleri", sa.Column("bildirim_webhook_url", sa.Text(), nullable=True))
    op.add_column(
        "analiz_gorevleri", sa.Column("deneme_sayisi", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("analiz_gorevleri", sa.Column("isci", sa.String(64), nullable=True))
    for kolon in ("baslama_zamani", "kalp_atisi", "bitis_zamani"):
        op.add_column("analiz_gorevleri", sa.Column(kolon, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for kolon in ("bitis_zamani", "kalp_atisi", "baslama_zamani", "isci", "deneme_sayisi", "bildirim_webhook_url"):
        op.drop_column("analiz_gorevleri", kolon)
    op.drop_column("analiz_gorevleri", "parametreler")
