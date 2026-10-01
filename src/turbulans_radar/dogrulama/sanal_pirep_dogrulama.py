"""
sanal_pirep_dogrulama.py
--------------------------
M6 başarı ölçütü: sanal PIREP'lerin aynı yer/zamandaki gerçek PIREP'lerle
eşleşmesi. ml_ornekleri'ndeki seyir irtifası PIREP'lerinin her biri için
çevresindeki ADS-B izleri (OpenSky state_vectors_data4, PIREP'in ±pencere
dakikası, ~90 km kutu, ±3000 ft) alınır, her uçak için olay tespiti çalışır:

  isabet       : PIREP tüpünde (50 km, ±2000 ft, ±pencere) en az bir olay var
  değerlendirilebilir: kutuda seyir verisi olan en az bir uçak var
  POD  = isabet / değerlendirilebilir, orta ve üstü PIREP'lerde (sinif >= 1)
  POFD = isabet / değerlendirilebilir, sinif 0 PIREP'lerde (yok/hafif)

sinif 0 hafif türbülansı da içerir; POFD bu yüzden üst sınır gibi okunmalıdır.
PIREP'i veren uçak ADS-B'de tanınamaz (PIREP'te çağrı işareti yok); tüpteki
herhangi bir uçağın olayı isabet sayılır.

OpenSky yükü: PIREP başına TEK sorgu, sonucu Parquet önbelleğine yazılır
(aynı PIREP bir daha sorulmaz); varsayılan maks_yeni_sorgu=0 yalnızca
önbelleği kullanır. Kilit ve günlük tavan veri_yukleme._sorgu_calistir'da.
"""

import argparse
import hashlib
import json
import math
import os
import time
import uuid

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from turbulans_radar import config, loglama
from turbulans_radar.depo.models import MlOrnegi
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.fizik.sanal_pirep import METRE_FT, coklu_izden_olaylar, yakin_mi

_logger = loglama.logger_al(__name__)

BAGLAM_PAYI_KM = 40.0
IRTIFA_BANDI_FT = 3000.0
_IZ_SUTUNLARI = ["zaman_unix", "icao24", "enlem", "boylam", "hiz", "yon", "dikey_hiz", "geo_irtifa_m", "baro_irtifa_m"]


def onbellek_yolu(pirep_anahtari: str, klasor: str | None = None) -> str:
    ozet = hashlib.sha1(pirep_anahtari.encode()).hexdigest()[:20]
    return os.path.join(klasor or config.SANAL_PIREP_ONBELLEK_KLASORU, f"{ozet}.parquet")


