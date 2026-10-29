"""
birlesik_esik.py
-------------------
Birleşik EDR'nin rota eşiği (kurul #4 kalanı, deney_protokolu.md §12). Eşik, TI1 7e-7 ile aynı
kuralla (Peirce'i en yüksek eşiğin gün bazlı bootstrap SE'si içindeki en yüksek eşik) aynı eğitim
günlerinde seçilir; aynı çerçevede TI1 için de hesaplanır (nihai paketteki 7,39e-7 ile kontrol).
Altın test günlerindeki POD/POFD yalnız bilgi amaçlıdır.

Çalıştırma (dondurma veritabanında, yalnız okuma):
    POSTGRES_DB=Turbulence-db-dondurma turbulans-birlesik-esik --kesme 2026-10-18 --cikti <klasör>
"""

import argparse
import os
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from turbulans_radar.ml.degerlendirme import bir_se_esigi, ikili_metrikler

CIKTI_ADI = "birlesik_esik.json"
TI1_RISK_ESIGI = 7e-7


def esikleri_sec(y, ti1, birlesik, gunler, altin_maskesi, tekrar=None) -> dict:
    y, ti1, birlesik = np.asarray(y, dtype=int), np.asarray(ti1, dtype=float), np.asarray(birlesik, dtype=float)
    gunler, altin = np.asarray(gunler), np.asarray(altin_maskesi, dtype=bool)
    egitim, gecerli = ~altin, np.isfinite(birlesik)
    ti1_kurali = bir_se_esigi(y[egitim], ti1[egitim], gunler[egitim], tekrar)
    e, t = egitim & gecerli, altin & gecerli
    birlesik_kurali = bir_se_esigi(y[e], birlesik[e], gunler[e], tekrar)
    return {
        "veri": {
            "egitim_ornek": int(egitim.sum()),
            "egitim_gun": int(len(set(gunler[egitim]))),
            "birlesik_gecerli_egitim_ornek": int(e.sum()),
            "altin_ornek": int(t.sum()),
            "altin_gun": int(len(set(gunler[t]))),
        },
        "ti1_kontrol": ti1_kurali,
        "birlesik_edr": birlesik_kurali,
        "altin_gunler": {
            "birlesik_edr": ikili_metrikler(y[t], birlesik[t], birlesik_kurali["esik"]),
            "ti1_7e-7": ikili_metrikler(y[t], ti1[t], TI1_RISK_ESIGI),
        },
        "egitim_gunleri": {
            "birlesik_edr": ikili_metrikler(y[e], birlesik[e], birlesik_kurali["esik"]),
            "ti1_7e-7": ikili_metrikler(y[e], ti1[e], TI1_RISK_ESIGI),
        },
    }


def markdown_ozeti(rapor) -> str:
    b, k = rapor["birlesik_edr"], rapor["ti1_kontrol"]
    v = rapor["veri"]

    def satir(ad, m):
        return f"| {ad} | {m['esik']:.4g} | {m['pod']:.3f} | {m['pofd']:.3f} | {m['peirce']:.3f} | {m['ornek']} |"

    return (
        "\n".join(
            [
                "# Birleşik EDR rota eşiği (kurul #4 kalanı, protokol §12)",
                "",
                f"Üretim: {rapor['meta']['uretim_zamani']} · commit `{rapor['meta'].get('commit') or '—'}` · veritabanı "
                f"`{rapor['meta']['veritabani']}` · kesme {rapor['meta']['kesme']}. Eğitim {v['egitim_gun']} gün "
                f"({v['egitim_ornek']} örnek; birleşik EDR'si hesaplanan {v['birlesik_gecerli_egitim_ornek']}); altın test "
                f"{v['altin_gun']} gün ({v['altin_ornek']} örnek).",
                "",
                f"**Seçilen eşik (1-SE kuralı):** birleşik EDR ≥ **{b['esik']:.4f}** m^(2/3) s⁻¹ (Peirce-maks eşiği "
                f"{b['peirce_max_esigi']:.4f}, Peirce {b['peirce_max']:.3f}, SE {b['se']:.3f}).",
                "",
                f"**Kontrol:** aynı kural aynı çerçevede TI1 için {k['esik']:.3g} verdi (nihai paket 7,39e-7; Peirce-maks "
                f"{k['peirce_max_esigi']:.3g}).",
                "",
                "| Altın test günleri (bilgi) | Eşik | POD | POFD | Peirce | Örnek |",
                "|---|---|---|---|---|---|",
                satir("Birleşik EDR", rapor["altin_gunler"]["birlesik_edr"]),
                satir("TI1 7e-7", rapor["altin_gunler"]["ti1_7e-7"]),
                "",
                "Eşik ABD ERA5 verisinden seçildi; Türkiye'de beceri ölçülmedi. Birleşik EDR TI1'i de içerir. Rota sapma "
                "kararı TI1'le kalır; bu eşik yalnız uyarı oranının ikinci sütunu içindir (§12).",
                "",
                "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
            ]
        )
        + "\n"
    )


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="Birleşik EDR rota eşiği (protokol §12; yalnız okuma).")
    ayrac.add_argument("--kesme", default="2026-10-18")
    ayrac.add_argument("--tekrar", type=int, default=None)
    ayrac.add_argument("--cikti", required=True)
    arg = ayrac.parse_args(argv)
    from turbulans_radar.depo.veritabani import motor_al
    from turbulans_radar.ml.ml_otomatik_egitim import _atomik_yaz_json, _json_guvenli, degerlendirme_gunleri_maskesi
    from turbulans_radar.ml.sonuc_disa_aktarimi import git_bilgisi, pirep_ornekleri, skorlari_hesapla

    yol = os.path.join(arg.cikti, CIKTI_ADI)
    if os.path.exists(yol):
        raise SystemExit(f"{yol} var: eşik bir kez seçilir, üzerine yazılmaz.")
    X, bilgi = pirep_ornekleri(motor_al(), arg.kesme)
    altin, yontem = degerlendirme_gunleri_maskesi(bilgi["gun"])
    skorlar = skorlari_hesapla(X)
    rapor = {
        "meta": {
            "protokol": "docs/deney_protokolu.md §12",
            "veritabani": os.environ.get("POSTGRES_DB", "—"),
            "kesme": arg.kesme,
            "altin_yontemi": yontem,
            "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
            **git_bilgisi(),
            "uyari": "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
        },
        **esikleri_sec(bilgi["y"], skorlar["TI1"], skorlar["Birleşik EDR"], bilgi["gun"], pd.Series(altin), arg.tekrar),
    }
    rapor = _json_guvenli(rapor)
    os.makedirs(arg.cikti, exist_ok=True)
    _atomik_yaz_json(yol, rapor)
    with open(os.path.join(arg.cikti, "README.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    print(markdown_ozeti(rapor))
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
