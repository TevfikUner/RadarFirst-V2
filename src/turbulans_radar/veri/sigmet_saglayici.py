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

SESSİZ KAYIP KORUMASI: "listede yok -> sonlandır" kuralı, akış
çözümlenemediğinde tüm aktif SIGMET'leri sonlandırıp sistemi "SIGMET yok"a
düşürebilirdi (örn. AWC 'coords' alanını yeniden adlandırsa). Bu yüzden akış
önce denetlenir (bkz. _akis_sagligini_denetle): boş/liste olmayan yanıt ya da
SIGMET kayıtlarının config.SIGMET_MAKS_COZUMLENEMEYEN_ORAN'dan fazlasının
çözümlenememesi KAYNAK HATASI sayılır -- mevcut kayıtlar sonlandırılmaz ve
kaynak başarılı güncelleme almaz (bayatlık uyarısı devreye girer). Her
kaynağın son başarılı çekimi veri_kaynagi_durumlari tablosunda tutulur.

Çalıştırma (n8n veya cron bunu periyodik tetikleyebilir; API karşılığı:
POST /api/v1/sigmet/guncelle):
    turbulans-sigmet
"""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta

import httpx
import shapely
from sqlalchemy import delete, func, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo.kaynak_durumu import kaynak_durumlarini_getir, kaynak_durumunu_kaydet
from turbulans_radar.depo.models import Sigmet, kutuyla_kesisir
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.loglama import logger_al
from turbulans_radar.veri.fir_sinirlari import fir_geometrisi
from turbulans_radar.yeniden_deneme import gecici_hatada_yeniden_dene

_logger = logger_al(__name__)

_AWC_TABAN_URL = "https://aviationweather.gov/api/data"
_KAYNAKLAR = ("airsigmet", "isigmet")

_yeniden_dene = gecici_hatada_yeniden_dene()


@_yeniden_dene
def _awc_listesini_getir(kaynak: str, timeout: float = 20.0) -> list[dict]:
    yanit = httpx.get(f"{_AWC_TABAN_URL}/{kaynak}", params={"format": "json"}, timeout=timeout)
    yanit.raise_for_status()
    return yanit.json() if yanit.content else []


def _zaman(epoch_saniye) -> datetime | None:
    return datetime.fromtimestamp(int(epoch_saniye), UTC) if epoch_saniye is not None else None


def durum_anahtari(kaynak: str) -> str:
    return f"sigmet:{kaynak}"


def kacinilacak_tehlikeler() -> tuple[str, ...]:
    return (*config.SIGMET_KACINILACAK_TEHLIKELER, config.SIGMET_BILINMEYEN_TEHLIKE)


def _dis_kimlik(kaynak: str, ham: dict, alan: list) -> str:
    anahtar = [
        kaynak,
        ham.get("icaoId"),
        ham.get("firId"),
        ham.get("seriesId"),
        ham.get("validTimeFrom"),
        ham.get("hazard"),
        [(k.get("lat"), k.get("lon")) if isinstance(k, dict) else k for k in alan],
    ]
    return hashlib.sha1(json.dumps(anahtar, sort_keys=True).encode()).hexdigest()


def _abd_bicimi_mi(ham: dict) -> bool:
    return "airSigmetType" in ham


_MAKS_MAKUL_IRTIFA_FT = 70_000


def _irtifa_ft(deger) -> int | None:
    try:
        irtifa = int(float(deger))
    except (TypeError, ValueError, OverflowError):
        return None
    return irtifa if 0 <= irtifa <= _MAKS_MAKUL_IRTIFA_FT else None


def _irtifa_bandi(ham: dict) -> tuple[int | None, int | None]:
    """Okunamayan/makul olmayan değer None olur -- A* None tabanı yer, None
    tavanı sonsuz sayar, yani belirsizlik HER ZAMAN daha geniş bir yasak
    bölgeye çevrilir. Taban > tavan ise bant tamamen belirsiz sayılır."""
    if _abd_bicimi_mi(ham):
        alt = [a for a in map(_irtifa_ft, (ham.get("altitudeLow1"), ham.get("altitudeLow2"))) if a is not None]
        ust = [a for a in map(_irtifa_ft, (ham.get("altitudeHi1"), ham.get("altitudeHi2"))) if a is not None]
        taban, tavan = (min(alt) if alt else None), (max(ust) if ust else None)
    else:
        taban, tavan = _irtifa_ft(ham.get("base")), _irtifa_ft(ham.get("top"))
    if taban is not None and tavan is not None and taban > tavan:
        return None, None
    return taban, tavan


_PUSULA = {
    ad: i * 22.5
    for i, ad in enumerate(
        ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
    )
}


def _sayi(deger) -> float | None:
    try:
        return float(deger)
    except (TypeError, ValueError):
        return None


def _hareket(ham: dict) -> tuple[float | None, float | None]:
    """(hareketin YÖNELDİĞİ yön derece, hız kt). Durağan/bilgi yok: (None, None);
    yön var hız bilinmiyor: (yön, None). ABD akışında movementDir hareketin
    GELDİĞİ yöndür ("MOV FROM 26025KT"); uluslararası akışta dir yöneldiği
    pusula yönüdür ("MOV NE 25KT")."""
    metin = str(ham.get("rawSigmet") or ham.get("rawAirSigmet") or "")
    if _abd_bicimi_mi(ham):
        gelis, hiz = _sayi(ham.get("movementDir")), _sayi(ham.get("movementSpd"))
        if gelis is None or "MOV LTL" in metin or "STNR" in metin:
            return None, None
        yon = (gelis + 180.0) % 360.0
    else:
        yon = _PUSULA.get(str(ham.get("dir") or "").strip().upper())
        if yon is None:
            return None, None
        hiz = _sayi(ham.get("spd"))
        if hiz is not None and re.search(rf"MOV\s+{ham.get('dir')}\s+0*{int(hiz)}\s*KMH", metin):
            hiz /= 1.852
    if hiz is not None and hiz <= 0:
        return None, None
    return yon, hiz


def _alanlar(ham: dict) -> list[list]:
    """AWC tek alanlı SIGMET'te 'coords' köşe listesidir; geom='AREAS'
    (aynı SIGMET'te birden fazla 'WI ...' alanı) ise köşe listelerinin
    listesidir -- canlı akışta görülüyor, eskiden sessizce atılıyordu."""
    koordinatlar = ham.get("coords") or []
    if koordinatlar and all(isinstance(k, list) for k in koordinatlar):
        return koordinatlar
    return [koordinatlar]


def _poligon_kaydi(kaynak: str, ham: dict, alan: list) -> dict | None:
    koseler = [(float(k["lon"]), float(k["lat"])) for k in alan if isinstance(k, dict) and "lat" in k and "lon" in k]
    if len(set(koseler)) < 3:
        return None
    if koseler[0] != koseler[-1]:
        koseler.append(koseler[0])
    taban_ft, tavan_ft = _irtifa_bandi(ham)
    hareket = _hareket(ham)
    boylamlar, enlemler = [k[0] for k in koseler], [k[1] for k in koseler]
    antimeridyen = max(abs(b - a) for a, b in zip(boylamlar, boylamlar[1:])) > 180.0 or max(boylamlar) > 180.0
    if antimeridyen:
        koseler = [((b + 360.0) % 360.0, e) for b, e in koseler]
        boylam_min, boylam_maks = -180.0, 180.0
    else:
        boylam_min, boylam_maks = min(boylamlar), max(boylamlar)
    return {
        "dis_kimlik": _dis_kimlik(kaynak, ham, alan),
        "kaynak": kaynak,
        "fir_kodu": ham.get("firId") or ham.get("icaoId"),
        "seri_no": ham.get("seriesId"),
        "tehlike": str(ham.get("hazard") or config.SIGMET_BILINMEYEN_TEHLIKE).upper(),
        "niteleyici": ham.get("qualifier"),
        "gecerlilik_baslangic": _zaman(ham.get("validTimeFrom")),
        "gecerlilik_bitis": _zaman(ham.get("validTimeTo")),
        "taban_ft": taban_ft,
        "tavan_ft": tavan_ft,
        "poligon": [list(k) for k in koseler],
        "enlem_min": min(enlemler),
        "enlem_maks": max(enlemler),
        "boylam_min": boylam_min,
        "boylam_maks": boylam_maks,
        "ham_metin": ham.get("rawSigmet") or ham.get("rawAirSigmet"),
        "hareket_yonu_derece": hareket[0],
        "hareket_hizi_kt": hareket[1],
    }


def _fir_poligon_kayitlari(kaynak: str, ham: dict) -> list[dict]:
    """Koordinatsız SIGMET için FIR'ın tamamı (parça başına bir kayıt)."""
    geometri = fir_geometrisi(ham.get("firId") or ham.get("icaoId"))
    if geometri is None:
        return []
    kayitlar = []
    for parca in shapely.get_parts(geometri):
        if parca.geom_type != "Polygon" or parca.is_empty:
            continue
        alan = [{"lon": round(x, 4), "lat": round(y, 4)} for x, y in parca.exterior.coords]
        kayit = _poligon_kaydi(kaynak, ham, alan)
        if kayit is not None:
            kayitlar.append(kayit)
    return kayitlar


def sigmet_kayitlarini_cozumle(kaynak: str, ham) -> tuple[list[dict], str | None]:
    """AWC JSON kaydını `sigmetler` satırlarına çevirir (çok alanlı SIGMET ->
    alan başına bir satır). Dönüş: (satırlar, neden). neden None ise başarılı;
    'sigmet_degil' (AIRMET/outlook) beklenen bir elemedir; 'poligon_yok',
    'gecerlilik_yok' ve 'bicim_hatasi' çözümlenemeyen SIGMET'lerdir.
    'fir_poligonu': koordinatı yoktu, FIR'ın tamamı kullanıldı (satırlar dolu).

    180° boylamını kesen (Pasifik FIR'ları) poligonların boylamları sürekli
    olacak şekilde 0..360 aralığına taşınır ve sınırlayıcı kutu tüm boylamları
    kapsar -- aksi halde örn. 175°/-175° köşeli bir SIGMET, dünyayı saran bir
    şerit gibi yorumlanıp alakasız rotaları yasaklardı. Geometrinin -180..180'e
    bölünmesi risk_katmanlari.sigmet_geometrisi'nde yapılır."""
    if not isinstance(ham, dict):
        return [], "bicim_hatasi"
    if _abd_bicimi_mi(ham) and ham.get("airSigmetType") != "SIGMET":
        return [], "sigmet_degil"
    try:
        if _zaman(ham.get("validTimeFrom")) is None or _zaman(ham.get("validTimeTo")) is None:
            return [], "gecerlilik_yok"
        kayitlar = [k for k in (_poligon_kaydi(kaynak, ham, alan) for alan in _alanlar(ham)) if k is not None]
    except (TypeError, ValueError, KeyError, OverflowError, OSError):
        return [], "bicim_hatasi"
    if kayitlar:
        return kayitlar, None
    fir_kayitlari = _fir_poligon_kayitlari(kaynak, ham)
    return (fir_kayitlari, "fir_poligonu") if fir_kayitlari else ([], "poligon_yok")


def sigmet_kaydini_normalize_et(kaynak: str, ham: dict) -> dict | None:
    """Tek alanlı kayıt için kısayol: ilk satır ya da None."""
    kayitlar, _ = sigmet_kayitlarini_cozumle(kaynak, ham)
    return kayitlar[0] if kayitlar else None


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


def _akisi_cozumle(kaynak: str, ham_liste: list) -> tuple[dict, dict]:
    kayitlar = {}
    sayim = {
        "ham": len(ham_liste),
        "sigmet": 0,
        "cozumlenen": 0,
        "cozumlenemeyen": 0,
        "fir_poligonu": 0,
        "nedenler": {},
    }
    for ham in ham_liste:
        satirlar, neden = sigmet_kayitlarini_cozumle(kaynak, ham)
        if neden == "sigmet_degil":
            continue
        sayim["sigmet"] += 1
        if neden in (None, "fir_poligonu"):
            sayim["cozumlenen"] += 1
            sayim["fir_poligonu"] += neden == "fir_poligonu"
            kayitlar.update((s["dis_kimlik"], s) for s in satirlar)
        else:
            sayim["cozumlenemeyen"] += 1
            sayim["nedenler"][neden] = sayim["nedenler"].get(neden, 0) + 1
    return kayitlar, sayim


def _akis_sagligini_denetle(ham_liste, sayim: dict | None) -> str | None:
    """Akış güvenilir değilse hata metni, güvenilirse None."""
    if not isinstance(ham_liste, list):
        return f"beklenmeyen yanıt biçimi ({type(ham_liste).__name__}, liste bekleniyordu)"
    if not ham_liste:
        return "boş akış"
    # FIR'a genişletilen (koordinatsız) kayıtlar da sayılır: koordinatlar
    # toptan kaybolursa FIR yedeği şema değişikliğini örtmesin.
    sorunlu = sayim["cozumlenemeyen"] + sayim.get("fir_poligonu", 0)
    if sayim["sigmet"] and sorunlu / sayim["sigmet"] > config.SIGMET_MAKS_COZUMLENEMEYEN_ORAN:
        return (
            f"şema uyuşmazlığı şüphesi: {sorunlu}/{sayim['sigmet']} SIGMET'in koordinatı çözümlenemedi "
            f"{sayim['nedenler']} (FIR'a genişletilen: {sayim.get('fir_poligonu', 0)})"
        )
    return None


def sigmetleri_guncelle(motor=None, getirici=_awc_listesini_getir, kaynaklar=_KAYNAKLAR) -> dict:
    """AWC kaynaklarını çekip veritabanını günceller. Bir kaynak başarısız
    olursa ya da akışı güvenilir değilse (bkz. _akis_sagligini_denetle) diğeri
    yine işlenir; o kaynağın mevcut kayıtları SONLANDIRILMAZ."""
    ozet = {"kaydedilen": 0, "sonlandirilan": 0, "silinen": 0, "kaynak_hatalari": {}, "kaynaklar": {}}
    for kaynak in kaynaklar:
        try:
            ham_liste = getirici(kaynak)
        except Exception as hata:
            _logger.warning("AWC '%s' çekilemedi: %s", kaynak, hata)
            ozet["kaynak_hatalari"][kaynak] = type(hata).__name__
            kaynak_durumunu_kaydet(durum_anahtari(kaynak), False, f"{type(hata).__name__}: {hata}", motor=motor)
            continue
        kayitlar, sayim = _akisi_cozumle(kaynak, ham_liste) if isinstance(ham_liste, list) else ({}, None)
        hata = _akis_sagligini_denetle(ham_liste, sayim)
        ozet["kaydedilen"] += sigmetleri_kaydet(list(kayitlar.values()), motor)
        if hata is None:
            ozet["sonlandirilan"] += akista_olmayanlari_sonlandir(kaynak, set(kayitlar), motor)
        else:
            _logger.error("AWC '%s' akışı güvenilir değil, mevcut SIGMET'ler korunuyor: %s", kaynak, hata)
            ozet["kaynak_hatalari"][kaynak] = hata
        kaynak_ozeti = {**(sayim or {}), "kaydedilen": len(kayitlar), "durum": "tamam" if hata is None else "hata"}
        ozet["kaynaklar"][kaynak] = kaynak_ozeti
        kaynak_durumunu_kaydet(durum_anahtari(kaynak), hata is None, hata, kaynak_ozeti, motor)
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
        "hareket_yonu_derece": s.hareket_yonu_derece,
        "hareket_hizi_kt": s.hareket_hizi_kt,
    }


