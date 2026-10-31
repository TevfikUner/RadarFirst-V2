import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar.fizik import edr_esleme
from turbulans_radar.fizik.turbulans_indeksleri import potansiyel_vortisite_hesapla, ti3_indeksi_hesapla
from turbulans_radar.ml import kesifsel_gostergeler as kg


@pytest.mark.parametrize(
    ("rapor", "gruplar", "sinif"),
    [
        ("BOS UA /OV BOS090030/TM 1200/FL350/TP B738/TB NEG 350/MOD 355/RM SMOOTH", ["NEG 350", "MOD 355"], 1),
        ("JFK UA /OV JFK/TM 0100/FL370/TP A320/TB LGT CHOP/RM X", ["LGT CHOP"], 0),
        ("UA /OV ABC/TM 0100/FL330/TP B752/TB MOD-SEV/IC NEG", ["MOD-SEV"], 2),
        ("UA /OV ABC/TM 0100/FL330/TP B752/SK CLR/TA M50", None, None),
        (None, None, None),
    ],
)
def test_tb_gruplari_ve_cok_grup_sinifi(rapor, gruplar, sinif):
    assert kg.tb_gruplari(rapor) == gruplar
    assert kg.cok_grup_sinifi(rapor) == sinif


def test_rapor_haritasi_celisen_anahtari_atar():
    metinler = pd.DataFrame({"anahtar": ["a", "a", "b", "c", "c"], "rapor": ["x", "y", "z", "w", "w"]})
    harita = kg.rapor_haritasi(metinler)
    assert harita.to_dict() == {"b": "z", "c": "w"}


def test_cok_grup_analizi_etiket_degisimini_sayar():
    rng = np.random.default_rng(0)
    n = 120
    gunler = np.repeat([f"2019-01-{i:02d}" for i in range(1, 13)], 10)
    y = rng.integers(0, 2, n)
    anahtar = [f"k{i}" for i in range(n)]
    rapor = ["UA /TB MOD 350/RM" if v else "UA /TB NEG 350/RM" for v in y]
    rapor[0] = "UA /TB NEG 350/MOD 355/RM" if y[0] == 0 else rapor[0]
    df = pd.DataFrame({"anahtar": anahtar, "y": y, "gun": gunler})
    skor = y + rng.random(n)
    sonuc = kg.cok_grup_analizi(df, df, {"TI1": skor}, pd.Series(rapor, index=anahtar), tekrar=50)
    s = sonuc["sayimlar"]["test"]
    assert s["rapor_bulunan"] == n and s["kontrol_tek_grupta_farkli"] == 0
    assert s["degisen_0_1"] == int(y[0] == 0) and s["degisen_1_0"] == 0
    assert np.isfinite(sonuc["farklar"]["TI1"]["fark"])


def test_auc2_agirliklari_toplami_bir_ve_yeniden_normalize():
    edrler = pd.DataFrame({"a": [0.1, 0.2, 0.3, 0.4], "b": [0.4, 0.3, np.nan, 0.1]})
    sonuc = kg.auc2_agirliklari([0, 0, 1, 1], edrler)
    assert sum(sonuc["agirlik"].values()) == pytest.approx(1.0)
    agirlik = {"a": 0.75, "b": 0.25}
    birlesik = kg.agirlikli_birlesik_edr(edrler, agirlik)
    assert birlesik[0] == pytest.approx(0.75 * 0.1 + 0.25 * 0.4)
    assert birlesik[2] == pytest.approx(0.3)


def test_esit_agirlikta_birlesik_edr_ile_ayni():
    katsayilar = edr_esleme.katsayilari_yukle()
    rng = np.random.default_rng(1)
    df = pd.DataFrame(
        {
            "ti1_indeksi": rng.uniform(1e-8, 1e-6, 50),
            "ti2_indeksi": rng.uniform(1e-8, 1e-6, 50),
            "dusey_ruzgar_kaymasi": rng.uniform(1e-3, 1e-2, 50),
            "yatay_deformasyon": rng.uniform(1e-5, 1e-4, 50),
            "richardson_sayisi": rng.uniform(0.5, 20, 50),
        }
    )
    edrler = kg.gosterge_edrleri(df, katsayilar)
    esit = {ad: 1 / edrler.shape[1] for ad in edrler}
    np.testing.assert_allclose(kg.agirlikli_birlesik_edr(edrler, esit), edr_esleme.birlesik_edr(df, katsayilar))


def test_pencere_teshisleri_demo_kupunde_sonlu():
    with xr.open_dataset("demo/era5/era5_THY322_2019-01-15.nc") as kup:
        kup = kup.load()
    oz = kg.pencere_teshisleri(kup, pd.Timestamp("2019-01-15T20:00"), 41.0, 35.0, 10668.0)
    assert set(oz) == set(kg.TESHIS_SUTUNLARI)
    assert all(np.isfinite(v) for v in oz.values())
    assert oz["sicaklik_gradyani"] > 0 and oz["ti1_yatay_maks"] > 0


def test_potansiyel_vortisite_stratosferde_pozitif_ve_ti3():
    pv = potansiyel_vortisite_hesapla(
        1e-5, 45.0, theta_ust=340.0, theta_alt=330.0, basinc_ust_hpa=200, basinc_alt_hpa=250
    )
    f = 2 * 7.292e-5 * np.sin(np.deg2rad(45.0))
    assert pv == pytest.approx(9.80665 * (1e-5 + f) * 10.0 / 5000.0 * 1e6)
    assert ti3_indeksi_hesapla(5e-7, 2e-5, -3e-5) == pytest.approx(5e-7 + 0.01 * 5e-5)


def test_komsuluk_analizi_esikleri_egitimde_secer():
    rng = np.random.default_rng(2)
    n = 200
    df = pd.DataFrame(
        {
            "y": rng.integers(0, 2, n),
            "gun": np.repeat([f"g{i}" for i in range(10)], 20),
            "ti1_indeksi": rng.uniform(1e-7, 1e-6, n),
        }
    )
    df["ti1_komsu_maks"] = df["ti1_indeksi"] * 1.5
    df["ti1_yatay_maks"] = df["ti1_indeksi"] * 1.2
    sonuc = kg.komsuluk_analizi(df, df, tekrar=20)
    assert sonuc["farklar"]["A_komsu_maks - TI1"]["fark"] == pytest.approx(0.0)
    assert sonuc["peirce_esiginde"]["A_komsu_maks"]["esik"] == pytest.approx(
        1.5 * sonuc["peirce_esiginde"]["TI1"]["esik"]
    )
