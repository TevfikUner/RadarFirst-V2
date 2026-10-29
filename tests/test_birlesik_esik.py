import numpy as np
import pytest

from turbulans_radar.ml import birlesik_esik as be

pytestmark = pytest.mark.birim


def _veri(n_gun=20, gunluk=40, tohum=0):
    rng = np.random.default_rng(tohum)
    gunler = np.repeat([f"2019-01-{g + 1:02d}" for g in range(n_gun)], gunluk)
    y = rng.integers(0, 2, len(gunler))
    birlesik = np.where(y == 1, rng.normal(0.20, 0.03, len(y)), rng.normal(0.12, 0.03, len(y)))
    ti1 = np.where(y == 1, rng.lognormal(np.log(8e-7), 0.3, len(y)), rng.lognormal(np.log(4e-7), 0.3, len(y)))
    altin = np.isin(gunler, gunler[: 4 * gunluk])
    return y, ti1, birlesik, gunler, altin


def test_esikler_yalniz_egitim_gunlerinden_secilir_ve_altinda_raporlanir():
    y, ti1, birlesik, gunler, altin = _veri()
    birlesik[5] = np.nan
    sonuc = be.esikleri_sec(y, ti1, birlesik, gunler, altin, tekrar=50)
    assert sonuc["veri"]["egitim_gun"] == 16 and sonuc["veri"]["altin_gun"] == 4
    assert sonuc["veri"]["birlesik_gecerli_egitim_ornek"] == sonuc["veri"]["egitim_ornek"]
    assert sonuc["veri"]["altin_ornek"] == 4 * 40 - 1
    b = sonuc["birlesik_edr"]
    assert 0.12 < b["esik"] < 0.22 and b["esik"] >= b["peirce_max_esigi"]
    assert sonuc["altin_gunler"]["birlesik_edr"]["esik"] == b["esik"]
    assert sonuc["altin_gunler"]["ti1_7e-7"]["esik"] == be.TI1_RISK_ESIGI
    assert sonuc["ti1_kontrol"]["esik"] >= sonuc["ti1_kontrol"]["peirce_max_esigi"]


def test_markdown_esigi_ve_kontrolu_yazar():
    y, ti1, birlesik, gunler, altin = _veri()
    rapor = {
        "meta": {"uretim_zamani": "t", "commit": "abc", "veritabani": "db", "kesme": "2026-10-18"},
        **be.esikleri_sec(y, ti1, birlesik, gunler, altin, tekrar=50),
    }
    metin = be.markdown_ozeti(rapor)
    assert "Seçilen eşik" in metin and "Kontrol" in metin and "sertifikalı EDR değildir" in metin
