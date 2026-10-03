"""
ayirma_gostergesi.py
-----------------------
Hoca önerisi 4 (Doç. Dr. Fulya Aybek Çetek), basitleştirilmiş sürüm: önerilen
rota, aynı zaman penceresinde GERÇEKTEN uçmuş trafiğin ADS-B izleriyle
karşılaştırılır; varsayımsal ayırma minimalarının ihlal edildiği uçaklar
raporlanır. Yalnızca GÖSTERGEDİR: rota kararına girmez, ayırma garanti etmez
(uçuş öncesinde diğer trafiğin yörüngesi bilinmez; ayırma ATC'nin taktik
sorumluluğudur).

Minimalar AIP Türkiye'den: ENR 1.6 §4.1 yatay radar ayırması asgari 5 NM,
ENR 1.8 EUR-RVSM (FL290-FL410) dikey 1000 ft (config.AYIRMA_*). Gösterge radar
kapsaması, ATC talimatı ve RVSM onay durumunu bilmez.

Kontrol: her rota AYIRMA_ADIM_SANIYE adımlarla zaman damgalı 4D yörüngeye
çevrilir; aynı zaman dilimindeki trafik örnekleriyle yatay (NM) ve dikey (ft)
fark birlikte minimanın altındaysa ihlal. Gerçek uçuşun kendi izi (icao24)
hariç tutulur. Gerçek iz için ihlal beklenmez (ATC ayırmıştır); çıkarsa veri
gürültüsüne işaret eder -- göstergenin kendi sağlama kontrolü.

OpenSky: uçuş başına TEK sorgu (pencere ≤ AYIRMA_MAKS_PENCERE_SAAT, rota kutusu,
irtifa bandı, 10 sn örnekleme, satır sınırı), Parquet önbelleği; varsayılan
yalnızca önbellek. Kilit ve günlük tavan veri_yukleme._sorgu_calistir'da.

    turbulans-ayirma THY322 2019-01-15                 (yalnız önbellek)
    turbulans-ayirma THY322 2019-01-15 --sorgu-izni    (gerekirse 1 OpenSky sorgusu)
"""

import argparse
import hashlib
import json
import math
import os
import uuid

import numpy as np
import pandas as pd

from turbulans_radar import config

METRE_FT = 3.28084
_KM_NM = 1.852
_DUNYA_YARICAPI_KM = 6371.0
_SUTUNLAR = ["zaman_unix", "icao24", "enlem", "boylam", "baro_irtifa_m", "geo_irtifa_m"]


def _mesafe_nm(e1, b1, e2, b2):
    p1, p2 = np.radians(e1), np.radians(e2)
    dp, dl = p2 - p1, np.radians(np.asarray(b2) - np.asarray(b1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * _DUNYA_YARICAPI_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1))) / _KM_NM


