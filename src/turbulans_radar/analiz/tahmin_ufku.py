"""
tahmin_ufku.py
----------------
Kurul raporu #11: GFS'in TI1 alanı tahmin ufku uzadıkça ne kadar tutarlı? Her geçerlilik
zamanı V için V koşusunun analizi (f000), V-24 koşusunun f024'ü ve V-48 koşusunun f048'i
aynı rastgele noktalarda TI1'e çevrilir; f024 ve f048, f000'a göre sıra uyumu (Spearman) ve
risk eşiğinde aynı karar oranıyla ölçülür. Referans GFS'in kendi analizidir, gözlem değildir;
ERA5 kıyası ERA5'in ~5 günlük yayın gecikmesi yüzünden ayrıca yapılır.

UCAR THREDDS geçmiş ~7,5 günün koşularını tutar; indirme bu pencerede çalışır:

    turbulans-tahmin-ufku --indir --baslangic 2026-10-23T00 --bitis 2026-10-28T00
    turbulans-tahmin-ufku --baslangic 2026-10-23T00 --bitis 2026-10-28T00 --cikti docs/sonuclar/<tarih>_tahmin_ufku

Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import contextlib
import io
import json
import os
import time
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.analiz.zaman_ornekleme import karsilastir, rastgele_noktalar
from turbulans_radar.veri.veri_saglayicilari import GfsThreddsSaglayici, Kutu, _canli_istegi_hizala, gfs_kosu_url

KUTU = Kutu(31.0, 46.0, 20.0, 51.0)
UFUKLAR_SAAT = (0, 24, 48)
ADIM_SAAT = 12
NOKTA_SAYISI = 5000
BEKLEME_SANIYE = 2.0


def _utc(zaman) -> pd.Timestamp:
    ts = pd.Timestamp(zaman)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def gecerlilik_zamanlari(baslangic, bitis, adim_saat=ADIM_SAAT) -> list[pd.Timestamp]:
    return list(pd.date_range(_utc(baslangic), _utc(bitis), freq=f"{adim_saat}h"))


def gerekli_dosyalar(zamanlar, ufuklar=UFUKLAR_SAAT) -> list[tuple[pd.Timestamp, int]]:
    """(koşu, ufuk) çiftleri: her V için V-ufuk koşusunun ufuk saatlik tahmini."""
    return sorted({(v - pd.Timedelta(hours=u), u) for v in zamanlar for u in ufuklar})


def dosya_yolu(klasor, kosu, ufuk) -> str:
    return os.path.join(klasor, f"gfs_{kosu:%Y%m%d%H}_f{ufuk:03d}.nc")


def indir(klasor, zamanlar, saglayici_fabrikasi=GfsThreddsSaglayici, bekle=time.sleep, kutu=KUTU) -> dict:
    os.makedirs(klasor, exist_ok=True)
    ozet: dict[str, list] = {"indirilen": [], "var_olan": [], "hata": []}
    for kosu, ufuk in gerekli_dosyalar(zamanlar):
        yol = dosya_yolu(klasor, kosu, ufuk)
        if os.path.exists(yol):
            ozet["var_olan"].append(os.path.basename(yol))
            continue
        gecerlilik = kosu + pd.Timedelta(hours=ufuk)
        saglayici = saglayici_fabrikasi(url=gfs_kosu_url(kosu))
        hizali, _, _ = _canli_istegi_hizala(kutu, gecerlilik, gecerlilik, saglayici)
        try:
            saglayici.kup_indir(hizali, gecerlilik, gecerlilik, yol)
            ozet["indirilen"].append(os.path.basename(yol))
        except Exception as hata:
            ozet["hata"].append({"dosya": os.path.basename(yol), "hata": f"{type(hata).__name__}: {hata}"[:200]})
        bekle(BEKLEME_SANIYE)
    return ozet


def _ti1(kup, noktalar) -> np.ndarray:
    from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir

    with contextlib.redirect_stdout(io.StringIO()):
        return rotayi_hava_durumuyla_eslestir(noktalar, kup)["ti1_indeksi"].to_numpy(dtype=float)


def _alan_adi(alan: str) -> str:
    return alan.replace("saatlik", "f000").replace("seyrekte", "tahminde").replace("seyrek", "tahmin")


def olcum_yap(klasor, zamanlar, nokta_sayisi=NOKTA_SAYISI, esik=None) -> dict:
    from turbulans_radar.fizik.ti1_esigi import kaynak_ti1_esigi

    esik = kaynak_ti1_esigi("gfs") if esik is None else esik
    kayitlar, eksik = [], []
    for i, v in enumerate(zamanlar):
        yollar = {u: dosya_yolu(klasor, v - pd.Timedelta(hours=u), u) for u in UFUKLAR_SAAT}
        if not all(os.path.exists(y) for y in yollar.values()):
            eksik.append(v.isoformat())
            continue
        kupler = {u: xr.load_dataset(y) for u, y in yollar.items()}
        noktalar = rastgele_noktalar(kupler[0], nokta_sayisi, tohum=i).assign(zaman=v.tz_convert(None))
        ti1 = {u: _ti1(k, noktalar) for u, k in kupler.items()}
        for u in UFUKLAR_SAAT[1:]:
            olcu = {_alan_adi(k): d for k, d in karsilastir(ti1[0], ti1[u], esik).items()}
            kayitlar.append({"gecerlilik": v.isoformat(), "ufuk_saat": u, **olcu})
    return {"esik": esik, "kayitlar": kayitlar, "eksik_gecerlilik": eksik, "ozet": ozetle(kayitlar)}


def ozetle(kayitlar) -> dict:
    ozet = {}
    for u in sorted({k["ufuk_saat"] for k in kayitlar}):
        grup = [k for k in kayitlar if k["ufuk_saat"] == u]

        def _medyan(alan, grup=grup):
            degerler = [k[alan] for k in grup if k[alan] is not None]
            return float(np.median(degerler)) if degerler else None

        ozet[f"f{u:03d}"] = {
            "gecerlilik_sayisi": len(grup),
            **{
                f"{alan}_medyan": _medyan(alan)
                for alan in (
                    "spearman",
                    "ayni_karar_orani",
                    "f000_riskli_orani",
                    "tahmin_riskli_orani",
                    "f000_riskli_tahminde_de_riskli",
                    "tahmin_riskli_f000te_de_riskli",
                )
            },
            "spearman_aralik": [min(k["spearman"] for k in grup), max(k["spearman"] for k in grup)],
        }
    return ozet


def _sayi(x, bicim="{:.3f}"):
    return "—" if x is None else bicim.format(x)


def markdown_ozeti(rapor) -> str:
    p = rapor["parametreler"]
    satirlar = [
        "# GFS tahmin ufku tutarlılığı (TI1)",
        "",
        f"Üretim: {rapor['uretim_zamani']} · commit `{rapor['commit'] or '—'}` · geçerlilik {p['baslangic']} – "
        f"{p['bitis']} (her {p['adim_saat']} sa) · kutu {p['kutu']} · {p['seviyeler_hpa']} hPa · her geçerlilikte "
        f"{p['nokta_sayisi']} rastgele nokta (FL310–380) · TI1 risk eşiği {rapor['esik']:.1e}.",
        "",
        'Referans f000 (aynı geçerlilik zamanındaki koşunun analizi). "Riskli" = TI1 > eşik.',
        "",
        "| Ufuk | Geçerlilik | Spearman medyanı [en az–en çok] | Aynı karar medyanı | f000 riskli oranı | Tahmin riskli "
        "oranı | f000'da riskli olanın tahminde de riskli olma oranı | Tahminde riskli olanın f000'da da riskli olma "
        "oranı |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for ad, o in rapor["ozet"].items():
        satirlar.append(
            f"| {ad} | {o['gecerlilik_sayisi']} | {_sayi(o['spearman_medyan'])} [{_sayi(o['spearman_aralik'][0])}–"
            f"{_sayi(o['spearman_aralik'][1])}] | {_sayi(o['ayni_karar_orani_medyan'])} | "
            f"{_sayi(o['f000_riskli_orani_medyan'])} | {_sayi(o['tahmin_riskli_orani_medyan'])} | "
            f"{_sayi(o['f000_riskli_tahminde_de_riskli_medyan'])} | "
            f"{_sayi(o['tahmin_riskli_f000te_de_riskli_medyan'])} |"
        )
    satirlar += [
        "",
        f"Eksik geçerlilik (dosyası olmayan): {len(rapor['eksik_gecerlilik'])}.",
        "",
        "**Okuma.** Ölçü GFS'in kendi kendisiyle tutarlılığıdır: f024/f048'in f000'a benzemesi doğruluk değil, "
        "öngörülebilirliktir; f000 de bir tahmindir ve gözlem değildir. Geçerlilik zamanları aynı hava sistemlerini "
        "paylaşır, bağımsız örnek değildir; değerler betimleyicidir. Tek bölge (Türkiye kutusu), tek mevsim, 3 basınç "
        "seviyesi. Ürünün 48 saatlik `ongoru_belirsiz` sınırı literatürden (Lee, 2025) alınmıştır; bu tablo o sınırı "
        "kalibre etmez, yalnız bu dönemde TI1'in yerinin ufukla ne kadar değiştiğini gösterir.",
        "",
        "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
    ]
    return "\n".join(satirlar) + "\n"


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="GFS tahmin ufku tutarlılığı (f000/f024/f048, TI1).")
    ayrac.add_argument("--baslangic", required=True, help="İlk geçerlilik zamanı (UTC), örn. 2026-10-23T00")
    ayrac.add_argument("--bitis", required=True, help="Son geçerlilik zamanı (UTC)")
    ayrac.add_argument("--adim-saat", type=int, default=ADIM_SAAT)
    ayrac.add_argument("--klasor", default=os.path.join(config.CIKTI_KLASORU, "tahmin_ufku"))
    ayrac.add_argument("--indir", action="store_true", help="Eksik GFS dosyalarını UCAR THREDDS'ten indir")
    ayrac.add_argument("--cikti", help="Rapor klasörü")
    ayrac.add_argument("--nokta", type=int, default=NOKTA_SAYISI)
    arg = ayrac.parse_args(argv)
    zamanlar = gecerlilik_zamanlari(arg.baslangic, arg.bitis, arg.adim_saat)
    if arg.indir:
        print(json.dumps(indir(arg.klasor, zamanlar), ensure_ascii=False, indent=2))
    if not arg.cikti:
        return 0
    from turbulans_radar.uretim_bilgisi import yazilim_commit

    rapor = {
        "parametreler": {
            "baslangic": zamanlar[0].isoformat(),
            "bitis": zamanlar[-1].isoformat(),
            "adim_saat": arg.adim_saat,
            "kutu": [KUTU.enlem_min, KUTU.enlem_maks, KUTU.boylam_min, KUTU.boylam_maks],
            "seviyeler_hpa": list(config.CANLI_BASINC_SEVIYELERI_HPA),
            "nokta_sayisi": arg.nokta,
            "ufuklar_saat": list(UFUKLAR_SAAT),
        },
        "commit": yazilim_commit(),
        "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
        **olcum_yap(arg.klasor, zamanlar, arg.nokta),
    }
    os.makedirs(arg.cikti, exist_ok=True)
    with open(os.path.join(arg.cikti, "tahmin_ufku.json"), "w", encoding="utf-8", newline="") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2)
    with open(os.path.join(arg.cikti, "README.md"), "w", encoding="utf-8", newline="") as dosya:
        dosya.write(markdown_ozeti(rapor))
    print(markdown_ozeti(rapor))
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
