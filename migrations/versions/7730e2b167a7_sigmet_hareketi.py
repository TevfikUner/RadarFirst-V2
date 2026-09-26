"""sigmet hareketi

Revision ID: 7730e2b167a7
Revises: d95d5ec32901
Create Date: 2026-09-27 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7730e2b167a7'
down_revision: Union[str, Sequence[str], None] = 'd95d5ec32901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sigmetler", sa.Column("hareket_yonu_derece", sa.Float(), nullable=True))
    op.add_column("sigmetler", sa.Column("hareket_hizi_kt", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("sigmetler", "hareket_hizi_kt")
    op.drop_column("sigmetler", "hareket_yonu_derece")
