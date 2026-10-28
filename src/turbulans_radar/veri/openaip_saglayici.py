"""
openaip_saglayici.py
-----------------------
GERÇEK kısıtlı/yasak saha verisi: openAIP Core API v2 (https://www.openaip.net)
-- ülkelerin AIP ENR 5.x yayınlarından derlenen hava sahaları. Alanlar resmi
OpenAPI şemasından doğrulandı
(api.core.openaip.net/api/schemas/response/airspace/airspace-schema.json):
  type          : 1 Restricted, 2 Danger, 3 Prohibited, 8 TRA, 9 TSA, ...
  lower/upperLimit: value + unit (0 metre, 1 feet, 6 FL) + referenceDatum
                  (0 GND, 1 MSL, 2 STD)
  geometry      : GeoJSON Polygon; activeFrom/activeUntil: ISO 8601

Kimlik: OPENAIP_API_ANAHTARI ('x-openaip-api-key' başlığı; openaip.net profil
sayfasından ücretsiz alınır). Herkese açık dışa aktarım dosyaları artık
anahtarsız indirilemiyor. LİSANS: openAIP verisi CC BY-NC 4.0 -- ticari
olmayan kullanım, atıf gerekli.

Varsayılan olarak Restricted + Prohibited sert kısıt olarak alınır
(OPENAIP_SAHA_TURLERI). GND referanslı (AGL) üst limitler arazi yüksekliği
bilinmediği için OPENAIP_AGL_UST_PAYI_FT kadar yükseltilir (muhafazakâr);
NOTAM ile etkinleşen sahalar NOTAM verisi olmadığından sürekli etkin sayılır.
Çalıştırma (AIRAC döngüsünde, 28 günde bir yenilemek yeterli):
    turbulans-kisitli-saha openaip --ulke TR
    POST /api/v1/kisitli-sahalar/openaip   (yönetici; kuyruğa girer)
"""

import os

import httpx

from turbulans_radar import config
from turbulans_radar.depo.kaynak_durumu import kaynak_durumunu_kaydet
from turbulans_radar.loglama import logger_al
from turbulans_radar.veri.kisitli_saha_saglayici import geojson_ice_aktar
from turbulans_radar.yeniden_deneme import gecici_hatada_yeniden_dene

_logger = logger_al(__name__)

OPENAIP_KAYNAK = "openaip"
# veri_kaynagi_durumlari anahtarı (bkz. api_servisi._kisitli_saha_kontrolu, _openaip_zamanlayicisi).
OPENAIP_DURUM_ANAHTARI = "kisitli:openaip"
_API = "https://api.core.openaip.net/api/airspaces"
_TUR = {
    1: ("KISITLI", "Restricted"),
    2: ("TEHLIKELI", "Danger"),
    3: ("YASAK", "Prohibited"),
    8: ("GECICI", "TRA"),
    9: ("GECICI", "TSA"),
}
_FL, _METRE, _FEET = 6, 0, 1
_GND = 0
_MAKS_FT = 70_000

_yeniden_dene = gecici_hatada_yeniden_dene()


def limit_ft(limit: dict | None, ust: bool) -> int | None:
    """openAIP dikey limitini feet'e çevirir; okunamazsa ya da üst limit
    pratikte sınırsızsa None (taban için yer, tavan için sınırsız)."""
    if not limit or limit.get("value") is None:
        return None
    deger, birim = limit["value"], limit.get("unit")
    if birim == _FL:
        ft = deger * 100.0
    elif birim == _METRE:
        ft = deger / 0.3048
    elif birim == _FEET:
        ft = float(deger)
    else:
        return None
    if limit.get("referenceDatum") == _GND and deger > 0 and ust:
        ft += config.OPENAIP_AGL_UST_PAYI_FT
    ft = max(0, round(ft))
    return None if ust and ft > _MAKS_FT else min(ft, _MAKS_FT)


