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

import os
import threading

import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import irtifa_metre_to_basinc_hpa
from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
from turbulans_radar.rota.rota_optimizasyonu import ruzgar_bilesenlerini_toplu_al

OZELLIK_SUTUNLARI = ["ti1_indeksi", "richardson_sayisi", "ruzgar_hizi_ms", "basinc_hpa"]
EK_OZELLIK_SUTUNLARI = ["dusey_ruzgar_kaymasi", "yatay_deformasyon", "yatay_diverjans", "ti2_indeksi"]
MODEL_OZELLIK_SUTUNLARI = OZELLIK_SUTUNLARI + EK_OZELLIK_SUTUNLARI
ESKI_MODEL_UYARISI = (
    "Aktif ML modeli eski veri hattıyla (300-400 feet'teki PIREP'leri seçen hatalı irtifa filtresi) "
    "eğitildiği için kullanılmıyor; doğru irtifalı veriyle eğitilen model gece işiyle aktifleşince "
    "kullanılacak (bkz. GET /api/v1/ml/durum)."
)
MODEL_YOK_UYARISI = "ML modeli henüz eğitilmedi (bkz. GET /api/v1/ml/durum)."
ESKI_VERI_HATTI_MESAJI = (
    "Bu eski ML veri hattı kullanım dışıdır: pirep_ust_seviye_siniflandirilmis.csv, IEM'in feet cinsinden "
    "FL sütununu uçuş seviyesi sanarak 300-400 feet'teki PIREP'leri seçmişti. Yeni hat: veri için "
    "POST /api/v1/ml/gece-isi, eğitim için turbulans-ml, EDR kalibrasyonu için turbulans-edr-kalibrasyon."
)


class EskiVeriHattiHatasi(RuntimeError):
    pass


# Tüm model dosyaları config.MODEL_KLASORU altında (Docker'da kalıcı volume).
MODEL_DOSYA_YOLU = os.path.join(config.MODEL_KLASORU, "turbulans_ml_modeli.joblib")
MODEL_BILGI_DOSYA_YOLU = os.path.join(config.MODEL_KLASORU, "turbulans_ml_modeli_bilgisi.json")

# Her ml_egitimi.py çalıştırması, MODEL_DOSYA_YOLU'nun (aktif model) yanına
# bu klasöre KALICI bir kopya + manifest kaydı bırakır -- yeniden eğitim
# gerekmeden eski bir modele geri dönebilmek (rollback) için, bkz.
# versiyon_kaydet/versiyona_geri_don.
MODEL_VERSIYONLARI_KLASORU = os.path.join(config.MODEL_KLASORU, "model_versiyonlari")
MODEL_VERSIYONLARI_MANIFEST_YOLU = os.path.join(MODEL_VERSIYONLARI_KLASORU, "manifest.json")


def _versiyon_dosyasi(versiyon) -> str:
    """Manifest'teki dosya_yolu yazıldığı andaki çalışma dizinine göreliydi
    (örn. 'model_versiyonlari/x.joblib'); klasör taşınınca (MODEL_KLASORU,
    Docker volume) kırılmasın diye dosya adı bugünkü klasörde aranır."""
    return os.path.join(MODEL_VERSIYONLARI_KLASORU, os.path.basename(versiyon["dosya_yolu"]))


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
            "baro_irtifa_m": nokta_df["irtifa_m"].to_numpy(dtype=float),
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
    basinc_hpa = irtifa_metre_to_basinc_hpa(rota_df["baro_irtifa_m"].to_numpy())
    gecerli = ~np.isnan(ti1_degerleri)
    if gecerli.any():
        u, v = ruzgar_bilesenlerini_toplu_al(
            veri_kupu,
            rota_df["enlem"].to_numpy()[gecerli],
            rota_df["boylam"].to_numpy()[gecerli],
            basinc_hpa[gecerli],
            list(rota_df["zaman"][gecerli]),
        )
        ruzgar_hizlari[gecerli] = np.hypot(u.astype(float), v.astype(float))

    return pd.DataFrame(
        {
            "ti1_indeksi": ti1_degerleri,
            "richardson_sayisi": eslesme["richardson_sayisi"].to_numpy(dtype=float),
            "ruzgar_hizi_ms": ruzgar_hizlari,
            "basinc_hpa": eslesme["basinc_hpa"].to_numpy(dtype=float),
            **{s: eslesme[s].to_numpy(dtype=float) for s in EK_OZELLIK_SUTUNLARI},
        }
    )


