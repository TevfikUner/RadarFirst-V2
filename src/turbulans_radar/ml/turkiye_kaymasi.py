"""
turkiye_kaymasi.py
-------------------
Kurul raporu #10 / VER-08: model yalnız ABD PIREP'leriyle eğitildi; Türkiye'de etiketli
doğrulama yok. Etiket olmadan da şu ölçülebilir: Türkiye girdileri (7 seviyeli Ocak 2019
ERA5 küpünde rastgele seyir noktaları) modelin eğitim verisinin (163 dondurma günü, ABD
PIREP noktaları) desteği içinde mi? Özellik başına PSI/KS (`ml/kayma_izleme.py`) ve ABD
dağılımının %0,5–%99,5 aralığı dışında kalan oran verilir. İki kontrol: ABD'nin yalnız kış
(Aralık–Şubat) günleri (mevsim etkisi) ve ABD içinde altın günler − eğitim günleri ("kayma
yok" ölçeği). Bu bir girdi örtüşmesi ölçümüdür; Türkiye'de beceri ölçümü DEĞİLDİR.
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import contextlib
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from turbulans_radar.ml.kayma_izleme import kayma_raporu
from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI

CIKTI_ADI = "turkiye_kaymasi.json"
VARSAYILAN_KUP = "ocak_2019_turbulans_7seviye.nc"
VARSAYILAN_NOKTA = 20000
FL_ARALIGI = (280, 420)
DESTEK_YUZDELIKLERI = (0.5, 99.5)
KIS_AYLARI = {"12", "01", "02"}
ALTIN_DOSYASI = Path(__file__).with_name("altin_test_gunleri.json")


def turkiye_noktalari(veri_kupu, nokta_sayisi=VARSAYILAN_NOKTA, fl_araligi=FL_ARALIGI, tohum=0) -> pd.DataFrame:
    """Küpün iç bölgesinde (kenardan 0,5° içeride), zamanda sürekli rastgele seyir noktaları."""
    rng = np.random.default_rng(tohum)
    enlem, boylam = veri_kupu["latitude"].values, veri_kupu["longitude"].values
    zamanlar = pd.DatetimeIndex(veri_kupu["valid_time"].values)
    return pd.DataFrame(
        {
            "zaman": pd.to_datetime(rng.uniform(zamanlar[0].value, zamanlar[-1].value, nokta_sayisi).astype("int64")),
            "enlem": rng.uniform(enlem.min() + 0.5, enlem.max() - 0.5, nokta_sayisi),
            "boylam": rng.uniform(boylam.min() + 0.5, boylam.max() - 0.5, nokta_sayisi),
            "irtifa_m": rng.uniform(*fl_araligi, nokta_sayisi) * 100 * 0.3048,
        }
    )


def destek_disi_oranlari(
    referans: pd.DataFrame, guncel: pd.DataFrame, sutunlar, yuzdelikler=DESTEK_YUZDELIKLERI
) -> dict:
    """Her özellik için güncel örneklerin referansın [alt, üst] yüzdelik aralığı dışında kalan oranı ve
    en az bir özellikte dışarıda kalan oran."""
    disarida_herhangi = np.zeros(len(guncel), dtype=bool)
    ozellikler = {}
    for sutun in sutunlar:
        alt, ust = np.percentile(referans[sutun].to_numpy(dtype=float), yuzdelikler)
        degerler = guncel[sutun].to_numpy(dtype=float)
        disarida = (degerler < alt) | (degerler > ust)
        disarida_herhangi |= disarida
        ozellikler[sutun] = {"alt": float(alt), "ust": float(ust), "disarida_orani": float(disarida.mean())}
    return {
        "yuzdelikler": list(yuzdelikler),
        "ozellikler": ozellikler,
        "herhangi_disarida_orani": float(disarida_herhangi.mean()),
    }


def ozet_istatistik(df: pd.DataFrame, sutunlar) -> dict:
    return {s: {k: float(v) for k, v in df[s].describe(percentiles=[0.05, 0.5, 0.95]).items()} for s in sutunlar}


def karsilastir(abd: pd.DataFrame, turkiye: pd.DataFrame, altin_gunleri, sutunlar=MODEL_OZELLIK_SUTUNLARI) -> dict:
    sutunlar = list(sutunlar)
    kis = abd[abd["gun"].str[5:7].isin(KIS_AYLARI)]
    altin = abd["gun"].isin(altin_gunleri)
    return {
        "ornek": {"abd": int(len(abd)), "abd_kis": int(len(kis)), "turkiye": int(len(turkiye))},
        "turkiye_abd": {
            **kayma_raporu(abd[sutunlar], turkiye[sutunlar], sutunlar),
            "destek": destek_disi_oranlari(abd, turkiye, sutunlar),
        },
        "turkiye_abd_kis": {
            **kayma_raporu(kis[sutunlar], turkiye[sutunlar], sutunlar),
            "destek": destek_disi_oranlari(kis, turkiye, sutunlar),
        },
        "kontrol_abd_altin_egitim": {
            **kayma_raporu(abd.loc[~altin, sutunlar], abd.loc[altin, sutunlar], sutunlar),
            "destek": destek_disi_oranlari(abd.loc[~altin], abd.loc[altin], sutunlar),
        },
        "dagilimlar": {"abd": ozet_istatistik(abd, sutunlar), "turkiye": ozet_istatistik(turkiye, sutunlar)},
    }


def _psi_satiri(ad, rapor, sutunlar) -> str:
    hucreler = [f"{rapor['ozellikler'][s]['psi']:.2f}" for s in sutunlar]
    return f"| {ad} | " + " | ".join(hucreler) + f" | %{100 * rapor['destek']['herhangi_disarida_orani']:.1f} |"


def markdown_ozeti(rapor) -> str:
    sutunlar = list(MODEL_OZELLIK_SUTUNLARI)
    o = rapor["sonuc"]
    satirlar = [
        "# Türkiye girdilerinin ABD eğitim verisine göre kayması (VER-08)",
        "",
        f"Üretim: {rapor['meta']['uretim_zamani']} · commit `{rapor['meta'].get('commit') or '—'}` · Türkiye: "
        f"`{rapor['veri']['kup']}` (7 seviye, Ocak 2019), {o['ornek']['turkiye']} rastgele nokta (FL{FL_ARALIGI[0]}–"
        f"{FL_ARALIGI[1]}, iç bölge, zamanda sürekli). ABD: 163 dondurma günündeki eşleşmiş seyir PIREP örnekleri "
        f"({o['ornek']['abd']}; kış günleri {o['ornek']['abd_kis']}).",
        "",
        "PSI (0,10 üstü orta, 0,25 üstü belirgin; kaba kural, kalibre değil) ve en az bir özellikte ABD'nin "
        f"%{DESTEK_YUZDELIKLERI[0]:g}–%{DESTEK_YUZDELIKLERI[1]:g} aralığı dışında kalan oran:",
        "",
        "| Karşılaştırma | " + " | ".join(sutunlar) + " | Destek dışı (herhangi) |",
        "|---|" + "---|" * (len(sutunlar) + 1),
        _psi_satiri("Türkiye − ABD (tüm)", o["turkiye_abd"], sutunlar),
        _psi_satiri("Türkiye − ABD (kış)", o["turkiye_abd_kis"], sutunlar),
        _psi_satiri("Kontrol: ABD altın − eğitim günleri", o["kontrol_abd_altin_egitim"], sutunlar),
        "",
        "**Okuma.** Kontrol satırı aynı dağılım içindeki gürültü düzeyidir. Türkiye satırları bunun belirgin üstündeyse "
        "girdi dağılımı kaymıştır; modelin ABD'de ölçülen becerisi Türkiye'ye taşınamaz. Türkiye noktaları ızgaradan "
        "rastgele, ABD örnekleri PIREP konumlarıdır (trafik ve raporlama yanlılığı); fark kısmen bu seçimden gelir. Bu "
        "bir girdi örtüşmesi ölçümüdür, Türkiye'de beceri ölçümü değildir.",
        "",
        "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
    ]
    return "\n".join(satirlar) + "\n"


def calistir(cikti: str, kup_yolu=VARSAYILAN_KUP, nokta_sayisi=VARSAYILAN_NOKTA, motor=None) -> dict:
    import xarray as xr

    from turbulans_radar.ml.ml_otomatik_egitim import _atomik_yaz_json, _json_guvenli
    from turbulans_radar.ml.rf_deneyi import eslesmis_ornekleri_oku, tam_ozellikli
    from turbulans_radar.ml.sonuc_disa_aktarimi import git_bilgisi
    from turbulans_radar.ml.turbulans_ml_modeli import ozellikleri_cikar
    from turbulans_radar.ml.yeni_gun_degerlendirmesi import dondurma_gunleri

    yol = os.path.join(cikti, CIKTI_ADI)
    if os.path.exists(yol):
        raise SystemExit(f"{yol} var; üzerine yazılmaz.")
    abd = tam_ozellikli(eslesmis_ornekleri_oku(motor), MODEL_OZELLIK_SUTUNLARI)
    abd = abd[abd["gun"].isin(dondurma_gunleri())].reset_index(drop=True)
    with xr.open_dataset(kup_yolu) as kup:
        kup = kup.load()
    noktalar = turkiye_noktalari(kup, nokta_sayisi)
    with contextlib.redirect_stdout(io.StringIO()):
        turkiye = tam_ozellikli(ozellikleri_cikar(noktalar, kup), MODEL_OZELLIK_SUTUNLARI)
    altin = set(json.loads(ALTIN_DOSYASI.read_text(encoding="utf-8"))["gunler"])
    rapor = _json_guvenli(
        {
            "meta": {
                "amac": "Kurul raporu #10 (VER-08): Türkiye girdilerinin ABD eğitim verisine göre kayması",
                "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
                **git_bilgisi(),
                "uyari": "Girdi örtüşmesi ölçümüdür, Türkiye'de beceri ölçümü değildir. Çıktılar sertifikalı EDR "
                "değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
            },
            "veri": {"kup": os.path.basename(kup_yolu), "istenen_nokta": nokta_sayisi},
            "sonuc": karsilastir(abd, turkiye, altin),
        }
    )
    os.makedirs(cikti, exist_ok=True)
    _atomik_yaz_json(yol, rapor)
    with open(os.path.join(cikti, "README.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="Türkiye girdilerinin ABD eğitim verisine göre kayması (PSI/KS).")
    ayristirici.add_argument("--kup", default=VARSAYILAN_KUP)
    ayristirici.add_argument("--nokta", type=int, default=VARSAYILAN_NOKTA)
    ayristirici.add_argument("--cikti", required=True)
    argumanlar = ayristirici.parse_args(argv)
    print(markdown_ozeti(calistir(argumanlar.cikti, argumanlar.kup, argumanlar.nokta)))


if __name__ == "__main__":
    ana()
