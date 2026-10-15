"""
tip_analizi.py
----------------
F3: uçak tipine (kanat yükü vekiline) göre katmanlı PIREP analizi. Amaç, "tip
bazlı etiketli veri yok" sınırlamasını ölçmek: aynı TI1 aralığında ağır kanat
yüklü uçakların türbülans bildirme oranı hafif yüklülerden farklı mı?

- Uçak tipi yerel IEM ham metninin /TP alanından (config.ML_PIREP_ARSIV_KLASORU,
  2018–Mart 2020) alınır; metni olmayan örnek analize girmez.
- Kanat yükü vekili = OpenAP MTOW / kanat alanı (kg/m²). Gerçek kütle bilinmez;
  OpenAP'de olmayan tip ve aile kodları (B757 gibi) atlanır, değer uydurulmaz.
- Altın test günleri okuma anında dışlanır (protokol ve sonuç paketi değişmez).
- Gruplar, tipler kanat yüküne göre sıralanıp örneklerin yaklaşık üçte birlerine
  bölünerek kurulur (bir tip iki gruba bölünmez). Fark, TI1 beşte birlik
  dilimleri içinde pozitif oran farkının dilim büyüklüğüyle ağırlıklı ortalamasıdır;
  güven aralığı gün bazlı blok bootstrap.

Bu analiz özellik eklemez; anlamlı fark çıkarsa tipe duyarlı risk (M4) ayrıca
tasarlanır.

    turbulans-ml-tip-analizi --cikti docs/rapor/veri
"""

import argparse
import glob
import json
import os
import re

import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.dogrulama.bagimsiz_kanit import pirep_siddet_sinifi
from turbulans_radar.ml.degerlendirme import _bootstrap_ornekleri, bootstrap_guven_araligi
from turbulans_radar.ml.ml_otomatik_egitim import _atomik_yaz_json, _json_guvenli, _utc_gunu, altin_test_gunleri
from turbulans_radar.ml.ml_veri_hatti import pirep_anahtari
from turbulans_radar.ml.rf_deneyi import altin_gunlerini_at

_TIP = re.compile(r"/TP\s*([A-Z][A-Z0-9]{1,3})\b")
GRUPLAR = ("hafif", "orta", "agir")


def rapordan_tip(rapor) -> str | None:
    eslesme = _TIP.search(str(rapor or ""))
    if not eslesme:
        return None
    return eslesme.group(1)


def kanat_yuku_kg_m2(tip) -> float | None:
    try:
        from openap import prop

        ucak = prop.aircraft(str(tip).lower())
    except Exception:
        return None
    alan = (ucak.get("wing") or {}).get("area")
    return float(ucak["mtow"]) / float(alan) if ucak.get("mtow") and alan else None


def arsiv_tipleri(klasor=None) -> pd.Series:
    """pirep_anahtari -> ICAO tip kodu (yalnız seyir irtifası, şiddeti ayrıştırılabilen raporlar)."""
    klasor = klasor or config.ML_PIREP_ARSIV_KLASORU
    sutunlar = ["VALID", "REPORT", "TURBULENCE", "FL", "LAT", "LON"]
    parcalar = []
    for dosya in sorted(glob.glob(os.path.join(klasor, "*.csv"))):
        ham = pd.read_csv(dosya, dtype=str, on_bad_lines="skip", usecols=lambda sutun: sutun in sutunlar)
        df = pd.DataFrame(
            {
                "zaman": pd.to_datetime(ham["VALID"], format="%Y%m%d%H%M", utc=True, errors="coerce"),
                "enlem": pd.to_numeric(ham["LAT"], errors="coerce"),
                "boylam": pd.to_numeric(ham["LON"], errors="coerce"),
                "irtifa_ft": pd.to_numeric(ham["FL"], errors="coerce"),
                "metin": ham["TURBULENCE"],
                "tip": ham["REPORT"].map(rapordan_tip),
            }
        ).dropna()
        df = df[df["irtifa_ft"].between(config.ML_MIN_IRTIFA_FT, config.ML_MAKS_IRTIFA_FT)]
        df = df[df["metin"].map(pirep_siddet_sinifi).notna()]
        anahtar = [pirep_anahtari(*s) for s in df[["zaman", "enlem", "boylam", "irtifa_ft"]].itertuples(index=False)]
        parcalar.append(pd.Series(df["tip"].to_numpy(), index=anahtar))
    if not parcalar:
        return pd.Series(dtype=str)
    tum = pd.concat(parcalar)
    return tum[~tum.index.duplicated(keep=False)]


def ornekleri_oku(motor=None) -> pd.DataFrame:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import MlOrnegi
    from turbulans_radar.depo.veritabani import motor_al

    altin = altin_test_gunleri()
    if altin is None:
        raise SystemExit("Altın test günleri dondurulmamış; analiz altın günleri dışlayamaz.")
    sorgu = select(MlOrnegi.pirep_anahtari, MlOrnegi.zaman, MlOrnegi.sinif, MlOrnegi.ozellikler).where(
        MlOrnegi.durum == "eslesti"
    )
    with Session(motor or motor_al()) as oturum:
        satirlar = oturum.execute(sorgu).all()
    df = pd.DataFrame(
        {
            "anahtar": [s.pirep_anahtari for s in satirlar],
            "y": [int(s.sinif >= 1) for s in satirlar],
            "gun": [_utc_gunu(s.zaman) for s in satirlar],
            "ti1": [(s.ozellikler or {}).get("ti1_indeksi") for s in satirlar],
        }
    )
    df["ti1"] = pd.to_numeric(df["ti1"], errors="coerce")
    return altin_gunlerini_at(df.dropna(subset=["ti1"]), altin)


