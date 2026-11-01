"""
sigmet_ti1_kiyasi.py
---------------------
Kayıtlı bir uçuşun TI1 noktalarını `sigmetler` tablosundaki SIGMET'lerle (AWC isigmet/airsigmet arşivi,
dünya geneli) zaman, poligon ve irtifa bandına göre ayırır; SIGMET içinde ve dışında riskli nokta oranını
verir. SIGMET gözlem değil uyarıdır; ardışık noktalar bağımsız değildir. Sonuç keşifseldir, isabet ölçüsü
değildir. Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.

Bant: None taban yer, None tavan sınırsız (rota kısıtıyla aynı). İrtifası bilinmeyen nokta yalnız bandı
tamamen açık SIGMET'in içinde sayılır. Hareket süpürmesi uygulanmaz; poligon geçerlilik süresince sabittir.

    turbulans-sigmet-ti1 --ucus THY4QR:2026-10-25 --cikti docs/sonuclar/2026-11-01_guncel_vaka
"""

import argparse
import json
import os
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import shapely

from turbulans_radar.fizik.ti1_esigi import kaynak_ti1_esigi
from turbulans_radar.rota.risk_katmanlari import sigmet_geometrisi

_FT_M = 3.28084


def _oran(pay: int, payda: int) -> float | None:
    return round(pay / payda, 4) if payda else None


def sigmet_maskesi(olcumler: pd.DataFrame, sigmet: dict) -> np.ndarray:
    zaman = pd.to_datetime(olcumler["zaman"], utc=True)
    maske = ((zaman >= sigmet["gecerlilik_baslangic"]) & (zaman <= sigmet["gecerlilik_bitis"])).to_numpy(copy=True)
    irtifa_ft = olcumler["irtifa_m"].to_numpy(dtype=float) * _FT_M
    if sigmet.get("taban_ft") is not None:
        maske &= irtifa_ft >= sigmet["taban_ft"]
    if sigmet.get("tavan_ft") is not None:
        maske &= irtifa_ft <= sigmet["tavan_ft"]
    if not maske.any():
        return maske
    geometri = sigmet_geometrisi(sigmet["poligon"])
    shapely.prepare(geometri)
    maske[maske] = shapely.contains_xy(
        geometri, olcumler["boylam"].to_numpy(dtype=float)[maske], olcumler["enlem"].to_numpy(dtype=float)[maske]
    )
    return maske


def kiyasla(olcumler: pd.DataFrame, sigmetler: list[dict], esik: float) -> dict:
    olcumler = olcumler[olcumler["ti1_indeksi"].notna()].reset_index(drop=True)
    riskli = olcumler["ti1_indeksi"].to_numpy(dtype=float) >= esik
    ici = np.zeros(len(olcumler), dtype=bool)
    satirlar = []
    for s in sigmetler:
        maske = sigmet_maskesi(olcumler, s)
        ici |= maske
        if maske.any():
            satirlar.append(
                {
                    "fir": s.get("fir_kodu"),
                    "seri": s.get("seri_no"),
                    "tehlike": s.get("tehlike"),
                    "baslangic": s["gecerlilik_baslangic"].isoformat(),
                    "bitis": s["gecerlilik_bitis"].isoformat(),
                    "taban_ft": s.get("taban_ft"),
                    "tavan_ft": s.get("tavan_ft"),
                    "nokta": int(maske.sum()),
                    "riskli": int((maske & riskli).sum()),
                    "riskli_orani": _oran(int((maske & riskli).sum()), int(maske.sum())),
                }
            )
    return {
        "ti1_nokta": len(olcumler),
        "riskli_nokta": int(riskli.sum()),
        "sigmet_ici_nokta": int(ici.sum()),
        "sigmet_ici_riskli": int((ici & riskli).sum()),
        "sigmet_ici_riskli_orani": _oran(int((ici & riskli).sum()), int(ici.sum())),
        "sigmet_disi_nokta": int((~ici).sum()),
        "sigmet_disi_riskli": int((~ici & riskli).sum()),
        "sigmet_disi_riskli_orani": _oran(int((~ici & riskli).sum()), int((~ici).sum())),
        "rota_cevresindeki_sigmet": len(sigmetler),
        "kesisen_sigmetler": satirlar,
    }


def _ucus_sigmetleri(olcumler: pd.DataFrame, tehlikeler, motor=None) -> list[dict]:
    from turbulans_radar.veri.sigmet_saglayici import gecerli_sigmetleri_getir

    zaman = pd.to_datetime(olcumler["zaman"], utc=True)
    return gecerli_sigmetleri_getir(
        zaman.min().to_pydatetime(),
        zaman.max().to_pydatetime(),
        olcumler["enlem"].min(),
        olcumler["enlem"].max(),
        olcumler["boylam"].min(),
        olcumler["boylam"].max(),
        tehlikeler=tehlikeler,
        motor=motor,
    )


