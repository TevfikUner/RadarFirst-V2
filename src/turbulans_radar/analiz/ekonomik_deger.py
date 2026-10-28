"""
ekonomik_deger.py
-------------------
Göreli ekonomik değer (REV; Richardson 2000) — maliyet/kayıp karar modeli. Uyarıya göre
önlem almanın maliyeti C, önlem alınmadan olay yaşanırsa kayıp L, alfa = C/L, s olay taban
oranı, H = POD, F = POFD:

    V(alfa) = [min(alfa, s) - alfa (H s + F (1 - s)) - s (1 - H)] / [min(alfa, s) - s alfa]

V = 1 kusursuz tahmin, V = 0 klimatoloji (hep önlem al / hiç alma), V < 0 klimatolojiden kötü.
En yüksek V (alfa = s) Peirce'e (H - F) eşittir. Eşik zarfı: her alfa'da eşikler arasından en
yüksek V. POD/POFD 18 Ekim nihai paketinin altın test günlerinden okunur (yeniden puanlama yok).

    turbulans-ekonomik-deger --cikti docs/sonuclar/2026-10-28_ekonomik_deger

Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

KOK = Path(__file__).resolve().parents[3]
PAKET = KOK / "docs" / "sonuclar" / "2026-10-18" / "sonuc_paketi.json"
UYARI_ORANI = KOK / "docs" / "sonuclar" / "2026-10-28_uyari_orani" / "uyari_orani.json"
ALFALAR = np.logspace(-3, 0, 601)[:-1]
RENKLER = ("#2a78d6", "#eb6834", "#1baf7a")
CIZGILER = ("-", "--", ":")


def rev(pod, pofd, taban, alfa):
    alfa = np.asarray(alfa, dtype=float)
    klimatoloji = np.minimum(alfa, taban)
    tahmin = alfa * (pod * taban + pofd * (1.0 - taban)) + taban * (1.0 - pod)
    return (klimatoloji - tahmin) / (klimatoloji - taban * alfa)


def zarf(noktalar, taban, alfa=ALFALAR) -> np.ndarray:
    return np.max([rev(h, f, taban, alfa) for h, f in noktalar], axis=0)


def egri_ozeti(egri, alfa=ALFALAR) -> dict:
    pozitif = alfa[egri > 0]
    return {
        "maks_rev": float(np.max(egri)),
        "maks_rev_alfa": float(alfa[int(np.argmax(egri))]),
        "deger_kattigi_alfa": [float(pozitif.min()), float(pozitif.max())] if len(pozitif) else None,
    }


def seriler(paket: dict) -> dict:
    tarama = paket["esik_taramasi"]
    risk = tarama["config_esikleri"]["TI1_ESIK_ORTA_SIDDETLI"]
    model = paket["model_olasilik_test"]
    return {
        "TI1 (eşik zarfı)": [(t["test_pod"], t["test_pofd"]) for t in tarama["tarama"]],
        f"TI1 risk eşiği ({risk['esik']:.0e})": [(risk["test"]["pod"], risk["test"]["pofd"])],
        f"Model (olasılık ≥ {model['esik']:g})": [(model["pod"], model["pofd"])],
    }


def hesapla(paket: dict, kacinma_bedeli_yuzde: float | None, madis_taban: float | None = None) -> dict:
    tabanlar = {"PIREP altın günler (ölçülen)": paket["pirep_test"]["taban_oran"]}
    if madis_taban is not None:
        tabanlar["MADIS EDR ≥ 0,1 oranı (gösterim)"] = madis_taban
    sonuc = {}
    for taban_adi, taban in tabanlar.items():
        satir = {}
        for ad, noktalar in seriler(paket).items():
            ozet = egri_ozeti(zarf(noktalar, taban))
            aralik = ozet["deger_kattigi_alfa"] if kacinma_bedeli_yuzde is not None else None
            ozet["en_az_kayip_yakit_yuzdesi"] = kacinma_bedeli_yuzde / aralik[1] if aralik else None
            ozet["en_cok_kayip_yakit_yuzdesi"] = kacinma_bedeli_yuzde / aralik[0] if aralik else None
            satir[ad] = ozet
        sonuc[taban_adi] = {"taban_oran": taban, "seriler": satir}
    return sonuc


def sekil_ciz(paket: dict, tabanlar: dict, yol: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, eksenler = plt.subplots(1, len(tabanlar), figsize=(6.2 * len(tabanlar), 4.4), sharey=True, squeeze=False)
    for eksen, (taban_adi, taban) in zip(eksenler[0], tabanlar.items(), strict=True):
        for (ad, noktalar), renk, cizgi in zip(seriler(paket).items(), RENKLER, CIZGILER, strict=True):
            egri = zarf(noktalar, taban)
            eksen.plot(
                ALFALAR,
                np.where(egri >= -0.2, egri, np.nan),
                color=renk,
                linestyle=cizgi,
                linewidth=2,
                label=f"{ad}, en yüksek {np.max(egri):.2f}",
            )
        eksen.axhline(0, color="#52514e", linewidth=0.8)
        eksen.axvline(taban, color="#e1e0d9", linewidth=1)
        eksen.set_xscale("log")
        eksen.set_ylim(-0.2, 0.5)
        eksen.set_xlabel("Maliyet / kayıp oranı α = C/L")
        eksen.set_title(f"{taban_adi}, s = {taban:.3f}", fontsize=10, color="#0b0b0b")
        eksen.grid(True, color="#e1e0d9", linewidth=0.5)
        for kenar in ("top", "right"):
            eksen.spines[kenar].set_visible(False)
    eksenler[0][0].set_ylabel("Göreli ekonomik değer (REV)")
    for eksen in eksenler[0]:
        eksen.legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("REV: altın test günleri POD/POFD (18 Ekim paketi); sertifikalı EDR değildir", fontsize=10)
    fig.tight_layout()
    fig.savefig(yol, dpi=150, metadata={"Software": None})
    plt.close(fig)


def _yuzde(x) -> str:
    return "—" if x is None else f"%{x:.1f}"


def markdown_ozeti(rapor) -> str:
    satirlar = [
        "# Göreli ekonomik değer (REV)",
        "",
        f"Üretim: {rapor['meta']['uretim_zamani']} · girdi `docs/sonuclar/2026-10-18/sonuc_paketi.json` (altın test "
        "günleri POD/POFD) · yöntem Richardson (2000) maliyet/kayıp modeli. Kaçınma bedeli medyanı "
        f"{_yuzde(rapor['kacinma_bedeli_yuzde'])} sefer yakıtı (`2026-10-28_uyari_orani`, rüzgâr-optimum rotaya göre).",
        "",
        "| Taban oran | Gösterge | En yüksek REV (α) | Değer kattığı α aralığı | Değer kattığı kayıp aralığı (sefer yakıtı) |",
        "|---|---|---|---|---|",
    ]
    for taban_adi, blok in rapor["sonuc"].items():
        for ad, o in blok["seriler"].items():
            aralik = o["deger_kattigi_alfa"]
            satirlar.append(
                f"| {taban_adi}, s = {blok['taban_oran']:.3f} | {ad} | {o['maks_rev']:.3f} ({o['maks_rev_alfa']:.3f}) | "
                + (f"{aralik[0]:.3f}–{aralik[1]:.3f}" if aralik else "yok")
                + f" | {_yuzde(o['en_az_kayip_yakit_yuzdesi'])}–{_yuzde(o['en_cok_kayip_yakit_yuzdesi'])} |"
            )
    satirlar += [
        "",
        "![REV eğrileri](rev_egrileri.png)",
        "",
        "**Okuma.** α, önlemin (sapma) maliyetinin önlemsiz olay kaybına oranıdır. REV > 0 olan α aralığında "
        'gösterge, "hep sap" ya da "hiç sapma" kurallarından daha ucuzdur; en yüksek değer α = s\'de Peirce\'e eşittir. '
        "Son sütun: C = kaçınma bedeli medyanı alınırsa, bir orta-üstü karşılaşmanın kaybı (sefer yakıtı cinsinden) bu "
        'aralıktaysa gösterge değer katar; altında "hiç sapma", üstünde "hep sap" daha ucuzdur. Kaybın gerçek '
        "değeri (yaralanma, muayene, gecikme) bilinmiyor ve uydurulmadı.",
        "",
        "**Sınırlar.** POD/POFD PIREP noktası başınadır, rota kararı başına değildir; bir rota birçok noktadan geçer. "
        "PIREP taban oranı (s ≈ 0,48) operasyonel karşılaşma sıklığı değildir (PIREP türbülans olunca verilir). İkinci "
        "panel aynı POD/POFD'nin MADIS'te ölçülen EDR ≥ 0,1 oranına (farklı olay, hafif ve üstü) aktarılabildiği "
        "varsayımıyla gösterimdir. Sonuç göstergeler arası sıralama ve büyüklük mertebesi içindir; bir eşik ya da "
        "seçim ağırlığı önerisi değildir.",
        "",
        "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
    ]
    return "\n".join(satirlar) + "\n"


def calistir(cikti: str, paket_yolu=PAKET, uyari_orani_yolu=UYARI_ORANI) -> dict:
    with open(paket_yolu, encoding="utf-8") as dosya:
        paket = json.load(dosya)
    bedel = None
    if uyari_orani_yolu and os.path.exists(uyari_orani_yolu):
        with open(uyari_orani_yolu, encoding="utf-8") as dosya:
            bedel = json.load(dosya)["ozet"]["genel"].get("kacinma_bedeli_yuzde_medyan")
    madis = paket.get("madis", {}).get("taban_oran")
    rapor = {
        "meta": {
            "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
            "yontem": "Richardson (2000) maliyet/kayıp REV; eşik zarfı",
            "uyari": "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
        },
        "kacinma_bedeli_yuzde": bedel,
        "sonuc": hesapla(paket, bedel, madis),
    }
    os.makedirs(cikti, exist_ok=True)
    with open(os.path.join(cikti, "ekonomik_deger.json"), "w", encoding="utf-8", newline="") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2)
    with open(os.path.join(cikti, "README.md"), "w", encoding="utf-8", newline="") as dosya:
        dosya.write(markdown_ozeti(rapor))
    sekil_ciz(paket, {ad: b["taban_oran"] for ad, b in rapor["sonuc"].items()}, os.path.join(cikti, "rev_egrileri.png"))
    return rapor


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="Göreli ekonomik değer (REV) eğrileri.")
    ayrac.add_argument("--cikti", required=True)
    arg = ayrac.parse_args(argv)
    print(markdown_ozeti(calistir(arg.cikti)))


if __name__ == "__main__":
    ana()
