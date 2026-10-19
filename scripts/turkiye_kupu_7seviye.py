"""Komite B-3: Ocak 2019 Türkiye küpünü eğitimdeki 7 seviyeyle indirir ve 3 seviyeli küple karşılaştırır.

İndirme (worker konteynerinde, CDS kimliği orada; varsayılan kuru deneme):
  docker compose exec -T worker python - indir [--gercekten-indir] < scripts/turkiye_kupu_7seviye.py
Karşılaştırma (WSL venv, depo kökünde; dış istek yok):
  ~/.venvs/turbulans/bin/python scripts/turkiye_kupu_7seviye.py karsilastir
"""

import argparse
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config

KUTU = (36.0, 42.0, 26.0, 45.0)
BASLANGIC, BITIS = "2019-01-01T00:00Z", "2019-01-31T23:00Z"
SEVIYELER_HPA = (350.0, 300.0, 250.0, 225.0, 200.0, 175.0, 150.0)
TAHMINI_MB = 130.0
KONTEYNER_CIKTI = "/app/ciktilar/ocak_2019_turbulans_7seviye.nc"
YENI_KUP = "ocak_2019_turbulans_7seviye.nc"
ESKI_KUP = "ocak_2019_turbulans.nc"
RAPOR_KLASORU = "docs/sonuclar/2026-10-20_turkiye_7seviye"


def indir(gercekten: bool) -> None:
    from turbulans_radar.depo import veri_butcesi
    from turbulans_radar.veri.era5_saglayici import CdsEra5Saglayici, cds_istekleri_olustur
    from turbulans_radar.veri.veri_saglayicilari import Kutu

    kutu = Kutu(*KUTU)
    istekler = cds_istekleri_olustur(kutu, BASLANGIC, BITIS, SEVIYELER_HPA)
    alan = sum(len(i["variable"]) * len(i["pressure_level"]) * len(i["time"]) for i in istekler)
    kullanilan = veri_butcesi.kullanilan_mb() if veri_butcesi.etkin_mi() else 0.0
    print(
        f"{len(istekler)} CDS isteği, {alan} alan, tahmini ≤{TAHMINI_MB:.0f} MB; bugün kullanılan {kullanilan:.1f} MB"
    )
    if not gercekten:
        print("Kuru deneme: istek gönderilmedi. Gerçek indirme için --gercekten-indir.")
        return
    if veri_butcesi.etkin_mi() and not veri_butcesi.yer_var_mi(TAHMINI_MB):
        sys.exit(f"Günlük veri bütçesi ({config.GUNLUK_VERI_BUTCESI_MB} MB) yetmiyor; indirilmedi.")
    saglayici = CdsEra5Saglayici(basinc_seviyeleri_hpa=SEVIYELER_HPA, bayt_sayaci=veri_butcesi.indirileni_say)
    saglayici.kup_indir(kutu, BASLANGIC, BITIS, KONTEYNER_CIKTI)
    print(f"Yazıldı: {KONTEYNER_CIKTI} ({os.path.getsize(KONTEYNER_CIKTI) / 1e6:.1f} MB)")


def karsilastir(adim_derece: float, saat_adimi: int, tekrar: int) -> dict:
    from turbulans_radar.analiz.esik_esleme import esleme_raporu, izgara_noktalari, ti1_orneklemi

    if not os.path.exists(YENI_KUP) and os.path.exists(os.path.join("ciktilar", YENI_KUP)):
        shutil.move(os.path.join("ciktilar", YENI_KUP), YENI_KUP)
    yeni = xr.load_dataset(YENI_KUP)
    eski = xr.load_dataset(ESKI_KUP)
    zamanlar = pd.date_range(BASLANGIC, BITIS, freq=f"{saat_adimi}h")
    noktalar = izgara_noktalari(KUTU, adim_derece, zamanlar, (300, 320, 340, 360, 380))
    ti1_yedi = ti1_orneklemi(yeni, noktalar)
    ti1_uc = ti1_orneklemi(eski, noktalar)
    rapor = esleme_raporu(noktalar, ti1_yedi, ti1_uc, config.TI1_ESIK_ORTA_SIDDETLI, tekrar=tekrar)
    rapor["ayarlar"] = {
        "kutu": list(KUTU),
        "adim_derece": adim_derece,
        "saat_adimi": saat_adimi,
        "referans": f"{YENI_KUP} ({', '.join(str(int(s)) for s in SEVIYELER_HPA)} hPa)",
        "karsilastirilan": f"{ESKI_KUP} ({', '.join(str(int(s)) for s in eski['pressure_level'].values)} hPa)",
        "esik": config.TI1_ESIK_ORTA_SIDDETLI,
    }
    rapor.pop("zamanlar", None)
    return rapor


