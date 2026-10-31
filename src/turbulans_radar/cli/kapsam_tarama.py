"""
kapsam_tarama.py
------------------
OpenSky ADS-B kapsamı iyi örnek uçuş bulur. Verilen günlerde seçili havalimanlarından
kalkan ya da inen uçuşları `flights_data4`'ten listeler, adayların izini çeker (rota
önbelleğine yazılır, ikinci kez sorulmaz) ve izdeki boşlukları ölçer: en büyük boşluk,
seyirde (FL280 üstü) kapsanan süre oranı. Gönüllü alıcı ağı Doğu Anadolu'da seyrek
olduğu için (THY322, 15 Ocak 2019: 65 dk boşluk) demo ve gösterim vakası buradan seçilir.

Sorgu sayısı: gün başına 1 + aday sayısı; günlük OpenSky kotasından düşer.

    turbulans-kapsam-tarama --gun 2026-10-20 --gun 2026-10-21 --adet 10
"""

import argparse
import os

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

import numpy as np
import pandas as pd

from turbulans_radar import config

VARSAYILAN_HAVALIMANLARI = ("LTFM", "LTFJ", "LTBJ", "LTAI", "LTFE", "LTBS", "LTAC")
SEYIR_TABANI_M = 280 * 100 * 0.3048
BOSLUK_ESIGI_SN = 60
MIN_SURE_DK = 45
MAKS_SURE_DK = 300


def ucuslari_listele(baglanti, gun, havalimanlari) -> pd.DataFrame:
    from turbulans_radar.veri.veri_yukleme import _sorgu_calistir

    gun_ts = int(pd.Timestamp(gun, tz="UTC").timestamp())
    yer = ", ".join("?" for _ in havalimanlari)
    sorgu = f"""
    SELECT icao24, TRIM(callsign), firstseen, lastseen, estdepartureairport, estarrivalairport
    FROM flights_data4
    WHERE day = ?
    AND callsign IS NOT NULL AND TRIM(callsign) != ''
    AND estdepartureairport IS NOT NULL AND estarrivalairport IS NOT NULL
    AND (estdepartureairport IN ({yer}) OR estarrivalairport IN ({yer}))
    """
    sutunlar = ["icao24", "ucus_numarasi", "ilk_gorulme", "son_gorulme", "kalkis", "varis"]
    return _sorgu_calistir(baglanti, sorgu, sutunlar, [gun_ts, *havalimanlari, *havalimanlari])


