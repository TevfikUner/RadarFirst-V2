"""
edr_esleme.py
--------------
Göstergeleri log-normal eşlemeyle EDR'ye çevirip birleştirir (Sharman & Pearson
2017, GTG yaklaşımı):

    ln EDR_D = a + b·ln D,   b = C2 / SD(ln D),   a = C1 − b·⟨ln D⟩

C1, C2: seyir irtifasında (20–45 kft) ln EDR'nin klimatolojik ortalaması ve
standart sapması; Sharman & Pearson (2017) değerleri, Kim vd. (2019,
doi:10.5194/amt-2019-442) aktarımıyla.
⟨ln D⟩ ve SD(ln D) bu projenin ERA5 pencere deposundan hesaplanır
(turbulans-edr-esleme) ve edr_esleme_katsayilari.json'da saklanır.
Birleşik EDR, eşlenmiş göstergelerin eşit ağırlıklı ortalamasıdır.

Sonuç sertifikalı EDR değildir; reanalizden türetilmiş bir tahmindir. Katsayı
dosyası yoksa birleşik EDR NaN döner ve edr_proxy tanh ölçeğine düşer (yedek).
"""

import argparse
import json
import os
import warnings
from functools import lru_cache

import numpy as np
import pandas as pd

C1_LN_EDR_ORTALAMA = -2.953
C2_LN_EDR_SS = 0.602
KAYNAK = "Sharman & Pearson (2017), 20–45 kft; Kim vd. (2019) doi:10.5194/amt-2019-442"

RI_TABANI = 0.01
GOSTERGELER = ("ti1_indeksi", "ti2_indeksi", "dusey_ruzgar_kaymasi", "yatay_deformasyon", "ters_richardson")
KATSAYI_DOSYASI = os.path.join(os.path.dirname(__file__), "edr_esleme_katsayilari.json")


def gosterge_tablosu(df: pd.DataFrame) -> pd.DataFrame:
    """Eşleme girdileri: Ri yerine 1/max(Ri, RI_TABANI) (Ri küçüldükçe artar);
    Ri <= 0 (statik kararsız) tabanda tutulur."""
    tablo = pd.DataFrame(index=df.index)
    for ad in GOSTERGELER[:-1]:
        tablo[ad] = pd.to_numeric(df[ad], errors="coerce") if ad in df else np.nan
    ri = pd.to_numeric(df["richardson_sayisi"], errors="coerce") if "richardson_sayisi" in df else np.nan
    tablo["ters_richardson"] = 1.0 / np.maximum(ri, RI_TABANI)
    tablo["dusey_ruzgar_kaymasi"] = tablo["dusey_ruzgar_kaymasi"].abs()
    return tablo


