"""
zaman_ornekleme.py
-------------------
Kurul raporu #24 / ATM-04: hava verisi zamanda en yakın adımdan okunur, enterpolasyon
yapılmaz. Canlı GFS'in 3 saatlik adımı noktayı 1,5 saate kadar kaydırır. Bu araç saatlik
ERA5 küpünde aynı rastgele noktaların TI1'ini saatlik küple ve küpün her 3. saatiyle
(GFS adımı) hesaplayıp farkı ölçer: sıra uyumu (Spearman) ve risk eşiğinde aynı karar
oranı. Yalnız zaman örneklemesinin etkisidir; GFS'in tahmin hatasını içermez.
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import contextlib
import io
import json
import os
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from turbulans_radar import config

VARSAYILAN_NOKTA = 20000
VARSAYILAN_FL = (310, 380)


def rastgele_noktalar(veri_kupu, nokta_sayisi=VARSAYILAN_NOKTA, fl_araligi=VARSAYILAN_FL, tohum=0) -> pd.DataFrame:
    """Küpün iç bölgesinde (kenardan 0,5° içeride), zaman ekseninde sürekli, seviyeleri çevreleyen FL bandında."""
    rng = np.random.default_rng(tohum)
    enlem, boylam = veri_kupu["latitude"].values, veri_kupu["longitude"].values
    zamanlar = pd.DatetimeIndex(veri_kupu["valid_time"].values)
    bas, son = zamanlar[0].value, zamanlar[-1].value
    return pd.DataFrame(
        {
            "zaman": pd.to_datetime(rng.uniform(float(bas), float(son), nokta_sayisi).astype("int64")),
            "enlem": rng.uniform(enlem.min() + 0.5, enlem.max() - 0.5, nokta_sayisi),
            "boylam": rng.uniform(boylam.min() + 0.5, boylam.max() - 0.5, nokta_sayisi),
            "baro_irtifa_m": rng.uniform(fl_araligi[0], fl_araligi[1], nokta_sayisi) * 100 * 0.3048,
        }
    )


def karsilastir(saatlik, seyrek, esik, seyrek_esik=None) -> dict:
    gecerli = np.isfinite(saatlik) & np.isfinite(seyrek)
    a, b = saatlik[gecerli], seyrek[gecerli]
    riskli_a, riskli_b = a > esik, b > (esik if seyrek_esik is None else seyrek_esik)
    return {
        "nokta": int(gecerli.sum()),
        "spearman": float(pd.Series(a).corr(pd.Series(b), method="spearman")),
        "ayni_karar_orani": float(np.mean(riskli_a == riskli_b)),
        "saatlik_riskli_orani": float(riskli_a.mean()),
        "seyrek_riskli_orani": float(riskli_b.mean()),
        "saatlik_riskli_seyrekte_de_riskli": float(riskli_b[riskli_a].mean()) if riskli_a.any() else None,
        "seyrek_riskli_saatlikte_de_riskli": float(riskli_a[riskli_b].mean()) if riskli_b.any() else None,
        "medyan_mutlak_log10_fark": float(
            np.median(np.abs(np.log10(a[(a > 0) & (b > 0)]) - np.log10(b[(a > 0) & (b > 0)])))
        ),
    }


def olcum_yap(veri_kupu, noktalar, adimlar=(3, 6), esik=None) -> dict:
    from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
    from turbulans_radar.fizik.ti1_esigi import etkin_ti1_esigi

    esik = etkin_ti1_esigi() if esik is None else esik

    def _ti1(kup):
        with contextlib.redirect_stdout(io.StringIO()):
            return rotayi_hava_durumuyla_eslestir(noktalar, kup)["ti1_indeksi"].to_numpy(dtype=float)

    saatlik = _ti1(veri_kupu)
    return {
        "esik": esik,
        "adimlar": {
            f"{adim}_saat": karsilastir(saatlik, _ti1(veri_kupu.isel(valid_time=slice(None, None, adim))), esik)
            for adim in adimlar
        },
    }


def markdown_ozeti(rapor) -> str:
    satirlar = [
        "# Zaman örneklemesinin TI1'e etkisi (ATM-04)",
        "",
        f"Üretim: {rapor['uretim_zamani']} · commit `{rapor['commit'] or '—'}` · küp `{rapor['kup']}` (saatlik) · "
        f"{rapor['nokta_sayisi']} rastgele nokta (iç bölge, FL{rapor['fl'][0]}–{rapor['fl'][1]}, zamanda sürekli) · "
        f"risk eşiği {rapor['esik']:.1e}. Referans: saatlik küp (en yakın saat, ≤ 30 dk kayma). Karşılaştırılan: "
        "küpün her N. saati (en yakın adım, ≤ N/2 sa kayma). Yalnız zaman örneklemesinin etkisidir; GFS'in tahmin "
        "hatasını ve 0,25°'lik uzay örneklemesini içermez.",
        "",
        "| Adım | Nokta | Spearman | Risk eşiğinde aynı karar | Riskli oranı (saatlik / seyrek) | Saatlikte riskli olanın seyrekte de riskli oranı | Medyan |log10 fark| |",
        "|---|---|---|---|---|---|---|",
    ]
    for ad, o in rapor["adimlar"].items():
        satirlar.append(
            f"| {ad.replace('_saat', ' sa')} | {o['nokta']} | {o['spearman']:.3f} | %{100 * o['ayni_karar_orani']:.1f} | "
            f"%{100 * o['saatlik_riskli_orani']:.1f} / %{100 * o['seyrek_riskli_orani']:.1f} | "
            f"%{100 * o['saatlik_riskli_seyrekte_de_riskli']:.1f} | {o['medyan_mutlak_log10_fark']:.3f} |"
        )
    satirlar += ["", "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır."]
    return "\n".join(satirlar) + "\n"


def ana(argv=None):
    ayrac = argparse.ArgumentParser(
        description="Zaman örneklemesinin (1 / 3 / 6 sa) TI1'e etkisi, saatlik ERA5 küpünde."
    )
    ayrac.add_argument("--kup", default=config.HAVA_DURUMU_DOSYASI)
    ayrac.add_argument("--nokta", type=int, default=VARSAYILAN_NOKTA)
    ayrac.add_argument("--cikti", required=True)
    arg = ayrac.parse_args(argv)
    import xarray as xr

    from turbulans_radar.uretim_bilgisi import yazilim_commit

    with xr.open_dataset(arg.kup) as kup:
        kup = kup.load()
    noktalar = rastgele_noktalar(kup, arg.nokta)
    rapor = {
        "kup": os.path.basename(arg.kup),
        "nokta_sayisi": arg.nokta,
        "fl": list(VARSAYILAN_FL),
        "commit": yazilim_commit(),
        "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
        **olcum_yap(kup, noktalar),
    }
    os.makedirs(arg.cikti, exist_ok=True)
    with open(os.path.join(arg.cikti, "zaman_ornekleme.json"), "w", encoding="utf-8") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2)
    with open(os.path.join(arg.cikti, "README.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    print(markdown_ozeti(rapor))
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