def sigmet_getir(sigmet_id: int, motor=None) -> tuple[dict, str | None] | None:
    """(kayıt, ham metin) ya da None."""
    with Session(motor or motor_al()) as oturum:
        satir = oturum.get(Sigmet, sigmet_id)
        return None if satir is None else (_satiri_sozluge_cevir(satir), satir.ham_metin)


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
        kutuyla_kesisir(Sigmet, enlem_min, enlem_maks, boylam_min, boylam_maks),
    ]
    if tehlikeler:
        kosullar.append(Sigmet.tehlike.in_([t.upper() for t in tehlikeler]))
    with Session(motor) as oturum:
        satirlar = oturum.execute(select(Sigmet).where(*kosullar).order_by(Sigmet.gecerlilik_baslangic)).scalars()
        return [_satiri_sozluge_cevir(s) for s in satirlar]


def arsiv_baslangici(motor=None, kaynaklar=_KAYNAKLAR) -> datetime | None:
    """Arşivin kapsadığı en erken an (saklanan en eski kaydın geçerlilik
    başlangıcı) -- bağımsız doğrulama, arşivin bir uçuşu kapsayıp
    kapsamadığına buna bakarak karar verir."""
    motor = motor or motor_al()
    with Session(motor) as oturum:
        return oturum.execute(
            select(func.min(Sigmet.gecerlilik_baslangic)).where(Sigmet.kaynak.in_(list(kaynaklar)))
        ).scalar_one()