def yorunge(enlemler, boylamlar, zamanlar, irtifa_ft, adim_sn=None) -> pd.DataFrame:
    """Rota noktalarından adim_sn aralıklı 4D yörünge (doğrusal ara değer)."""
    adim_sn = adim_sn or config.AYIRMA_ADIM_SANIYE
    t = (pd.to_datetime(pd.Series(list(zamanlar)), utc=True) - pd.Timestamp(0, tz="UTC")).dt.total_seconds().to_numpy()
    irtifa = np.broadcast_to(np.asarray(irtifa_ft, dtype=float), t.shape)
    ornek = t[0] + np.arange(int((t[-1] - t[0]) // adim_sn) + 1) * adim_sn
    if ornek[-1] < t[-1]:
        ornek = np.append(ornek, t[-1])
    return pd.DataFrame(
        {
            "t": ornek,
            "enlem": np.interp(ornek, t, np.asarray(enlemler, dtype=float)),
            "boylam": np.interp(ornek, t, np.asarray(boylamlar, dtype=float)),
            "irtifa_ft": np.interp(ornek, t, irtifa),
        }
    )


def ihlalleri_bul(yorunge_df, trafik_df, haric_icao24=None, yatay_nm=None, dikey_ft=None, adim_sn=None):
    """trafik_df: zaman_unix, icao24, enlem, boylam, baro_irtifa_m (yoksa geo).
    Dönüş: uçak başına ihlal özeti (DataFrame)."""
    yatay_nm = config.AYIRMA_YATAY_NM if yatay_nm is None else yatay_nm
    dikey_ft = config.AYIRMA_DIKEY_FT if dikey_ft is None else dikey_ft
    adim_sn = adim_sn or config.AYIRMA_ADIM_SANIYE
    bos = pd.DataFrame(columns=["icao24", "ilk_zaman", "son_zaman", "min_yatay_nm", "min_dikey_ft", "nokta_sayisi"])
    if trafik_df is None or trafik_df.empty or yorunge_df.empty:
        return bos
    trafik = trafik_df.copy()
    if haric_icao24:
        trafik = trafik[trafik["icao24"].str.lower() != str(haric_icao24).lower()]
    irtifa_m = pd.to_numeric(trafik.get("baro_irtifa_m"), errors="coerce")
    if "geo_irtifa_m" in trafik:
        irtifa_m = irtifa_m.fillna(pd.to_numeric(trafik["geo_irtifa_m"], errors="coerce"))
    trafik = trafik.assign(irtifa_ft=irtifa_m * METRE_FT).dropna(subset=["enlem", "boylam", "irtifa_ft"])
    trafik["dilim"] = np.round(trafik["zaman_unix"].astype(float) / adim_sn).astype("int64")
    yor = yorunge_df.assign(dilim=np.round(yorunge_df["t"] / adim_sn).astype("int64"))
    ciftler = yor.merge(trafik, on="dilim", suffixes=("", "_t"))
    if ciftler.empty:
        return bos
    ciftler["yatay_nm"] = _mesafe_nm(ciftler["enlem"], ciftler["boylam"], ciftler["enlem_t"], ciftler["boylam_t"])
    ciftler["dikey_ft"] = (ciftler["irtifa_ft"] - ciftler["irtifa_ft_t"]).abs()
    ihlal = ciftler[(ciftler["yatay_nm"] < yatay_nm) & (ciftler["dikey_ft"] < dikey_ft)]
    if ihlal.empty:
        return bos
    ozet = ihlal.groupby("icao24").agg(
        ilk_zaman=("t", "min"),
        son_zaman=("t", "max"),
        min_yatay_nm=("yatay_nm", "min"),
        min_dikey_ft=("dikey_ft", "min"),
        nokta_sayisi=("t", "size"),
    )
    for sutun in ("ilk_zaman", "son_zaman"):
        ozet[sutun] = pd.to_datetime(ozet[sutun], unit="s", utc=True)
    return ozet.reset_index()


def trafik_sorgusu(kutu, baslangic, bitis, irtifa_alt_ft, irtifa_ust_ft) -> tuple[str, list]:
    bas, bit = int(pd.Timestamp(baslangic).timestamp()), int(pd.Timestamp(bitis).timestamp())
    sorgu = f"""
    SELECT time, icao24, lat, lon, baroaltitude, geoaltitude
    FROM state_vectors_data4
    WHERE hour >= ? AND hour <= ?
    AND time >= ? AND time <= ? AND time % {int(config.AYIRMA_ADIM_SANIYE)} = 0
    AND lat >= ? AND lat <= ? AND lon >= ? AND lon <= ?
    AND baroaltitude >= ? AND baroaltitude <= ?
    AND onground = false
    LIMIT {config.MAKS_STATE_VECTOR_SATIRI}
    """
    parametreler = [
        (bas // 3600) * 3600,
        (bit // 3600) * 3600,
        bas,
        bit,
        *kutu,
        irtifa_alt_ft / METRE_FT,
        irtifa_ust_ft / METRE_FT,
    ]
    return sorgu, parametreler


def _onbellek_yolu(sorgu_parametreleri) -> str:
    ozet = hashlib.sha1(json.dumps([float(x) for x in sorgu_parametreleri]).encode()).hexdigest()[:20]
    return os.path.join(config.AYIRMA_ONBELLEK_KLASORU, f"{ozet}.parquet")


def trafik_izleri(kutu, baslangic, bitis, irtifa_alt_ft, irtifa_ust_ft, sorgu_izni=False, baglanti=None):
    """Önbellekte varsa oradan; yoksa ve sorgu_izni varsa OpenSky'dan TEK sorgu.
    Hiçbiri yoksa None. Pencere AYIRMA_MAKS_PENCERE_SAAT'ten uzunsa ValueError."""
    if (pd.Timestamp(bitis) - pd.Timestamp(baslangic)) > pd.Timedelta(hours=config.AYIRMA_MAKS_PENCERE_SAAT):
        raise ValueError(f"Trafik penceresi {config.AYIRMA_MAKS_PENCERE_SAAT} saatten uzun olamaz (OpenSky yükü).")
    sorgu, parametreler = trafik_sorgusu(kutu, baslangic, bitis, irtifa_alt_ft, irtifa_ust_ft)
    yol = _onbellek_yolu(parametreler)
    if os.path.exists(yol):
        return pd.read_parquet(yol)
    kapsayan = _kapsayan_onbellek(parametreler)
    if kapsayan is not None:
        return kapsayan
    if not sorgu_izni:
        return None
    from turbulans_radar.veri.veri_yukleme import _sorgu_calistir, trino_baglantisi_olustur

    df = _sorgu_calistir(baglanti or trino_baglantisi_olustur(), sorgu, _SUTUNLAR, parametreler)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    gecici = f"{yol}.{uuid.uuid4().hex[:12]}.yaziliyor"
    try:
        df.to_parquet(gecici, index=False)
        os.replace(gecici, yol)
    finally:
        if os.path.exists(gecici):
            os.remove(gecici)
    kayit_yaz(yol, parametreler)
    return df


def kayit_yaz(yol: str, parametreler) -> None:
    """Önbellek dosyasının sorgu parametreleri (kapsayan önbellek araması için)."""
    with open(yol.replace(".parquet", ".json"), "w", encoding="utf-8") as dosya:
        json.dump({"parametreler": [float(x) for x in parametreler], "adim_sn": config.AYIRMA_ADIM_SANIYE}, dosya)


def _kapsayan_onbellek(parametreler) -> pd.DataFrame | None:
    """İstenen pencereyi, kutuyu ve irtifa bandını KAPSAYAN önceki bir sorgunun
    önbelleği varsa ondan süzerek döner: OpenSky'a yeniden sorgu gitmez."""
    _, _, bas, bit, e_min, e_maks, b_min, b_maks, i_min, i_maks = map(float, parametreler)
    if not os.path.isdir(config.AYIRMA_ONBELLEK_KLASORU):
        return None
    for ad in sorted(os.listdir(config.AYIRMA_ONBELLEK_KLASORU)):
        if not ad.endswith(".json"):
            continue
        try:
            with open(os.path.join(config.AYIRMA_ONBELLEK_KLASORU, ad), encoding="utf-8") as dosya:
                kayit = json.load(dosya)
            _, _, k_bas, k_bit, ke_min, ke_maks, kb_min, kb_maks, ki_min, ki_maks = kayit["parametreler"]
        except (OSError, ValueError, KeyError):
            continue
        kapsar = (
            kayit.get("adim_sn") == config.AYIRMA_ADIM_SANIYE
            and k_bas <= bas
            and bit <= k_bit
            and ke_min <= e_min
            and e_maks <= ke_maks
            and kb_min <= b_min
            and b_maks <= kb_maks
            and ki_min <= i_min
            and i_maks <= ki_maks
        )
        yol = os.path.join(config.AYIRMA_ONBELLEK_KLASORU, ad.replace(".json", ".parquet"))
        if kapsar and os.path.exists(yol):
            df = pd.read_parquet(yol)
            return df[
                df["zaman_unix"].between(bas, bit)
                & df["enlem"].between(e_min, e_maks)
                & df["boylam"].between(b_min, b_maks)
                & df["baro_irtifa_m"].between(i_min, i_maks)
            ].reset_index(drop=True)
    return None


def _ozet(ihlaller: pd.DataFrame) -> dict:
    return {
        "ihlal_eden_ucak": len(ihlaller),
        "en_yakin_yatay_nm": None if ihlaller.empty else round(float(ihlaller["min_yatay_nm"].min()), 2),
        "en_yakin_dikey_ft": None if ihlaller.empty else round(float(ihlaller["min_dikey_ft"].min())),
        "ucaklar": ihlaller.astype({"ilk_zaman": str, "son_zaman": str}).to_dict(orient="records")
        if not ihlaller.empty
        else [],
    }


def rotalar_icin_gosterge(rotalar: dict, trafik_df, haric_icao24=None) -> dict:
    """rotalar: ad -> (enlemler, boylamlar, zamanlar, irtifa_ft)."""
    return {
        ad: _ozet(ihlalleri_bul(yorunge(*noktalar), trafik_df, haric_icao24=haric_icao24))
        for ad, noktalar in rotalar.items()
    }


def ucus_ayirma_gostergesi(ucus_numarasi, tarih_str, sorgu_izni=False, ucak_modeli=None, motor=None) -> dict:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import Ucus
    from turbulans_radar.depo.veritabani import motor_al
    from turbulans_radar.dogrulama.rota_backtest import _simulasyon_rotasi, backtest_girdileri

    motor = motor or motor_al()
    girdi = backtest_girdileri(ucus_numarasi, tarih_str, ucak_modeli or config.BACKTEST_UCAK_MODELI, motor)
    seyir, simulasyon, irtifa_ft = girdi["seyir"], girdi["simulasyon"], girdi["irtifa_ft"]
    rotalar = {
        "gercek": (seyir["enlem"], seyir["boylam"], list(seyir["zaman"]), seyir["irtifa_m"].to_numpy() / 0.3048),
        "buyuk_daire": _simulasyon_rotasi(simulasyon["normal_rota"]),
        "optimize": _simulasyon_rotasi(simulasyon["optimize_rota"]),
    }
    tum_enlem = np.concatenate([np.asarray(r[0], dtype=float) for r in rotalar.values()])
    tum_boylam = np.concatenate([np.asarray(r[1], dtype=float) for r in rotalar.values()])
    pay = config.AYIRMA_YATAY_NM * _KM_NM / 111.0 + 0.1
    kutu = (
        float(tum_enlem.min()) - pay,
        float(tum_enlem.max()) + pay,
        float(tum_boylam.min()) - pay / max(math.cos(math.radians(float(np.abs(tum_enlem).max()))), 0.1),
        float(tum_boylam.max()) + pay / max(math.cos(math.radians(float(np.abs(tum_enlem).max()))), 0.1),
    )
    bant = config.AYIRMA_DIKEY_FT + 2000.0
    bitis = max(pd.Timestamp(r[2][-1]) for r in rotalar.values())
    trafik = trafik_izleri(
        kutu, girdi["baslangic_zamani"], bitis, irtifa_ft - bant, irtifa_ft + bant, sorgu_izni=sorgu_izni
    )
    with Session(motor) as oturum:
        icao24 = oturum.execute(
            select(Ucus.icao24).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == pd.Timestamp(tarih_str).date())
        ).scalar_one_or_none()
    sonuc = {
        "ucus_numarasi": ucus_numarasi,
        "tarih": str(tarih_str),
        "minima": {
            "yatay_nm": config.AYIRMA_YATAY_NM,
            "dikey_ft": config.AYIRMA_DIKEY_FT,
            "kaynak": "AIP Türkiye ENR 1.6 §4.1 (5 NM), ENR 1.8 EUR-RVSM (1000 ft)",
        },
        "not": (
            "Gösterge: geçmiş trafikle ayırma minimalarının (AIP Türkiye ENR 1.6/1.8) karşılaştırması; "
            "rota kararına girmez, ayırma garanti etmez."
        ),
    }
    if trafik is None:
        return {**sonuc, "durum": "trafik_verisi_yok"}
    return {
        **sonuc,
        "durum": "olculdu",
        "trafik_ucak_sayisi": int(trafik["icao24"].nunique()) if not trafik.empty else 0,
        "satir_siniri_doldu": len(trafik) >= config.MAKS_STATE_VECTOR_SATIRI,
        "rotalar": rotalar_icin_gosterge(rotalar, trafik, haric_icao24=icao24),
    }


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Önerilen rota için geçmiş trafikle ayırma göstergesi (varsayımsal minima)."
    )
    ayristirici.add_argument("ucus_numarasi")
    ayristirici.add_argument("tarih")
    ayristirici.add_argument("--sorgu-izni", action="store_true", help="Önbellekte yoksa OpenSky'a TEK sorgu gönder.")
    argumanlar = ayristirici.parse_args(argv)
    sonuc = ucus_ayirma_gostergesi(argumanlar.ucus_numarasi, argumanlar.tarih, sorgu_izni=argumanlar.sorgu_izni)
    print(json.dumps(sonuc, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    ana()
