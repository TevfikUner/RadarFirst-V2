"""ml ornekleri pencere dosyasi

ERA5 pencere deposu kataloğu: örneğin penceresinin depo köküne göreli dosya
yolu (bkz. ml/ozellik_deposu.py, docs/adr/0002-era5-pencere-deposu.md).

Revision ID: d1f8a2c6e4b7
Revises: c4e7a1d9b3f2
Create Date: 2026-10-01 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1f8a2c6e4b7"
down_revision: Union[str, Sequence[str], None] = "c4e7a1d9b3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ml_ornekleri", sa.Column("pencere_dosyasi", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("ml_ornekleri", "pencere_dosyasi")