def kaynak_saglik_durumlari(kaynaklar=_KAYNAKLAR, motor=None) -> list[dict]:
    anahtarlar = [durum_anahtari(k) for k in kaynaklar]
    kayitli = {d["kaynak"]: d for d in kaynak_durumlarini_getir(anahtarlar, motor)}
    return [kayitli.get(a, {"kaynak": a, "son_basari_zamani": None, "ardisik_hata_sayisi": 0}) for a in anahtarlar]


def son_guncelleme_zamani(motor=None, kaynaklar=_KAYNAKLAR) -> datetime | None:
    """Yapılandırılmış TÜM kaynakların en eski son BAŞARILI çekimi; biri hiç
    başarılı olmadıysa None (= hiç güncellenmemiş sayılır)."""
    zamanlar = [d["son_basari_zamani"] for d in kaynak_saglik_durumlari(kaynaklar, motor)]
    return None if any(z is None for z in zamanlar) else min(zamanlar)


def sorunlu_kaynaklar(motor=None, kaynaklar=_KAYNAKLAR) -> list[str]:
    return [
        d["kaynak"].removeprefix("sigmet:")
        for d in kaynak_saglik_durumlari(kaynaklar, motor)
        if d["ardisik_hata_sayisi"] or d["son_basari_zamani"] is None
    ]


def ana():
    from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

    konsolu_utf8_yap()
    print(sigmetleri_guncelle())


if __name__ == "__main__":
    ana()
