import argparse
import json
import os
import time
from datetime import UTC, datetime

from turbulans_radar import config

VARSAYILAN_NOKTA_SAYILARI = (21, 41, 81)
VARSAYILAN_IZGARA_KM = (10.0, 20.0, 40.0)
_OLCUTLER = ("toplam_sure_dk", "tahmini_yakit_kg", "riskli_sure_dk", "mesafe_km")


def _ozet(sonuc) -> dict:
    optimize = sonuc["optimize_rota"]
    return {
        "strateji": sonuc["kacinma_stratejisi"],
        "veri": sonuc["ruzgar_verisi_kaynagi"],
        **{o: optimize.get(o) for o in _OLCUTLER},
    }


def _fark(deger, referans) -> float | None:
    if deger is None or referans is None:
        return None
    return float(deger) - float(referans)


def tarama_yap(senaryolar, nokta_sayilari, izgara_km_listesi, rota_fonksiyonu=None, saat=time.perf_counter) -> dict:
    if rota_fonksiyonu is None:
        from turbulans_radar.rota.rota_optimizasyonu import rota_simulasyonu_olustur as rota_fonksiyonu
    eski = (
        config.ROTA_SIMULASYONU_NOKTA_SAYISI,
        config.ROTA_YANAL_IZGARA_KM,
        config.ERA5_OTOMATIK_INDIRME,
        config.CANLI_HAVA_VERISI_ETKIN,
    )
    config.ERA5_OTOMATIK_INDIRME = config.CANLI_HAVA_VERISI_ETKIN = False
    kayitlar = []
    try:
        for ad, girdi, sigmetler, sahalar in senaryolar:
            for nokta in nokta_sayilari:
                for izgara in izgara_km_listesi:
                    config.ROTA_SIMULASYONU_NOKTA_SAYISI, config.ROTA_YANAL_IZGARA_KM = int(nokta), float(izgara)
                    baslangic = saat()
                    sonuc = rota_fonksiyonu(*girdi, "A320", sigmetler=sigmetler, kisitli_sahalar=sahalar)
                    sure_ms = (saat() - baslangic) * 1000.0
                    kayitlar.append(
                        {
                            "senaryo": ad,
                            "nokta": int(nokta),
                            "izgara_km": float(izgara),
                            "hesap_ms": sure_ms,
                            **_ozet(sonuc),
                        }
                    )
    finally:
        (
            config.ROTA_SIMULASYONU_NOKTA_SAYISI,
            config.ROTA_YANAL_IZGARA_KM,
            config.ERA5_OTOMATIK_INDIRME,
            config.CANLI_HAVA_VERISI_ETKIN,
        ) = eski
    referans_ayari = (max(nokta_sayilari), min(izgara_km_listesi))
    for kayit in kayitlar:
        referans = next(
            k for k in kayitlar if k["senaryo"] == kayit["senaryo"] and (k["nokta"], k["izgara_km"]) == referans_ayari
        )
        for o in _OLCUTLER:
            kayit[f"{o}_fark"] = _fark(kayit[o], referans[o])
        kayit["strateji_ayni_mi"] = kayit["strateji"] == referans["strateji"]
    return {
        "referans": {"nokta": referans_ayari[0], "izgara_km": referans_ayari[1]},
        "varsayilan": {"nokta": eski[0], "izgara_km": eski[1]},
        "kayitlar": kayitlar,
        "uretim_zamani": datetime.now(UTC).isoformat(),
    }


def _sayi(x, bicim="{:+.1f}"):
    return "—" if x is None else bicim.format(x)


def markdown_ozeti(rapor) -> str:
    ref = rapor["referans"]
    vars_ = rapor["varsayilan"]
    satirlar = [
        "# Rota ayrıklaştırma yakınsama çalışması",
        "",
        f"Üretim: {rapor['uretim_zamani']}. Referans en ince ayar: {ref['nokta']} ara nokta, "
        f"{ref['izgara_km']:g} km yanal ızgara. Varsayılan: {vars_['nokta']} nokta, {vars_['izgara_km']:g} km. "
        "Farklar önerilen (optimize) rotanın referansa göre farkıdır. Veri yerel ERA5 (Ocak 2019); canlı veri ve "
        "otomatik indirme kapalı.",
        "",
        "| Senaryo | Nokta | Izgara (km) | Strateji | Süre farkı (dk) | Yakıt farkı (kg) | Riskli süre farkı (dk) | Hesap (ms) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k in rapor["kayitlar"]:
        varsayilan_mi = (k["nokta"], k["izgara_km"]) == (vars_["nokta"], vars_["izgara_km"])
        isaret = " **(varsayılan)**" if varsayilan_mi else ""
        strateji = k["strateji"] + ("" if k["strateji_ayni_mi"] else " ≠ ref")
        satirlar.append(
            f"| {k['senaryo']} | {k['nokta']}{isaret} | {k['izgara_km']:g} | {strateji} | "
            f"{_sayi(k['toplam_sure_dk_fark'], '{:+.2f}')} | {_sayi(k['tahmini_yakit_kg_fark'])} | "
            f"{_sayi(k['riskli_sure_dk_fark'])} | {k['hesap_ms']:.0f} |"
        )
    satirlar += [
        "",
        "Hesap süresi tek ölçümdür (soğuk/sıcak ayrılmadı); yalnız ayarlar arası göreli karşılaştırma içindir. "
        "Yakıt ve süre modelin kendi tahminidir; gerçek uçuş değildir.",
    ]
    return "\n".join(satirlar) + "\n"


def varsayilan_senaryolar():
    from turbulans_radar.cli.performans_olcumu import ROTA_SENARYOLARI, _sentetik_sigmet
    from turbulans_radar.veri.kisitli_saha_saglayici import ORNEK_DOSYA, ORNEK_KAYNAK, geojson_kayitlarina_cevir

    sahalar = geojson_kayitlarina_cevir(json.loads(ORNEK_DOSYA.read_text(encoding="utf-8")), ORNEK_KAYNAK)
    return [
        (ad, girdi, [_sentetik_sigmet()] if kisit == "sigmet" else [], sahalar if kisit == "saha" else [])
        for ad, girdi, kisit in ROTA_SENARYOLARI
        if "kapsam dışı" not in ad
    ]


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="Rota ara nokta sayısı ve yanal ızgara aralığının sonuca etkisi.")
    ayrac.add_argument("--nokta", default=",".join(str(n) for n in VARSAYILAN_NOKTA_SAYILARI))
    ayrac.add_argument("--izgara-km", default=",".join(f"{k:g}" for k in VARSAYILAN_IZGARA_KM))
    ayrac.add_argument("--cikti", required=True, help="Rapor klasörü (örn. docs/sonuclar/2026-10-16)")
    arg = ayrac.parse_args(argv)
    rapor = tarama_yap(
        varsayilan_senaryolar(),
        tuple(int(x) for x in arg.nokta.split(",")),
        tuple(float(x) for x in arg.izgara_km.split(",")),
    )
    os.makedirs(arg.cikti, exist_ok=True)
    with open(os.path.join(arg.cikti, "ayriklastirma.json"), "w", encoding="utf-8") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2)
    with open(os.path.join(arg.cikti, "ayriklastirma.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    print(markdown_ozeti(rapor))
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
