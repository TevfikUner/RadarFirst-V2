"""
canli_adsb.py
----------------
Sanal PIREP (M6) için süreli canlı ADS-B oturumu: bir bölgeyi kısa aralıkla
sorgulayıp her uçağın izini kurar, oturum sonunda izleri sanal PIREP hattına
verir (analiz/sanal_pirep_hatti.py). Geçmiş veri için değil, canlı gözlem
içindir; geçmiş izler OpenSky Trino'da kalır.

Kaynaklar (fikir: kewonit/aeris ve debjit450/skywatch-live'daki yedekli
sağlayıcı zinciri), sırayla; biri hata ya da 429 verirse sonraki denenir:
  - adsb.fi açık veri: saniyede en fazla 1 istek, yalnızca kişisel/ticari
    olmayan kullanım, adsb.fi'ye atıf ve bağlantı zorunlu
    (https://github.com/adsbfi/opendata).
  - adsb.lol: ODbL 1.0, hız sınırı yüke göre değişir (https://www.adsb.lol).
  - airplanes.live genel API'si 29 Nisan 2026'da kapandı; kullanılmaz.

Ban koruması: istekler arası en az CANLI_ADSB_MIN_ARALIK_SANIYE (varsayılan
oturum aralığı 10 sn = adsb.fi sınırının onda biri), oturum en fazla
CANLI_ADSB_MAKS_SURE_DK, günde en fazla CANLI_ADSB_GUNLUK_MAKS_ISTEK istek
(veritabanı sayacı), aynı anda tek oturum (dağıtık kilit). 429'da sağlayıcı
CANLI_ADSB_429_BEKLEME_SANIYE boyunca atlanır. Varsayılan kapalıdır
(CANLI_ADSB_ETKIN).
"""

import time
from collections.abc import Callable

import httpx
import pandas as pd

from turbulans_radar import config
from turbulans_radar.depo.hiz_siniri import KOTA_ONEKI, istegi_say_senkron
from turbulans_radar.loglama import logger_al

_logger = logger_al(__name__)

KOTA_ANAHTARI = f"{KOTA_ONEKI}canli_adsb_gunluk_istek"
FT_M = 0.3048
SAGLAYICI_URL = {
    "adsb_fi": "https://opendata.adsb.fi/api/v3/lat/{enlem:.4f}/lon/{boylam:.4f}/dist/{yaricap_nm:.0f}",
    "adsb_lol": "https://api.adsb.lol/v2/point/{enlem:.4f}/{boylam:.4f}/{yaricap_nm:.0f}",
}
ATIF = {
    "adsb_fi": "adsb.fi açık veri (https://adsb.fi), kişisel/ticari olmayan kullanım",
    "adsb_lol": "ADSB.lol (https://www.adsb.lol), ODbL 1.0",
}
SUTUNLAR = ["icao24", "ucus_numarasi", "zaman", "enlem", "boylam", "baro_irtifa_m", "geo_irtifa_m", "dikey_hiz"]


class CanliAdsbKapaliHatasi(RuntimeError):
    pass


class CanliAdsbKotaHatasi(RuntimeError):
    pass


def yaniti_normalize_et(veri: dict) -> pd.DataFrame:
    """readsb/ADSBexchange v2 biçimi ('ac' ya da 'aircraft', 'now' ms):
    konumu ve barometrik irtifası olan havadaki uçaklar."""
    simdi = pd.Timestamp(veri.get("now", time.time() * 1000), unit="ms", tz="UTC")
    satirlar = []
    for ucak in veri.get("ac") or veri.get("aircraft") or []:
        baro = ucak.get("alt_baro")
        if ucak.get("lat") is None or ucak.get("lon") is None or not isinstance(baro, int | float):
            continue
        hiz = ucak.get("baro_rate", ucak.get("geom_rate"))
        geo = ucak.get("alt_geom")
        satirlar.append(
            {
                "icao24": str(ucak.get("hex", "")).lower().lstrip("~"),
                "ucus_numarasi": (ucak.get("flight") or "").strip() or None,
                "zaman": simdi - pd.Timedelta(seconds=float(ucak.get("seen_pos") or 0.0)),
                "enlem": float(ucak["lat"]),
                "boylam": float(ucak["lon"]),
                "baro_irtifa_m": float(baro) * FT_M,
                "geo_irtifa_m": float(geo) * FT_M if isinstance(geo, int | float) else float("nan"),
                "dikey_hiz": float(hiz) * FT_M / 60.0 if isinstance(hiz, int | float) else float("nan"),
            }
        )
    return pd.DataFrame(satirlar, columns=SUTUNLAR)