def openaip_ozelligine_cevir(ham: dict, turler) -> dict | None:
    """openAIP hava sahası -> kisitli_saha_saglayici GeoJSON Feature'ı."""
    tur = ham.get("type")
    geometri = ham.get("geometry") or {}
    if tur not in turler or tur not in _TUR or geometri.get("type") != "Polygon" or not ham.get("_id"):
        return None
    taban, tavan = limit_ft(ham.get("lowerLimit"), ust=False), limit_ft(ham.get("upperLimit"), ust=True)
    if taban is not None and tavan is not None and taban > tavan:
        return None
    bizim_tur, openaip_turu = _TUR[tur]
    notlar = ["openAIP (CC BY-NC 4.0)"]
    if ham.get("byNotam"):
        notlar.append("NOTAM ile etkinleşir; NOTAM verisi olmadığından sürekli etkin sayıldı")
    return {
        "type": "Feature",
        "geometry": geometri,
        "properties": {
            "kimlik": ham["_id"],
            "ad": f"{ham.get('name') or ham['_id']} ({openaip_turu})",
            "tur": bizim_tur,
            "taban_ft": taban,
            "tavan_ft": tavan,
            "baslangic": ham.get("activeFrom"),
            "bitis": ham.get("activeUntil"),
            "aciklama": "; ".join(notlar),
        },
    }


@_yeniden_dene
def _sayfa_getir(ulke: str, sayfa: int, api_anahtari: str) -> dict:
    yanit = httpx.get(
        _API,
        params={"country": ulke, "page": sayfa, "limit": 1000},
        headers={"x-openaip-api-key": api_anahtari},
        timeout=60,
    )
    yanit.raise_for_status()
    return yanit.json()


def openaip_sahalarini_getir(ulke: str, api_anahtari: str, getirici=_sayfa_getir) -> list[dict]:
    kayitlar: list[dict] = []
    sayfa = 1
    while sayfa:
        yanit = getirici(ulke, sayfa, api_anahtari)
        kayitlar += yanit.get("items") or []
        sayfa = yanit.get("nextPage")
    return kayitlar


def openaip_ice_aktar(ulkeler=None, api_anahtari=None, turler=None, getirici=_sayfa_getir, motor=None) -> dict:
    """Ülkelerin sahalarını çekip 'openaip' kaynağı olarak TAM yeniler (bir
    önceki çekimde olup artık yayınlanmayan saha kaldırılır). Hiç saha
    gelmezse hata -- boş bir yanıt mevcut veriyi silmesin. Sonuç (başarı ya da
    hata) veri_kaynagi_durumlari'na yazılır: sağlık kontrolü bayatlığı, API
    zamanlayıcısı bir sonraki yenileme zamanını buradan görür."""
    try:
        sonuc = _openaip_ice_aktar(ulkeler, api_anahtari, turler, getirici, motor)
    except Exception as hata:
        _durumu_kaydet(False, f"{type(hata).__name__}: {hata}", motor=motor)
        raise
    _durumu_kaydet(True, ozet=sonuc, motor=motor)
    return sonuc


def _durumu_kaydet(basarili, hata=None, ozet=None, motor=None):
    try:
        kaynak_durumunu_kaydet(OPENAIP_DURUM_ANAHTARI, basarili, hata, ozet, motor=motor)
    except Exception as db_hatasi:
        _logger.warning("openAIP kaynak durumu kaydedilemedi: %s", db_hatasi)


def _openaip_ice_aktar(ulkeler, api_anahtari, turler, getirici, motor) -> dict:
    api_anahtari = api_anahtari or os.environ.get("OPENAIP_API_ANAHTARI")
    if not api_anahtari:
        raise ValueError("OPENAIP_API_ANAHTARI tanımlı değil (openaip.net profil sayfasından ücretsiz alınır).")
    ulkeler = [u.strip().upper() for u in (ulkeler or config.OPENAIP_ULKELER) if u.strip()]
    turler = set(turler or config.OPENAIP_SAHA_TURLERI)
    ozellikler, atlanan = [], 0
    for ulke in ulkeler:
        for ham in openaip_sahalarini_getir(ulke, api_anahtari, getirici):
            ozellik = openaip_ozelligine_cevir(ham, turler)
            if ozellik is not None:
                ozellikler.append(ozellik)
            elif ham.get("type") in turler:
                atlanan += 1
    if not ozellikler:
        raise ValueError(
            f"openAIP'ten {', '.join(ulkeler)} için seçilen türde hiç saha gelmedi; mevcut veri korunuyor."
        )
    sonuc = geojson_ice_aktar(
        {"type": "FeatureCollection", "features": ozellikler},
        OPENAIP_KAYNAK,
        eskileri_kaldir=True,
        motor=motor,
        maks_ozellik=None,
    )
    _logger.info("openAIP'ten %d kısıtlı saha içe aktarıldı (%d atlandı).", sonuc["kaydedilen"], atlanan)
    return {**sonuc, "atlanan": atlanan, "ulkeler": ulkeler}
