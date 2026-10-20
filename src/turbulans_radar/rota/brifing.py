"""Rota noktalarının paketlenmesi, riskli bölümler, kabin önerisi ve brifing kartı (rota_optimizasyonu'ndan ayrıldı)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.fizik.cografya import mesafe_km as buyuk_daire_mesafesi_km
from turbulans_radar.fizik.iz_bulutu import duyarli_nokta_sayisi
from turbulans_radar.fizik.ti1_esigi import etkin_ti1_esigi
from turbulans_radar.rota.geometri import NM_KM
from turbulans_radar.rota.risk_katmanlari import rota_eslesmesi


def _ucus_seviyesi(irtifa_m) -> int:
    return int(round(float(irtifa_m) / 0.3048 / 100.0))


def _riskli_maskesi(ti1):
    """Nokta başına True/False; TI1 hesaplanamayan (kapsam dışı) nokta None."""
    if ti1 is None:
        return None
    ti1 = np.asarray(ti1, dtype=float)
    with np.errstate(invalid="ignore"):
        esik = etkin_ti1_esigi()
        return [None if np.isnan(t) else bool(t >= esik) for t in ti1]


def _sonlu(deger):
    return None if deger is None or not np.isfinite(deger) else float(deger)


def _noktalari_paketle(enlemler, boylamlar, irtifa_m, zamanlar, ti1=None, birlesik_edr=None):
    riskli = _riskli_maskesi(ti1) or [None] * len(enlemler)
    ti1 = [None] * len(enlemler) if ti1 is None else ti1
    birlesik_edr = [None] * len(enlemler) if birlesik_edr is None else birlesik_edr
    fl = _ucus_seviyesi(irtifa_m)
    return [
        {
            "enlem": float(e),
            "boylam": float(b),
            "irtifa_m": float(irtifa_m),
            "fl": fl,
            "zaman": z.isoformat(),
            "ti1": _sonlu(t),
            "birlesik_edr": _sonlu(d),
            "riskli": r,
        }
        for e, b, z, t, d, r in zip(enlemler, boylamlar, zamanlar, ti1, birlesik_edr, riskli, strict=True)
    ]


def _nokta_hucre_uzunluklari_km(enlemler, boylamlar):
    """Her noktanın temsil ettiği rota uzunluğu: komşu bacakların yarıları."""
    bacak = np.array(
        [
            buyuk_daire_mesafesi_km(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
            for i in range(len(enlemler) - 1)
        ]
    )
    hucre = np.zeros(len(enlemler))
    hucre[:-1] += bacak / 2
    hucre[1:] += bacak / 2
    return hucre


def _edr_siddeti(edr):
    if edr is None or not np.isfinite(edr):
        return None
    if edr >= config.EDR_ESIK_SIDDETLI:
        return "şiddetli"
    if edr >= config.EDR_ESIK_ORTA:
        return "orta"
    if edr >= config.EDR_ESIK_HAFIF:
        return "hafif"
    return "hafif altı"


def riskli_bolumler(aday) -> list[dict] | None:
    """Ardışık riskli noktalar tek bölüm: başlangıç/bitiş UTC, FL, NM, dakika,
    en yüksek TI1 ve birleşik EDR. RISKLI_BOLUM_MIN_NM'den kısa bölümler
    atılır (varsayılan 0: kalibre edilmedi, mevcut davranış). Risk hesaplanmadıysa None."""
    maske = _riskli_maskesi(aday.get("ti1"))
    if maske is None or all(m is None for m in maske):
        return None
    hucre_km = _nokta_hucre_uzunluklari_km(aday["enlem"], aday["boylam"])
    zamanlar = list(aday["zamanlar"])
    ti1 = np.asarray(aday["ti1"], dtype=float)
    birlesik = np.asarray(
        aday.get("birlesik_edr") if aday.get("birlesik_edr") is not None else np.full(len(ti1), np.nan)
    )
    bolumler, i = [], 0
    while i < len(maske):
        if not maske[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(maske) and maske[j + 1]:
            j += 1
        uzunluk_nm = float(hucre_km[i : j + 1].sum()) / NM_KM
        if uzunluk_nm >= config.RISKLI_BOLUM_MIN_NM:
            baslangic = zamanlar[max(i - 1, 0)] + (zamanlar[i] - zamanlar[max(i - 1, 0)]) / 2
            bitis = zamanlar[j] + (zamanlar[min(j + 1, len(zamanlar) - 1)] - zamanlar[j]) / 2
            maks_edr = float(np.nanmax(birlesik[i : j + 1])) if np.isfinite(birlesik[i : j + 1]).any() else None
            bolumler.append(
                {
                    "baslangic_utc": pd.Timestamp(baslangic).isoformat(),
                    "bitis_utc": pd.Timestamp(bitis).isoformat(),
                    "fl": _ucus_seviyesi(aday["irtifa_m"]),
                    "uzunluk_nm": uzunluk_nm,
                    "sure_dk": (pd.Timestamp(bitis) - pd.Timestamp(baslangic)).total_seconds() / 60.0,
                    "baslangic_enlem": float(aday["enlem"][i]),
                    "baslangic_boylam": float(aday["boylam"][i]),
                    "bitis_enlem": float(aday["enlem"][j]),
                    "bitis_boylam": float(aday["boylam"][j]),
                    "maks_ti1": float(np.nanmax(ti1[i : j + 1])),
                    "maks_birlesik_edr": maks_edr,
                    "beklenen_siddet": _edr_siddeti(maks_edr),
                }
            )
        i = j + 1
    return bolumler


def kabin_onerisi(bolumler) -> dict | None:
    """Yalnızca önerilen rotada kalan risk varsa: ilk bölüm için dispeçer/kabin
    dilinde öneri. Başlangıç tek bir saat değil, ±KABIN_PENCERE_PAYI_DK'lik
    pencere olarak verilir (pay kalibre edilmedi). Karar kaptanındır;
    sertifikalı EDR değildir."""
    if not bolumler:
        return None
    ilk = bolumler[0]
    toplam_dk = sum(b["sure_dk"] for b in bolumler)
    pay = pd.Timedelta(minutes=config.KABIN_PENCERE_PAYI_DK)
    pencere_baslangic = pd.Timestamp(ilk["baslangic_utc"]) - pay
    pencere_bitis = pd.Timestamp(ilk["baslangic_utc"]) + pay
    metin = (
        f"Öneri (karar kaptanındır): FL{ilk['fl']:03d}'te olası türbülansın ~{pencere_baslangic:%H:%M}–"
        f"{pencere_bitis:%H:%M}Z arasında başlaması ve ~{ilk['sure_dk']:.0f} dk sürmesi bekleniyor. Kabin "
        "servisinin bu pencereden önce tamamlanması ve emniyet kemeri işaretinin açılması değerlendirilebilir."
    )
    if len(bolumler) > 1:
        metin += f" Rotada toplam {len(bolumler)} bölüm, ~{toplam_dk:.0f} dk."
    return {
        "metin": metin,
        "ilk_bolum_baslangic_utc": ilk["baslangic_utc"],
        "pencere_baslangic_utc": pencere_baslangic.isoformat(),
        "pencere_bitis_utc": pencere_bitis.isoformat(),
        "pencere_payi_dk": float(config.KABIN_PENCERE_PAYI_DK),
        "pencere_payi_notu": "Parametrik varsayım, kalibre edilmedi.",
        "bolum_sayisi": len(bolumler),
        "toplam_sure_dk": toplam_dk,
    }


_BRIFING_STRATEJI = {
    "yok": "planlanan rota korunur",
    "yanal": "yanal sapma",
    "irtifa_yukari": "tırmanma",
    "irtifa_asagi": "alçalma",
    "ats_alternatif": "ATS alternatifi",
}


_SIDDET_SIRASI = ("hafif altı", "hafif", "orta", "şiddetli")


def _kutle_bandi_metni(sonuc) -> str:
    bant = sonuc.get("yakit_tasarrufu_yuzde_araligi") or {}
    if bant.get("en_dusuk") is None or round(bant["en_dusuk"], 1) == round(bant["en_yuksek"], 1):
        return ""
    oranlar = bant["kutle_oranlari"]
    return (
        f" (kütle %{100 * oranlar[0]:.0f}–{100 * oranlar[-1]:.0f} MTOW: "
        f"%{-bant['en_yuksek']:+.1f}…%{-bant['en_dusuk']:+.1f})"
    )


def iz_bulutu_seviye_bilgisi(aday, veri_kupu, fark_fl=(-20, 20)) -> dict | None:
    sayi = aday.get("iz_bulutu_sayisi")
    if not sayi:
        return None
    fl = _ucus_seviyesi(aday["irtifa_m"])
    secenekler = []
    for fark in fark_fl:
        irtifa_m = (fl + fark) * 100 * 0.3048
        eslesme = rota_eslesmesi(aday["enlem"], aday["boylam"], irtifa_m, aday["zamanlar"], veri_kupu)
        secenekler.append({"fl": fl + fark, "duyarli_nokta_sayisi": duyarli_nokta_sayisi(eslesme["iz_bulutu_duyarli"])})
    return {
        "fl": fl,
        "duyarli_nokta_sayisi": int(sayi),
        "secenekler": secenekler,
        "aciklama": (
            "Bilgi: önerilen rotanın yatay izi ±2000 ft'te kalıcı iz bulutu duyarlılığı (Schmidt-Appleman + buza "
            "göre doygunluk, ERA5 nemi). Yakıt, yarım daire kuralı ve ATC değerlendirilmedi; rota kararına girmez. "
            "Duyarlılık göstergesidir, gözlenmiş iz bulutu değildir."
        ),
    }


def brifing_karti(sonuc) -> list[str]:
    """Var olan sonucun 3 satırlık özeti (rota, kalan risk, kabin); yeni hesap
    yapmaz. Karar destek amaçlıdır; sertifikalı EDR değildir."""
    normal, optimize = sonuc["normal_rota"], sonuc["optimize_rota"]
    strateji = sonuc["kacinma_stratejisi"]
    etiket = next((v for k, v in _BRIFING_STRATEJI.items() if strateji.startswith(k)), strateji)
    if normal["riskli_nokta_sayisi"] is None:
        rota = f"Rota: FL{optimize['fl']:03d}; türbülans riski hesaplanamadı ({sonuc['ruzgar_verisi_kaynagi']})."
    else:
        rota = (
            f"Rota: {etiket}, FL{optimize['fl']:03d}; riskli nokta {normal['riskli_nokta_sayisi']}→"
            f"{optimize['riskli_nokta_sayisi']}, süre {-sonuc['sure_tasarrufu_dk']:+.0f} dk, "
            f"yakıt %{-sonuc['yakit_tasarrufu_yuzde']:+.1f}{_kutle_bandi_metni(sonuc)}."
        )
    bolumler = optimize["riskli_bolumler"]
    if bolumler is None:
        risk = "Kalan risk: hesaplanamadı."
    elif not bolumler:
        risk = "Kalan risk: önerilen rotada riskli bölüm yok."
    else:
        siddetler = [b["beklenen_siddet"] for b in bolumler if b["beklenen_siddet"] in _SIDDET_SIRASI]
        risk = f"Kalan risk: {len(bolumler)} bölüm, ~{optimize['riskli_sure_dk']:.0f} dk" + (
            f"; en yüksek beklenen şiddet {max(siddetler, key=_SIDDET_SIRASI.index)}." if siddetler else "."
        )
    oneri = sonuc.get("kabin_onerisi")
    if oneri is None:
        kabin = "Kabin: ek öneri yok."
    else:
        baslangic, bitis = pd.Timestamp(oneri["pencere_baslangic_utc"]), pd.Timestamp(oneri["pencere_bitis_utc"])
        kabin = (
            f"Kabin: olası türbülans başlangıcı ~{baslangic:%H:%M}–{bitis:%H:%M}Z, FL{bolumler[0]['fl']:03d}; "
            "servisin öncesinde tamamlanması değerlendirilebilir (karar kaptanındır)."
        )
    return [rota, risk, kabin]
