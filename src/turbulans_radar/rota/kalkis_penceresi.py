import pandas as pd

BILGI_NOTU = (
    "Yalnız bilgi amaçlıdır, öneri değildir: kalkış saati slot, ATC ve operasyonel kısıtlara bağlıdır. "
    "Her satır aynı rota isteğinin yalnız kalkış saati kaydırılarak yeniden hesaplanmasıdır; ileri saatlerde "
    "SIGMET henüz yayımlanmamış olabilir."
)
VARSAYILAN_FARKLAR_SAAT = (-2, -1, 1, 2)


def _satir(fark_saat, kalkis, sonuc) -> dict:
    normal, optimize = sonuc["normal_rota"], sonuc["optimize_rota"]
    return {
        "fark_saat": fark_saat,
        "kalkis_utc": kalkis.isoformat(),
        "veri": sonuc["ruzgar_verisi_kaynagi"],
        "normal_riskli_sure_dk": normal.get("riskli_sure_dk"),
        "optimize_riskli_sure_dk": optimize.get("riskli_sure_dk"),
        "optimize_sure_dk": optimize.get("toplam_sure_dk"),
        "optimize_yakit_kg": optimize.get("tahmini_yakit_kg"),
        "strateji": sonuc["kacinma_stratejisi"],
        "guvenli_rota_bulundu_mu": sonuc["guvenli_rota_bulundu_mu"],
    }


def kalkis_penceresi(
    ana_sonuc, rota_fonksiyonu, argumanlar, zaman_iso, farklar_saat=VARSAYILAN_FARKLAR_SAAT, **anahtarlar
):
    ana_kalkis = pd.Timestamp(zaman_iso)
    ana_kalkis = ana_kalkis.tz_localize("UTC") if ana_kalkis.tzinfo is None else ana_kalkis.tz_convert("UTC")
    satirlar = [_satir(0, ana_kalkis, ana_sonuc)]
    hatalar = []
    for fark in farklar_saat:
        kalkis = ana_kalkis + pd.Timedelta(hours=fark)
        try:
            sonuc = rota_fonksiyonu(*argumanlar, kalkis.strftime("%Y-%m-%dT%H:%M:%S"), **anahtarlar)
            satirlar.append(_satir(fark, kalkis, sonuc))
        except Exception as hata:
            hatalar.append({"fark_saat": fark, "hata": f"{type(hata).__name__}: {hata}"})
    return {"bilgi_notu": BILGI_NOTU, "satirlar": sorted(satirlar, key=lambda s: s["fark_saat"]), "hatalar": hatalar}