def _rapor_metni(rapor: dict) -> str:
    p = rapor["parametreler"]
    satirlar = [
        "# SIGMET ↔ TI1 kıyası (keşifsel)",
        "",
        f"Üretim: {rapor['uretim_zamani']} · commit `{rapor['commit']}` · `turbulans-sigmet-ti1`",
        f"TI1 eşiği {p['ti1_esigi']:.3g} ({p['kaynak']}), tehlikeler: {', '.join(p['tehlikeler'])}.",
        "",
        "SIGMET gözlem değil uyarıdır; ardışık noktalar bağımsız değildir; oranlar isabet ölçüsü değildir.",
        "Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.",
        "",
        "| Uçuş | TI1 nokta | SIGMET içi | İçeride riskli | Dışarıda riskli | Rota çevresindeki SIGMET |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for u in rapor["ucuslar"]:
        satirlar.append(
            f"| {u['ucus']} {u['tarih']} | {u['ti1_nokta']} | {u['sigmet_ici_nokta']} | "
            f"{_yuzde(u['sigmet_ici_riskli_orani'])} | {_yuzde(u['sigmet_disi_riskli_orani'])} | "
            f"{u['rota_cevresindeki_sigmet']} |"
        )
    for u in rapor["ucuslar"]:
        if not u["kesisen_sigmetler"]:
            continue
        satirlar += [
            "",
            f"## {u['ucus']} — kesişen SIGMET'ler",
            "",
            "| FIR | Seri | Bant (ft) | Geçerlilik | Nokta | Riskli |",
        ]
        satirlar.append("|---|---|---|---|---:|---:|")
        for s in u["kesisen_sigmetler"]:
            taban = "yer" if s["taban_ft"] is None else s["taban_ft"]
            bant = f"{taban}–{'sınırsız' if s['tavan_ft'] is None else s['tavan_ft']}"
            satirlar.append(
                f"| {s['fir']} | {s['seri']} | {bant} | {s['baslangic'][11:16]}–{s['bitis'][11:16]} | "
                f"{s['nokta']} | {_yuzde(s['riskli_orani'])} |"
            )
    return "\n".join(satirlar) + "\n"


def _yuzde(oran: float | None) -> str:
    return "—" if oran is None else f"%{oran * 100:.1f}".replace(".", ",")


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="Kayıtlı uçuşların TI1 noktalarını arşivdeki SIGMET'lerle kıyaslar.")
    ayrac.add_argument("--ucus", action="append", required=True, help="UCUS:YYYY-AA-GG (tekrarlanabilir)")
    ayrac.add_argument("--tehlike", action="append", default=None, help="Varsayılan TURB")
    ayrac.add_argument("--kaynak", choices=("era5", "gfs"), default="era5", help="TI1 eşiğinin hava kaynağı")
    ayrac.add_argument("--cikti", required=True, help="Rapor klasörü")
    arg = ayrac.parse_args(argv)
    from turbulans_radar.depo.veritabani import ucus_olcumlerini_dataframe_olarak_getir
    from turbulans_radar.uretim_bilgisi import yazilim_commit

    tehlikeler = [t.upper() for t in (arg.tehlike or ["TURB"])]
    esik = kaynak_ti1_esigi(arg.kaynak)
    ucuslar = []
    for ucus_tarih in arg.ucus:
        ucus, _, tarih = ucus_tarih.partition(":")
        olcumler = ucus_olcumlerini_dataframe_olarak_getir(ucus, tarih)
        if olcumler is None or olcumler.empty:
            raise SystemExit(f"{ucus} / {tarih} veritabanında yok.")
        ucuslar.append(
            {"ucus": ucus, "tarih": tarih, **kiyasla(olcumler, _ucus_sigmetleri(olcumler, tehlikeler), esik)}
        )
    rapor = {
        "parametreler": {"ti1_esigi": esik, "kaynak": arg.kaynak, "tehlikeler": tehlikeler},
        "commit": yazilim_commit(),
        "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
        "ucuslar": ucuslar,
    }
    os.makedirs(arg.cikti, exist_ok=True)
    with open(os.path.join(arg.cikti, "sigmet_ti1.json"), "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)
    with open(os.path.join(arg.cikti, "SIGMET_TI1.md"), "w", encoding="utf-8") as f:
        f.write(_rapor_metni(rapor))
    print(os.path.join(arg.cikti, "SIGMET_TI1.md"))


if __name__ == "__main__":
    ana()