def ozellikleri_temizle(ozellik_df: pd.DataFrame, etiketler: pd.Series | None = None, sutunlar=None):
    """NaN/sonsuz içeren (ya da sütunu hiç olmayan) satırları eler (kapsam dışı
    nokta, sıfıra bölme vb. -- bkz. turbulans_indeksleri.py'nin Richardson
    notu). Dönüş: (temiz_ozellik_df, temiz_etiketler ya da None)."""
    sutunlar = list(sutunlar or OZELLIK_SUTUNLARI)
    secili = ozellik_df.reindex(columns=sutunlar)
    temiz_maske = np.isfinite(secili.to_numpy(dtype=float)).all(axis=1)
    temiz_ozellikler = secili.loc[temiz_maske].reset_index(drop=True)
    if etiketler is None:
        return temiz_ozellikler, None
    return temiz_ozellikler, etiketler.loc[temiz_maske].reset_index(drop=True)


_ONBELLEK_MODEL = {"model": None, "imza": None}
# Yeni model yayınlandığı anda gelen eşzamanlı tahmin istekleri (asyncio.to_thread
# iş parçacıkları) aynı dosyayı ayrı ayrı joblib.load etmesin.
_model_yukleme_kilidi = threading.Lock()


def _modeli_yukle():
    """Dosyanın (mtime, boyut) imzası değiştiyse yeniden yükler: API açıkken
    ml_egitimi.py yeni model yazarsa ya da model hiç yokken eğitilirse süreç
    yeniden başlatılmadan yeni modeli kullanır (eskiden ilk denemenin sonucu
    -- 'model yok' dahil -- süreç boyunca önbellekte kalıyordu)."""
    import os

    try:
        bilgi = os.stat(MODEL_DOSYA_YOLU)
    except FileNotFoundError:
        with _model_yukleme_kilidi:
            _ONBELLEK_MODEL.update(model=None, imza=None)
        return None
    imza = (bilgi.st_mtime_ns, bilgi.st_size)
    if imza == _ONBELLEK_MODEL["imza"]:
        return _ONBELLEK_MODEL["model"]
    with _model_yukleme_kilidi:
        if imza != _ONBELLEK_MODEL["imza"]:
            import joblib

            _ONBELLEK_MODEL.update(model=joblib.load(MODEL_DOSYA_YOLU), imza=imza)
        return _ONBELLEK_MODEL["model"]


def _atomik_kopyala(kaynak, hedef):
    """Okuyan bir süreç yarım yazılmış dosyayı görmesin diye önce geçici
    dosyaya kopyalayıp os.replace ile tek adımda yerine koyar."""
    import os
    import shutil

    gecici = f"{hedef}.{os.getpid()}.gecici"
    shutil.copyfile(kaynak, gecici)
    os.replace(gecici, hedef)


def turbulans_riski_tahmin_et(nokta_df: pd.DataFrame, veri_kupu):
    """
    Eğitilmiş modeli kullanarak her nokta için türbülans riski OLASILIĞINI
    (0-1 arası, 'güven skoru') tahmin eder -- bkz. modül dosya başlığı.
    Model henüz eğitilip kaydedilmediyse (bkz. ml_egitimi.py) None döner
    (uydurma bir tahmin üretmek yerine dürüstçe "yok" der).
    """
    if not model_kullanilabilir_mi()[0] or _modeli_yukle() is None:
        return None
    return ozelliklerden_risk_tahmin_et(ozellikleri_cikar(nokta_df, veri_kupu))


def model_kullanilabilir_mi(bilgi=None, model_var_mi=None) -> tuple[bool, str | None]:
    import os

    if model_var_mi is None:
        model_var_mi = os.path.isfile(MODEL_DOSYA_YOLU)
    if not model_var_mi:
        return False, MODEL_YOK_UYARISI
    bilgi = model_bilgisini_yukle() if bilgi is None else bilgi
    if config.ML_ESKI_MODELI_KULLAN or (bilgi is not None and "veri_kaynagi" in bilgi):
        return True, None
    return False, ESKI_MODEL_UYARISI


def ozelliklerden_risk_tahmin_et(ozellikler: pd.DataFrame):
    """turbulans_riski_tahmin_et ile aynı, ama özellikler zaten çıkarılmışsa
    (bkz. api_servisi.turbulans_tahmini) ikinci kez hesaplatmaz."""
    if not model_kullanilabilir_mi()[0]:
        return None
    model = _modeli_yukle()
    if model is None:
        return None
    sutunlar = modelin_ozellik_sutunlari(model)
    tum_tahminler = np.full(len(ozellikler), np.nan)
    gecerli_maske = np.isfinite(ozellikler.reindex(columns=sutunlar).to_numpy(dtype=float)).all(axis=1)
    if gecerli_maske.any():
        temiz_ozellikler, _ = ozellikleri_temizle(ozellikler, sutunlar=sutunlar)
        tum_tahminler[gecerli_maske] = model.predict_proba(temiz_ozellikler)[:, 1]
    return tum_tahminler


def modelin_ozellik_sutunlari(model) -> list[str]:
    """Modelin eğitildiği sütunlar. Model dosyasından okunur (bilgi JSON'u
    modelden ayrı yazıldığı için yayın anında bir an eski kalabilir); adları
    taşımayan eski modeller için OZELLIK_SUTUNLARI."""
    isimler = getattr(model, "feature_names_in_", None)
    return [str(i) for i in isimler] if isimler is not None else list(OZELLIK_SUTUNLARI)


