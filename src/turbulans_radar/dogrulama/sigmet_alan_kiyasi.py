"""
sigmet_alan_kiyasi.py
----------------------
Protokol §14: Türk FIR'larındaki (LTAA, LTBB) TURB SIGMET'lerin alanında ERA5 TI1, aynı saatte ve aynı irtifa
bandında SIGMET'in 300 km'lik çevresinden (halka) daha sık mı riskli? SIGMET başına rastgele noktalar, içeride ve
halkada riskli oranı, fark d; SIGMET'ler eşit ağırlıklı ortalama d ve SIGMET bloklu bootstrap GA. Keşifseldir:
SIGMET gözlem değil uyarıdır, noktalar uzaysal olarak bağımlıdır. Çıktılar sertifikalı EDR değildir; sistem karar
destek aracıdır.

    CDSAPI_RC=<CDSAPI_RC_DOSYASI> turbulans-sigmet-alan --cikti docs/sonuclar/2026-11-12_turkiye_sigmet_ti1
"""

import argparse
import contextlib
import io
import json
import os
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import shapely

from turbulans_radar import config
from turbulans_radar.fizik.ti1_esigi import kaynak_ti1_esigi
from turbulans_radar.rota.risk_katmanlari import sigmet_geometrisi

FIRLER = ("LTAA", "LTBB")
ILK_GUN = "2026-09-30"
HALKA_KM = 300.0
NOKTA_SAYISI = 6000
FL_ARALIGI = (280, 430)
BOOTSTRAP_TEKRAR = 10_000
_FT_M = 0.3048
_KM_DERECE = 111.2


def _utc(zaman) -> pd.Timestamp:
    ts = pd.Timestamp(zaman)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def tam_saatler(sigmet) -> list[pd.Timestamp]:
    bas, son = _utc(sigmet["gecerlilik_baslangic"]), _utc(sigmet["gecerlilik_bitis"])
    return list(pd.date_range(bas.ceil("h"), son.floor("h"), freq="h"))


def fl_bandi(sigmet, fl_araligi=FL_ARALIGI) -> tuple[float, float] | None:
    taban = -np.inf if sigmet.get("taban_ft") is None else sigmet["taban_ft"] / 100.0
    tavan = np.inf if sigmet.get("tavan_ft") is None else sigmet["tavan_ft"] / 100.0
    alt, ust = max(fl_araligi[0], taban), min(fl_araligi[1], tavan)
    return (float(alt), float(ust)) if alt < ust else None


def ornekle(sigmet, saatler, bant, nokta_sayisi=NOKTA_SAYISI, halka_km=HALKA_KM, tohum=0) -> pd.DataFrame:
    """Poligon kutusunun halka kadar genişletilmiş hâlinde düzgün noktalar; 'bolge' içeride / halka / dışarıda."""
    ic = sigmet_geometrisi(sigmet["poligon"])
    dis = sigmet_geometrisi(sigmet["poligon"], tampon_km=halka_km)
    boylam_min, enlem_min, boylam_maks, enlem_maks = shapely.bounds(dis)
    rng = np.random.default_rng(tohum)
    noktalar = pd.DataFrame(
        {
            "zaman": [saatler[i].tz_convert(None) for i in rng.integers(0, len(saatler), nokta_sayisi)],
            "enlem": rng.uniform(enlem_min, enlem_maks, nokta_sayisi),
            "boylam": rng.uniform(boylam_min, boylam_maks, nokta_sayisi),
            "baro_irtifa_m": rng.uniform(bant[0], bant[1], nokta_sayisi) * 100 * _FT_M,
        }
    )
    icinde = shapely.contains_xy(ic, noktalar["boylam"].to_numpy(), noktalar["enlem"].to_numpy())
    tamponda = shapely.contains_xy(dis, noktalar["boylam"].to_numpy(), noktalar["enlem"].to_numpy())
    noktalar["bolge"] = np.where(icinde, "iceride", np.where(tamponda, "halka", "disarida"))
    return noktalar


