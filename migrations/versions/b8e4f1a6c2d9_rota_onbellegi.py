"""rota onbellegi

Süreçler arası paylaşılan rota önbelleği (bkz. api/rota_onbellegi.py).

Revision ID: b8e4f1a6c2d9
Revises: a5d3e9b2c7f1
Create Date: 2026-10-02 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b8e4f1a6c2d9"
down_revision: Union[str, Sequence[str], None] = "a5d3e9b2c7f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rota_onbellegi",
        sa.Column("anahtar", sa.String(64), nullable=False),
        sa.Column("olusturma", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sonuc", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("anahtar"),
        prefixes=["UNLOGGED"],
    )
    op.create_index("ix_rota_onbellegi_olusturma", "rota_onbellegi", ["olusturma"])


def downgrade() -> None:
    op.drop_index("ix_rota_onbellegi_olusturma", table_name="rota_onbellegi")
    op.drop_table("rota_onbellegi")
