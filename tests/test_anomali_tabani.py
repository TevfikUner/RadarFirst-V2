import numpy as np

"""Denetimsiz anomali tabanı. İzler ve PIREP'ler SENTETİKTİR."""

import pandas as pd
import pytest
from test_sanal_pirep import BASLANGIC, _sentetik_iz

from turbulans_radar.dogrulama import anomali_tabani as at
from turbulans_radar.fizik.sanal_pirep import coklu_izden_olaylar


def _pirep(sinif, boylam):
    return {
        "enlem": 40.0,
        "boylam": boylam,
        "zaman": BASLANGIC + pd.Timedelta(minutes=10),
        "irtifa_ft": 35000.0,
        "sinif": sinif,
    }


def test_ozellikler_yalniz_seyir_noktalarinda_ve_kural_orani_olayi_kapsar():
    iz = _sentetik_iz(sapma=(600, 40, 300))
    noktalar = at.seyir_noktalari(iz)
    assert not noktalar.empty and set(at.OZELLIKLER) <= set(noktalar.columns)
    olaylar, _ = coklu_izden_olaylar(iz)
    oran = at.kural_nokta_orani(noktalar, olaylar)
    assert 0 < oran < 0.2


@pytest.mark.filterwarnings("ignore:Duplicate values are leading to incorrect results:UserWarning")
def test_esit_alarm_butcesiyle_isaretler_ve_karsilastirma_raporu():
    noktalar = at.seyir_noktalari(_sentetik_iz(sapma=(600, 40, 300)))
    isaretler = at.anomali_isaretle(noktalar, 0.05)
    beklenen = round(0.05 * len(noktalar))
    assert all(int(i.sum()) == beklenen for i in isaretler.values())

    sarsintili = _sentetik_iz(sapma=(600, 40, 300), icao24="a00001")
    sakin = _sentetik_iz(boylam=-90.0, icao24="a00002")
    rapor = at.karsilastir([(_pirep(1, -98.4), sarsintili), (_pirep(0, -88.4), sakin)])
    assert rapor["degerlendirilebilir_pirep"] == 2
    assert rapor["kural"]["pod"]["isabet"] == 1 and rapor["kural"]["pofd"]["isabet"] == 0
    assert rapor["kural"]["peirce"] == 1.0
    assert set(rapor["kural_ile_ayni_sonuc"]) == {"isolation_forest", "lof"}


def test_tekrar_eden_kuantize_degerlerde_lof_uyarisi_vermez():
    import warnings

    rng = np.random.default_rng(1)
    noktalar = pd.DataFrame(
        {
            "mutlak_sapma_ft": np.r_[np.zeros(900), rng.choice([25.0, 50.0], 100)],
            "irtifa_oynakligi_ft": np.zeros(1000),
            "mutlak_dikey_hiz_ftdk": np.r_[np.zeros(900), rng.choice([64.0, 128.0], 100)],
            "dikey_hiz_degisimi_ftdk": np.zeros(1000),
        }
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        isaretler = at.anomali_isaretle(noktalar, 0.05)
    assert isaretler["lof"].sum() == 50
    assert np.array_equal(isaretler["lof"], at.anomali_isaretle(noktalar, 0.05)["lof"])
