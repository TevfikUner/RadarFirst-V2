"""
dedektor_duyarliligi.py
--------------------------
F6: sanal PIREP dedektörünün (fizik/sanal_pirep.py) sentetik izlerle duyarlılık
testi. Dedektörün kendisini ölçer, türbülans becerisini ölçmez.

- Taban iz: OpenAP FlightGenerator (tırmanış, seyir, alçalış), 5 sn örnekleme.
- ADS-B benzeri bozulma: Gauss irtifa gürültüsü + 25 ft kuantizasyon; düşey hıza
  Gauss gürültü. Gürültü düzeyleri varsayımdır ve raporda yazılıdır.
- Olay: seyirde rastgele bir anda bilinen genlikte Gauss biçimli irtifa sapması
  (σ = OLAY_SIGMA_SN) ve onun türevi kadar düşey hız tepkisi.
- Tespit: olay tepesine ±60 sn içinde bir dedektör olayı. Yanlış alarm: olaysız
  izlerde seyir saati başına olay; seyir dışında (tırmanış/alçalış) olay ayrıca sayılır.
- OpenAP FlightPhase etiketleriyle dedektörün seyir maskesinin uyumu ikinci kontrol
  olarak raporlanır (dedektöre bağlanmaz).

    turbulans-sanal-pirep-duyarlilik --cikti docs/rapor/veri
"""

import argparse
import json
import os

import numpy as np
import pandas as pd

from turbulans_radar.fizik.sanal_pirep import METRE_FT, MS_FTDK, _iz_hazirla, olaylari_tespit_et, seyir_maskesi

ADIM_SN = 5
KUANTUM_FT = 25.0
OLAY_SIGMA_SN = 6.0
ESLESME_SN = 60
GENLIKLER_FT = (30, 60, 90, 120, 150, 200, 300)
GURULTULER_FT = (5.0, 15.0, 30.0)
DIKEY_HIZ_GURULTUSU_FTDK = 50.0
BASLANGIC = pd.Timestamp("2026-01-01T00:00:00Z")


def taban_iz(tip="a320") -> pd.DataFrame:
    from openap import FlightGenerator

    ucus = FlightGenerator(tip).complete(dt=ADIM_SN, random=False)
    return pd.DataFrame(
        {
            "t": ucus["t"].to_numpy(dtype=float),
            "irtifa_ft": ucus["altitude"].to_numpy(dtype=float),
            "dikey_hiz_ftdk": ucus["vertical_rate"].to_numpy(dtype=float),
            "hiz_kt": ucus["groundspeed"].to_numpy(dtype=float),
        }
    )


def _iz_df(taban: pd.DataFrame, irtifa_ft, dikey_hiz_ftdk) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "zaman": BASLANGIC + pd.to_timedelta(taban["t"], unit="s"),
            "enlem": 40.0,
            "boylam": 30.0 + taban["t"] * 0.002,
            "baro_irtifa_m": np.asarray(irtifa_ft) / METRE_FT,
            "dikey_hiz": np.asarray(dikey_hiz_ftdk) / MS_FTDK,
        }
    )


def bozulmus_iz(taban, rng, gurultu_ft, genlik_ft=0.0, tepe_sn=None) -> pd.DataFrame:
    t = taban["t"].to_numpy()
    irtifa = taban["irtifa_ft"].to_numpy().copy()
    dikey = taban["dikey_hiz_ftdk"].to_numpy().copy()
    if genlik_ft and tepe_sn is not None:
        isaret = rng.choice([-1.0, 1.0])
        tumsek = np.exp(-0.5 * ((t - tepe_sn) / OLAY_SIGMA_SN) ** 2)
        irtifa += isaret * genlik_ft * tumsek
        dikey += isaret * genlik_ft * tumsek * (-(t - tepe_sn) / OLAY_SIGMA_SN**2) * 60.0
    irtifa = np.round((irtifa + rng.normal(0, gurultu_ft, len(t))) / KUANTUM_FT) * KUANTUM_FT
    dikey = dikey + rng.normal(0, DIKEY_HIZ_GURULTUSU_FTDK, len(t))
    return _iz_df(taban, irtifa, dikey)


def seyir_araligi(taban) -> tuple[float, float]:
    tavan = taban["irtifa_ft"].max()
    seyir = taban.loc[(taban["irtifa_ft"] >= tavan - 50) & (taban["dikey_hiz_ftdk"].abs() < 100), "t"]
    return float(seyir.min()), float(seyir.max())


