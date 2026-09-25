"""
turbulans_ml_modeli.py
-------------------------
Komisyon rubriğinin "minimum gereksinim" maddesi: TI1/Richardson gibi
FİZİK-FORMÜLÜ tabanlı göstergelerin yanına, GERÇEK gözlem verisiyle
(IEM PIREP arşivi -- pilotların bildirdiği gerçek türbülans şiddeti) etiketli,
çalışan bir makine öğrenmesi sınıflandırıcısı ekler.

NEDEN PIREP (Türkiye/ERA5 örnek verisiyle DEĞİL)?
Bu depodaki `ocak_2019_turbulans.nc` (Türkiye/Doğu Akdeniz) için gerçek,
doğrulanmış türbülans etiketi YOK -- ne SIGMET (sadece ABD hava sahası, bkz.
sigmet_dogrulama.py) ne PIREP/AMDAR (bkz. kalibrasyon.py'nin "bu depoda yok"
notu) bu bölge/tarih için mevcut. Uydurma etiketle model eğitmek yerine,
GERÇEK etiketli bir veri seti kurmak için ABD hava sahasına özgü, halka açık
IEM PIREP arşivinden (mesonet.agron.iastate.edu) 2018-2020 arası binlerce
gerçek pilot raporu + eşleşen gerçek ERA5 verisi kullanıldı (bkz.
`ml_egitimi.py`, `pirep_ust_seviye_siniflandirilmis.csv`). Model, FİZİKSEL
(bölgeden bağımsız) özelliklerle eğitildiği için Türkiye üzerinde de
(gerçek ERA5 verisi olduğu sürece) tahmin üretebilir -- ama gerçek başarı
metrikleri SADECE ABD verisiyle doğrulanmıştır (bkz. ml_egitimi.py çıktısı).

ÖZELLİK SEÇİMİ (bilinçli olarak BÖLGEDEN BAĞIMSIZ tutuldu -- enlem/boylam
KASITLI OLARAK özellik listesine ALINMADI, yoksa model ABD'nin bölgesel hava
düzenine ezberler, Türkiye gibi hiç görmediği bir bölgede anlamsızlaşırdı):
  - ti1_indeksi        -> Ellrod TI1 (turbulans_indeksleri.py, projenin ANA fiziksel göstergesi)
  - richardson_sayisi  -> bulk Richardson sayısı (dinamik kararsızlık göstergesi)
  - ruzgar_hizi_ms      -> yatay rüzgar hızı (sqrt(u^2+v^2)) -- CAT ile bilinen korelasyon
  - basinc_hpa          -> basınç seviyesi (irtifa/atmosfer katmanı bilgisi)

ETİKET: PIREP'in bildirdiği gerçek türbülans şiddeti, İKİLİ (orta-şiddetli
VE ÜZERİ = 1, hafif altı/hiç = 0) -- projenin TI1_ESIK_ORTA_SIDDETLI ile
AYNI eşik felsefesiyle, gerçek pilot gözlemine dayalı.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from birim_donusumleri import irtifa_metre_to_basinc_hpa
from eslestirme import rotayi_hava_durumuyla_eslestir
from rota_optimizasyonu import ruzgar_bilesenlerini_al

OZELLIK_SUTUNLARI = ["ti1_indeksi", "richardson_sayisi", "ruzgar_hizi_ms", "basinc_hpa"]

MODEL_DOSYA_YOLU = "turbulans_ml_modeli.joblib"
MODEL_BILGI_DOSYA_YOLU = "turbulans_ml_modeli_bilgisi.json"


def ozellikleri_cikar(nokta_df: pd.DataFrame, veri_kupu) -> pd.DataFrame:
    """
    nokta_df: en az 'zaman', 'enlem', 'boylam', 'irtifa_m' sütunları
              (PIREP noktaları ya da herhangi bir sorgu noktası olabilir).
    veri_kupu: xarray.Dataset (u, v, t; pressure_level, valid_time, latitude,
               longitude boyutları -- ocak_2019_turbulans.nc ile AYNI şema).

    Dönüş: nokta_df ile aynı sıradaki satırlar için OZELLIK_SUTUNLARI'nı
    içeren bir DataFrame (eşleşmeyen/kapsam dışı noktalar NaN).
    """
    rota_df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(nokta_df["zaman"]),
            "enlem": nokta_df["enlem"].to_numpy(dtype=float),
            "boylam": nokta_df["boylam"].to_numpy(dtype=float),
            "geo_irtifa_m": nokta_df["irtifa_m"].to_numpy(dtype=float),
        }
    )
    eslesme = rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)
    ti1_degerleri = eslesme["ti1_indeksi"].to_numpy(dtype=float)

    # ÖNEMLİ: xarray'in .sel(method="nearest") fonksiyonu (ruzgar_bilesenlerini_al
    # bunu kullanıyor) mesafe sınırı olmadan HER ZAMAN bir sonuç döndürür (bkz.
    # eslestirme.py'nin kendi başındaki aynı uyarı) -- bu yüzden rüzgar hızı,
    # SADECE eslestirme.py'nin kapsam içi bulduğu (ti1_indeksi NaN OLMAYAN)
    # noktalar için hesaplanır; aksi halde kapsam dışı bir nokta için "en
    # yakın ama çok uzak" bir rüzgar değeri sessizce sızabilirdi.
    ruzgar_hizlari = np.full(len(nokta_df), np.nan)
    basinc_hpa = irtifa_metre_to_basinc_hpa(rota_df["geo_irtifa_m"].to_numpy())
    for i in range(len(nokta_df)):
        if np.isnan(ti1_degerleri[i]):
            continue
        u, v = ruzgar_bilesenlerini_al(
            veri_kupu, rota_df["enlem"].iloc[i], rota_df["boylam"].iloc[i], basinc_hpa[i], rota_df["zaman"].iloc[i]
        )
        ruzgar_hizlari[i] = float(np.hypot(u, v))

    return pd.DataFrame(
        {
            "ti1_indeksi": ti1_degerleri,
            "richardson_sayisi": eslesme["richardson_sayisi"].to_numpy(dtype=float),
            "ruzgar_hizi_ms": ruzgar_hizlari,
            "basinc_hpa": eslesme["basinc_hpa"].to_numpy(dtype=float),
        }
    )


def ozellikleri_temizle(ozellik_df: pd.DataFrame, etiketler: pd.Series | None = None):
    """NaN/sonsuz içeren satırları eler (kapsam dışı nokta, sıfıra bölme
    vb. -- bkz. turbulans_indeksleri.py'nin Richardson notu). Dönüş:
    (temiz_ozellik_df, temiz_etiketler ya da None)."""
    temiz_maske = np.isfinite(ozellik_df[OZELLIK_SUTUNLARI].to_numpy()).all(axis=1)
    temiz_ozellikler = ozellik_df.loc[temiz_maske, OZELLIK_SUTUNLARI].reset_index(drop=True)
    if etiketler is None:
        return temiz_ozellikler, None
    return temiz_ozellikler, etiketler.loc[temiz_maske].reset_index(drop=True)


_ONBELLEK_MODEL = {"model": None, "denendi": False}


def _modeli_yukle():
    if not _ONBELLEK_MODEL["denendi"]:
        _ONBELLEK_MODEL["denendi"] = True
        try:
            import joblib

            _ONBELLEK_MODEL["model"] = joblib.load(MODEL_DOSYA_YOLU)
        except FileNotFoundError:
            _ONBELLEK_MODEL["model"] = None
    return _ONBELLEK_MODEL["model"]


def turbulans_riski_tahmin_et(nokta_df: pd.DataFrame, veri_kupu):
    """
    Eğitilmiş modeli kullanarak her nokta için türbülans riski OLASILIĞINI
    (0-1 arası, 'güven skoru') tahmin eder -- bkz. modül dosya başlığı.
    Model henüz eğitilip kaydedilmediyse (bkz. ml_egitimi.py) None döner
    (uydurma bir tahmin üretmek yerine dürüstçe "yok" der).
    """
    model = _modeli_yukle()
    if model is None:
        return None
    ozellikler = ozellikleri_cikar(nokta_df, veri_kupu)
    temiz_ozellikler, _ = ozellikleri_temizle(ozellikler)
    if temiz_ozellikler.empty:
        return np.full(len(nokta_df), np.nan)

    tum_tahminler = np.full(len(nokta_df), np.nan)
    gecerli_indeksler = ozellikler[OZELLIK_SUTUNLARI].notna().all(axis=1)
    tum_tahminler[gecerli_indeksler.to_numpy()] = model.predict_proba(temiz_ozellikler)[:, 1]
    return tum_tahminler


def model_bilgisini_yukle():
    """ml_egitimi.py'nin kaydettiği model metadata'sını (seçilen model adı,
    test metrikleri, özellik listesi, eğitim tarihi) döner. Model henüz
    eğitilip kaydedilmediyse (bkz. MODEL_BILGI_DOSYA_YOLU yok) dürüstçe
    None döner -- uydurma bir bilgi üretilmez."""
    import json

    try:
        with open(MODEL_BILGI_DOSYA_YOLU, encoding="utf-8") as dosya:
            return json.load(dosya)
    except FileNotFoundError:
        return None
