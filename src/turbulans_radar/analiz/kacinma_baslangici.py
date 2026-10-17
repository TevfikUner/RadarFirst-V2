import argparse
import json
import os
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.fizik.ti1_esigi import ayri_esik_baglaminda, kaynaga_gore_ayarla
from turbulans_radar.loglama import logger_al
from turbulans_radar.rota import performans_modeli
from turbulans_radar.rota import rota_optimizasyonu as ro
from turbulans_radar.rota.risk_katmanlari import rota_eslesmesi
from turbulans_radar.veri.veri_saglayicilari import GfsThreddsSaglayici, Kutu, _canli_istegi_hizala, gfs_kosu_url

_logger = logger_al(__name__)

ROTALAR = {
    "LTFM-LTAI": (41.26, 28.74, 36.90, 30.80),
    "LTFM-LTCI": (41.26, 28.74, 38.47, 43.33),
    "LTBJ-LTCE": (38.29, 27.16, 39.96, 41.17),
    "LTAI-LTCG": (36.90, 30.80, 41.00, 39.78),
    "LTAJ-LTFM": (36.95, 37.48, 41.26, 28.74),
}
KALKISLAR = ("2026-10-12T10:00:00Z", "2026-10-14T16:00:00Z", "2026-10-16T04:00:00Z")
KUTU = Kutu(31.0, 46.0, 20.0, 51.0)
IRTIFA_FT = 35000
UCAK = "A320"
PLAN_ONCESI_SAAT = 6
KUP_PENCERESI_SAAT = 4

UYARI = (
    "Gösterim amaçlı küçük deney; istatistiksel genelleme yapılmaz. Referans gerçek analiz değil, yeniden planlama "
    "anında başlamış en son GFS koşusunun kısa öngörülü tahminidir; R1'in koşusu referansa zamanca daha yakın "
    "olduğu için sonuç R1 lehine yanlı olabilir (bu günlerde gözlemle doğrulama yok). SIGMET ve kısıtlı sahalar yok sayıldı; yalnız "
    "seyir bölümü. Karar destek amaçlıdır, sertifikalı EDR değildir."
)


def _utc(zaman) -> pd.Timestamp:
    ts = pd.Timestamp(zaman)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def elde_olan_kosu(an, gecikme_saat=None) -> pd.Timestamp:
    gecikme_saat = config.GFS_KOSU_GECIKMESI_SAAT if gecikme_saat is None else gecikme_saat
    return (_utc(an) - pd.Timedelta(hours=gecikme_saat)).floor("6h")


def referans_kosusu(yeniden_planlama, r1_kosusu) -> pd.Timestamp:
    kosu = _utc(yeniden_planlama).floor("6h")
    return kosu if kosu != r1_kosusu else kosu + pd.Timedelta(hours=6)


def kosu_kupu(kosu, baslangic, bitis, klasor, saglayici_fabrikasi=GfsThreddsSaglayici, kutu=KUTU):
    os.makedirs(klasor, exist_ok=True)
    kosu, baslangic, bitis = _utc(kosu), _utc(baslangic), _utc(bitis)
    yol = os.path.join(klasor, f"kosu_{kosu:%Y%m%d%H}_{baslangic:%Y%m%d%H}_{bitis:%Y%m%d%H}.nc")
    if not os.path.exists(yol):
        saglayici = saglayici_fabrikasi(url=gfs_kosu_url(kosu))
        hizali, bas, bit = _canli_istegi_hizala(kutu, baslangic, bitis, saglayici)
        saglayici.kup_indir(hizali, max(bas, kosu), bit, yol)
    return xr.load_dataset(yol)