def katmanli_fark(df: pd.DataFrame, a="agir", b="hafif", dilim_sayisi=5) -> float:
    """TI1 dilimleri içinde pozitif oran(a) - pozitif oran(b), dilim büyüklüğüyle ağırlıklı."""
    farklar, agirliklar = [], []
    for _, dilim in df.groupby("ti1_dilimi", observed=True):
        ga, gb = dilim[dilim["grup"] == a], dilim[dilim["grup"] == b]
        if len(ga) and len(gb):
            farklar.append(ga["y"].mean() - gb["y"].mean())
            agirliklar.append(len(dilim))
    return float(np.average(farklar, weights=agirliklar)) if farklar else float("nan")


def tip_gruplari(df: pd.DataFrame) -> pd.Series:
    """Tipler kanat yüküne göre sıralanır; kümülatif örnek payının orta noktası
    1/3 ve 2/3'e göre hafif/orta/ağır. Bir tip iki gruba bölünmez."""
    tipler = df.groupby("tip").agg(yuk=("kanat_yuku", "first"), n=("y", "size")).sort_values(["yuk", "n"])
    orta_nokta = (tipler["n"].cumsum() - tipler["n"] / 2) / tipler["n"].sum()
    grup = pd.Series(np.select([orta_nokta < 1 / 3, orta_nokta < 2 / 3], GRUPLAR[:2], GRUPLAR[2]), index=tipler.index)
    return df["tip"].map(grup)


def analiz(df: pd.DataFrame, tekrar=None, tohum=0) -> dict:
    tekrar = config.ML_BOOTSTRAP_TEKRAR if tekrar is None else tekrar
    df = df.copy()
    df["grup"] = tip_gruplari(df)
    df["ti1_dilimi"] = pd.qcut(df["ti1"], 5, labels=False, duplicates="drop")
    gunler = df["gun"].to_numpy()
    gruplar = {}
    for ad in GRUPLAR:
        alt = df[df["grup"] == ad]
        if alt.empty:
            continue
        gruplar[ad] = {
            "ornek": int(len(alt)),
            "gun": int(alt["gun"].nunique()),
            "kanat_yuku_aralik_kg_m2": [float(alt["kanat_yuku"].min()), float(alt["kanat_yuku"].max())],
            "pozitif_orani": float(alt["y"].mean()),
            "en_sik_tipler": alt["tip"].value_counts().head(5).to_dict(),
            "ti1_roc_auc": bootstrap_guven_araligi(alt["y"], alt["ti1"], alt["gun"].to_numpy(), tekrar=tekrar),
            "ti1_dilimi_pozitif_orani": alt.groupby("ti1_dilimi")["y"].mean().round(4).to_dict(),
        }
    nokta = katmanli_fark(df)
    tekrarlar = np.array([katmanli_fark(df.iloc[i]) for i in _bootstrap_ornekleri(gunler, tekrar, tohum)])
    tekrarlar = tekrarlar[np.isfinite(tekrarlar)]
    alt_sinir, ust_sinir = np.quantile(tekrarlar, [0.025, 0.975]) if len(tekrarlar) else (np.nan, np.nan)
    return {
        "gruplar": gruplar,
        "agir_eksi_hafif_katmanli_pozitif_orani": {
            "fark": nokta,
            "alt": float(alt_sinir),
            "ust": float(ust_sinir),
            "gecerli_tekrar": int(len(tekrarlar)),
            "anlamli": bool(alt_sinir > 0 or ust_sinir < 0),
        },
    }


def analiz_raporu_yaz(klasor: str, motor=None, tekrar=None) -> dict:
    ornekler = ornekleri_oku(motor)
    tipler = arsiv_tipleri()
    ornekler["tip"] = ornekler["anahtar"].map(tipler)
    yukler = {t: kanat_yuku_kg_m2(t) for t in ornekler["tip"].dropna().unique()}
    ornekler["kanat_yuku"] = ornekler["tip"].map(yukler)
    kullanilan = ornekler.dropna(subset=["tip", "kanat_yuku"])
    rapor = {
        "kapsam": {
            "okunan_ornek": int(len(ornekler)),
            "tipi_bilinen": int(ornekler["tip"].notna().sum()),
            "openap_kanat_yuku_olan": int(len(kullanilan)),
            "openap_disi_tipler": sorted(t for t, y in yukler.items() if y is None)[:40],
            "altin_gunler": "okuma anında dışlandı",
        },
        "yontem": "Kanat yükü = OpenAP MTOW / kanat alanı (gerçek kütle bilinmez). Gruplar tip bazında, örneklerin "
        "yaklaşık üçte birleri; "
        "fark TI1 beşte birlik dilimleri içinde, gün bazlı blok bootstrap %95 GA.",
        **(analiz(kullanilan, tekrar) if len(kullanilan) else {"durum": "veri_yok"}),
        "uyari": "Analizdir; özellik eklemez, protokolü değiştirmez. PIREP öznel ve yanlıdır; ağır uçak "
        "pilotlarının bildirme eşiği de farklı olabilir (etki tip ile bildirme davranışını ayırmaz).",
    }
    rapor = _json_guvenli(rapor)
    os.makedirs(klasor, exist_ok=True)
    _atomik_yaz_json(os.path.join(klasor, "tip_analizi.json"), rapor)
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="F3: kanat yükü vekiline göre katmanlı PIREP analizi.")
    ayristirici.add_argument("--cikti", required=True, help="Sonuç klasörü (tip_analizi.json)")
    argumanlar = ayristirici.parse_args(argv)
    rapor = analiz_raporu_yaz(argumanlar.cikti)
    print(json.dumps(rapor, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