class BolgeSorgulayici:
    """Sağlayıcı zinciri; 429/hata veren sağlayıcı bir süre atlanır."""

    def __init__(self, saglayicilar=None, getirici=None, sayac=None, saat=time.monotonic):
        self.saglayicilar = list(saglayicilar or config.CANLI_ADSB_SAGLAYICILAR)
        bilinmeyen = set(self.saglayicilar) - set(SAGLAYICI_URL)
        if bilinmeyen:
            raise ValueError(f"Bilinmeyen canlı ADS-B sağlayıcısı: {sorted(bilinmeyen)}")
        self._getir = getirici or self._http_getir
        self._sayac = sayac or (lambda: istegi_say_senkron(KOTA_ANAHTARI, 86400))
        self._saat = saat
        self._askida: dict[str, float] = {}
        self.kullanilan: set[str] = set()

    @staticmethod
    def _http_getir(url: str) -> tuple[int, dict | None]:
        yanit = httpx.get(
            url, timeout=httpx.Timeout(10.0, read=20.0), headers={"User-Agent": config.CANLI_ADSB_KULLANICI_AJANI}
        )
        return yanit.status_code, (yanit.json() if yanit.status_code == 200 else None)

    def sorgula(self, enlem, boylam, yaricap_nm) -> tuple[pd.DataFrame, str | None]:
        if self._sayac() > config.CANLI_ADSB_GUNLUK_MAKS_ISTEK:
            raise CanliAdsbKotaHatasi(f"Günlük canlı ADS-B istek sınırı ({config.CANLI_ADSB_GUNLUK_MAKS_ISTEK}) doldu.")
        for ad in self.saglayicilar:
            if self._askida.get(ad, 0.0) > self._saat():
                continue
            url = SAGLAYICI_URL[ad].format(enlem=enlem, boylam=boylam, yaricap_nm=yaricap_nm)
            try:
                durum, veri = self._getir(url)
            except Exception as hata:
                _logger.warning("Canlı ADS-B (%s) alınamadı: %s", ad, hata)
                self._askida[ad] = self._saat() + config.CANLI_ADSB_HATA_BEKLEME_SANIYE
                continue
            if durum == 200 and veri is not None:
                self.kullanilan.add(ad)
                return yaniti_normalize_et(veri), ad
            bekleme = config.CANLI_ADSB_429_BEKLEME_SANIYE if durum == 429 else config.CANLI_ADSB_HATA_BEKLEME_SANIYE
            _logger.warning("Canlı ADS-B (%s) HTTP %s; %s sn atlanacak.", ad, durum, bekleme)
            self._askida[ad] = self._saat() + bekleme
        return pd.DataFrame(columns=SUTUNLAR), None


def canli_oturum(
    sure_dk=None,
    aralik_saniye=None,
    enlem=None,
    boylam=None,
    yaricap_nm=None,
    yayinla: Callable[[dict], None] | None = None,
    sorgulayici: BolgeSorgulayici | None = None,
    uyku=time.sleep,
    saat=time.monotonic,
    pirep_uretici=None,
    kilit=None,
) -> dict:
    """Bölgeyi sure_dk boyunca aralik_saniye'de bir sorgular, izleri sanal PIREP
    hattına verir. Dönüş: istek, nokta, uçak ve olay sayıları ile atıf."""
    if not config.CANLI_ADSB_ETKIN:
        raise CanliAdsbKapaliHatasi("Canlı ADS-B kapalı (CANLI_ADSB_ETKIN=false).")
    sure_dk = min(float(sure_dk or config.CANLI_ADSB_SURE_DK), config.CANLI_ADSB_MAKS_SURE_DK)
    aralik_saniye = max(float(aralik_saniye or config.CANLI_ADSB_ARALIK_SANIYE), config.CANLI_ADSB_MIN_ARALIK_SANIYE)
    enlem = config.CANLI_ADSB_MERKEZ_ENLEM if enlem is None else enlem
    boylam = config.CANLI_ADSB_MERKEZ_BOYLAM if boylam is None else boylam
    yaricap_nm = min(float(yaricap_nm or config.CANLI_ADSB_YARICAP_NM), 250.0)
    sorgulayici = sorgulayici or BolgeSorgulayici()
    if kilit is None:
        from turbulans_radar.depo.dagitik_kilit import dagitik_kilit

        kilit = dagitik_kilit("canli_adsb", zaman_asimi_saniye=0)

    parcalar, istek = [], 0
    with kilit:
        bitis = saat() + sure_dk * 60.0
        while True:
            df, _ = sorgulayici.sorgula(enlem, boylam, yaricap_nm)
            istek += 1
            if not df.empty:
                parcalar.append(df)
            if saat() + aralik_saniye > bitis:
                break
            uyku(aralik_saniye)
    izler = pd.concat(parcalar, ignore_index=True) if parcalar else pd.DataFrame(columns=SUTUNLAR)
    izler = izler.drop_duplicates(["icao24", "zaman"]).sort_values(["icao24", "zaman"])
    if pirep_uretici is None:
        from turbulans_radar.analiz.sanal_pirep_hatti import izden_sanal_pirep_uret as pirep_uretici
    olay = 0
    for icao24, iz in izler.groupby("icao24"):
        if len(iz) < 3:
            continue
        ucus = iz["ucus_numarasi"].dropna()
        ozet = pirep_uretici(
            iz.reset_index(drop=True),
            "canli_adsb",
            yayinla or (lambda mesaj: None),
            icao24=icao24,
            ucus_numarasi=ucus.iloc[-1] if len(ucus) else None,
        )
        olay += int((ozet or {}).get("kaydedilen", 0) or 0)
    return {
        "istek": istek,
        "nokta": len(izler),
        "ucak": int(izler["icao24"].nunique()),
        "olay": olay,
        "sure_dk": sure_dk,
        "aralik_saniye": aralik_saniye,
        "atif": [ATIF[ad] for ad in sorted(sorgulayici.kullanilan)],
    }


def ana(argv=None):
    import argparse
    import json

    ayristirici = argparse.ArgumentParser(description="Süreli canlı ADS-B oturumu -> sanal PIREP (M6).")
    ayristirici.add_argument("--sure-dk", type=float, default=None)
    ayristirici.add_argument("--aralik-saniye", type=float, default=None)
    ayristirici.add_argument("--enlem", type=float, default=None)
    ayristirici.add_argument("--boylam", type=float, default=None)
    ayristirici.add_argument("--yaricap-nm", type=float, default=None)
    a = ayristirici.parse_args(argv)
    ozet = canli_oturum(a.sure_dk, a.aralik_saniye, a.enlem, a.boylam, a.yaricap_nm)
    print(json.dumps(ozet, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
