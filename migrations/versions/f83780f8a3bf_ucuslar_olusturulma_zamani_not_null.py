"""ucuslar olusturulma zamani not null

ORM modeliyle (Ucus.olusturulma_zamani: Mapped[object], nullable=False'u
ima eder) ilk şema migration'ı (64f50586f90c) arasındaki sapmayı giderir --
sütun server_default=now() ile her zaman dolduruluyor, gerçek bir NULL
hiç oluşmuyordu (uygulama koleksiyonlarında doğrulandı).

Revision ID: f83780f8a3bf
Revises: 7730e2b167a7
Create Date: 2026-09-27 01:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f83780f8a3bf'
down_revision: Union[str, Sequence[str], None] = '7730e2b167a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("ucuslar", "olusturulma_zamani", nullable=False)


def downgrade() -> None:
    op.alter_column("ucuslar", "olusturulma_zamani", nullable=True)
