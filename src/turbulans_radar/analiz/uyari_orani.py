"""
uyari_orani.py
---------------
Uyarı oranı / alarm yorgunluğu ölçümü (kurul raporu #4, YAPILACAKLAR Fikir 9).
Yerel Ocak 2019 küpünde, ağsız, sabit şehir çiftleri × günler × saatler × FL için
rota simülasyonu çalıştırır ve şunu sayar: normal rotada riskli TI1 noktası olan
uçuş oranı, sistemin sapma önerdiği uçuş oranı, sapmanın yakıt bedeli ve sapma
önerilirken daha ucuz ama riskli nokta bırakan bir seçeneğin bulunduğu oran.
Rotalar aynı günlerin hava sistemlerini paylaştığı için bağımsız değildir; oranlar
betimleyicidir. Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import json
import os
import statistics
import time
from datetime import UTC, datetime, timedelta

from turbulans_radar import config

SEHIR_CIFTLERI = (
    ("İstanbul→Van", 41.0, 28.9, 38.5, 43.4),
    ("İzmir→Erzurum", 38.4, 27.1, 39.9, 41.3),
    ("Antalya→Kars", 36.9, 30.7, 40.6, 43.1),
    ("İstanbul→Gaziantep", 41.0, 28.9, 36.9, 37.4),
    ("Ankara→Van", 39.9, 32.9, 38.5, 43.4),
    ("İzmir→Trabzon", 38.4, 27.1, 41.0, 39.7),
)
VARSAYILAN_SEVIYELER_FT = (35000, 37000)
VARSAYILAN_SAATLER = (0, 6, 12, 18)
VARSAYILAN_BASLANGIC = "2019-01-01"
VARSAYILAN_GUN_SAYISI = 31


def senaryolari_uret(
    baslangic=VARSAYILAN_BASLANGIC,
    gun_sayisi=VARSAYILAN_GUN_SAYISI,
    saatler=VARSAYILAN_SAATLER,
    seviyeler_ft=VARSAYILAN_SEVIYELER_FT,
    ciftler=SEHIR_CIFTLERI,
):
    ilk_gun = datetime.fromisoformat(baslangic)
    for gun in range(gun_sayisi):
        for saat in saatler:
            kalkis = (ilk_gun + timedelta(days=gun, hours=saat)).strftime("%Y-%m-%dT%H:%M:%S")
            for ad, enlem1, boylam1, enlem2, boylam2 in ciftler:
                for seviye in seviyeler_ft:
                    yield ad, (enlem1, boylam1, enlem2, boylam2, seviye, kalkis)


def _onerilen_secenek(sonuc):
    return next((s for s in sonuc.get("secenekler") or [] if s.get("onerilen")), None)


def _daha_ucuz_riskli_secenek(sonuc):
    onerilen = _onerilen_secenek(sonuc)
    if onerilen is None:
        return None
    adaylar = [
        s
        for s in sonuc.get("secenekler") or []
        if not s.get("onerilen")
        and s["riskli_nokta_sayisi"] > onerilen["riskli_nokta_sayisi"]
        and s["ek_yakit_yuzde"] < onerilen["ek_yakit_yuzde"]
    ]
    if not adaylar:
        return None
    en_ucuz = min(adaylar, key=lambda s: s["ek_yakit_yuzde"])
    return {
        "strateji": en_ucuz["strateji"],
        "ek_yakit_yuzde": en_ucuz["ek_yakit_yuzde"],
        "riskli_nokta_sayisi": en_ucuz["riskli_nokta_sayisi"],
        "yakit_avantaji_yuzde": onerilen["ek_yakit_yuzde"] - en_ucuz["ek_yakit_yuzde"],
    }


def kaydi_cikar(ad, girdi, sonuc, hesap_ms) -> dict:
    normal, optimize = sonuc["normal_rota"], sonuc["optimize_rota"]
    onerilen = _onerilen_secenek(sonuc)
    bedel = (sonuc.get("referans_karsilastirmasi") or {}).get("kacinma_bedeli") or {}
    strateji = sonuc["kacinma_stratejisi"]
    return {
        "cift": ad,
        "fl": int(girdi[4] // 100),
        "kalkis": girdi[5],
        "veri": sonuc["ruzgar_verisi_kaynagi"],
        "normal_riskli_nokta": normal.get("riskli_nokta_sayisi"),
        "normal_riskli_sure_dk": normal.get("riskli_sure_dk"),
        "strateji": strateji,
        "sapma": strateji != "yok",
        "guvenli_rota_bulundu_mu": sonuc["guvenli_rota_bulundu_mu"],
        "optimize_riskli_nokta": optimize.get("riskli_nokta_sayisi"),
        "optimize_riskli_sure_dk": optimize.get("riskli_sure_dk"),
        "ek_yakit_yuzde": onerilen["ek_yakit_yuzde"] if onerilen else 0.0,
        "kacinma_bedeli_yakit_yuzde": bedel.get("ek_yakit_yuzde"),
        "daha_ucuz_riskli_secenek": _daha_ucuz_riskli_secenek(sonuc),
        "hesap_ms": hesap_ms,
    }


def olcum_yap(senaryolar, rota_fonksiyonu=None, saat=time.perf_counter) -> list[dict]:
    if rota_fonksiyonu is None:
        from turbulans_radar.rota.rota_optimizasyonu import rota_simulasyonu_olustur as rota_fonksiyonu
    eski = (config.ERA5_OTOMATIK_INDIRME, config.CANLI_HAVA_VERISI_ETKIN)
    config.ERA5_OTOMATIK_INDIRME = config.CANLI_HAVA_VERISI_ETKIN = False
    kayitlar = []
    try:
        for ad, girdi in senaryolar:
            baslangic = saat()
            try:
                sonuc = rota_fonksiyonu(*girdi, "A320", sigmetler=[], kisitli_sahalar=[])
            except Exception as hata:
                kayitlar.append({"cift": ad, "fl": int(girdi[4] // 100), "kalkis": girdi[5], "hata": str(hata)})
                continue
            kayitlar.append(kaydi_cikar(ad, girdi, sonuc, (saat() - baslangic) * 1000.0))
    finally:
        config.ERA5_OTOMATIK_INDIRME, config.CANLI_HAVA_VERISI_ETKIN = eski
    return kayitlar


def _yuzdelik(degerler, oran):
    if not degerler:
        return None
    sirali = sorted(degerler)
    return sirali[min(len(sirali) - 1, int(round(oran * (len(sirali) - 1))))]


def _grup_ozeti(kayitlar) -> dict:
    gecerli = [
        k for k in kayitlar if "hata" not in k and k["veri"] == "era5_gercek" and k["normal_riskli_nokta"] is not None
    ]
    riskli = [k for k in gecerli if k["normal_riskli_nokta"] > 0]
    sapma = [k for k in gecerli if k["sapma"]]
    ucuz = [k for k in sapma if k["daha_ucuz_riskli_secenek"]]
    ek_yakit = [k["ek_yakit_yuzde"] for k in sapma]
    bedel = [k["kacinma_bedeli_yakit_yuzde"] for k in sapma if k["kacinma_bedeli_yakit_yuzde"] is not None]
    return {
        "rota": len(gecerli),
        "riskli_rota": len(riskli),
        "riskli_rota_orani": len(riskli) / len(gecerli) if gecerli else None,
        "sapma": len(sapma),
        "sapma_orani": len(sapma) / len(gecerli) if gecerli else None,
        "oneri_yok": sum(1 for k in gecerli if not k["guvenli_rota_bulundu_mu"]),
        "riskli_sure_dk_medyan": statistics.median([k["normal_riskli_sure_dk"] for k in riskli]) if riskli else None,
        "sapmada_kalan_riskli_rota": sum(1 for k in sapma if (k["optimize_riskli_nokta"] or 0) > 0),
        "sapma_ek_yakit_yuzde_medyan": statistics.median(ek_yakit) if ek_yakit else None,
        "sapma_ek_yakit_yuzde_p90": _yuzdelik(ek_yakit, 0.9),
        "kacinma_bedeli_yuzde_medyan": statistics.median(bedel) if bedel else None,
        "daha_ucuz_riskli_secenekli_sapma": len(ucuz),
        "daha_ucuz_riskli_secenekli_sapma_orani": len(ucuz) / len(sapma) if sapma else None,
        "ucuz_secenek_yakit_avantaji_medyan": (
            statistics.median([k["daha_ucuz_riskli_secenek"]["yakit_avantaji_yuzde"] for k in ucuz]) if ucuz else None
        ),
        "ucuz_secenek_riskli_nokta_medyan": (
            statistics.median([k["daha_ucuz_riskli_secenek"]["riskli_nokta_sayisi"] for k in ucuz]) if ucuz else None
        ),
    }


def ozetle(kayitlar) -> dict:
    return {
        "genel": _grup_ozeti(kayitlar),
        "fl": {
            str(fl): _grup_ozeti([k for k in kayitlar if k["fl"] == fl]) for fl in sorted({k["fl"] for k in kayitlar})
        },
        "cift": {
            c: _grup_ozeti([k for k in kayitlar if k["cift"] == c]) for c in dict.fromkeys(k["cift"] for k in kayitlar)
        },
        "hata": sum(1 for k in kayitlar if "hata" in k),
        "era5_disi": sum(1 for k in kayitlar if "hata" not in k and k["veri"] != "era5_gercek"),
    }


def _oran(x):
    return "—" if x is None else f"%{100 * x:.1f}"


def _sayi(x, bicim="{:.1f}"):
    return "—" if x is None else bicim.format(x)


def _tablo_satiri(ad, o) -> str:
    return (
        f"| {ad} | {o['rota']} | {_oran(o['riskli_rota_orani'])} | {_oran(o['sapma_orani'])} | "
        f"{_sayi(o['riskli_sure_dk_medyan'])} | {_sayi(o['sapma_ek_yakit_yuzde_medyan'], '{:+.1f}')} | "
        f"{_sayi(o['sapma_ek_yakit_yuzde_p90'], '{:+.1f}')} | {_oran(o['daha_ucuz_riskli_secenekli_sapma_orani'])} | "
        f"{_sayi(o['ucuz_secenek_yakit_avantaji_medyan'])} | {_sayi(o['ucuz_secenek_riskli_nokta_medyan'], '{:g}')} |"
    )


def markdown_ozeti(rapor) -> str:
    o = rapor["ozet"]
    g = o["genel"]
    p = rapor["parametreler"]
    satirlar = [
        "# Uyarı oranı / alarm yorgunluğu ölçümü",
        "",
        f"Üretim: {rapor['uretim_zamani']} · commit `{rapor['commit'] or '—'}` · TI1 risk eşiği {p['ti1_esigi']:.1e} · "
        f"{p['gun_sayisi']} gün ({p['baslangic']}'ten) × saatler {p['saatler']} × {len(p['ciftler'])} şehir çifti × "
        f"FL {p['fl']}. Veri yerel ERA5 küpü (3 seviye, Türkiye, Ocak 2019); canlı veri, otomatik indirme, SIGMET ve "
        "kısıtlı saha kapalı (yalnız TI1 etkisi ölçülür). A320, koridor modu, varsayılan seçim kuralı (önce riskli "
        "nokta sayısı, sonra yakıt).",
        "",
        "| Grup | Rota | Normal rotada riskli nokta olan | Sapma önerilen | Riskli süre medyanı (dk, riskli rotalarda) | "
        "Sapmada ek yakıt medyanı (%) | Sapmada ek yakıt p90 (%) | Sapmalarda daha ucuz riskli seçenek bulunan | "
        "O seçeneğin yakıt avantajı medyanı (puan) | O seçenekte kalan riskli nokta medyanı |",
        "|---|---|---|---|---|---|---|---|---|---|",
        _tablo_satiri("**Tümü**", g),
        *(_tablo_satiri(f"FL{fl}", v) for fl, v in o["fl"].items()),
        *(_tablo_satiri(c, v) for c, v in o["cift"].items()),
        "",
        f"Öneri yok (sert kısıt yok, beklenen 0): {g['oneri_yok']}. Sapmadan sonra hâlâ riskli nokta kalan rota: "
        f"{g['sapmada_kalan_riskli_rota']}/{g['sapma']}. Kaçınma bedeli medyanı (rüzgâr-optimum rotaya göre): "
        f"{_sayi(g['kacinma_bedeli_yuzde_medyan'], '{:+.1f}')} %. Hata: {o['hata']}; ERA5 dışı veriyle dönen: "
        f"{o['era5_disi']} (tabloya girmez).",
        "",
        '**Okuma.** "Ek yakıt" önerilen rotanın büyük daireye göre yakıt farkıdır (rüzgâr kazancını da içerir); '
        'kaçınmanın saf bedeli "kaçınma bedeli"dir. "Daha ucuz riskli seçenek": seçenekler listesinde önerilenden '
        "daha az yakıt yakan ama daha çok riskli nokta bırakan Pareto seçeneği; seçim kuralı riskli nokta sayısını "
        "yakıtla takas etmediği için önerilmez (SISTEM_KARTI §3). Rotalar aynı günlerin hava sistemlerini paylaşır, "
        "bağımsız örnek değildir; oranlar betimleyicidir, güven aralığı verilmedi. Tek bölge, tek ay, 3 seviyeli "
        "küp (FL340–360'ta riski 7 seviyeye göre az gösterir, SISTEM_KARTI §5).",
        "",
        "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
    ]
    return "\n".join(satirlar) + "\n"


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="Toplu rota simülasyonuyla uyarı ve sapma oranı ölçümü (ağsız).")
    ayrac.add_argument("--baslangic", default=VARSAYILAN_BASLANGIC)
    ayrac.add_argument("--gun", type=int, default=VARSAYILAN_GUN_SAYISI)
    ayrac.add_argument("--saatler", default=",".join(str(s) for s in VARSAYILAN_SAATLER))
    ayrac.add_argument("--fl", default=",".join(str(s // 100) for s in VARSAYILAN_SEVIYELER_FT))
    ayrac.add_argument("--cikti", required=True, help="Rapor klasörü (örn. docs/sonuclar/2026-10-28_uyari_orani)")
    arg = ayrac.parse_args(argv)
    from turbulans_radar.fizik.ti1_esigi import etkin_ti1_esigi
    from turbulans_radar.uretim_bilgisi import yazilim_commit

    saatler = tuple(int(s) for s in arg.saatler.split(","))
    seviyeler = tuple(int(s) * 100 for s in arg.fl.split(","))
    kayitlar = olcum_yap(senaryolari_uret(arg.baslangic, arg.gun, saatler, seviyeler))
    rapor = {
        "parametreler": {
            "baslangic": arg.baslangic,
            "gun_sayisi": arg.gun,
            "saatler": list(saatler),
            "fl": [s // 100 for s in seviyeler],
            "ciftler": [list(c) for c in SEHIR_CIFTLERI],
            "ti1_esigi": etkin_ti1_esigi(),
            "ucak": "A320",
        },
        "commit": yazilim_commit(),
        "uretim_zamani": datetime.now(UTC).isoformat(),
        "ozet": ozetle(kayitlar),
        "kayitlar": kayitlar,
    }
    os.makedirs(arg.cikti, exist_ok=True)
    with open(os.path.join(arg.cikti, "uyari_orani.json"), "w", encoding="utf-8") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2)
    with open(os.path.join(arg.cikti, "README.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    print(markdown_ozeti(rapor))
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
