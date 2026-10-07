"""
test_ml_egitimi.py
---------------------
ml_egitimi.py için birim testleri:
  - modelleri_egit_ve_karsilastir/en_iyi_modeli_sec_ve_kaydet, SENTETİK
    (gerçek PIREP/ERA5 gerektirmeyen, hızlı) bir sınıflandırma verisiyle
    test edilir -- burada doğrulanan şey gerçek verinin kendisi değil,
    metrik hesaplama/model seçimi/dosya yazma MANTIĞI.
  - veriyi_hazirla, gerçek IEM PIREP + ERA5 verisi (pirep_ust_seviye_
    siniflandirilmis.csv, era5_egitim_verisi/*.nc -- ml_veri_indir.py ile
    indirilir) bulunmazsa atlanır (diğer "gerçek veri" testleriyle AYNI
    desen).
"""

import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml.ml_egitimi import (
    DengeliGradientBoosting,
    bir_se_kurali_ile_sec,
    en_iyi_modeli_sec_ve_kaydet,
    modelleri_egit_ve_karsilastir,
    veriyi_hazirla,
)


def _sentetik_ozellik_etiket_uret(n=120, tohum=0):
    rng = np.random.default_rng(tohum)
    X = pd.DataFrame(
        {
            "ti1_indeksi": rng.uniform(1e-8, 1e-6, n),
            "richardson_sayisi": rng.uniform(-1, 2, n),
            "ruzgar_hizi_ms": rng.uniform(0, 60, n),
            "basinc_hpa": rng.uniform(200, 400, n),
        }
    )
    y = pd.Series(rng.integers(0, 2, n))
    return X, y


def test_modelleri_egit_ve_karsilastir_uc_modeli_de_doner():
    X, y = _sentetik_ozellik_etiket_uret()
    sonuclar, degerlendirme = modelleri_egit_ve_karsilastir(X, y, tekrar_sayisi=2)

    assert set(sonuclar) == {"Lojistik Regresyon", "Random Forest", "Gradient Boosting"}
    for isim, (model, metrikler, _olcekleyici) in sonuclar.items():
        assert hasattr(model, "predict_proba")
        for anahtar in ("accuracy", "precision", "recall", "f1", "roc_auc"):
            assert 0.0 <= metrikler[anahtar] <= 1.0 or np.isnan(metrikler[anahtar])
            assert metrikler[f"{anahtar}_std"] >= 0.0
        assert metrikler["yanlis_negatif"] + metrikler["dogru_pozitif"] == int(y.sum())
        assert len(degerlendirme["oof_olasilik"][isim]) == len(y)


def test_gruplu_dogrulamada_ayni_gun_hem_egitimde_hem_testte_olmaz(monkeypatch):
    from turbulans_radar.ml import ml_egitimi

    X, y = _sentetik_ozellik_etiket_uret(n=120)
    gruplar = pd.Series(np.repeat([f"gun{i}" for i in range(20)], 6))
    gorulen_bolmeler = []
    gercek_cvp = ml_egitimi.cross_val_predict

    def izleyen_cvp(model, X_, y_, groups=None, cv=None, method=None):
        gorulen_bolmeler.extend(cv.split(X_, y_, groups))
        return gercek_cvp(model, X_, y_, groups=groups, cv=cv, method=method)

    monkeypatch.setattr(ml_egitimi, "cross_val_predict", izleyen_cvp)
    sonuclar, _ = modelleri_egit_ve_karsilastir(X, y, gruplar, tekrar_sayisi=1)

    assert gorulen_bolmeler
    for egitim, test in gorulen_bolmeler:
        assert not set(gruplar.iloc[egitim]) & set(gruplar.iloc[test])
    assert "gruplu" in sonuclar["Random Forest"][1]["degerlendirme_yontemi"]


def test_en_iyi_modeli_sec_ve_kaydet_en_yuksek_recalli_modeli_secer(tmp_path, monkeypatch):
    from turbulans_radar.ml import ml_egitimi

    monkeypatch.setattr(ml_egitimi, "MODEL_DOSYA_YOLU", str(tmp_path / "model.joblib"))
    monkeypatch.setattr(ml_egitimi, "MODEL_BILGI_DOSYA_YOLU", str(tmp_path / "bilgi.json"))

    # gerçek bir sklearn modeli yerine joblib'in picklenebilir herhangi bir
    # nesneyi kaydedebildiğinden faydalanan sahte bir değer kullanılıyor --
    # burada test edilen şey tahmin kalitesi değil, seçim/kaydetme mantığı.
    sonuclar = {
        "Dusuk Recall": ({"tur": "sahte"}, {"recall": 0.5, "f1": 0.6}, None),
        "Yuksek Recall": ({"tur": "sahte"}, {"recall": 0.9, "f1": 0.4}, None),
    }

    en_iyi_isim, metrikler = en_iyi_modeli_sec_ve_kaydet(sonuclar, egitim_orneklem_sayisi=100, test_orneklem_sayisi=25)

    assert en_iyi_isim == "Yuksek Recall"
    assert metrikler["recall"] == 0.9


