"""
performans_modeli.py
--------------------
Seyir yakıtı ve NOx için OpenAP (TU Delft, LGPL-3.0; motor verisi ICAO emisyon
bankası, yakıt modeli Acropole) sarmalayıcısı. Yakıt akışı kütleye, TAS'a,
irtifaya ve düşey hıza bağlıdır; kütle seyir boyunca yanan yakıtla azalır.

Başlangıç kütlesi MTOW x ROTA_SEYIR_KUTLE_ORANI'dır: parametrik varsayım,
kalibre edilmedi (yük ve yakıt planı bilinmiyor). Değerler mutlak yakıt değil,
aynı tipteki rotalar arası karşılaştırma içindir.

OpenAP kurulu değilse, tip desteklenmiyorsa ya da ROTA_YAKIT_MODELI='sabit'
ise fonksiyonlar None döner; çağıran sabit tabloya düşer.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from turbulans_radar import config

METRE_FT = 3.28084
MS_KT = 1.943844

OPENAP_TIPLERI = {"A320": "a320", "B738": "b738", "B77W": "b77w", "A359": "a359"}
KAYNAK_NOTU = "OpenAP (LGPL-3.0): kütle, TAS, irtifa ve düşey hıza bağlı yakıt akışı; NOx ICAO emisyon bankasından."


@lru_cache(maxsize=None)
def _modeller(tip: str):
    kod = OPENAP_TIPLERI.get(tip)
    if kod is None:
        return None
    try:
        from openap import Emission, FuelFlow, prop
    except ImportError:
        return None
    return FuelFlow(kod), Emission(kod), prop.aircraft(kod)


def openap_surumu() -> str | None:
    try:
        from importlib.metadata import version

        return version("openap")
    except Exception:
        return None


def kullanilabilir_mi(tip: str) -> bool:
    return config.ROTA_YAKIT_MODELI == "openap" and _modeller(tip) is not None


def baslangic_kutlesi_kg(tip: str, kutle_orani: float | None = None) -> float | None:
    if not kullanilabilir_mi(tip):
        return None
    return float(_modeller(tip)[2]["mtow"]) * (config.ROTA_SEYIR_KUTLE_ORANI if kutle_orani is None else kutle_orani)


def _yakit_akisi_kg_s(tip, kutle_kg, tas_kt, irtifa_ft, dikey_hiz_ftdk=0.0) -> float:
    return float(_modeller(tip)[0].enroute(mass=kutle_kg, tas=tas_kt, alt=irtifa_ft, vs=dikey_hiz_ftdk))


def seyir_yakiti(
    tip: str, sure_s: float, tas_ms: float, irtifa_m: float, adim_s: float = 60.0, kutle_orani: float | None = None
) -> dict | None:
    """Sabit TAS ve irtifada sure_s boyunca yakıt ve NOx (kg). Kütle her adımda
    yanan yakıt kadar azalır. Kullanılamıyorsa None."""
    if not kullanilabilir_mi(tip):
        return None
    _, emisyon, _ = _modeller(tip)
    tas_kt, irtifa_ft = tas_ms * MS_KT, irtifa_m * METRE_FT
    adim_sayisi = max(1, math.ceil(sure_s / adim_s))
    dt = sure_s / adim_sayisi
    kutle = baslangic_kutlesi_kg(tip, kutle_orani)
    yakit = nox = 0.0
    akislar = []
    for _ in range(adim_sayisi):
        akis = _yakit_akisi_kg_s(tip, kutle, tas_kt, irtifa_ft)
        akislar.append(akis)
        yakit += akis * dt
        kutle -= akis * dt
    for deger in np.atleast_1d(emisyon.nox(np.asarray(akislar), tas=tas_kt, alt=irtifa_ft)):
        nox += float(deger) * dt / 1000.0
    return {"yakit_kg": yakit, "nox_kg": nox}


def seviye_degisimi_ek_yakiti(
    tip: str,
    eski_irtifa_m: float,
    yeni_irtifa_m: float,
    tas_ms: float,
    dikey_hiz_ftdk: float,
    kutle_orani: float | None = None,
) -> float | None:
    """Geçici seviyeye gidiş + planlanan seviyeye dönüşte, düşey hızın
    (±dikey_hiz_ftdk) seyre göre ek yakıtı (kg). Tırmanış ek yakıt, alçalış
    eksi (kredi) verir; iki seviyenin ortalama irtifasında hesaplanır.
    Seviye farkının seyir yakıtına etkisi adayın kendi seyir yakıtındadır."""
    if not kullanilabilir_mi(tip):
        return None
    fark_ft = abs(yeni_irtifa_m - eski_irtifa_m) * METRE_FT
    if fark_ft == 0:
        return 0.0
    sure_s = fark_ft / dikey_hiz_ftdk * 60.0
    tas_kt, irtifa_ft = tas_ms * MS_KT, (eski_irtifa_m + yeni_irtifa_m) / 2 * METRE_FT
    kutle = baslangic_kutlesi_kg(tip, kutle_orani)
    seyir = _yakit_akisi_kg_s(tip, kutle, tas_kt, irtifa_ft)
    tirmanis = _yakit_akisi_kg_s(tip, kutle, tas_kt, irtifa_ft, dikey_hiz_ftdk)
    alcalis = _yakit_akisi_kg_s(tip, kutle, tas_kt, irtifa_ft, -dikey_hiz_ftdk)
    return (tirmanis - seyir + alcalis - seyir) * sure_s


def iz_yakiti(tip: str, zaman_sn, tas_ms, irtifa_m, dikey_hiz_hesapla=True) -> dict | None:
    """Değişken TAS ve irtifalı iz (ör. gerçek uçuş) boyunca yakıt ve NOx (kg).
    Bacak başına ortalama TAS/irtifa; dikey_hiz_hesapla ise irtifa farkından düşey
    hız (gürültülü irtifada False: düşey hız 0). Kütle bacak bacak azalır.
    Kullanılamıyorsa ya da sonuç sonlu değilse None."""
    if not kullanilabilir_mi(tip):
        return None
    import numpy as np

    _, emisyon, _ = _modeller(tip)
    zaman_sn, tas_ms, irtifa_m = (np.asarray(d, dtype=float) for d in (zaman_sn, tas_ms, irtifa_m))
    kutle = baslangic_kutlesi_kg(tip)
    yakit = nox = 0.0
    for i in range(len(zaman_sn) - 1):
        dt = zaman_sn[i + 1] - zaman_sn[i]
        if dt <= 0:
            continue
        tas_kt = (tas_ms[i] + tas_ms[i + 1]) / 2 * MS_KT
        irtifa_ft = (irtifa_m[i] + irtifa_m[i + 1]) / 2 * METRE_FT
        dikey = (irtifa_m[i + 1] - irtifa_m[i]) * METRE_FT / (dt / 60.0) if dikey_hiz_hesapla else 0.0
        akis = _yakit_akisi_kg_s(tip, kutle, tas_kt, irtifa_ft, dikey)
        nox += float(emisyon.nox(akis, tas=tas_kt, alt=irtifa_ft)) * dt / 1000.0
        yakit += akis * dt
        kutle -= akis * dt
    if not (np.isfinite(yakit) and np.isfinite(nox)):
        return None
    return {"yakit_kg": float(yakit), "nox_kg": float(nox)}
