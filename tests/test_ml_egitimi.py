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

from ml_egitimi import (
    ERA5_KLASORU,
    PIREP_DOSYASI,
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
    sonuclar, (X_test, y_test) = modelleri_egit_ve_karsilastir(X, y)

    assert set(sonuclar) == {"Lojistik Regresyon", "Random Forest", "Gradient Boosting"}
    for _isim, (model, metrikler, _olcekleyici) in sonuclar.items():
        assert hasattr(model, "predict_proba")
        for anahtar in ("accuracy", "precision", "recall", "f1", "roc_auc"):
            assert 0.0 <= metrikler[anahtar] <= 1.0 or np.isnan(metrikler[anahtar])
        assert metrikler["yanlis_negatif"] + metrikler["dogru_pozitif"] == int(y_test.sum())


def test_en_iyi_modeli_sec_ve_kaydet_en_yuksek_recalli_modeli_secer(tmp_path, monkeypatch):
    import ml_egitimi

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

    import ml_egitimi

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


def test_veriyi_hazirla_gercek_pirep_era5_verisiyle():
    import glob
    import os

    if not os.path.exists(PIREP_DOSYASI) or not glob.glob(f"{ERA5_KLASORU}/*.nc"):
        pytest.skip(
            f"'{PIREP_DOSYASI}' veya '{ERA5_KLASORU}/*.nc' bulunamadı -- "
            "ml_veri_indir.py ile indirilmedikçe bu test atlanır."
        )

    X, y = veriyi_hazirla()
    assert len(X) == len(y)
    assert len(X) > 0
    assert set(X.columns) == {"ti1_indeksi", "richardson_sayisi", "ruzgar_hizi_ms", "basinc_hpa"}
    assert set(y.unique()) <= {0, 1}
