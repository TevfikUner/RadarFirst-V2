"""denetim veri temizligi

6 Ekim 2026 denetimi: AWC validTimeFrom=0 ile 1970 başlangıçlı yazılan
SIGMET'ler bitiş - 4 saate (SIGMET yayın ufku) çekilir; pandas NaN'ından
gelen "NaN" metinli havalimanı/icao24 alanları NULL yapılır. Veri onarımıdır;
downgrade bozuk değerleri geri yazmaz.

Revision ID: e9c1d4b7a2f6
Revises: c6f2a8d4e1b9
Create Date: 2026-10-06 17:30:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e9c1d4b7a2f6"
down_revision: Union[str, Sequence[str], None] = "c6f2a8d4e1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE sigmetler SET gecerlilik_baslangic = gecerlilik_bitis - interval '4 hours' "
        "WHERE gecerlilik_baslangic < '2000-01-01' AND gecerlilik_bitis >= '2000-01-01'"
    )
    for sutun in ("icao24", "kalkis_havaalani", "varis_havaalani"):
        op.execute(f"UPDATE ucuslar SET {sutun} = NULL WHERE {sutun} IN ('NaN', 'nan', 'None', '')")


def downgrade() -> None:
    pass