def test_en_iyi_modeli_sec_ve_kaydet_model_bilgisi_dosyasini_dogru_yazar(tmp_path, monkeypatch):
    import json

    from turbulans_radar.ml import ml_egitimi

    model_yolu = tmp_path / "model.joblib"
    bilgi_yolu = tmp_path / "bilgi.json"
    monkeypatch.setattr(ml_egitimi, "MODEL_DOSYA_YOLU", str(model_yolu))
    monkeypatch.setattr(ml_egitimi, "MODEL_BILGI_DOSYA_YOLU", str(bilgi_yolu))

    sonuclar = {"Tek Model": ({"tur": "sahte"}, {"recall": 0.75, "f1": 0.68, "roc_auc": 0.84}, None)}
    en_iyi_modeli_sec_ve_kaydet(sonuclar, egitim_orneklem_sayisi=134, test_orneklem_sayisi=45)

    assert model_yolu.exists()
    bilgi = json.loads(bilgi_yolu.read_text(encoding="utf-8"))
    assert bilgi["secilen_model"] == "Tek Model"
    assert bilgi["metrikler"]["recall"] == 0.75
    assert bilgi["egitim_orneklem_sayisi"] == 134
    assert bilgi["test_orneklem_sayisi"] == 45
    assert "egitim_zamani" in bilgi


def test_eski_csv_veri_hazirlama_kilitlidir():
    from turbulans_radar.ml.turbulans_ml_modeli import EskiVeriHattiHatasi

    with pytest.raises(EskiVeriHattiHatasi, match="feet"):
        veriyi_hazirla()


@pytest.mark.parametrize(
    "rf_auc,se,beklenen",
    [(0.70, 0.02, "Lojistik Regresyon"), (0.70, 0.005, "Random Forest"), (0.66, 0.02, "Lojistik Regresyon")],
)
def test_bir_se_kurali_fark_standart_hatadan_kucukse_lojistigi_secer(rf_auc, se, beklenen):
    metrikler = {
        "Lojistik Regresyon": {"roc_auc": 0.69, "roc_auc_se": 0.02},
        "Random Forest": {"roc_auc": rf_auc, "roc_auc_se": se},
        "Gradient Boosting": {"roc_auc": 0.60, "roc_auc_se": 0.02},
    }
    assert bir_se_kurali_ile_sec(metrikler) == beklenen


def test_esit_performansli_sentetik_veride_lojistik_secilir():
    rng = np.random.default_rng(3)
    n = 600
    y = pd.Series(rng.integers(0, 2, n))
    X = pd.DataFrame({"a": rng.normal(0, 1, n) + 0.8 * y, "b": rng.normal(0, 1, n), "c": rng.normal(0, 1, n)})
    gruplar = pd.Series(np.repeat(np.arange(60), 10))
    sonuclar, _ = modelleri_egit_ve_karsilastir(X, y, gruplar, tekrar_sayisi=2)
    metrikler = {ad: m for ad, (_, m, _) in sonuclar.items()}
    assert all(m["roc_auc_se"] > 0 for m in metrikler.values())
    assert bir_se_kurali_ile_sec(metrikler) == "Lojistik Regresyon"


def test_gradient_boosting_sinif_dengeli_agirlikla_egitilir():
    rng = np.random.default_rng(0)
    n = 500
    y = (rng.random(n) < 0.15).astype(int)
    X = pd.DataFrame({"a": rng.normal(0, 1, n) + 0.5 * y, "b": rng.normal(0, 1, n)})
    dengeli = DengeliGradientBoosting(n_estimators=50, max_depth=2, random_state=0).fit(X, y)
    duz = DengeliGradientBoosting(n_estimators=50, max_depth=2, random_state=0).fit(X, y, sample_weight=np.ones(n))
    assert dengeli.predict_proba(X)[:, 1].mean() > duz.predict_proba(X)[:, 1].mean() + 0.1