def pirep_cevresi_sorgusu(pirep: dict) -> tuple[str, list]:
    zaman = int(pd.Timestamp(pirep["zaman"]).timestamp())
    pencere = config.SANAL_PIREP_DOGRULAMA_PENCERE_DAKIKA * 60
    yaricap = config.SANAL_PIREP_KUME_YARICAPI_KM + BAGLAM_PAYI_KM
    d_enlem = yaricap / 111.0
    d_boylam = min(180.0, yaricap / (111.0 * max(math.cos(math.radians(pirep["enlem"])), 0.05)))
    irtifa_m = pirep["irtifa_ft"] / METRE_FT
    bant_m = IRTIFA_BANDI_FT / METRE_FT
    sorgu = f"""
    SELECT time, icao24, lat, lon, velocity, heading, vertrate, geoaltitude, baroaltitude
    FROM state_vectors_data4
    WHERE hour >= ? AND hour <= ?
    AND time >= ? AND time <= ?
    AND lat >= ? AND lat <= ? AND lon >= ? AND lon <= ?
    AND baroaltitude >= ? AND baroaltitude <= ?
    AND onground = false
    ORDER BY icao24, time
    LIMIT {config.MAKS_STATE_VECTOR_SATIRI}
    """
    parametreler = [
        ((zaman - pencere) // 3600) * 3600,
        ((zaman + pencere) // 3600) * 3600,
        zaman - pencere,
        zaman + pencere,
        pirep["enlem"] - d_enlem,
        pirep["enlem"] + d_enlem,
        pirep["boylam"] - d_boylam,
        pirep["boylam"] + d_boylam,
        irtifa_m - bant_m,
        irtifa_m + bant_m,
    ]
    return sorgu, parametreler


def _onbellege_yaz(df: pd.DataFrame, yol: str) -> None:
    os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
    gecici = f"{yol}.{uuid.uuid4().hex[:12]}.yaziliyor"
    try:
        df.to_parquet(gecici, index=False)
        os.replace(gecici, yol)
    finally:
        if os.path.exists(gecici):
            os.remove(gecici)


def pirep_cevresi_izleri(pirep: dict, baglanti=None, sorgu_izni: bool = False) -> pd.DataFrame | None:
    """Önbellekte varsa oradan; yoksa ve sorgu_izni varsa OpenSky'dan (tek
    sorgu) çekip önbelleğe yazar. Hiçbiri yoksa None."""
    yol = onbellek_yolu(pirep["pirep_anahtari"])
    if os.path.exists(yol):
        return pd.read_parquet(yol)
    if not sorgu_izni:
        return None
    from turbulans_radar.veri.veri_yukleme import _sorgu_calistir, trino_baglantisi_olustur

    baglanti = baglanti or trino_baglantisi_olustur()
    sorgu, parametreler = pirep_cevresi_sorgusu(pirep)
    df = _sorgu_calistir(baglanti, sorgu, _IZ_SUTUNLARI, parametreler)
    if not df.empty:
        df["zaman"] = pd.to_datetime(df["zaman_unix"], unit="s", utc=True)
    else:
        df = pd.DataFrame(columns=[*_IZ_SUTUNLARI, "zaman"])
    df.attrs["kesildi"] = len(df) >= config.MAKS_STATE_VECTOR_SATIRI
    _onbellege_yaz(df, yol)
    return df


def pirep_isabeti(pirep: dict, izler: pd.DataFrame) -> dict:
    if izler is None or izler.empty:
        return {"degerlendirilebilir": False, "isabet": False, "ucak_sayisi": 0, "olay_sayisi": 0}
    olaylar, ozetler = coklu_izden_olaylar(izler)
    seyirde_ucak = int((ozetler["seyir_suresi_sn"] > 0).sum()) if not ozetler.empty else 0
    isabet = False
    if not olaylar.empty:
        isabet = bool(
            yakin_mi(
                pirep["enlem"],
                pirep["boylam"],
                pirep["zaman"],
                pirep["irtifa_ft"],
                olaylar["enlem"].to_numpy(),
                olaylar["boylam"].to_numpy(),
                olaylar["zaman"],
                (olaylar["seviye_ft"] + olaylar["sapma_ft"]).to_numpy(),
                config.SANAL_PIREP_KUME_YARICAPI_KM,
                pd.Timedelta(minutes=config.SANAL_PIREP_DOGRULAMA_PENCERE_DAKIKA),
                config.SANAL_PIREP_KUME_IRTIFA_FARKI_FT,
            ).any()
        )
    return {
        "degerlendirilebilir": seyirde_ucak > 0,
        "isabet": isabet,
        "ucak_sayisi": seyirde_ucak,
        "olay_sayisi": len(olaylar),
    }


def wilson_araligi(basari: int, toplam: int, z: float = 1.96) -> tuple[float, float] | None:
    if toplam == 0:
        return None
    p = basari / toplam
    payda = 1 + z * z / toplam
    merkez = (p + z * z / (2 * toplam)) / payda
    yaricap = z * math.sqrt(p * (1 - p) / toplam + z * z / (4 * toplam * toplam)) / payda
    return max(0.0, merkez - yaricap), min(1.0, merkez + yaricap)


def pirepleri_sec(pozitif: int, negatif: int, motor=None) -> list[dict]:
    """Belirlenimci örneklem (anahtarın md5'ine göre sıralı): her çalıştırma
    aynı PIREP'leri seçer, önbellek yeniden kullanılır."""
    motor = motor or motor_al()
    secilen = []
    with Session(motor) as oturum:
        for kosul, adet in ((MlOrnegi.sinif >= 1, pozitif), (MlOrnegi.sinif == 0, negatif)):
            if adet <= 0:
                continue
            satirlar = oturum.execute(
                select(
                    MlOrnegi.pirep_anahtari,
                    MlOrnegi.zaman,
                    MlOrnegi.enlem,
                    MlOrnegi.boylam,
                    MlOrnegi.irtifa_ft,
                    MlOrnegi.sinif,
                )
                .where(kosul)
                .order_by(func.md5(MlOrnegi.pirep_anahtari))
                .limit(adet)
            ).all()
            secilen.extend(dict(s._mapping) for s in satirlar)
    return secilen


def _oran(isabet, toplam):
    return {
        "isabet": isabet,
        "degerlendirilebilir": toplam,
        "oran": None if toplam == 0 else round(isabet / toplam, 4),
        "guven_araligi_95": None if toplam == 0 else [round(x, 4) for x in wilson_araligi(isabet, toplam)],
    }


def dogrulama_calistir(pozitif=50, negatif=50, maks_yeni_sorgu=0, motor=None, baglanti=None) -> dict:
    pirepler = pirepleri_sec(pozitif, negatif, motor=motor)
    yeni_sorgu = 0
    sorgulanmadi = 0
    sonuclar = []
    for pirep in pirepler:
        izin = yeni_sorgu < maks_yeni_sorgu
        onbellekte = os.path.exists(onbellek_yolu(pirep["pirep_anahtari"]))
        if not onbellekte and izin and yeni_sorgu > 0:
            time.sleep(config.TOPLU_ANALIZ_ISTEKLER_ARASI_BEKLEME_SANIYE)
        if not onbellekte and izin and baglanti is None:
            from turbulans_radar.veri.veri_yukleme import trino_baglantisi_olustur

            baglanti = trino_baglantisi_olustur()
        izler = pirep_cevresi_izleri(pirep, baglanti=baglanti, sorgu_izni=izin)
        if not onbellekte and izler is not None:
            yeni_sorgu += 1
        if izler is None:
            sorgulanmadi += 1
            continue
        sonuclar.append({**pirep, **pirep_isabeti(pirep, izler)})
    df = pd.DataFrame(sonuclar)
    ozet = {"pod": _oran(0, 0), "pofd": _oran(0, 0)}
    if not df.empty:
        degerli = df[df["degerlendirilebilir"]]
        for ad, maske in (("pod", degerli["sinif"] >= 1), ("pofd", degerli["sinif"] == 0)):
            ozet[ad] = _oran(int(degerli.loc[maske, "isabet"].sum()), int(maske.sum()))
    return {
        **ozet,
        "secilen_pirep": len(pirepler),
        "izi_olan_pirep": len(df),
        "onbellekte_olmayan_sorgulanmayan": sorgulanmadi,
        "yeni_opensky_sorgusu": yeni_sorgu,
        "parametreler": {
            "sapma_esigi_ft": config.SANAL_PIREP_SAPMA_ESIGI_FT,
            "dikey_hiz_tutarlilik_ftdk": config.SANAL_PIREP_DIKEY_HIZ_TUTARLILIK_FTDK,
            "min_irtifa_ft": config.SANAL_PIREP_MIN_IRTIFA_FT,
            "tup_km": config.SANAL_PIREP_KUME_YARICAPI_KM,
            "tup_irtifa_ft": config.SANAL_PIREP_KUME_IRTIFA_FARKI_FT,
            "pencere_dakika": config.SANAL_PIREP_DOGRULAMA_PENCERE_DAKIKA,
        },
    }


def ana(argv=None):
    from turbulans_radar.fizik.sanal_pirep import olaylari_tespit_et

    ayristirici = argparse.ArgumentParser(description="M6 sanal PIREP: tek iz tespiti ve PIREP doğrulaması (POD/POFD).")
    alt = ayristirici.add_subparsers(dest="komut", required=True)
    iz = alt.add_parser("iz", help="Bir Parquet izinde (OpenSky önbellek biçimi) olayları listeler.")
    iz.add_argument("dosya")
    dogrula = alt.add_parser("dogrula", help="ml_ornekleri PIREP'leriyle POD/POFD.")
    dogrula.add_argument("--pozitif", type=int, default=50)
    dogrula.add_argument("--negatif", type=int, default=50)
    dogrula.add_argument(
        "--maks-yeni-sorgu",
        type=int,
        default=0,
        help=f"OpenSky'a en fazla bu kadar yeni sorgu (0 = yalnızca önbellek; üst sınır {config.SANAL_PIREP_DOGRULAMA_MAKS_SORGU}).",
    )
    dogrula.add_argument("--cikti", default=os.path.join(config.CIKTI_KLASORU, "sanal_pirep_dogrulama.json"))
    argumanlar = ayristirici.parse_args(argv)

    if argumanlar.komut == "iz":
        olaylar, ozet = olaylari_tespit_et(pd.read_parquet(argumanlar.dosya))
        print(json.dumps(ozet, ensure_ascii=False))
        print(olaylar.to_string(index=False) if not olaylar.empty else "Olay yok.")
        return
    maks = min(max(argumanlar.maks_yeni_sorgu, 0), config.SANAL_PIREP_DOGRULAMA_MAKS_SORGU)
    sonuc = dogrulama_calistir(argumanlar.pozitif, argumanlar.negatif, maks_yeni_sorgu=maks)
    os.makedirs(os.path.dirname(argumanlar.cikti) or ".", exist_ok=True)
    with open(argumanlar.cikti, "w", encoding="utf-8") as dosya:
        json.dump(sonuc, dosya, ensure_ascii=False, indent=2)
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
