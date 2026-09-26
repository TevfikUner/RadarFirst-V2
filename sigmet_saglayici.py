"""
sigmet_saglayici.py
----------------------
aviationweather.gov (NOAA/AWC) canlı SIGMET veri sağlayıcısı. İki uç nokta
birlikte kullanılır:
  - /api/data/airsigmet : ABD iç SIGMET'leri (irtifa: altitudeLow1/Hi1)
  - /api/data/isigmet   : uluslararası SIGMET'ler (irtifa: base/top) --
                          Ankara FIR (LTAA) dahil dünya geneli
Kayıtlar tek bir şemaya normalize edilip `sigmetler` tablosuna (bkz.
models.Sigmet) upsert edilir; rota_optimizasyonu.py bunları A*'ın SERT
kısıtı olarak kullanır (bkz. risk_katmanlari.SigmetKisitKatmani).

İptal (CNL) edilen SIGMET'ler AWC'nin canlı listesinden düşer. Bu yüzden bir
kaynaktan başarılı çekim yapıldığında, o kaynağın hâlâ "geçerli" görünen ama
yeni listede OLMAYAN kayıtlarının geçerliliği o an sona erdirilir --
kaldırılmış bir uyarıdan rota saptırmaya devam edilmesin diye.

Çalıştırma (n8n veya cron bunu periyodik tetikleyebilir; API karşılığı:
POST /api/v1/sigmet/guncelle):
    python sigmet_saglayici.py
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete, func, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

import config
from loglama import logger_al
from models import Sigmet
from veritabani import motor_al

_logger = logger_al(__name__)

_AWC_TABAN_URL = "https://aviationweather.gov/api/data"
_KAYNAKLAR = ("airsigmet", "isigmet")

_yeniden_dene = retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)


@_yeniden_dene
def _awc_listesini_getir(kaynak: str, timeout: float = 20.0) -> list[dict]:
    yanit = httpx.get(f"{_AWC_TABAN_URL}/{kaynak}", params={"format": "json"}, timeout=timeout)
    yanit.raise_for_status()
    return yanit.json() if yanit.content else []


def _zaman(epoch_saniye) -> datetime | None:
    return datetime.fromtimestamp(int(epoch_saniye), UTC) if epoch_saniye is not None else None


def _dis_kimlik(kaynak: str, ham: dict) -> str:
    anahtar = [
        kaynak,
        ham.get("icaoId"),
        ham.get("firId"),
        ham.get("seriesId"),
        ham.get("validTimeFrom"),
        ham.get("hazard"),
        [(k.get("lat"), k.get("lon")) for k in ham.get("coords") or []],
    ]
    return hashlib.sha1(json.dumps(anahtar, sort_keys=True).encode()).hexdigest()


def _abd_bicimi_mi(ham: dict) -> bool:
    return "airSigmetType" in ham


def _irtifa_bandi(ham: dict) -> tuple[int | None, int | None]:
    if not _abd_bicimi_mi(ham):
        return ham.get("base"), ham.get("top")
    alt = [a for a in (ham.get("altitudeLow1"), ham.get("altitudeLow2")) if a is not None]
    ust = [a for a in (ham.get("altitudeHi1"), ham.get("altitudeHi2")) if a is not None]
    return (min(alt) if alt else None), (max(ust) if ust else None)


def sigmet_kaydini_normalize_et(kaynak: str, ham: dict) -> dict | None:
    """AWC JSON kaydını `sigmetler` satırına çevirir. Poligonu olmayan (üçten
    az köşeli) ya da SIGMET olmayan (AIRMET/outlook) kayıtlar için None."""
    if _abd_bicimi_mi(ham) and ham.get("airSigmetType") != "SIGMET":
        return None
    koseler = [(float(k["lon"]), float(k["lat"])) for k in ham.get("coords") or [] if "lat" in k and "lon" in k]
    if len({k for k in koseler}) < 3:
        return None
    if koseler[0] != koseler[-1]:
        koseler.append(koseler[0])
    baslangic, bitis = _zaman(ham.get("validTimeFrom")), _zaman(ham.get("validTimeTo"))
    if baslangic is None or bitis is None:
        return None
    taban_ft, tavan_ft = _irtifa_bandi(ham)
    boylamlar, enlemler = [k[0] for k in koseler], [k[1] for k in koseler]
    return {
        "dis_kimlik": _dis_kimlik(kaynak, ham),
        "kaynak": kaynak,
        "fir_kodu": ham.get("firId") or ham.get("icaoId"),
        "seri_no": ham.get("seriesId"),
        "tehlike": str(ham.get("hazard") or "BILINMIYOR").upper(),
        "niteleyici": ham.get("qualifier"),
        "gecerlilik_baslangic": baslangic,
        "gecerlilik_bitis": bitis,
        "taban_ft": taban_ft,
        "tavan_ft": tavan_ft,
        "poligon": [list(k) for k in koseler],
        "enlem_min": min(enlemler),
        "enlem_maks": max(enlemler),
        "boylam_min": min(boylamlar),
        "boylam_maks": max(boylamlar),
        "ham_metin": ham.get("rawSigmet") or ham.get("rawAirSigmet"),
    }


def sigmetleri_kaydet(kayitlar: list[dict], motor=None) -> int:
    if not kayitlar:
        return 0
    motor = motor or motor_al()
    ifade = insert(Sigmet).values(kayitlar)
    guncellenecek = {s: ifade.excluded[s] for s in kayitlar[0] if s != "dis_kimlik"}
    guncellenecek["alinma_zamani"] = func.now()
    with Session(motor) as oturum:
        oturum.execute(ifade.on_conflict_do_update(index_elements=["dis_kimlik"], set_=guncellenecek))
        oturum.commit()
    return len(kayitlar)


def akista_olmayanlari_sonlandir(kaynak: str, akistaki_kimlikler: set[str], motor=None) -> int:
    motor = motor or motor_al()
    simdi = datetime.now(UTC)
    with Session(motor) as oturum:
        sonuc = oturum.execute(
            update(Sigmet)
            .where(
                Sigmet.kaynak == kaynak,
                Sigmet.gecerlilik_bitis > simdi,
                Sigmet.dis_kimlik.not_in(akistaki_kimlikler) if akistaki_kimlikler else true(),
            )
            .values(gecerlilik_bitis=simdi)
        )
        oturum.commit()
        return sonuc.rowcount


def eski_sigmetleri_temizle(saklama_suresi: timedelta | None = None, motor=None) -> int:
    saklama_suresi = saklama_suresi or timedelta(days=config.SIGMET_SAKLAMA_GUN)
    motor = motor or motor_al()
    with Session(motor) as oturum:
        sonuc = oturum.execute(delete(Sigmet).where(Sigmet.gecerlilik_bitis < datetime.now(UTC) - saklama_suresi))
        oturum.commit()
        return sonuc.rowcount


def sigmetleri_guncelle(motor=None, getirici=_awc_listesini_getir, kaynaklar=_KAYNAKLAR) -> dict:
    """AWC kaynaklarını çekip veritabanını günceller. Bir kaynak başarısız
    olursa diğeri yine işlenir; o kaynağın mevcut kayıtlarına dokunulmaz."""
    ozet = {"kaydedilen": 0, "sonlandirilan": 0, "silinen": 0, "kaynak_hatalari": {}}
    for kaynak in kaynaklar:
        try:
            ham_liste = getirici(kaynak)
        except Exception as hata:
            _logger.warning("AWC '%s' çekilemedi: %s", kaynak, hata)
            ozet["kaynak_hatalari"][kaynak] = type(hata).__name__
            continue
        kayitlar = {}
        for ham in ham_liste:
            kayit = sigmet_kaydini_normalize_et(kaynak, ham)
            if kayit is not None:
                kayitlar[kayit["dis_kimlik"]] = kayit
        ozet["kaydedilen"] += sigmetleri_kaydet(list(kayitlar.values()), motor)
        ozet["sonlandirilan"] += akista_olmayanlari_sonlandir(kaynak, set(kayitlar), motor)
    ozet["silinen"] = eski_sigmetleri_temizle(motor=motor)
    return ozet


def _satiri_sozluge_cevir(s: Sigmet) -> dict:
    return {
        "id": s.id,
        "kaynak": s.kaynak,
        "fir_kodu": s.fir_kodu,
        "seri_no": s.seri_no,
        "tehlike": s.tehlike,
        "niteleyici": s.niteleyici,
        "gecerlilik_baslangic": s.gecerlilik_baslangic,
        "gecerlilik_bitis": s.gecerlilik_bitis,
        "taban_ft": s.taban_ft,
        "tavan_ft": s.tavan_ft,
        "poligon": s.poligon,
    }


def gecerli_sigmetleri_getir(
    baslangic: datetime,
    bitis: datetime,
    enlem_min: float = -90.0,
    enlem_maks: float = 90.0,
    boylam_min: float = -180.0,
    boylam_maks: float = 180.0,
    tehlikeler=None,
    motor=None,
) -> list[dict]:
    """[baslangic, bitis] zaman aralığıyla ve verilen kutuyla kesişen SIGMET'ler."""
    motor = motor or motor_al()
    enlem_min, enlem_maks, boylam_min, boylam_maks = map(float, (enlem_min, enlem_maks, boylam_min, boylam_maks))
    kosullar = [
        Sigmet.gecerlilik_baslangic <= bitis,
        Sigmet.gecerlilik_bitis >= baslangic,
        Sigmet.enlem_min <= enlem_maks,
        Sigmet.enlem_maks >= enlem_min,
        Sigmet.boylam_min <= boylam_maks,
        Sigmet.boylam_maks >= boylam_min,
    ]
    if tehlikeler:
        kosullar.append(Sigmet.tehlike.in_([t.upper() for t in tehlikeler]))
    with Session(motor) as oturum:
        satirlar = oturum.execute(select(Sigmet).where(*kosullar).order_by(Sigmet.gecerlilik_baslangic)).scalars()
        return [_satiri_sozluge_cevir(s) for s in satirlar]


def son_guncelleme_zamani(motor=None) -> datetime | None:
    motor = motor or motor_al()
    with Session(motor) as oturum:
        return oturum.execute(select(func.max(Sigmet.alinma_zamani))).scalar_one()


if __name__ == "__main__":
    from konsol_kurulumu import konsolu_utf8_yap

    konsolu_utf8_yap()
    print(sigmetleri_guncelle())