@ayri_esik_baglaminda
def yol_degerlendir(enlemler, boylamlar, irtifa_m, baslangic, veri_kupu, ucak=UCAK) -> dict:
    esik = kaynaga_gore_ayarla("gfs")
    tas_ms = ro.UCAK_PROFILLERI[ucak]["tas_ms"]
    saniye, zamanlar = ro._rotayi_zamanla(enlemler, boylamlar, irtifa_m, _utc(baslangic), tas_ms, veri_kupu, True)
    eslesme = rota_eslesmesi(enlemler, boylamlar, irtifa_m, zamanlar, veri_kupu)
    ti1 = eslesme["ti1_indeksi"].to_numpy(dtype=float)
    aday = {
        "enlem": list(enlemler),
        "boylam": list(boylamlar),
        "irtifa_m": irtifa_m,
        "zamanlar": zamanlar,
        "ti1": ti1,
        "birlesik_edr": eslesme["birlesik_edr"].to_numpy(dtype=float) if "birlesik_edr" in eslesme else None,
    }
    bolumler = ro.riskli_bolumler(aday)
    seyir = performans_modeli.seyir_yakiti(ucak, saniye, tas_ms, irtifa_m)
    return {
        "sure_dk": saniye / 60.0,
        "riskli_sure_dk": None if bolumler is None else float(sum(b["sure_dk"] for b in bolumler)),
        "maks_ti1": float(np.nanmax(ti1)) if np.isfinite(ti1).any() else None,
        "kapsam_disi_nokta": int(np.isnan(ti1).sum()),
        "yakit_kg": None if seyir is None else float(seyir["yakit_kg"]),
        "esik": esik,
    }


def _noktalardan(noktalar):
    return [n["enlem"] for n in noktalar], [n["boylam"] for n in noktalar], float(noktalar[0]["irtifa_m"])


def ara_nokta_indeksi(noktalar) -> int:
    zamanlar = [_utc(n["zaman"]) for n in noktalar]
    yari = zamanlar[0] + (zamanlar[-1] - zamanlar[0]) / 2
    indeks = next(i for i, z in enumerate(zamanlar) if z >= yari)
    return min(max(indeks, 1), len(noktalar) - 2)


def seviye_degisimi_ek_maliyeti(ozet, ayni_kupte_yol) -> dict:
    return {
        "sure_dk": ozet["toplam_sure_dk"] - ayni_kupte_yol["sure_dk"],
        "yakit_kg": _fark(ozet.get("tahmini_yakit_kg"), ayni_kupte_yol["yakit_kg"]),
    }


def _fark(a, b):
    return None if a is None or b is None else a - b


