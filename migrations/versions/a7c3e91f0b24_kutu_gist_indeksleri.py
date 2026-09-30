"""kutu gist indeksleri

SIGMET ve kısıtlı saha sınır kutusu aramalarında 4 sütunlu B-tree yerine
Postgres'in yerleşik `box` tipi üzerinde GiST (PostGIS gerekmez). İfade
depo/models.kutu_ifadesi ile birebir aynı olmalı -- sorgu da onu kullanır.

Revision ID: a7c3e91f0b24
Revises: 8e41b2c6d7f3
Create Date: 2026-09-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c3e91f0b24'
down_revision: Union[str, Sequence[str], None] = '8e41b2c6d7f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KUTU = "box(point(boylam_min, enlem_min), point(boylam_maks, enlem_maks))"


def upgrade() -> None:
    op.execute(f"CREATE INDEX ix_sigmetler_kutu_gist ON sigmetler USING gist (({_KUTU}))")
    op.execute(f"CREATE INDEX ix_kisitli_hava_sahalari_kutu_gist ON kisitli_hava_sahalari USING gist (({_KUTU}))")
    op.drop_index("ix_sigmetler_kutu", table_name="sigmetler")
    op.drop_index("ix_kisitli_hava_sahalari_kutu", table_name="kisitli_hava_sahalari")


def downgrade() -> None:
    op.create_index(
        "ix_kisitli_hava_sahalari_kutu",
        "kisitli_hava_sahalari",
        ["enlem_min", "enlem_maks", "boylam_min", "boylam_maks"],
    )
    op.create_index("ix_sigmetler_kutu", "sigmetler", ["enlem_min", "enlem_maks", "boylam_min", "boylam_maks"])
    op.drop_index("ix_kisitli_hava_sahalari_kutu_gist", table_name="kisitli_hava_sahalari")
    op.drop_index("ix_sigmetler_kutu_gist", table_name="sigmetler")