def risk_durumlarini_hesapla(olasiliklar, bilgi=None):
    """Aktif modelin konformal eşiğiyle her olasılık için dusuk_risk / yuksek_risk
    / belirsiz (bkz. ml/belirsizlik.py). Model konformal eşikle eğitilmediyse None."""
    from turbulans_radar.ml.belirsizlik import risk_durumlari

    if olasiliklar is None:
        return None
    konformal = ((model_bilgisini_yukle() if bilgi is None else bilgi) or {}).get("konformal")
    if not konformal or konformal.get("esik") is None:
        return None
    return risk_durumlari(olasiliklar, konformal["esik"])


def ml_karar_esigi(bilgi=None) -> float:
    """ml_riski_var_mi eşiği: ML_KARAR_ESIGI verildiyse o, yoksa modelin eğitim
    günlerinde Peirce'ı maksimize eden eşiği, o da yoksa 0.5."""
    if config.ML_KARAR_ESIGI is not None:
        return float(config.ML_KARAR_ESIGI)
    esik = ((bilgi or {}).get("esikler") or {}).get("model")
    return float(esik) if esik is not None else 0.5


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


def _versiyonlari_oku():
    import json

    try:
        with open(MODEL_VERSIYONLARI_MANIFEST_YOLU, encoding="utf-8") as dosya:
            return json.load(dosya)
    except FileNotFoundError:
        return []


def model_versiyonlarini_listele():
    """Şimdiye kadar eğitilmiş TÜM model versiyonlarını (en yeni önce)
    döner. Hiç versiyon yoksa (henüz hiç eğitim yapılmadıysa) dürüstçe
    boş liste döner."""
    return sorted(_versiyonlari_oku(), key=lambda v: v["egitim_zamani"], reverse=True)


def versiyon_kaydet(gecici_model_dosya_yolu, model_bilgisi):
    """ml_egitimi.py, her eğitim çalıştırmasından sonra bunu çağırır --
    o çalıştırmanın modelini `model_versiyonlari/` altına KALICI olarak
    kopyalar ve manifest'e ekler. Dönüş: üretilen versiyon_id."""
    import json
    import os
    import shutil
    import uuid

    os.makedirs(MODEL_VERSIYONLARI_KLASORU, exist_ok=True)
    versiyon_id = f"{model_bilgisi['egitim_zamani'].replace(':', '-')}_{uuid.uuid4().hex[:8]}"
    hedef_dosya_yolu = os.path.join(MODEL_VERSIYONLARI_KLASORU, f"{versiyon_id}.joblib")
    shutil.copyfile(gecici_model_dosya_yolu, hedef_dosya_yolu)

    versiyonlar = _versiyonlari_oku()
    versiyonlar.append({"versiyon_id": versiyon_id, "dosya_yolu": hedef_dosya_yolu, **model_bilgisi})
    with open(MODEL_VERSIYONLARI_MANIFEST_YOLU, "w", encoding="utf-8") as dosya:
        json.dump(versiyonlar, dosya, ensure_ascii=False, indent=2)
    return versiyon_id


def versiyona_geri_don(versiyon_id):
    """Belirli bir geçmiş model versiyonunu AKTİF model olarak işaretler --
    MODEL_DOSYA_YOLU/MODEL_BILGI_DOSYA_YOLU o versiyonun içeriğiyle
    değiştirilir, yeniden eğitim GEREKMEZ (rollback). Bilinmeyen bir
    versiyon_id için ValueError fırlatır -- uydurma bir geri dönüş yapılmaz.
    """
    import json
    import os

    versiyon = next((v for v in _versiyonlari_oku() if v["versiyon_id"] == versiyon_id), None)
    if versiyon is None:
        raise ValueError(f"Bilinmeyen versiyon_id: '{versiyon_id}'.")

    kaynak = _versiyon_dosyasi(versiyon)
    if not os.path.isfile(kaynak):
        raise ValueError(f"'{versiyon_id}' versiyonunun model dosyası bulunamadı: {os.path.basename(kaynak)}")
    _atomik_kopyala(kaynak, MODEL_DOSYA_YOLU)
    aktif_bilgi = {k: v for k, v in versiyon.items() if k not in ("versiyon_id", "dosya_yolu")}
    gecici = f"{MODEL_BILGI_DOSYA_YOLU}.{os.getpid()}.gecici"
    with open(gecici, "w", encoding="utf-8") as dosya:
        json.dump(aktif_bilgi, dosya, ensure_ascii=False, indent=2)
    os.replace(gecici, MODEL_BILGI_DOSYA_YOLU)

    _ONBELLEK_MODEL["imza"] = None  # aynı mtime çözünürlüğünde kopyalansa bile yeniden yüklensin
    return aktif_bilgi
