"""İz bulutu duyarlılığı. Nem alanı SENTETİKTİR; sıcaklık ve rüzgar gerçek demo küpünden."""

import numpy as np
import pytest

from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
from turbulans_radar.fizik.iz_bulutu import duyarli_nokta_sayisi, iz_bulutu_duyarli


def test_olcut_soguk_ve_buza_gore_doymus_havayi_isaretler():
    sonuc = iz_bulutu_duyarli([220.0, 220.0, 240.0, 233.15, np.nan], [105.0, 95.0, 120.0, 100.0, 110.0])
    assert list(sonuc) == [True, False, False, True, None]
    assert duyarli_nokta_sayisi(sonuc) == 2
    assert duyarli_nokta_sayisi([None, None]) is None


@pytest.fixture(scope="module")
def veri_kupu():
    xr = pytest.importorskip("xarray")
    from test_eslestirme import NC_YOLU

    try:
        with xr.open_dataset(NC_YOLU) as kup:
            return kup.load()
    except FileNotFoundError:
        pytest.skip("Demo küpü yok.")


def test_eslestirme_nem_varsa_iz_bulutu_sutunlarini_doldurur_yoksa_bos_birakir(veri_kupu):
    from test_eslestirme import _sentetik_rota_uret

    rota = _sentetik_rota_uret(veri_kupu, n=30)
    nemsiz = rotayi_hava_durumuyla_eslestir(rota, veri_kupu)
    assert nemsiz["buz_bagil_nem_yuzde"].isna().all() and nemsiz["iz_bulutu_duyarli"].isna().all()

    nemli_kup = veri_kupu.assign(r=veri_kupu["t"] * 0 + 110.0)
    nemli = rotayi_hava_durumuyla_eslestir(rota, nemli_kup)
    kapsamda = nemli["ti1_indeksi"].notna() | nemli["basinc_hpa"].notna()
    assert (nemli.loc[kapsamda, "buz_bagil_nem_yuzde"] == 110.0).all()
    soguk = nemli.loc[kapsamda, "iz_bulutu_duyarli"].astype(bool)
    assert soguk.any()
