"""kisitli saha aktivasyonu

Kısıtlı/askerî sahalara aktif zaman aralıkları ve haftalık takvim
(bkz. veri/saha_aktivasyonu.py). NULL: geçerlilik içinde her zaman aktif.

Revision ID: f4a9c2e7b1d3
Revises: e2b6c8d4a1f9
Create Date: 2026-10-02 02:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f4a9c2e7b1d3"
down_revision: Union[str, Sequence[str], None] = "e2b6c8d4a1f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kisitli_hava_sahalari", sa.Column("aktivasyon", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("kisitli_hava_sahalari", "aktivasyon")
