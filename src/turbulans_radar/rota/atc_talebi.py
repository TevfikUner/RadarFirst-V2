"""
atc_talebi.py
----------------
ATC talep önerisi: rota_optimizasyonu'nun ZATEN değerlendirdiği adaylardan, pilotun/dispeçerin ATC'den
isteyeceği en fazla üç seçenek. Kararı değiştirmez: 1. seçenek her zaman önerilen (seçilmiş) rotadır,
kalanlar aynı seçim ölçütüyle (önce riskli nokta, sonra yakıt) sıralanır. Seviye seçenekleri yalnız
yarım daire kuralına uygun seviyelerden olur (rota/ucus_seviyeleri.py). Sistem trafiği bilmez; her
seçenek ATC onayına tabidir.
"""

import math

from turbulans_radar.rota import ucus_seviyeleri
from turbulans_radar.rota.geometri import yanal_sapma_yonu

NM_KM = 1.852
AZAMI_SECENEK = 3
YANAL_YUVARLAMA_NM = 5
GEREKCE = "DUE TO TURBULENCE"
NOT_METNI = "Sistem trafiği bilmez; ATC reddederse sıradaki seçenek."
YON_ADI = {"R": "RIGHT", "L": "LEFT"}
YON_TR = {"R": "sağ", "L": "sol"}


def seviye_talebi(fl: int) -> str:
    return f"REQUEST FL{int(fl):03d} {GEREKCE}"


def yanal_talep(sapma_nm: int, yon: str) -> str:
    return f"REQUEST {int(sapma_nm)}NM {YON_ADI[yon]} OF TRACK {GEREKCE}"


def rota_talebi(fl: int | None = None) -> str:
    return f"REQUEST FL{int(fl):03d} AND REROUTE {GEREKCE}" if fl is not None else f"REQUEST REROUTE {GEREKCE}"


def yanal_sapma_nm(sapma_km: float) -> int:
    nm = float(sapma_km) / NM_KM
    return max(YANAL_YUVARLAMA_NM, int(math.ceil(nm / YANAL_YUVARLAMA_NM) * YANAL_YUVARLAMA_NM))


def _fl(irtifa_m) -> int:
    return int(round(float(irtifa_m) / 0.3048 / 100.0))


def _talep(aday, planli_fl: int, arama_uzayi: str) -> dict | None:
    fl = _fl(aday["irtifa_m"])
    strateji = aday["strateji"]
    if strateji.startswith("irtifa_"):
        if arama_uzayi == "ats":
            return {
                "tur": "seviye_rota",
                "hedef": f"FL{fl:03d} + ATS rotası",
                "hedef_fl": fl,
                "talep_metni": rota_talebi(fl),
            }
        return {"tur": "seviye", "hedef": f"FL{fl:03d}", "hedef_fl": fl, "talep_metni": seviye_talebi(fl)}
    if fl != planli_fl:
        return None
    if strateji.startswith("ats_"):
        return {"tur": "rota", "hedef": "ATS ağında alternatif rota", "hedef_fl": fl, "talep_metni": rota_talebi()}
    if strateji.startswith("yanal"):
        yon = yanal_sapma_yonu(aday["enlem"], aday["boylam"])
        if yon is None:
            return None
        nm = yanal_sapma_nm(aday["yanal_sapma_km"])
        return {
            "tur": "yanal",
            "hedef": f"{nm} NM {YON_TR[yon]}",
            "hedef_fl": fl,
            "sapma_nm": nm,
            "yon": yon,
            "talep_metni": yanal_talep(nm, yon),
        }
    return None


def _bos(neden: str) -> dict:
    return {"gerekli": False, "neden": neden, "secenekler": [], "aciklama": NOT_METNI}


def atc_talep_onerisi(
    adaylar, en_iyi, normal, yakit_fonksiyonu, seviye, arama_uzayi="koridor", guvenli_rota_bulundu_mu=True
) -> dict:
    """adaylar: _kacinma_adaylari çıktısı; en_iyi: zaten seçilmiş rota (değiştirilmez)."""
    yasal = set(ucus_seviyeleri.yasal_seyir_seviyeleri(seviye["manyetik_iz"], seviye.get("azami_fl")))
    planli_fl = int(seviye["fl"])
    if not guvenli_rota_bulundu_mu:
        return _bos("Sert kısıtlara uyan bir seçenek bulunamadı; ATC talebi önerilmiyor.")
    if en_iyi is normal:
        risksiz = normal["riskli_sayisi"] == 0 and normal["sigmet_ihlali"] == 0 and normal["kisitli_saha_ihlali"] == 0
        return _bos(
            "Planlanan rota ve seviyede riskli nokta ya da kısıt yok; ATC talebi gerekmiyor."
            if risksiz
            else "Seçim kuralı planlanan rotayı tuttu; ATC talebi önerilmiyor."
        )
    secilen_talep = _talep(en_iyi, planli_fl, arama_uzayi)
    if secilen_talep is None or secilen_talep["hedef_fl"] not in yasal:
        return _bos("Önerilen rota için ATC talep metni üretilemedi.")

    normal_saniye = normal["saniye"] + normal["ekstra_saniye"]
    normal_yakit = yakit_fonksiyonu(normal)
    uygun = [a for a in adaylar if a["sigmet_ihlali"] == 0 and a["kisitli_saha_ihlali"] == 0]
    siralama = sorted(uygun, key=lambda a: (a is not en_iyi, a["riskli_sayisi"], yakit_fonksiyonu(a)))
    secenekler, metinler = [], set()
    for aday in siralama:
        talep = _talep(aday, planli_fl, arama_uzayi)
        if talep is None or talep["hedef_fl"] not in yasal or talep["talep_metni"] in metinler:
            continue
        metinler.add(talep["talep_metni"])
        yakit = yakit_fonksiyonu(aday)
        secenekler.append(
            {
                "sira": len(secenekler) + 1,
                "strateji": aday["strateji"],
                "secilen": aday is en_iyi,
                **talep,
                "kalan_riskli_nokta": int(aday["riskli_sayisi"]),
                "ek_sure_dk": (aday["saniye"] + aday["ekstra_saniye"] - normal_saniye) / 60.0,
                "ek_yakit_kg": yakit - normal_yakit,
                "ek_yakit_yuzde": 100.0 * (yakit - normal_yakit) / normal_yakit if normal_yakit else 0.0,
            }
        )
        if len(secenekler) == AZAMI_SECENEK:
            break
    return {"gerekli": True, "neden": None, "secenekler": secenekler, "aciklama": NOT_METNI}