def indirme_kutusu(sigmet, halka_km=HALKA_KM) -> tuple[float, float, float, float]:
    boylam_min, enlem_min, boylam_maks, enlem_maks = shapely.bounds(
        sigmet_geometrisi(sigmet["poligon"], tampon_km=halka_km)
    )
    return (float(enlem_min), float(enlem_maks), float(boylam_min), float(boylam_maks))


def _ti1(kup, noktalar) -> np.ndarray:
    from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir

    with contextlib.redirect_stdout(io.StringIO()):
        return rotayi_hava_durumuyla_eslestir(noktalar, kup)["ti1_indeksi"].to_numpy(dtype=float)


def sigmet_olcumu(noktalar, ti1, esik) -> dict:
    gecerli = np.isfinite(ti1)
    sonuc: dict = {"nokta": int(gecerli.sum())}
    for bolge in ("iceride", "halka"):
        maske = gecerli & (noktalar["bolge"].to_numpy() == bolge)
        medyan = float(np.median(ti1[maske])) if maske.any() else None
        sonuc[f"{bolge}_nokta"] = int(maske.sum())
        sonuc[f"{bolge}_riskli_orani"] = float(np.mean(ti1[maske] > esik)) if maske.any() else None
        sonuc[f"{bolge}_medyan_log10_ti1"] = float(np.log10(medyan)) if medyan is not None and medyan > 0 else None
    ic, halka = sonuc["iceride_riskli_orani"], sonuc["halka_riskli_orani"]
    sonuc["fark"] = None if ic is None or halka is None else ic - halka
    ic_log, halka_log = sonuc["iceride_medyan_log10_ti1"], sonuc["halka_medyan_log10_ti1"]
    sonuc["medyan_log10_farki"] = None if ic_log is None or halka_log is None else ic_log - halka_log
    return sonuc


def havuzla(farklar, tekrar=BOOTSTRAP_TEKRAR, tohum=0) -> dict:
    d = np.asarray([f for f in farklar if f is not None], dtype=float)
    if len(d) == 0:
        return {"sigmet": 0, "ortalama_fark": None, "ga95": None, "pozitif_sigmet": 0}
    rng = np.random.default_rng(tohum)
    ornekler = d[rng.integers(0, len(d), (tekrar, len(d)))].mean(axis=1)
    return {
        "sigmet": int(len(d)),
        "ortalama_fark": float(d.mean()),
        "ga95": [float(np.percentile(ornekler, 2.5)), float(np.percentile(ornekler, 97.5))],
        "pozitif_sigmet": int((d > 0).sum()),
    }


def okuma(havuz) -> str:
    if not havuz["sigmet"]:
        return "SIGMET yok"
    alt = havuz["ga95"][0]
    if alt > 0 and havuz["pozitif_sigmet"] * 2 > havuz["sigmet"]:
        return "TI1 Türk TURB SIGMET alanlarında çevresinden daha sık riskli"
    return "fark gösterilemedi"


def sigmetleri_getir(bitis, firler=FIRLER, ilk_gun=ILK_GUN, motor=None) -> list[dict]:
    from turbulans_radar.veri.sigmet_saglayici import gecerli_sigmetleri_getir

    sigmetler = gecerli_sigmetleri_getir(
        _utc(ilk_gun).to_pydatetime(), _utc(bitis).to_pydatetime(), tehlikeler=["TURB"], motor=motor
    )
    return [s for s in sigmetler if s["fir_kodu"] in firler and _utc(s["gecerlilik_baslangic"]) <= _utc(bitis)]