def vaka_calistir(rota_adi, kalkis, klasor, rota_fonksiyonu=None, kup_fonksiyonu=None) -> dict:
    rota_fonksiyonu = rota_fonksiyonu or ro.rota_simulasyonu_olustur
    kup_fonksiyonu = kup_fonksiyonu or (lambda kosu, bas, bit: kosu_kupu(kosu, bas, bit, klasor))
    bas_enlem, bas_boylam, bit_enlem, bit_boylam = ROTALAR[rota_adi]
    kalkis = _utc(kalkis)
    pencere = (kalkis, kalkis + pd.Timedelta(hours=KUP_PENCERESI_SAAT))

    r0_kosusu = elde_olan_kosu(kalkis - pd.Timedelta(hours=PLAN_ONCESI_SAAT))
    r0_kupu = kup_fonksiyonu(r0_kosusu, *pencere)
    r0 = rota_fonksiyonu(
        bas_enlem,
        bas_boylam,
        bit_enlem,
        bit_boylam,
        IRTIFA_FT,
        f"{kalkis:%Y-%m-%dT%H:%M:%S}",
        UCAK,
        sigmetler=[],
        kisitli_sahalar=[],
        veri_kupu=r0_kupu,
    )
    plan = r0["optimize_rota"]["noktalar"]
    k = ara_nokta_indeksi(plan)
    yeniden = _utc(plan[k]["zaman"])
    r0_kalan = plan[k:]

    r1_kosusu = elde_olan_kosu(yeniden)
    r1_kupu = kup_fonksiyonu(r1_kosusu, *pencere)
    r1 = rota_fonksiyonu(
        plan[k]["enlem"],
        plan[k]["boylam"],
        bit_enlem,
        bit_boylam,
        int(plan[k]["fl"]) * 100,
        f"{yeniden:%Y-%m-%dT%H:%M:%S}",
        UCAK,
        sigmetler=[],
        kisitli_sahalar=[],
        veri_kupu=r1_kupu,
    )

    ref_kosusu = referans_kosusu(yeniden, r1_kosusu)
    ref_kupu = kup_fonksiyonu(ref_kosusu, *pencere)
    r1_yolu = _noktalardan(r1["optimize_rota"]["noktalar"])
    degerlendirme = {
        "r0_kalan": yol_degerlendir(*_noktalardan(r0_kalan), yeniden, ref_kupu),
        "r1": yol_degerlendir(*r1_yolu, yeniden, ref_kupu),
        "normal_kalan": yol_degerlendir(*_noktalardan(r1["normal_rota"]["noktalar"]), yeniden, ref_kupu),
    }
    r1_seviye = seviye_degisimi_ek_maliyeti(r1["optimize_rota"], yol_degerlendir(*r1_yolu, yeniden, r1_kupu))
    degerlendirme["r1"]["sure_dk"] += r1_seviye["sure_dk"]
    if degerlendirme["r1"]["yakit_kg"] is not None and r1_seviye["yakit_kg"] is not None:
        degerlendirme["r1"]["yakit_kg"] += r1_seviye["yakit_kg"]
    bitis = yeniden + pd.Timedelta(minutes=degerlendirme["r0_kalan"]["sure_dk"])
    return {
        "rota": rota_adi,
        "kalkis_utc": kalkis.isoformat(),
        "yeniden_planlama_utc": yeniden.isoformat(),
        "ara_nokta": {"indeks": k, "enlem": plan[k]["enlem"], "boylam": plan[k]["boylam"], "fl": plan[k]["fl"]},
        "kosular": {"r0": r0_kosusu.isoformat(), "r1": r1_kosusu.isoformat(), "referans": ref_kosusu.isoformat()},
        "r1_yeni_kosu_mu": bool(r1_kosusu > r0_kosusu),
        "referans_on_gorusu_saat": [
            round((yeniden - ref_kosusu).total_seconds() / 3600, 2),
            round((bitis - ref_kosusu).total_seconds() / 3600, 2),
        ],
        "strateji": {"r0": r0["kacinma_stratejisi"], "r1": r1["kacinma_stratejisi"]},
        "r1_seviye_degisimi_ek": r1_seviye,
        "r0_kalan_planlama_kupuyle": yol_degerlendir(*_noktalardan(r0_kalan), yeniden, r0_kupu),
        "degerlendirme": degerlendirme,
        "riskli_sure_kazanci_dk": _fark(
            degerlendirme["r0_kalan"]["riskli_sure_dk"], degerlendirme["r1"]["riskli_sure_dk"]
        ),
        "sure_maliyeti_dk": degerlendirme["r1"]["sure_dk"] - degerlendirme["r0_kalan"]["sure_dk"],
        "yakit_maliyeti_kg": _fark(degerlendirme["r1"]["yakit_kg"], degerlendirme["r0_kalan"]["yakit_kg"]),
    }


def ozetle(vakalar) -> dict:
    tamam = [v for v in vakalar if "hata" not in v]
    kazanc = np.array([v["riskli_sure_kazanci_dk"] for v in tamam if v["riskli_sure_kazanci_dk"] is not None])
    maliyet = np.array([v["sure_maliyeti_dk"] for v in tamam])
    riskli = [
        v
        for v in tamam
        if any((v["degerlendirme"][a]["riskli_sure_dk"] or 0) > 0 for a in ("r0_kalan", "r1", "normal_kalan"))
    ]
    return {
        "vaka_sayisi": len(vakalar),
        "hesaplanan": len(tamam),
        "hata": len(vakalar) - len(tamam),
        "riskli_vaka": len(riskli),
        "yeni_kosu_olmayan": sum(not v["r1_yeni_kosu_mu"] for v in tamam),
        "kazanc_pozitif": int((kazanc > 1e-9).sum()),
        "kazanc_negatif": int((kazanc < -1e-9).sum()),
        "kazanc_sifir": int((np.abs(kazanc) <= 1e-9).sum()),
        "riskli_sure_kazanci_dk": {
            "toplam": float(kazanc.sum()) if len(kazanc) else None,
            "ortalama": float(kazanc.mean()) if len(kazanc) else None,
            "medyan": float(np.median(kazanc)) if len(kazanc) else None,
        },
        "sure_maliyeti_dk": {
            "ortalama": float(maliyet.mean()) if len(maliyet) else None,
            "medyan": float(np.median(maliyet)) if len(maliyet) else None,
            "en_buyuk": float(maliyet.max()) if len(maliyet) else None,
        },
    }


