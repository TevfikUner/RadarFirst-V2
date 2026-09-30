"""
kisitli_saha_saglayici.py
----------------------------
Kısıtlı/yasak hava sahaları: çatışma bölgeleri, yasak (P), kısıtlı (R) ve
tehlikeli (D) sahalar, NOTAM'la ilan edilen geçici kısıtlar. A* bunları SIGMET
gibi SERT kısıt olarak kullanır (bkz. risk_katmanlari.KisitliSahaKatmani):
yanal sapma, planlı rotanın kullanmadığı bir kısıtlı sahaya asla önerilmez.

Veri GeoJSON FeatureCollection olarak içe aktarılır. Geometri Polygon ya da
MultiPolygon (her parça ayrı kayıt); iç halkalar (delikler) muhafazakâr olarak
yok sayılır. properties: kimlik, ad, tur (CATISMA/YASAK/KISITLI/TEHLIKELI/
GECICI), taban_ft, tavan_ft (boş = yer / sınırsız), baslangic, bitis (ISO
8601; boş = süresiz), aciklama.
    turbulans-kisitli-saha ice-aktar sahalar.geojson --kaynak aip
    POST /api/v1/kisitli-sahalar?kaynak=notam   (örn. n8n: NOTAM -> geçici kısıt)

ÖRNEK VERİ: paketle gelen ornek_kisitli_sahalar.geojson, Natural Earth 1:50m
(kamu malı) ülke sınırlarından Suriye ve Irak'ı "çatışma bölgesi" olarak
içerir -- mekanizmayı göstermek içindir, resmi FIR/CZIB sınırı DEĞİLDİR.
config.KISITLI_SAHA_ORNEK_VERI_YUKLE açıkken API açılışında (bu kaynaktan hiç
kayıt yoksa) yüklenir; gerçek kullanımda kapatılıp resmi veri aktarılmalıdır.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turbulans_radar.depo.models import KisitliHavaSahasi, kutuyla_kesisir
from turbulans_radar.depo.veritabani import motor_al

SAHA_TURLERI = ("CATISMA", "YASAK", "KISITLI", "TEHLIKELI", "GECICI")
ORNEK_KAYNAK = "ornek"
ORNEK_DOSYA = Path(__file__).with_name("ornek_kisitli_sahalar.geojson")
MAKS_OZELLIK = 1000
MAKS_KOSE = 20_000
_MAKS_IRTIFA_FT = 70_000


def _hata(sira, mesaj):
    return ValueError(f"features[{sira}]: {mesaj}")


def _zaman(deger, sira, alan):
    if deger in (None, ""):
        return None
    try:
        zaman = datetime.fromisoformat(str(deger).replace("Z", "+00:00"))
    except ValueError:
        raise _hata(sira, f"'{alan}' ISO 8601 olmalı") from None
    return zaman.replace(tzinfo=UTC) if zaman.tzinfo is None else zaman.astimezone(UTC)


def _irtifa(deger, sira, alan):
    if deger is None:
        return None
    if isinstance(deger, bool) or not isinstance(deger, int | float) or not 0 <= deger <= _MAKS_IRTIFA_FT:
        raise _hata(sira, f"'{alan}' 0-{_MAKS_IRTIFA_FT} ft arası bir sayı ya da null olmalı")
    return int(deger)


def _dis_halkalar(geometri, sira):
    if not isinstance(geometri, dict) or geometri.get("type") not in ("Polygon", "MultiPolygon"):
        raise _hata(sira, "geometri Polygon ya da MultiPolygon olmalı")
    poligonlar = geometri.get("coordinates") or []
    if geometri["type"] == "Polygon":
        poligonlar = [poligonlar]
    halkalar = []
    for poligon in poligonlar:
        try:
            halka = [(float(k[0]), float(k[1])) for k in poligon[0]]
        except (TypeError, ValueError, IndexError, KeyError):
            raise _hata(sira, "koordinatlar [boylam, enlem] çiftleri olmalı") from None
        if len(set(halka)) < 3:
            raise _hata(sira, "bir poligonun en az 3 farklı köşesi olmalı")
        if len(halka) > MAKS_KOSE:
            raise _hata(sira, f"bir poligon en fazla {MAKS_KOSE} köşe içerebilir")
        if any(not (-180 <= b <= 180 and -90 <= e <= 90) for b, e in halka):
            raise _hata(sira, "koordinatlar boylam -180..180, enlem -90..90 aralığında olmalı")
        if halka[0] != halka[-1]:
            halka.append(halka[0])
        halkalar.append(halka)
    if not halkalar:
        raise _hata(sira, "geometri boş")
    return halkalar


def _dis_kimlik(kaynak, kimlik, parca, parca_sayisi):
    ham = f"{kaynak}:{kimlik}" + (f"#{parca}" if parca_sayisi > 1 else "")
    return ham if len(ham) <= 128 else f"{kaynak}:{hashlib.sha1(ham.encode()).hexdigest()}"


def geojson_kayitlarina_cevir(geojson: dict, kaynak: str, maks_ozellik: int | None = MAKS_OZELLIK) -> list[dict]:
    """GeoJSON FeatureCollection -> `kisitli_hava_sahalari` satırları. Geçersiz
    girdide hangi özelliğin neden reddedildiğini söyleyen ValueError."""
    if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON bir FeatureCollection olmalı.")
    ozellikler = geojson.get("features")
    if not isinstance(ozellikler, list) or not ozellikler:
        raise ValueError("'features' boş olmayan bir liste olmalı.")
    if maks_ozellik is not None and len(ozellikler) > maks_ozellik:
        raise ValueError(f"Tek seferde en fazla {maks_ozellik} özellik içe aktarılabilir.")
    kayitlar = {}
    for sira, ozellik in enumerate(ozellikler):
        if not isinstance(ozellik, dict):
            raise _hata(sira, "Feature nesnesi olmalı")
        ozellikler_ = ozellik.get("properties") or {}
        halkalar = _dis_halkalar(ozellik.get("geometry"), sira)
        tur = str(ozellikler_.get("tur") or "KISITLI").upper()
        if tur not in SAHA_TURLERI:
            raise _hata(sira, f"'tur' şunlardan biri olmalı: {', '.join(SAHA_TURLERI)}")
        taban = _irtifa(ozellikler_.get("taban_ft"), sira, "taban_ft")
        tavan = _irtifa(ozellikler_.get("tavan_ft"), sira, "tavan_ft")
        if taban is not None and tavan is not None and taban > tavan:
            raise _hata(sira, "taban_ft tavan_ft'ten büyük olamaz")
        baslangic = _zaman(ozellikler_.get("baslangic"), sira, "baslangic")
        bitis = _zaman(ozellikler_.get("bitis"), sira, "bitis")
        if baslangic and bitis and baslangic >= bitis:
            raise _hata(sira, "baslangic bitis'ten önce olmalı")
        kimlik = str(ozellikler_.get("kimlik") or hashlib.sha1(json.dumps(halkalar).encode()).hexdigest()[:16])
        ad = str(ozellikler_.get("ad") or kimlik)
        for parca, halka in enumerate(halkalar):
            boylamlar, enlemler = [k[0] for k in halka], [k[1] for k in halka]
            dis_kimlik = _dis_kimlik(kaynak, kimlik, parca, len(halkalar))
            kayitlar[dis_kimlik] = {
                "dis_kimlik": dis_kimlik,
                "kaynak": kaynak,
                "ad": ad,
                "tur": tur,
                "taban_ft": taban,
                "tavan_ft": tavan,
                "gecerlilik_baslangic": baslangic,
                "gecerlilik_bitis": bitis,
                "poligon": [list(k) for k in halka],
                "enlem_min": min(enlemler),
                "enlem_maks": max(enlemler),
                "boylam_min": min(boylamlar),
                "boylam_maks": max(boylamlar),
                "aciklama": ozellikler_.get("aciklama"),
            }
            # MultiPolygon her PARÇASI ayrı bir kayıt üretir (yukarı bkz.);
            # maks_ozellik sadece 'features' sayısını sınırlar, tek bir
            # feature'ı binlerce ufak parçalı bir MultiPolygon yaparak bu
            # sınır atlatılıp devasa bellek/INSERT'e yol açılabilir -- bu
            # yüzden toplam üretilen kayıt sayısı da aynı tavanla sınırlanır.
            if maks_ozellik is not None and len(kayitlar) > maks_ozellik:
                raise ValueError(f"Tek seferde en fazla {maks_ozellik} saha (parça dahil) içe aktarılabilir.")
    return list(kayitlar.values())


def geojson_ice_aktar(geojson: dict, kaynak: str, eskileri_kaldir=False, motor=None, maks_ozellik=MAKS_OZELLIK) -> dict:
    """Upsert (dis_kimlik = kaynak:kimlik). eskileri_kaldir: bu kaynağın yeni
    veride olmayan kayıtlarını siler (örn. AIRAC döngüsünde tam yenileme)."""
    if not kaynak or len(kaynak) > 32:
        raise ValueError("kaynak 1-32 karakter olmalı.")
    kayitlar = geojson_kayitlarina_cevir(geojson, kaynak, maks_ozellik)
    motor = motor or motor_al()
    ifade = insert(KisitliHavaSahasi).values(kayitlar)
    with Session(motor) as oturum:
        oturum.execute(
            ifade.on_conflict_do_update(
                index_elements=["dis_kimlik"],
                set_={
                    **{k: ifade.excluded[k] for k in kayitlar[0] if k != "dis_kimlik"},
                    "guncellenme_zamani": datetime.now(UTC),
                },
            )
        )
        kaldirilan = 0
        if eskileri_kaldir:
            kaldirilan = oturum.execute(
                delete(KisitliHavaSahasi).where(
                    KisitliHavaSahasi.kaynak == kaynak,
                    KisitliHavaSahasi.dis_kimlik.not_in([k["dis_kimlik"] for k in kayitlar]),
                )
            ).rowcount
        oturum.commit()
    return {"kaydedilen": len(kayitlar), "kaldirilan": kaldirilan}


def dosyadan_ice_aktar(yol, kaynak: str, eskileri_kaldir=False, motor=None) -> dict:
    return geojson_ice_aktar(json.loads(Path(yol).read_text(encoding="utf-8")), kaynak, eskileri_kaldir, motor)


def ornek_veriyi_yukle(motor=None, zorla=False) -> int:
    """Paketle gelen örnek sahaları yükler; bu kaynaktan kayıt varsa (zorla
    değilse) dokunmaz -- operatörün sildiği örnek veri geri gelmesin diye
    sadece hiç kayıt yokken çalışır."""
    motor = motor or motor_al()
    if not zorla:
        with Session(motor) as oturum:
            if oturum.execute(
                select(KisitliHavaSahasi.id).where(KisitliHavaSahasi.kaynak == ORNEK_KAYNAK).limit(1)
            ).first():
                return 0
    return dosyadan_ice_aktar(ORNEK_DOSYA, ORNEK_KAYNAK, eskileri_kaldir=True, motor=motor)["kaydedilen"]


def _satiri_sozluge_cevir(s: KisitliHavaSahasi) -> dict:
    return {
        "id": s.id,
        "dis_kimlik": s.dis_kimlik,
        "kaynak": s.kaynak,
        "ad": s.ad,
        "tur": s.tur,
        "taban_ft": s.taban_ft,
        "tavan_ft": s.tavan_ft,
        "gecerlilik_baslangic": s.gecerlilik_baslangic,
        "gecerlilik_bitis": s.gecerlilik_bitis,
        "poligon": s.poligon,
        "aciklama": s.aciklama,
    }


def gecerli_kisitli_sahalari_getir(
    baslangic: datetime,
    bitis: datetime,
    enlem_min: float = -90.0,
    enlem_maks: float = 90.0,
    boylam_min: float = -180.0,
    boylam_maks: float = 180.0,
    motor=None,
) -> list[dict]:
    """[baslangic, bitis] aralığında geçerli (süresizler dahil) ve kutuyla kesişen sahalar."""
    motor = motor or motor_al()
    enlem_min, enlem_maks, boylam_min, boylam_maks = map(float, (enlem_min, enlem_maks, boylam_min, boylam_maks))
    kosullar = [
        (KisitliHavaSahasi.gecerlilik_baslangic.is_(None)) | (KisitliHavaSahasi.gecerlilik_baslangic <= bitis),
        (KisitliHavaSahasi.gecerlilik_bitis.is_(None)) | (KisitliHavaSahasi.gecerlilik_bitis >= baslangic),
        kutuyla_kesisir(KisitliHavaSahasi, enlem_min, enlem_maks, boylam_min, boylam_maks),
    ]
    with Session(motor) as oturum:
        satirlar = oturum.execute(select(KisitliHavaSahasi).where(*kosullar).order_by(KisitliHavaSahasi.dis_kimlik))
        return [_satiri_sozluge_cevir(s) for s in satirlar.scalars()]


def kisitli_sahayi_sil(dis_kimlik: str, motor=None) -> bool:
    motor = motor or motor_al()
    with Session(motor) as oturum:
        silinen = oturum.execute(delete(KisitliHavaSahasi).where(KisitliHavaSahasi.dis_kimlik == dis_kimlik)).rowcount
        oturum.commit()
    return bool(silinen)


def ana():
    from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

    konsolu_utf8_yap()
    ayristirici = argparse.ArgumentParser(description="Kısıtlı/yasak hava sahalarını yönetir (A*'ın sert kısıtı).")
    alt = ayristirici.add_subparsers(dest="komut", required=True)
    ice = alt.add_parser("ice-aktar", help="GeoJSON FeatureCollection içe aktarır")
    ice.add_argument("dosya")
    ice.add_argument("--kaynak", required=True, help="örn. aip, czib, notam (en fazla 32 karakter)")
    ice.add_argument("--eskileri-kaldir", action="store_true", help="Bu kaynağın yeni dosyada olmayan kayıtlarını sil")
    alt.add_parser("ornek-yukle", help="Paketle gelen örnek veriyi (yeniden) yükler")
    openaip = alt.add_parser("openaip", help="Gerçek sahaları openAIP'ten çeker (OPENAIP_API_ANAHTARI gerekir)")
    openaip.add_argument("--ulke", action="append", help="ISO ülke kodu, birden çok verilebilir (varsayılan: config)")
    alt.add_parser("listele", help="Şu an geçerli sahaları listeler")
    sil = alt.add_parser("sil", help="Bir sahayı dis_kimlik ile siler")
    sil.add_argument("dis_kimlik")
    argumanlar = ayristirici.parse_args()

    if argumanlar.komut == "ice-aktar":
        print(dosyadan_ice_aktar(argumanlar.dosya, argumanlar.kaynak, argumanlar.eskileri_kaldir))
    elif argumanlar.komut == "openaip":
        from turbulans_radar.veri.openaip_saglayici import openaip_ice_aktar

        print(openaip_ice_aktar(argumanlar.ulke))
    elif argumanlar.komut == "ornek-yukle":
        print({"kaydedilen": ornek_veriyi_yukle(zorla=True)})
    elif argumanlar.komut == "listele":
        simdi = datetime.now(UTC)
        for saha in gecerli_kisitli_sahalari_getir(simdi, simdi):
            print(f"{saha['dis_kimlik']:40} {saha['tur']:10} {saha['ad']}")
    else:
        print({"silindi": kisitli_sahayi_sil(argumanlar.dis_kimlik)})


if __name__ == "__main__":
    ana()
