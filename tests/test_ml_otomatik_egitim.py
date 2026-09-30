import json
import os

import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml import ml_otomatik_egitim as me
from turbulans_radar.ml import turbulans_ml_modeli as tm


def _veri(gun_sayisi=80, gunluk=6, ayrim=2.0, tohum=0):
    rng = np.random.default_rng(tohum)
    n = gun_sayisi * gunluk
    y = pd.Series(rng.integers(0, 2, n))
    X = pd.DataFrame(
        {
            "ti1_indeksi": (rng.normal(0, 1, n) + ayrim * y) * 1e-7 + 5e-7,
            "richardson_sayisi": rng.normal(2, 1, n) - 0.5 * ayrim * y,
            "ruzgar_hizi_ms": rng.normal(30, 5, n),
            "basinc_hpa": rng.choice([200.0, 250.0, 300.0], n),
        }
    )[tm.OZELLIK_SUTUNLARI]
    gunler = pd.Series(np.repeat(pd.date_range("2019-01-01", periods=gun_sayisi).strftime("%Y-%m-%d"), gunluk))
    return X, y, gunler


@pytest.fixture
def gecici_model_klasoru(monkeypatch, tmp_path):
    model, bilgi = str(tmp_path / "model.joblib"), str(tmp_path / "model_bilgisi.json")
    monkeypatch.setattr(me, "MODEL_DOSYA_YOLU", model)
    monkeypatch.setattr(me, "MODEL_BILGI_DOSYA_YOLU", bilgi)
    monkeypatch.setattr(tm, "MODEL_VERSIYONLARI_KLASORU", str(tmp_path / "versiyonlar"))
    monkeypatch.setattr(tm, "MODEL_VERSIYONLARI_MANIFEST_YOLU", str(tmp_path / "versiyonlar" / "manifest.json"))
    return tmp_path


def test_zamansal_holdout_en_son_gunleri_ayirir():
    gunler = pd.Series(["2019-01-03", "2019-01-01", "2019-01-02", "2019-01-05", "2019-01-04", "2019-01-05"])
    assert me.zamansal_holdout(gunler, oran=0.4).tolist() == [False, False, False, True, True, True]


@pytest.mark.parametrize(
    "aday,sampiyon,beklenen",
    [
        ({"f1": 0.7, "recall": 0.7}, None, True),
        ({"f1": 0.7, "recall": 0.7}, {"f1": 0.6, "recall": 0.7}, True),
        ({"f1": 0.605, "recall": 0.7}, {"f1": 0.6, "recall": 0.7}, False),
        ({"f1": 0.8, "recall": 0.6}, {"f1": 0.6, "recall": 0.7}, False),
        ({"f1": 0.8, "recall": 0.69}, {"f1": 0.6, "recall": 0.7}, True),
    ],
)
def test_terfi_karari(aday, sampiyon, beklenen):
    y = pd.Series([1] * 40 + [0] * 40)
    assert me.terfi_karari(aday, sampiyon, y)[0] is beklenen


def test_holdout_yetersizse_hic_terfi_edilmez():
    terfi, gerekce = me.terfi_karari({"f1": 1.0, "recall": 1.0}, None, pd.Series([1] * 30 + [0] * 2))
    assert not terfi and "yetersiz" in gerekce.lower()


def test_yetersiz_ornek_ya_da_gun_varsa_egitim_atlanir(monkeypatch, gecici_model_klasoru):
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: _veri(gun_sayisi=10, gunluk=50))
    assert me.otomatik_egitim_calistir()["karar"] == "atlandi"
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: _veri(gun_sayisi=80, gunluk=2))
    sonuc = me.otomatik_egitim_calistir()
    assert sonuc["karar"] == "atlandi" and "örnek" in sonuc["gerekce"]
    assert not os.path.exists(me.MODEL_DOSYA_YOLU)


def test_aktif_model_yokken_aday_aktiflestirilir_ve_versiyonlanir(monkeypatch, gecici_model_klasoru):
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: _veri())
    sonuc = me.otomatik_egitim_calistir(sampiyon_yukleyici=lambda: None, kat_sayisi=3, tekrar_sayisi=1)
    assert sonuc["karar"] == "aktiflestirildi"
    assert os.path.isfile(me.MODEL_DOSYA_YOLU)
    with open(me.MODEL_BILGI_DOSYA_YOLU, encoding="utf-8") as dosya:
        bilgi = json.load(dosya)
    assert bilgi["aktiflestirildi"] is True and bilgi["farkli_gun_sayisi"] == 80
    assert [v["versiyon_id"] for v in tm.model_versiyonlarini_listele()] == [sonuc["versiyon_id"]]
    assert not [d for d in os.listdir(gecici_model_klasoru) if d.endswith(".aday")]


def test_aday_aktif_modeli_gecemezse_aktif_model_degismez(monkeypatch, gecici_model_klasoru):
    X, y, gunler = _veri(ayrim=0.0)
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: (X, y, gunler))

    class _Kahin:
        def predict_proba(self, X_):
            p = y.loc[X_.index].to_numpy(dtype=float)
            return np.column_stack([1 - p, p])

    with open(me.MODEL_DOSYA_YOLU, "wb") as dosya:
        dosya.write(b"aktif")
    sonuc = me.otomatik_egitim_calistir(sampiyon_yukleyici=_Kahin, kat_sayisi=3, tekrar_sayisi=1)
    assert sonuc["karar"] == "saklandi" and "geçemedi" in sonuc["gerekce"]
    with open(me.MODEL_DOSYA_YOLU, "rb") as dosya:
        assert dosya.read() == b"aktif"
    assert not os.path.exists(me.MODEL_BILGI_DOSYA_YOLU)
    surum = tm.model_versiyonlarini_listele()[0]
    assert surum["aktiflestirildi"] is False and surum["holdout"]["aktif_model"]["f1"] == 1.0
