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


def test_cli_raporu_bir_kez_yazar(tmp_path, monkeypatch):
    import json

    import pandas as pd

    import turbulans_radar.depo.veritabani as vt
    import turbulans_radar.ml.ml_otomatik_egitim as moe
    import turbulans_radar.ml.sonuc_disa_aktarimi as sda

    y, ti1, birlesik, gunler, altin = _veri()
    monkeypatch.setattr(vt, "motor_al", lambda: None)
    monkeypatch.setattr(sda, "pirep_ornekleri", lambda motor, kesme: (None, {"y": y, "gun": pd.Series(gunler)}))
    monkeypatch.setattr(sda, "skorlari_hesapla", lambda X: {"TI1": ti1, "Birleşik EDR": birlesik})
    monkeypatch.setattr(sda, "git_bilgisi", lambda: {"commit": "abc"})
    monkeypatch.setattr(moe, "degerlendirme_gunleri_maskesi", lambda g: (altin, "test"))
    assert be.ana(["--cikti", str(tmp_path), "--tekrar", "20"]) == 0
    rapor = json.loads((tmp_path / be.CIKTI_ADI).read_text(encoding="utf-8"))
    assert rapor["meta"]["altin_yontemi"] == "test" and rapor["veri"]["altin_gun"] == 4
    assert "Seçilen eşik" in (tmp_path / "README.md").read_text(encoding="utf-8")
    with pytest.raises(SystemExit, match="üzerine yazılmaz"):
        be.ana(["--cikti", str(tmp_path)])