def deneyi_calistir(klasor, rotalar=None, kalkislar=KALKISLAR) -> dict:
    vakalar = []
    for kalkis in kalkislar:
        for rota_adi in rotalar or ROTALAR:
            try:
                vakalar.append(vaka_calistir(rota_adi, kalkis, klasor))
            except Exception as hata:
                _logger.warning("Vaka %s %s hesaplanamadı: %s", rota_adi, kalkis, hata)
                vakalar.append(
                    {"rota": rota_adi, "kalkis_utc": _utc(kalkis).isoformat(), "hata": f"{type(hata).__name__}: {hata}"}
                )
    indirilen = (
        sum(os.path.getsize(os.path.join(klasor, ad)) for ad in os.listdir(klasor)) if os.path.isdir(klasor) else 0
    )
    return {
        "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
        "ayarlar": {
            "ucak": UCAK,
            "irtifa_ft": IRTIFA_FT,
            "plan_oncesi_saat": PLAN_ONCESI_SAAT,
            "kosu_gecikmesi_saat": config.GFS_KOSU_GECIKMESI_SAAT,
            "kutu": [KUTU.enlem_min, KUTU.enlem_maks, KUTU.boylam_min, KUTU.boylam_maks],
            "rotalar": {ad: ROTALAR[ad] for ad in (rotalar or ROTALAR)},
            "kalkislar": list(kalkislar),
        },
        "indirilen_mb": round(indirilen / 1e6, 2),
        "uyari": UYARI,
        "ozet": ozetle(vakalar),
        "vakalar": vakalar,
    }


def _s(deger, basamak=1):
    return "—" if deger is None else f"{deger:.{basamak}f}".replace(".", ",")