def calistir(sigmetler, kup_getir, esik, nokta_sayisi=NOKTA_SAYISI, tekrar=BOOTSTRAP_TEKRAR) -> dict:
    """kup_getir(gun, saatler, kutu) -> o günün ERA5 küpü."""
    kayitlar = []
    for sira, sigmet in enumerate(sigmetler):
        kimlik = {
            "id": sigmet.get("id"),
            "fir": sigmet["fir_kodu"],
            "seri_no": sigmet.get("seri_no"),
            "gecerlilik": [
                _utc(sigmet["gecerlilik_baslangic"]).isoformat(),
                _utc(sigmet["gecerlilik_bitis"]).isoformat(),
            ],
            "bant_ft": [sigmet.get("taban_ft"), sigmet.get("tavan_ft")],
        }
        bant, saatler = fl_bandi(sigmet), tam_saatler(sigmet)
        if bant is None or not saatler:
            kayitlar.append({**kimlik, "dustu": "bant FL280–430 ile kesişmiyor" if bant is None else "tam saat yok"})
            continue
        noktalar = ornekle(sigmet, saatler, bant, nokta_sayisi, tohum=sira)
        kutu = indirme_kutusu(sigmet)
        ti1 = np.full(len(noktalar), np.nan)
        for gun, grup in noktalar.groupby(noktalar["zaman"].dt.normalize()):
            kup = kup_getir(gun, sorted({int(s.hour) for s in saatler if s.tz_convert(None).normalize() == gun}), kutu)
            ti1[grup.index.to_numpy()] = _ti1(kup, grup.reset_index(drop=True))
        kayitlar.append(
            {**kimlik, "fl_bandi": list(bant), "saatler": len(saatler), **sigmet_olcumu(noktalar, ti1, esik)}
        )
    havuz = havuzla([k.get("fark") for k in kayitlar], tekrar)
    return {"kayitlar": kayitlar, "havuz": havuz, "okuma": okuma(havuz)}


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="Türk TURB SIGMET alanlarında ERA5 TI1 (protokol §14).")
    ayrac.add_argument("--cikti", required=True, help="Rapor klasörü (dosya varsa üzerine yazılmaz)")
    ayrac.add_argument("--era5-klasor", default=os.path.join(config.CIKTI_KLASORU, "sigmet_alan", "era5"))
    ayrac.add_argument("--nokta", type=int, default=NOKTA_SAYISI)
    arg = ayrac.parse_args(argv)
    yol = os.path.join(arg.cikti, "sigmet_alan.json")
    if os.path.exists(yol):
        raise SystemExit(f"{yol} var; protokol §14 gereği üzerine yazılmaz.")
    from turbulans_radar.analiz.esik_esleme import era5_gununu_getir
    from turbulans_radar.uretim_bilgisi import yazilim_commit

    simdi = datetime.now(UTC)
    bitis = _utc(simdi) - pd.Timedelta(days=config.ERA5_YAYIN_GECIKMESI_GUN)
    os.makedirs(arg.era5_klasor, exist_ok=True)
    esik = kaynak_ti1_esigi("era5")
    sigmetler = sigmetleri_getir(bitis)
    sonuc = calistir(
        sigmetler, lambda gun, saatler, kutu: era5_gununu_getir(gun, saatler, kutu, arg.era5_klasor), esik, arg.nokta
    )
    rapor = {
        "protokol": "docs/deney_protokolu.md §14",
        "parametreler": {
            "firler": list(FIRLER),
            "ilk_gun": ILK_GUN,
            "son_baslangic": bitis.isoformat(),
            "ti1_esigi": esik,
            "halka_km": HALKA_KM,
            "nokta": arg.nokta,
            "fl_araligi": list(FL_ARALIGI),
            "bootstrap_tekrar": BOOTSTRAP_TEKRAR,
        },
        "commit": yazilim_commit(),
        "uretim_zamani": simdi.isoformat(timespec="seconds"),
        **sonuc,
    }
    os.makedirs(arg.cikti, exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)
    print(json.dumps({"havuz": sonuc["havuz"], "okuma": sonuc["okuma"]}, ensure_ascii=False))


if __name__ == "__main__":
    ana()