def _ln_pozitif(degerler) -> np.ndarray:
    degerler = np.asarray(degerler, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(degerler > 0, np.log(degerler), np.nan)


def klimatoloji_hesapla(df: pd.DataFrame) -> dict:
    """Her gösterge için pozitif değerlerin ln ortalaması ve standart sapması."""
    tablo = gosterge_tablosu(df)
    sonuc = {}
    for ad in GOSTERGELER:
        ln = _ln_pozitif(tablo[ad])
        ln = ln[np.isfinite(ln)]
        if len(ln) < 2 or np.std(ln) == 0:
            continue
        sonuc[ad] = {"ln_ortalama": float(np.mean(ln)), "ln_ss": float(np.std(ln, ddof=1)), "ornek": int(len(ln))}
    return sonuc


@lru_cache(maxsize=4)
def _katsayi_oku(yol, _degisim_zamani):
    with open(yol, encoding="utf-8") as dosya:
        return json.load(dosya)


def katsayilari_yukle(yol=None) -> dict | None:
    yol = yol or KATSAYI_DOSYASI
    if not os.path.exists(yol):
        return None
    return _katsayi_oku(yol, os.path.getmtime(yol))


def gosterge_edr(degerler, ln_ortalama, ln_ss, c1=C1_LN_EDR_ORTALAMA, c2=C2_LN_EDR_SS) -> np.ndarray:
    b = c2 / ln_ss
    a = c1 - b * ln_ortalama
    return np.exp(a + b * _ln_pozitif(degerler))


def birlesik_edr(df: pd.DataFrame, katsayilar: dict | None = None) -> np.ndarray:
    """Eşlenmiş göstergelerin ortalaması; gösterge pozitif değilse (ör. TI2 < 0)
    o gösterge o noktada ortalamaya katılmaz. Katsayı yoksa NaN."""
    katsayilar = katsayilar if katsayilar is not None else katsayilari_yukle()
    if not katsayilar:
        return np.full(len(df), np.nan)
    tablo = gosterge_tablosu(df)
    c1, c2 = katsayilar.get("c1", C1_LN_EDR_ORTALAMA), katsayilar.get("c2", C2_LN_EDR_SS)
    eslenen = [
        gosterge_edr(tablo[ad], k["ln_ortalama"], k["ln_ss"], c1, c2)
        for ad, k in katsayilar["gostergeler"].items()
        if ad in tablo
    ]
    if not eslenen:
        return np.full(len(df), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(np.vstack(eslenen), axis=0)


def _depo_ornekleri(gun_listesi=None, seviye_min=150.0, seviye_maks=300.0) -> pd.DataFrame:
    """Pencere deposundaki tüm ızgara hücrelerinde (yalnız PIREP noktası değil)
    seyir seviyelerinde göstergeleri hesaplar."""
    from turbulans_radar import config
    from turbulans_radar.fizik.birim_donusumleri import basinc_hpa_to_irtifa_metre
    from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
    from turbulans_radar.ml.ozellik_deposu import ozellik_kupu, pencere_dosyasini_ac, pencereden_kup

    parcalar = []
    for kok, _, adlar in os.walk(config.ML_DEPO_KLASORU):
        for ad in sorted(adlar):
            if not ad.endswith(".nc"):
                continue
            goreli = os.path.relpath(os.path.join(kok, ad), config.ML_DEPO_KLASORU)
            gun = "-".join(goreli.replace("\\", "/").split("/")[:3])
            if gun_listesi is not None and gun not in gun_listesi:
                continue
            pencereler = pencere_dosyasini_ac(goreli)
            for ornek_id in pencereler["ornek_id"].values:
                kup = ozellik_kupu(pencereden_kup(pencereler, int(ornek_id)))
                seviyeler = [s for s in kup["pressure_level"].values if seviye_min <= s <= seviye_maks]
                zaman = pd.Timestamp(kup["valid_time"].values[len(kup["valid_time"]) // 2], tz="UTC")
                seviye, enlem, boylam = (
                    d.ravel()
                    for d in np.meshgrid(seviyeler, kup["latitude"].values[1:-1], kup["longitude"].values[1:-1])
                )
                nokta = pd.DataFrame(
                    {
                        "zaman": zaman,
                        "enlem": enlem,
                        "boylam": boylam,
                        "baro_irtifa_m": basinc_hpa_to_irtifa_metre(seviye),
                    }
                )
                parcalar.append(rotayi_hava_durumuyla_eslestir(nokta, kup).assign(gun=gun))
    return pd.concat(parcalar, ignore_index=True) if parcalar else pd.DataFrame()


def ana(argv=None):
    import contextlib
    import io

    from turbulans_radar.ml.ml_otomatik_egitim import zamansal_holdout

    ayristirici = argparse.ArgumentParser(
        description="Log-normal EDR eşleme klimatolojisini pencere deposundan hesaplar."
    )
    ayristirici.add_argument("--cikti", default=KATSAYI_DOSYASI)
    argumanlar = ayristirici.parse_args(argv)
    with contextlib.redirect_stdout(io.StringIO()):
        tum = _depo_ornekleri()
    if tum.empty:
        raise SystemExit("Pencere deposunda örnek yok.")
    gunler = pd.Series(sorted(tum["gun"].unique()))
    egitim_gunleri = set(gunler[~zamansal_holdout(gunler)])
    egitim = tum[tum["gun"].isin(egitim_gunleri)]
    sonuc = {
        "kaynak": KAYNAK,
        "c1": C1_LN_EDR_ORTALAMA,
        "c2": C2_LN_EDR_SS,
        "veri": "ERA5 pencere deposu, 150–300 hPa, PIREP pencerelerindeki tüm iç ızgara hücreleri, eğitim günleri",
        "gun_sayisi": len(egitim_gunleri),
        "test_gunleri_haric": sorted(set(gunler) - egitim_gunleri),
        "gostergeler": klimatoloji_hesapla(egitim),
    }
    with open(argumanlar.cikti, "w", encoding="utf-8") as dosya:
        json.dump(sonuc, dosya, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in sonuc.items() if k != "test_gunleri_haric"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
