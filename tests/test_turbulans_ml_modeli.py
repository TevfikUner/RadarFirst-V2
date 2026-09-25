"""
test_turbulans_ml_modeli.py
------------------------------
turbulans_ml_modeli.py için birim testleri:
  - Özellik çıkarımı gerçek ERA5 veri küpüyle (ocak_2019_turbulans.nc)
    doğru sütunları/şekli üretiyor mu (bulunmazsa atlanır -- diğer
    testlerle aynı desen).
  - Kapsam dışı/NaN noktalar ozellikleri_temizle ile doğru elenip
    etiketlerle senkron kalıyor mu.
  - Eğitilmiş model dosyası yoksa turbulans_riski_tahmin_et dürüstçe None
    döner (uydurma bir tahmin üretmez).
"""

import numpy as np
import pandas as pd
import pytest

import config
from turbulans_ml_modeli import OZELLIK_SUTUNLARI, ozellikleri_cikar, ozellikleri_temizle

xr = pytest.importorskip("xarray")


@pytest.fixture(scope="module")
def veri_kupu():
    try:
        return xr.open_dataset(config.HAVA_DURUMU_DOSYASI)
    except FileNotFoundError:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı, gerçek veri gerektiren test atlanıyor.")


def test_ozellik_cikarimi_dogru_sutunlari_uretir(veri_kupu):
    lat_min, lat_maks = float(veri_kupu.latitude.min()), float(veri_kupu.latitude.max())
    lon_min, lon_maks = float(veri_kupu.longitude.min()), float(veri_kupu.longitude.max())
    zaman = pd.Timestamp(veri_kupu.valid_time.values[len(veri_kupu.valid_time) // 2])

    nokta_df = pd.DataFrame(
        {
            "zaman": [zaman, zaman],
            "enlem": [(lat_min + lat_maks) / 2, (lat_min + lat_maks) / 2],
            "boylam": [(lon_min + lon_maks) / 2, (lon_min + lon_maks) / 2],
            "irtifa_m": [10000.0, 10000.0],
        }
    )
    ozellikler = ozellikleri_cikar(nokta_df, veri_kupu)

    assert list(ozellikler.columns) == OZELLIK_SUTUNLARI
    assert len(ozellikler) == 2
    # Veri küpü kapsamı içinde, gerçek bir nokta -- NaN olmamalı.
    assert ozellikler.notna().all().all()


def test_kapsam_disi_nokta_temizlenirken_etiketle_senkron_kalir(veri_kupu):
    lat_min, lat_maks = float(veri_kupu.latitude.min()), float(veri_kupu.latitude.max())
    lon_min, lon_maks = float(veri_kupu.longitude.min()), float(veri_kupu.longitude.max())
    zaman = pd.Timestamp(veri_kupu.valid_time.values[0])

    nokta_df = pd.DataFrame(
        {
            "zaman": [zaman, zaman, zaman],
            "enlem": [(lat_min + lat_maks) / 2, 5.0, (lat_min + lat_maks) / 2],  # ortadaki kapsam dışı
            "boylam": [(lon_min + lon_maks) / 2, -90.0, (lon_min + lon_maks) / 2],
            "irtifa_m": [10000.0, 10000.0, 10000.0],
        }
    )
    etiketler = pd.Series([1, 0, 0])

    ozellikler = ozellikleri_cikar(nokta_df, veri_kupu)
    assert ozellikler.iloc[1].isna().all()  # kapsam dışı nokta NaN olmalı

    temiz_ozellikler, temiz_etiketler = ozellikleri_temizle(ozellikler, etiketler)
    assert len(temiz_ozellikler) == 2
    assert len(temiz_etiketler) == 2
    assert temiz_etiketler.tolist() == [1, 0]  # kapsam dışı olanın etiketi de elendi, kalanlar sırayla eşleşti


def test_egitilmis_model_yoksa_durustce_none_doner(veri_kupu, tmp_path, monkeypatch):
    import turbulans_ml_modeli as tm

    monkeypatch.setattr(tm, "MODEL_DOSYA_YOLU", str(tmp_path / "olmayan_model.joblib"))
    monkeypatch.setitem(tm._ONBELLEK_MODEL, "model", None)
    monkeypatch.setitem(tm._ONBELLEK_MODEL, "denendi", False)

    nokta_df = pd.DataFrame(
        {
            "zaman": [pd.Timestamp(veri_kupu.valid_time.values[0])],
            "enlem": [40.0],
            "boylam": [30.0],
            "irtifa_m": [10000.0],
        }
    )
    sonuc = tm.turbulans_riski_tahmin_et(nokta_df, veri_kupu)
    assert sonuc is None


def test_model_bilgisi_dosyasi_yoksa_durustce_none_doner(tmp_path, monkeypatch):
    import turbulans_ml_modeli as tm

    monkeypatch.setattr(tm, "MODEL_BILGI_DOSYA_YOLU", str(tmp_path / "olmayan_bilgi.json"))
    assert tm.model_bilgisini_yukle() is None


def test_model_bilgisi_dosyasi_varsa_okunur(tmp_path, monkeypatch):
    import json

    import turbulans_ml_modeli as tm

    bilgi_dosyasi = tmp_path / "bilgi.json"
    bilgi_dosyasi.write_text(json.dumps({"secilen_model": "Random Forest"}), encoding="utf-8")
    monkeypatch.setattr(tm, "MODEL_BILGI_DOSYA_YOLU", str(bilgi_dosyasi))
    assert tm.model_bilgisini_yukle() == {"secilen_model": "Random Forest"}


def test_egitilmis_model_varsa_0_1_arasi_olasilik_doner():
    import turbulans_ml_modeli as tm

    if tm._modeli_yukle() is None:
        pytest.skip(f"'{tm.MODEL_DOSYA_YOLU}' henüz eğitilmedi (bkz. ml_egitimi.py) -- test atlanıyor.")

    veri_kupu = xr.open_dataset(config.HAVA_DURUMU_DOSYASI)
    nokta_df = pd.DataFrame(
        {
            "zaman": [pd.Timestamp(veri_kupu.valid_time.values[0])],
            "enlem": [float(veri_kupu.latitude.mean())],
            "boylam": [float(veri_kupu.longitude.mean())],
            "irtifa_m": [10000.0],
        }
    )
    sonuc = tm.turbulans_riski_tahmin_et(nokta_df, veri_kupu)
    assert sonuc is not None
    gecerli = sonuc[np.isfinite(sonuc)]
    assert ((gecerli >= 0.0) & (gecerli <= 1.0)).all()