def markdown_ozeti(rapor) -> str:
    o = rapor["ozet"]
    k, m = o["riskli_sure_kazanci_dk"], o["sure_maliyeti_dk"]
    esik = next((v["degerlendirme"]["r1"]["esik"] for v in rapor["vakalar"] if "hata" not in v), None)
    satirlar = [
        "# Kaçınma başlangıç zamanı (Fikir 18)",
        "",
        f"Üretim: {rapor['uretim_zamani']} · `turbulans-kacinma-baslangici` · indirilen {_s(rapor['indirilen_mb'], 2)} MB",
        "",
        f"> {rapor['uyari']}",
        "",
        "## Yöntem",
        "",
        f"- R0: kalkıştan {rapor['ayarlar']['plan_oncesi_saat']} sa önce elde olan GFS koşusuyla tüm rota "
        f"(koşu gecikmesi {rapor['ayarlar']['kosu_gecikmesi_saat']} sa).",
        "- R1: R0 planında sürenin yarısına gelinen noktada, o an elde olan en yeni koşuyla kalan kısım yeniden planlanır.",
        "- Referans: yeniden planlama anında ya da öncesinde başlamış koşu (R1 ile aynıysa bir sonraki). "
        "R0'ın kalan kısmı, R1 ve büyük daire (normal) kalan kısmı bu küple değerlendirilir.",
        "- R1 yolda seviye değiştiriyorsa rota kodunun kendi seviye değişimi farkı R1'e eklenir (modelde düşey "
        "geçiş süresi 0; yakıt farkı birkaç kg, alçalmada kredi olabilir).",
        f"- {rapor['ayarlar']['ucak']}, {rapor['ayarlar']['irtifa_ft']} ft istek; TI1 eşiği "
        f"{'—' if esik is None else f'{esik:.2e}'} (GFS'e özgü nihai eşik 18 Ekim paketine bağlı).",
        "",
        "## Özet",
        "",
        f"- Vaka: {o['vaka_sayisi']} (hesaplanan {o['hesaplanan']}, hata {o['hata']}); referansta riskli bölüm "
        f"içeren vaka {o['riskli_vaka']}; R1'de yeni koşu olmayan {o['yeni_kosu_olmayan']}.",
        f"- Riskli süre kazancı (R0 kalan − R1, dk): toplam {_s(k['toplam'])}, ortalama {_s(k['ortalama'], 2)}, "
        f"medyan {_s(k['medyan'], 2)}; azalan {o['kazanc_pozitif']}, artan {o['kazanc_negatif']}, "
        f"değişmeyen {o['kazanc_sifir']}.",
        f"- Süre maliyeti (R1 − R0 kalan, dk): ortalama {_s(m['ortalama'], 2)}, medyan {_s(m['medyan'], 2)}, "
        f"en büyük {_s(m['en_buyuk'], 2)}.",
        "",
        "## Vakalar",
        "",
        "| Rota | Kalkış | Yeniden plan | Koşular R0/R1/Ref | Öngörü (sa) | Strateji R0/R1 | Riskli dk R0 kalan / R1 / normal | "
        "R0 kendi tahmini | Kazanç dk | Süre maliyeti dk |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for v in rapor["vakalar"]:
        if "hata" in v:
            satirlar.append(f"| {v['rota']} | {v['kalkis_utc'][:16]} | hata: {v['hata'][:80]} | | | | | | | |")
            continue
        d, kos = v["degerlendirme"], v["kosular"]
        satirlar.append(
            f"| {v['rota']} | {v['kalkis_utc'][5:16]} | {v['yeniden_planlama_utc'][11:16]} | "
            f"{kos['r0'][8:13]} / {kos['r1'][8:13]} / {kos['referans'][8:13]} | "
            f"{_s(v['referans_on_gorusu_saat'][0])}–{_s(v['referans_on_gorusu_saat'][1])} | "
            f"{v['strateji']['r0']} / {v['strateji']['r1']} | "
            f"{_s(d['r0_kalan']['riskli_sure_dk'])} / {_s(d['r1']['riskli_sure_dk'])} / "
            f"{_s(d['normal_kalan']['riskli_sure_dk'])} | {_s(v['r0_kalan_planlama_kupuyle']['riskli_sure_dk'])} | "
            f"{_s(v['riskli_sure_kazanci_dk'])} | {_s(v['sure_maliyeti_dk'], 2)} |"
        )
    satirlar += [
        "",
        'Koşular gün ve saat (GGTSS) olarak; "R0 kendi tahmini": R0 kalan kısmının R0 koşusuyla öngörülen riskli süresi.',
        "Karşılaştırma: Kim vd. (2015) LTAR 1/2/3 (+16 dk, 10 dk tasarruf, +2 dk) farklı bölge ve yöntemdir; "
        "sayılar doğrudan kıyaslanmaz.",
        "",
    ]
    return "\n".join(satirlar)


def ana(argv=None):
    ayrac = argparse.ArgumentParser(
        description="Kalkışta ve yolda yeniden planlanan kaçınmayı karşılaştırır (Fikir 18)."
    )
    ayrac.add_argument("--cikti", required=True, help="Rapor klasörü (örn. docs/sonuclar/2026-10-17)")
    ayrac.add_argument("--veri-klasoru", default=os.path.join("ciktilar", "kacinma_baslangici"))
    ayrac.add_argument("--kalkislar", default=",".join(KALKISLAR), help="Virgülle ayrılmış UTC kalkış saatleri")
    ayrac.add_argument("--rotalar", default=",".join(ROTALAR), help=f"Virgülle: {', '.join(ROTALAR)}")
    arg = ayrac.parse_args(argv)
    rapor = deneyi_calistir(
        arg.veri_klasoru, [r.strip() for r in arg.rotalar.split(",")], [k.strip() for k in arg.kalkislar.split(",")]
    )
    os.makedirs(arg.cikti, exist_ok=True)
    with open(os.path.join(arg.cikti, "kacinma_baslangici.json"), "w", encoding="utf-8") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2)
    with open(os.path.join(arg.cikti, "kacinma_baslangici.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    o = rapor["ozet"]
    print(
        f"{o['hesaplanan']}/{o['vaka_sayisi']} vaka; riskli {o['riskli_vaka']}; kazanç toplam "
        f"{_s(o['riskli_sure_kazanci_dk']['toplam'])} dk; {rapor['indirilen_mb']} MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