def _bilimsel(x):
    return "—" if x is None else f"{x:.2e}"


def _bilimsiz(x):
    return "—" if x is None else f"{x:.2f}"


def _ozet(rapor: dict) -> str:
    g = rapor["genel"]
    ga = g.get("gfs_esdeger_esik_ga95") or [None, None]

    def yuzde(x):
        return "—" if x is None else f"%{100 * x:.1f}"

    satirlar = [
        "# Türkiye küpü: 3 seviye ↔ 7 seviye TI1 (komite B-3)",
        "",
        f"Referans {rapor['ayarlar']['referans']}; karşılaştırılan {rapor['ayarlar']['karsilastirilan']}. "
        f"Kutu {rapor['ayarlar']['kutu']}, {rapor['ayarlar']['adim_derece']}° adım, "
        f"{rapor['ayarlar']['saat_adimi']} saatte bir, FL300–380, {rapor['zaman_sayisi']} saat.",
        "",
        "| Ölçü | Değer |",
        "|---|---|",
        f"| Nokta | {g['n']} |",
        f"| Riskli oranı, 7 seviye (≥ {rapor['ayarlar']['esik']:.0e}) | {yuzde(g.get('era5_riskli_orani'))} |",
        f"| Riskli oranı, 3 seviye (aynı eşik) | {yuzde(g.get('gfs_riskli_orani_ayni_esikte'))} |",
        f"| 3 seviyede eşdeğer eşik | {_bilimsel(g.get('gfs_esdeger_esik'))} |",
        f"| Eşdeğer eşik %95 GA (saat bootstrap) | {_bilimsel(ga[0])} – {_bilimsel(ga[1])} |",
        f"| Spearman (sıra uyumu) | {_bilimsiz(g.get('spearman'))} |",
        "",
        "| FL | 7 seviye riskli | 3 seviye riskli | Eşdeğer eşik |",
        "|---|---|---|---|",
    ]
    for fl, s in rapor["seviyeler"].items():
        satirlar.append(
            f"| {fl} | {yuzde(s.get('era5_riskli_orani'))} | {yuzde(s.get('gfs_riskli_orani_ayni_esikte'))} "
            f"| {_bilimsel(s.get('gfs_esdeger_esik'))} |"
        )
    satirlar += [
        "",
        "Yalnız veri düzeni farkını ölçer (aynı ERA5, farklı katman kalınlığı); Türkiye'de beceri ölçümü değildir (B-4).",
    ]
    return "\n".join(satirlar) + "\n"


def main(argv=None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    alt = ayristirici.add_subparsers(dest="komut", required=True)
    i = alt.add_parser("indir")
    i.add_argument("--gercekten-indir", action="store_true")
    k = alt.add_parser("karsilastir")
    k.add_argument("--adim-derece", type=float, default=0.25)
    k.add_argument("--saat-adimi", type=int, default=3)
    k.add_argument("--tekrar", type=int, default=500)
    a = ayristirici.parse_args(argv)
    if a.komut == "indir":
        indir(a.gercekten_indir)
        return
    rapor = karsilastir(a.adim_derece, a.saat_adimi, a.tekrar)
    os.makedirs(RAPOR_KLASORU, exist_ok=True)
    with open(os.path.join(RAPOR_KLASORU, "kup_karsilastirmasi.json"), "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2, default=lambda x: float(x) if np.isscalar(x) else str(x))
    with open(os.path.join(RAPOR_KLASORU, "README.md"), "w", encoding="utf-8") as f:
        f.write(_ozet(rapor))
    print(_ozet(rapor))


if __name__ == "__main__":
    main()
