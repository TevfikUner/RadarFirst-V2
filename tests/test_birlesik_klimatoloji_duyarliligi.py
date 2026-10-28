import numpy as np
import pandas as pd
import pytest

from turbulans_radar.fizik.edr_esleme import gosterge_tablosu, klimatoloji_hesapla
from turbulans_radar.ml import birlesik_klimatoloji_duyarliligi as bk

pytestmark = pytest.mark.birim


def _gosterge_verisi(n, tohum):
    rng = np.random.default_rng(tohum)
    return pd.DataFrame(
        {
            "ti1_indeksi": rng.lognormal(-15, 1.1, n),
            "ti2_indeksi": rng.normal(3e-7, 4e-7, n),
            "dusey_ruzgar_kaymasi": rng.lognormal(-5, 0.8, n),
            "yatay_deformasyon": rng.lognormal(-10, 0.7, n),
            "richardson_sayisi": rng.lognormal(1, 1.5, n),
        }
    )


def test_gun_toplamlarindan_klimatoloji_tek_seferlik_hesapla_ayni():
    gunler = {"2019-01-01": _gosterge_verisi(300, 1), "2019-01-02": _gosterge_verisi(500, 2)}
    gunluk = {g: bk.gun_toplamlari(gosterge_tablosu(df)) for g, df in gunler.items()}
    birlesik = bk.klimatoloji_birlestir(gunluk, sorted(gunler))
    tek_seferde = klimatoloji_hesapla(pd.concat(gunler.values(), ignore_index=True))
    assert set(birlesik) == set(tek_seferde)
    for ad, beklenen in tek_seferde.items():
        assert birlesik[ad]["ornek"] == beklenen["ornek"]
        assert birlesik[ad]["ln_ortalama"] == pytest.approx(beklenen["ln_ortalama"])
        assert birlesik[ad]["ln_ss"] == pytest.approx(beklenen["ln_ss"])
    assert bk.klimatoloji_birlestir(gunluk, ["2019-01-01"])["ti1_indeksi"]["ornek"] == 300


def test_puanla_ayni_orneklerde_skorlar_ve_mevcuda_gore_fark_verir():
    X = pd.concat([_gosterge_verisi(200, t) for t in range(6)], ignore_index=True)
    y = (X["ti1_indeksi"] > X["ti1_indeksi"].median()).astype(int).to_numpy()
    gunler = np.repeat([f"2019-01-{g:02d}" for g in range(1, 7)], 200)
    gunluk = {g: bk.gun_toplamlari(gosterge_tablosu(X[gunler == g])) for g in sorted(set(gunler))}
    katsayilar = {
        "mevcut": bk.katsayi_kumesi(klimatoloji_hesapla(X)),
        "egitim": bk.katsayi_kumesi(bk.klimatoloji_birlestir(gunluk, sorted(set(gunler))[:3])),
        "altin_dahil": bk.katsayi_kumesi(bk.klimatoloji_birlestir(gunluk, sorted(set(gunler)))),
    }
    sonuc = bk.puanla(X, y, gunler, katsayilar, tekrar=20)
    assert set(sonuc["test"]["skorlar"]) == {"mevcut", "egitim", "altin_dahil"}
    assert set(sonuc["farklar"]) == {"egitim - mevcut", "altin_dahil - mevcut", "altin_dahil - egitim"}
    assert sonuc["farklar"]["altin_dahil - mevcut"]["fark"] == pytest.approx(0.0, abs=1e-9)