def tespit_orani(taban, genlik_ft, gurultu_ft, tekrar, rng) -> dict:
    bas, son = seyir_araligi(taban)
    yakalanan = 0
    for _ in range(tekrar):
        tepe = rng.uniform(bas + 600, son - 600)
        olaylar, _ = olaylari_tespit_et(bozulmus_iz(taban, rng, gurultu_ft, genlik_ft, tepe))
        if len(olaylar):
            fark = (pd.to_datetime(olaylar["zaman"]) - (BASLANGIC + pd.Timedelta(seconds=tepe))).dt.total_seconds()
            yakalanan += int((fark.abs() <= ESLESME_SN).any())
    return {"genlik_ft": genlik_ft, "gurultu_ft": gurultu_ft, "tekrar": tekrar, "tespit_orani": yakalanan / tekrar}


def yanlis_alarm(taban, gurultu_ft, tekrar, rng) -> dict:
    bas, son = seyir_araligi(taban)
    seyir_sn = olay = seyir_disi = 0.0
    for _ in range(tekrar):
        olaylar, ozet = olaylari_tespit_et(bozulmus_iz(taban, rng, gurultu_ft))
        seyir_sn += ozet["seyir_suresi_sn"]
        if len(olaylar):
            sn = (pd.to_datetime(olaylar["zaman"]) - BASLANGIC).dt.total_seconds()
            olay += len(olaylar)
            seyir_disi += int(((sn < bas) | (sn > son)).sum())
    return {
        "gurultu_ft": gurultu_ft,
        "tekrar": tekrar,
        "seyir_saati": seyir_sn / 3600.0,
        "olay": int(olay),
        "seyir_saati_basina_yanlis_alarm": olay / (seyir_sn / 3600.0) if seyir_sn else float("nan"),
        "seyir_disi_olay": int(seyir_disi),
    }


def faz_uyumu(taban, rng, gurultu_ft=15.0) -> dict:
    from openap import FlightPhase

    iz = bozulmus_iz(taban, rng, gurultu_ft)
    hazir = seyir_maskesi(_iz_hazirla(iz)).set_index("zaman")["seyirde"]
    maske = pd.to_datetime(iz["zaman"], utc=True).map(hazir).fillna(False).to_numpy(dtype=bool)
    faz = FlightPhase()
    faz.set_trajectory(
        taban["t"].to_numpy(),
        iz["baro_irtifa_m"].to_numpy() * METRE_FT,
        taban["hiz_kt"].to_numpy(),
        iz["dikey_hiz"].to_numpy() * MS_FTDK,
    )
    openap_seyir = np.asarray(faz.phaselabel()) == "CR"
    return {
        "dedektor_seyir_noktasi": int(maske.sum()),
        "openap_seyir_noktasi": int(openap_seyir.sum()),
        "dedektor_seyirinin_openap_cr_orani": float(openap_seyir[maske].mean()) if maske.any() else float("nan"),
        "openap_cr_nin_dedektor_seyir_orani": float(maske[openap_seyir].mean()) if openap_seyir.any() else float("nan"),
    }


def duyarlilik_raporu(tekrar=40, tohum=0) -> dict:
    rng = np.random.default_rng(tohum)
    taban = taban_iz()
    return {
        "varsayimlar": {
            "tip": "a320 (OpenAP FlightGenerator, random=False)",
            "adim_sn": ADIM_SN,
            "kuantum_ft": KUANTUM_FT,
            "olay_sigma_sn": OLAY_SIGMA_SN,
            "dikey_hiz_gurultusu_ftdk": DIKEY_HIZ_GURULTUSU_FTDK,
            "eslesme_sn": ESLESME_SN,
            "not": "Gürültü düzeyleri ve olay biçimi varsayımdır; gerçek ADS-B hata dağılımı ölçülmedi.",
        },
        "tespit": [
            tespit_orani(taban, genlik, gurultu, tekrar, rng) for gurultu in GURULTULER_FT for genlik in GENLIKLER_FT
        ],
        "yanlis_alarm": [yanlis_alarm(taban, gurultu, tekrar, rng) for gurultu in GURULTULER_FT],
        "faz_uyumu": faz_uyumu(taban, rng),
        "uyari": "Dedektörün sentetik duyarlılığıdır; türbülans becerisi değildir, eşikler bununla ayarlanmadı.",
    }


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="F6: sanal PIREP dedektörünün sentetik duyarlılık testi.")
    ayristirici.add_argument("--cikti", required=True, help="Sonuç klasörü (sanal_pirep_duyarlilik.json)")
    ayristirici.add_argument("--tekrar", type=int, default=40)
    argumanlar = ayristirici.parse_args(argv)
    rapor = duyarlilik_raporu(argumanlar.tekrar)
    os.makedirs(argumanlar.cikti, exist_ok=True)
    with open(os.path.join(argumanlar.cikti, "sanal_pirep_duyarlilik.json"), "w", encoding="utf-8") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2)
    print(json.dumps(rapor, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
