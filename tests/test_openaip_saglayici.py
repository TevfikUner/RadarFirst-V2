from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from turbulans_radar.depo import veritabani as vt
from turbulans_radar.veri import openaip_saglayici as oa
from turbulans_radar.veri.kisitli_saha_saglayici import gecerli_kisitli_sahalari_getir

KARE = {"type": "Polygon", "coordinates": [[[32.0, 39.0], [33.0, 39.0], [33.0, 40.0], [32.0, 40.0], [32.0, 39.0]]]}


def _saha(kimlik, tur, alt, ust, **ek):
    """openAIP airspace-schema.json biçiminde bir kayıt."""
    return {
        "_id": kimlik,
        "name": f"LTR{kimlik}",
        "type": tur,
        "geometry": KARE,
        "lowerLimit": alt,
        "upperLimit": ust,
        **ek,
    }


def _limit(deger, birim, referans):
    return {"value": deger, "unit": birim, "referenceDatum": referans}


@pytest.mark.parametrize(
    "limit, ust, beklenen",
    [
        (_limit(195, 6, 2), True, 19500),
        (_limit(3000, 1, 1), True, 3000),
        (_limit(1000, 0, 1), True, 3281),
        (_limit(0, 1, 0), False, 0),
        (_limit(500, 1, 0), True, 15500),
        (_limit(999, 6, 2), True, None),
        (_limit(10, 99, 1), False, None),
        (None, True, None),
    ],
    ids=["FL", "feet_msl", "metre", "yer", "agl_ust_pay", "sinirsiz", "bilinmeyen_birim", "yok"],
)
def test_dikey_limitler_feete_cevrilir(limit, ust, beklenen):
    assert oa.limit_ft(limit, ust) == beklenen


def test_sadece_secilen_turler_ve_gecerli_sahalar_donusturulur():
    turler = {1, 3}
    kisitli = oa.openaip_ozelligine_cevir(
        _saha("r1", 1, _limit(0, 1, 0), _limit(195, 6, 2), byNotam=True, activeUntil="2026-12-31T00:00:00Z"), turler
    )
    assert kisitli["properties"]["tur"] == "KISITLI"
    assert (kisitli["properties"]["taban_ft"], kisitli["properties"]["tavan_ft"]) == (0, 19500)
    assert "NOTAM" in kisitli["properties"]["aciklama"] and kisitli["properties"]["bitis"] == "2026-12-31T00:00:00Z"
    assert oa.openaip_ozelligine_cevir(_saha("p1", 3, None, None), turler)["properties"]["tur"] == "YASAK"
    assert oa.openaip_ozelligine_cevir(_saha("d1", 2, None, None), turler) is None
    assert oa.openaip_ozelligine_cevir(_saha("ctr", 4, None, None), turler) is None
    ters = _saha("r2", 1, _limit(300, 6, 2), _limit(100, 6, 2))
    assert oa.openaip_ozelligine_cevir(ters, turler) is None


def test_anahtar_yoksa_ya_da_hic_saha_gelmezse_mevcut_veri_korunur(monkeypatch):
    monkeypatch.delenv("OPENAIP_API_ANAHTARI", raising=False)
    with pytest.raises(ValueError, match="OPENAIP_API_ANAHTARI"):
        oa.openaip_ice_aktar(["TR"])
    with pytest.raises(ValueError, match="hiç saha gelmedi"):
        oa.openaip_ice_aktar(["TR"], api_anahtari="x", getirici=lambda u, s, a: {"items": []})


@pytest.fixture(autouse=True)
def _openaip_durumunu_geride_birakma():
    """openaip_ice_aktar her denemeyi veri_kaynagi_durumlari'na yazar; testin
    bıraktığı sahte hata/başarı geliştirme veritabanında gerçek zamanlayıcıyı
    (bir sonraki yenileme zamanı son denemeye göre) yanıltmasın."""
    yield
    try:
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(
                text("DELETE FROM veri_kaynagi_durumlari WHERE kaynak = :k"), {"k": oa.OPENAIP_DURUM_ANAHTARI}
            )
    except Exception:
        pass


@pytest.fixture
def test_veritabani():
    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    with motor.begin() as baglanti:
        onceki = baglanti.execute(text("SELECT count(*) FROM kisitli_hava_sahalari WHERE kaynak = 'openaip'")).scalar()
    if onceki:
        pytest.skip("Geliştirme veritabanında gerçek openAIP verisi var; test ona dokunmaz.")
    yield motor
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM kisitli_hava_sahalari WHERE kaynak = 'openaip'"))


def test_sayfalanan_yanit_ice_aktarilir_ve_kaynak_tam_yenilenir(test_veritabani):
    sayfalar = {
        1: {"items": [_saha("r1", 1, _limit(0, 1, 0), _limit(195, 6, 2)), _saha("d1", 2, None, None)], "nextPage": 2},
        2: {"items": [_saha("p1", 3, None, None)]},
    }
    istekler = []

    def getirici(ulke, sayfa, anahtar):
        istekler.append((ulke, sayfa, anahtar))
        return sayfalar[sayfa]

    sonuc = oa.openaip_ice_aktar(["tr"], api_anahtari="gizli", getirici=getirici)
    assert istekler == [("TR", 1, "gizli"), ("TR", 2, "gizli")]
    assert (sonuc["kaydedilen"], sonuc["kaldirilan"], sonuc["atlanan"]) == (2, 0, 0)
    simdi = datetime.now(UTC)
    kimlikler = {s["dis_kimlik"] for s in gecerli_kisitli_sahalari_getir(simdi, simdi) if s["kaynak"] == "openaip"}
    assert kimlikler == {"openaip:r1", "openaip:p1"}

    sonuc = oa.openaip_ice_aktar(["TR"], api_anahtari="gizli", getirici=lambda u, s, a: sayfalar[2])
    assert (sonuc["kaydedilen"], sonuc["kaldirilan"]) == (1, 1)


def test_ice_aktarma_sonucu_kaynak_durumuna_yazilir(test_veritabani):
    from turbulans_radar.depo.kaynak_durumu import kaynak_durumlarini_getir

    with test_veritabani.begin() as baglanti:
        baglanti.execute(text("DELETE FROM veri_kaynagi_durumlari WHERE kaynak = :k"), {"k": oa.OPENAIP_DURUM_ANAHTARI})
    try:
        oa.openaip_ice_aktar(["TR"], api_anahtari="x", getirici=lambda u, s, a: {"items": [_saha("r1", 1, None, None)]})
        (durum,) = kaynak_durumlarini_getir([oa.OPENAIP_DURUM_ANAHTARI])
        assert durum["son_basari_zamani"] is not None and durum["ardisik_hata_sayisi"] == 0

        with pytest.raises(ValueError):
            oa.openaip_ice_aktar(["TR"], api_anahtari="x", getirici=lambda u, s, a: {"items": []})
        (durum,) = kaynak_durumlarini_getir([oa.OPENAIP_DURUM_ANAHTARI])
        assert durum["ardisik_hata_sayisi"] == 1 and "hiç saha gelmedi" in durum["son_hata"]
    finally:
        with test_veritabani.begin() as baglanti:
            baglanti.execute(
                text("DELETE FROM veri_kaynagi_durumlari WHERE kaynak = :k"), {"k": oa.OPENAIP_DURUM_ANAHTARI}
            )