def adaylari_sec(
    ucuslar: pd.DataFrame,
    havalimanlari,
    adet,
    min_sure_dk=MIN_SURE_DK,
    maks_sure_dk=MAKS_SURE_DK,
    uzun_dis=False,
    saat_araligi=None,
):
    """İki ucu da listede olan (iç hat) en uzun uçuşlar ve bir ucu listede olan en kısa dış hatlar, yarı yarıya;
    aynı uçuş numarasından bir tane. uzun_dis: yalnız dış hatlar, en uzun önce (seyri uzun vaka için)."""
    if ucuslar.empty:
        return ucuslar
    df = ucuslar.assign(sure_dk=(ucuslar["son_gorulme"] - ucuslar["ilk_gorulme"]) / 60)
    df = df[(df["sure_dk"] >= min_sure_dk) & (df["sure_dk"] <= maks_sure_dk) & (df["kalkis"] != df["varis"])]
    df = df.drop_duplicates("ucus_numarasi")
    if saat_araligi:
        saat = pd.to_datetime(df["ilk_gorulme"], unit="s", utc=True).dt.hour
        df = df[(saat >= saat_araligi[0]) & (saat <= saat_araligi[1])]
    ic_maske = df["kalkis"].isin(havalimanlari) & df["varis"].isin(havalimanlari)
    ic = df[ic_maske].sort_values("sure_dk", ascending=False)
    dis = df[~ic_maske].sort_values("sure_dk", ascending=not uzun_dis)
    ic_adet = 0 if uzun_dis else min(len(ic), (adet + 1) // 2)
    secim = pd.concat([ic.head(ic_adet), dis.head(adet - ic_adet)])
    return secim.reset_index(drop=True)


def _bosluklar(zaman_sn: np.ndarray, esik_sn: float) -> tuple[float, float]:
    """(kapsanan süre, en büyük boşluk) saniye; ardışık iki nokta arası esik_sn'den uzunsa boşluktur."""
    if len(zaman_sn) < 2:
        return 0.0, 0.0
    farklar = np.diff(np.sort(zaman_sn))
    return float(farklar[farklar <= esik_sn].sum()), float(farklar.max())


def kapsam_olc(rota: pd.DataFrame, ilk_gorulme=None, son_gorulme=None, esik_sn=BOSLUK_ESIGI_SN) -> dict:
    zaman = pd.to_numeric(rota["zaman_unix"], errors="coerce").dropna().to_numpy(dtype=float)
    if not len(zaman):
        return {"nokta": 0, "kapsam_orani": 0.0, "seyir_nokta": 0, "seyir_kapsam_orani": None}
    bas = float(ilk_gorulme) if ilk_gorulme is not None else zaman.min()
    son = float(son_gorulme) if son_gorulme is not None else zaman.max()
    toplam = max(son - bas, 1.0)
    kapsanan, en_buyuk = _bosluklar(np.concatenate([[bas], zaman, [son]]), esik_sn)
    seyir = rota[pd.to_numeric(rota["baro_irtifa_m"], errors="coerce") >= SEYIR_TABANI_M]
    seyir_zaman = pd.to_numeric(seyir["zaman_unix"], errors="coerce").dropna().to_numpy(dtype=float)
    sonuc = {
        "nokta": len(zaman),
        "sure_dk": round(toplam / 60, 1),
        "kapsam_orani": round(kapsanan / toplam, 3),
        "en_buyuk_bosluk_dk": round(en_buyuk / 60, 1),
        "seyir_nokta": len(seyir_zaman),
        "seyir_suresi_dk": None,
        "seyir_kapsam_orani": None,
        "seyir_en_buyuk_bosluk_dk": None,
        "seyir_fl_maks": None,
    }
    if len(seyir_zaman) >= 2:
        seyir_toplam = seyir_zaman.max() - seyir_zaman.min()
        seyir_kapsanan, seyir_bosluk = _bosluklar(seyir_zaman, esik_sn)
        sonuc.update(
            seyir_suresi_dk=round(seyir_toplam / 60, 1),
            seyir_kapsam_orani=round(seyir_kapsanan / max(seyir_toplam, 1.0), 3),
            seyir_en_buyuk_bosluk_dk=round(seyir_bosluk / 60, 1),
            seyir_fl_maks=int(pd.to_numeric(seyir["baro_irtifa_m"]).max() / 0.3048 / 100),
        )
    return sonuc


def _rota_getir(baglanti, aday, gun):
    from turbulans_radar.veri.opensky_onbellegi import rota_onbellege_yaz, rota_onbellekten_oku
    from turbulans_radar.veri.veri_yukleme import ucus_rotasini_cek

    rota = rota_onbellekten_oku(aday["ucus_numarasi"], gun)
    if rota is not None:
        return rota, True
    rota = ucus_rotasini_cek(baglanti, aday["icao24"], int(aday["ilk_gorulme"]), int(aday["son_gorulme"]))
    if not rota.empty:
        rota = rota.assign(
            ucus_numarasi=aday["ucus_numarasi"], kalkis_havaalani=aday["kalkis"], varis_havaalani=aday["varis"]
        )
        rota_onbellege_yaz(rota, aday["ucus_numarasi"], gun)
    return rota, False


def tara(
    gunler,
    havalimanlari=VARSAYILAN_HAVALIMANLARI,
    adet=10,
    baglanti=None,
    uzun_dis=False,
    sure_araligi=None,
    saat_araligi=None,
) -> pd.DataFrame:
    if baglanti is None:
        from turbulans_radar.veri.veri_yukleme import trino_baglantisi_olustur

        baglanti = trino_baglantisi_olustur()
    satirlar = []
    for gun in gunler:
        adaylar = adaylari_sec(
            ucuslari_listele(baglanti, gun, havalimanlari),
            havalimanlari,
            adet,
            *(sure_araligi or (MIN_SURE_DK, MAKS_SURE_DK)),
            uzun_dis=uzun_dis,
            saat_araligi=saat_araligi,
        )
        print(f"[Bilgi] {gun}: {len(adaylar)} aday")
        for _, aday in adaylar.iterrows():
            rota, onbellekten = _rota_getir(baglanti, aday, gun)
            olcu = kapsam_olc(rota, aday["ilk_gorulme"], aday["son_gorulme"]) if not rota.empty else {"nokta": 0}
            satirlar.append(
                {
                    "gun": gun,
                    "ucus_numarasi": aday["ucus_numarasi"],
                    "kalkis": aday["kalkis"],
                    "varis": aday["varis"],
                    "icao24": aday["icao24"],
                    "onbellekten": onbellekten,
                    **olcu,
                }
            )
    return pd.DataFrame(satirlar)


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="OpenSky ADS-B kapsamı iyi örnek uçuş taraması.")
    ayrac.add_argument("--gun", action="append", required=True, help="YYYY-MM-DD (birden çok verilebilir)")
    ayrac.add_argument("--havalimanlari", default=",".join(VARSAYILAN_HAVALIMANLARI))
    ayrac.add_argument("--adet", type=int, default=10, help="Gün başına aday (her biri bir sorgu)")
    ayrac.add_argument(
        "--sure-dk", default=f"{MIN_SURE_DK},{MAKS_SURE_DK}", help="Uçuş süresi aralığı, dk (en az,en çok)"
    )
    ayrac.add_argument("--saat", help="Kalkış saati aralığı, UTC (örn. 8,14)")
    ayrac.add_argument("--uzun-dis", action="store_true", help="Yalnız dış hatlar, en uzun seyirli önce")
    ayrac.add_argument("--cikti", default=os.path.join(config.CIKTI_KLASORU, "kapsam_tarama.csv"))
    arg = ayrac.parse_args(argv)
    havalimanlari = tuple(h.strip().upper() for h in arg.havalimanlari.split(",") if h.strip())
    sonuc = tara(
        arg.gun,
        havalimanlari,
        arg.adet,
        uzun_dis=arg.uzun_dis,
        sure_araligi=tuple(float(x) for x in arg.sure_dk.split(",")),
        saat_araligi=tuple(int(x) for x in arg.saat.split(",")) if arg.saat else None,
    )
    os.makedirs(os.path.dirname(arg.cikti) or ".", exist_ok=True)
    sonuc.to_csv(arg.cikti, index=False)
    if not sonuc.empty and "seyir_kapsam_orani" in sonuc:
        sonuc = sonuc.sort_values(["seyir_kapsam_orani", "seyir_suresi_dk"], ascending=False)
        sutunlar = ["gun", "ucus_numarasi", "kalkis", "varis", "seyir_suresi_dk", "seyir_kapsam_orani",
                    "seyir_en_buyuk_bosluk_dk", "en_buyuk_bosluk_dk"]  # fmt: skip
        print(sonuc[sutunlar].head(10).to_string(index=False))
    print(arg.cikti)
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
