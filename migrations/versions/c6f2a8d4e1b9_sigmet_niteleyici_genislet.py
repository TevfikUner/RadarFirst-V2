"""sigmet niteleyici genislet

VA SIGMET'lerinde AWC 'qualifier' alanı yanardağ adını taşıyor
("ERUPTION MT LEWOTOLOK", 21 karakter); 16 karakter toplu INSERT'i düşürüyordu.

Revision ID: c6f2a8d4e1b9
Revises: b8e4f1a6c2d9
Create Date: 2026-10-04 12:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c6f2a8d4e1b9"
down_revision: Union[str, Sequence[str], None] = "b8e4f1a6c2d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "sigmetler", "niteleyici", existing_type=sa.String(length=16), type_=sa.String(length=128), existing_nullable=True
    )


def downgrade() -> None:
    op.execute("UPDATE sigmetler SET niteleyici = left(niteleyici, 16) WHERE length(niteleyici) > 16")
    op.alter_column(
        "sigmetler", "niteleyici", existing_type=sa.String(length=128), type_=sa.String(length=16), existing_nullable=True
    )
