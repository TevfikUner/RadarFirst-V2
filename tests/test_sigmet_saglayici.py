from datetime import UTC, datetime, timedelta

import pytest
import shapely
from sqlalchemy import text

from turbulans_radar.depo import veritabani as vt
from turbulans_radar.veri import sigmet_saglayici as ss

_SIMDI = int(datetime.now(UTC).timestamp())


@pytest.fixture(autouse=True)
def _fir_verisi_varsayilan_yok(monkeypatch):
    """Testler makinede gerçekten indirilmiş fir_sinirlari.geojson olsun ya
    da olmasın AYNI (deterministik) sonucu vermeli -- bu yüzden FIR sınırı
    varsayılan olarak 'yok' sayılır; FIR yedeğini test eden testler kendi
    içinde fir_geometrisi'ni açıkça mockluyor (bkz. aşağıdaki testler)."""
    monkeypatch.setattr(ss, "fir_geometrisi", lambda fir_kodu: None)


ULUSLARARASI_ORNEK = {
    "icaoId": "LTAA",
    "firId": "LTAA",
    "firName": "LTAA ANKARA",
    "validTimeFrom": _SIMDI - 3600,
    "validTimeTo": _SIMDI + 3600,
    "seriesId": "T01",
    "hazard": "TURB",
    "qualifier": "SEV",
    "base": None,
    "top": 39000,
    "geom": "AREA",
    "coords": [{"lat": 38.0, "lon": 30.0}, {"lat": 40.0, "lon": 30.0}, {"lat": 40.0, "lon": 32.0}],
    "rawSigmet": "LTAA SIGMET T01 VALID ... SEV TURB",
}

ABD_ORNEK = {
    "icaoId": "KKCI",
    "seriesId": "11E",
    "validTimeFrom": _SIMDI - 3600,
    "validTimeTo": _SIMDI + 3600,
    "airSigmetType": "SIGMET",
    "hazard": "CONVECTIVE",
    "altitudeLow1": None,
    "altitudeLow2": 5000,
    "altitudeHi1": 32000,
    "altitudeHi2": 34000,
    "coords": [{"lat": 41.0, "lon": -70.0}, {"lat": 40.0, "lon": -71.0}, {"lat": 39.0, "lon": -74.0}],
    "rawAirSigmet": "CONVECTIVE SIGMET 11E",
}


def test_uluslararasi_kayit_normalize_edilir_ve_poligon_kapanir():
    kayit = ss.sigmet_kaydini_normalize_et("isigmet", ULUSLARARASI_ORNEK)
    assert kayit["fir_kodu"] == "LTAA"
    assert kayit["tehlike"] == "TURB"
    assert (kayit["taban_ft"], kayit["tavan_ft"]) == (None, 39000)
    assert kayit["poligon"][0] == kayit["poligon"][-1] == [30.0, 38.0]
    assert (kayit["enlem_min"], kayit["enlem_maks"], kayit["boylam_min"], kayit["boylam_maks"]) == (38, 40, 30, 32)
    assert kayit["gecerlilik_bitis"] - kayit["gecerlilik_baslangic"] == timedelta(hours=2)


def test_abd_kaydinin_irtifa_bandi_en_genis_aralik_olarak_alinir():
    kayit = ss.sigmet_kaydini_normalize_et("airsigmet", ABD_ORNEK)
    assert (kayit["taban_ft"], kayit["tavan_ft"]) == (5000, 34000)
    assert kayit["tehlike"] == "CONVECTIVE"


def test_airmet_ve_poligonsuz_kayit_elenir():
    assert ss.sigmet_kaydini_normalize_et("airsigmet", {**ABD_ORNEK, "airSigmetType": "AIRMET"}) is None
    assert (
        ss.sigmet_kaydini_normalize_et("isigmet", {**ULUSLARARASI_ORNEK, "coords": ULUSLARARASI_ORNEK["coords"][:2]})
        is None
    )


def test_ayni_kayit_ayni_dis_kimligi_uretir():
    a = ss.sigmet_kaydini_normalize_et("isigmet", ULUSLARARASI_ORNEK)
    b = ss.sigmet_kaydini_normalize_et("isigmet", dict(ULUSLARARASI_ORNEK))
    c = ss.sigmet_kaydini_normalize_et("isigmet", {**ULUSLARARASI_ORNEK, "seriesId": "T02"})
    assert a["dis_kimlik"] == b["dis_kimlik"] != c["dis_kimlik"]


@pytest.fixture
def test_veritabani():
    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    yield motor
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM sigmetler WHERE kaynak = 'test'"))
        baglanti.execute(text("DELETE FROM veri_kaynagi_durumlari WHERE kaynak IN ('sigmet:test', 'sigmet:test_yok')"))


def test_guncelleme_upsert_eder_ve_akistan_dusen_sigmeti_sonlandirir(test_veritabani):
    ikinci = {**ULUSLARARASI_ORNEK, "seriesId": "T02", "hazard": "TS"}
    akislar = [[ULUSLARARASI_ORNEK, ikinci], [ULUSLARARASI_ORNEK, ikinci], [ULUSLARARASI_ORNEK]]

    def sahte_getirici(kaynak):
        return akislar.pop(0)

    for _ in range(2):
        ozet = ss.sigmetleri_guncelle(getirici=sahte_getirici, kaynaklar=("test",))
    assert ozet["kaydedilen"] == 2 and ozet["sonlandirilan"] == 0
    simdi = datetime.now(UTC)
    assert len([s for s in ss.gecerli_sigmetleri_getir(simdi, simdi) if s["kaynak"] == "test"]) == 2

    ozet = ss.sigmetleri_guncelle(getirici=sahte_getirici, kaynaklar=("test",))
    assert ozet["sonlandirilan"] == 1
    sonra = datetime.now(UTC) + timedelta(seconds=1)
    aktif = [s for s in ss.gecerli_sigmetleri_getir(sonra, sonra) if s["kaynak"] == "test"]
    assert [s["tehlike"] for s in aktif] == ["TURB"]


def test_basarisiz_kaynak_mevcut_kayitlara_dokunmaz(test_veritabani):
    ss.sigmetleri_guncelle(getirici=lambda k: [ULUSLARARASI_ORNEK], kaynaklar=("test",))

    def hatali(kaynak):
        raise TimeoutError("AWC yanıt vermedi")

    ozet = ss.sigmetleri_guncelle(getirici=hatali, kaynaklar=("test",))
    assert ozet["kaynak_hatalari"] == {"test": "TimeoutError"}
    simdi = datetime.now(UTC)
    assert [s for s in ss.gecerli_sigmetleri_getir(simdi, simdi) if s["kaynak"] == "test"]


def test_kutu_ve_tehlike_filtresi(test_veritabani):
    ss.sigmetleri_guncelle(getirici=lambda k: [ULUSLARARASI_ORNEK], kaynaklar=("test",))
    simdi = datetime.now(UTC)

    def testler(**filtre):
        return [s for s in ss.gecerli_sigmetleri_getir(simdi, simdi, **filtre) if s["kaynak"] == "test"]

    assert testler(enlem_min=39, enlem_maks=41, boylam_min=31, boylam_maks=33)
    assert not testler(enlem_min=10, enlem_maks=20, boylam_min=31, boylam_maks=33)
    assert not testler(tehlikeler=["ICE"])


def test_antimeridyeni_kesen_poligon_surekli_boylama_tasinir():
    pasifik = {
        **ULUSLARARASI_ORNEK,
        "firId": "NZZO",
        "coords": [
            {"lat": 30.0, "lon": 175.0},
            {"lat": 30.0, "lon": -175.0},
            {"lat": 40.0, "lon": -175.0},
            {"lat": 40.0, "lon": 175.0},
        ],
    }
    kayit = ss.sigmet_kaydini_normalize_et("isigmet", pasifik)
    assert [k[0] for k in kayit["poligon"]] == [175.0, 185.0, 185.0, 175.0, 175.0]
    assert (kayit["boylam_min"], kayit["boylam_maks"]) == (-180.0, 180.0)


def test_cok_alanli_sigmet_her_alan_icin_ayri_kayit_uretir():
    cok_alanli = {
        **ULUSLARARASI_ORNEK,
        "firId": "FCCC",
        "hazard": "TS",
        "geom": "AREAS",
        "coords": [
            [{"lon": 11.633, "lat": 1.183}, {"lon": 11.05, "lat": 0.667}, {"lon": 10.717, "lat": 1.533}],
            [{"lon": 13.017, "lat": 4.383}, {"lon": 13.067, "lat": 3.967}, {"lon": 12.483, "lat": 4.167}],
        ],
    }
    kayitlar, neden = ss.sigmet_kayitlarini_cozumle("isigmet", cok_alanli)
    assert neden is None
    assert len(kayitlar) == 2 and kayitlar[0]["dis_kimlik"] != kayitlar[1]["dis_kimlik"]
    assert [k["poligon"][0] for k in kayitlar] == [[11.633, 1.183], [13.017, 4.383]]
    assert all(k["tehlike"] == "TS" and k["fir_kodu"] == "FCCC" for k in kayitlar)


def test_tek_alanli_kaydin_dis_kimligi_degismedi():
    import hashlib
    import json

    anahtar = [
        "isigmet",
        "LTAA",
        "LTAA",
        "T01",
        ULUSLARARASI_ORNEK["validTimeFrom"],
        "TURB",
        [(k["lat"], k["lon"]) for k in ULUSLARARASI_ORNEK["coords"]],
    ]
    beklenen = hashlib.sha1(json.dumps(anahtar, sort_keys=True).encode()).hexdigest()
    assert ss.sigmet_kaydini_normalize_et("isigmet", ULUSLARARASI_ORNEK)["dis_kimlik"] == beklenen


@pytest.mark.parametrize(
    "ham, neden",
    [
        ({**ULUSLARARASI_ORNEK, "coords": [[30.0, 38.0], [30.0, 40.0], [32.0, 40.0]]}, "poligon_yok"),
        ({**ULUSLARARASI_ORNEK, "validTimeTo": "2026-09-26T21:40:00Z"}, "bicim_hatasi"),
        ({**ULUSLARARASI_ORNEK, "validTimeFrom": None}, "gecerlilik_yok"),
        ("SIGMET metni", "bicim_hatasi"),
    ],
    ids=["koordinat_dizisi", "iso_zaman", "gecerlilik_eksik", "sozluk_degil"],
)
def test_bozuk_kayit_istisna_firlatmadan_nedeniyle_elenir(ham, neden):
    assert ss.sigmet_kayitlarini_cozumle("isigmet", ham) == ([], neden)


def test_makul_olmayan_irtifa_bandi_muhafazakar_genisletilir():
    def bant(**alanlar):
        kayit = ss.sigmet_kaydini_normalize_et("isigmet", {**ULUSLARARASI_ORNEK, **alanlar})
        return kayit["taban_ft"], kayit["tavan_ft"]

    assert bant(base=None, top="FL390") == (None, None)
    assert bant(base=10000, top=390000) == (10000, None)
    assert bant(base=30000, top=20000) == (None, None)


def test_tehlikesi_okunamayan_sigmet_bilinmiyor_olarak_saklanir():
    kayit = ss.sigmet_kaydini_normalize_et("isigmet", {**ULUSLARARASI_ORNEK, "hazard": None})
    assert kayit["tehlike"] == "BILINMIYOR"
    assert "BILINMIYOR" in ss.kacinilacak_tehlikeler()


def _aktif_test_sigmetleri():
    sonra = datetime.now(UTC) + timedelta(seconds=1)
    return [s for s in ss.gecerli_sigmetleri_getir(sonra, sonra) if s["kaynak"] == "test"]


def test_sema_degisikliginde_mevcut_sigmetler_korunur_ve_kaynak_hatali_isaretlenir(test_veritabani):
    ikinci = {**ULUSLARARASI_ORNEK, "seriesId": "T02", "hazard": "TS"}
    ss.sigmetleri_guncelle(getirici=lambda k: [ULUSLARARASI_ORNEK, ikinci], kaynaklar=("test",))
    ilk_basari = ss.son_guncelleme_zamani(kaynaklar=("test",))
    assert ilk_basari is not None and ss.sorunlu_kaynaklar(kaynaklar=("test",)) == []

    yeni_sema = [{**h, "geometry": h["coords"], "coords": None} for h in (ULUSLARARASI_ORNEK, ikinci)]
    ozet = ss.sigmetleri_guncelle(getirici=lambda k: yeni_sema, kaynaklar=("test",))

    assert ozet["sonlandirilan"] == 0
    assert "şema uyuşmazlığı" in ozet["kaynak_hatalari"]["test"]
    kaynak_ozeti = ozet["kaynaklar"]["test"]
    assert (kaynak_ozeti["ham"], kaynak_ozeti["cozumlenemeyen"], kaynak_ozeti["durum"]) == (2, 2, "hata")
    assert len(_aktif_test_sigmetleri()) == 2
    assert ss.son_guncelleme_zamani(kaynaklar=("test",)) == ilk_basari
    assert ss.sorunlu_kaynaklar(kaynaklar=("test",)) == ["test"]


@pytest.mark.parametrize("akis", [[], {"error": "bakim"}], ids=["bos", "liste_degil"])
def test_bos_ya_da_liste_olmayan_akis_mevcut_sigmetleri_sonlandirmaz(test_veritabani, akis):
    ss.sigmetleri_guncelle(getirici=lambda k: [ULUSLARARASI_ORNEK], kaynaklar=("test",))
    ozet = ss.sigmetleri_guncelle(getirici=lambda k: akis, kaynaklar=("test",))
    assert ozet["sonlandirilan"] == 0 and "test" in ozet["kaynak_hatalari"]
    assert len(_aktif_test_sigmetleri()) == 1


def test_esik_altindaki_cozumlenemeyen_kayit_guncellemeyi_durdurmaz(test_veritabani):
    saglam = [{**ULUSLARARASI_ORNEK, "seriesId": f"T{i:02d}"} for i in range(4)]
    bozuk = {**ULUSLARARASI_ORNEK, "seriesId": "T99", "coords": []}
    ozet = ss.sigmetleri_guncelle(getirici=lambda k: [*saglam, bozuk], kaynaklar=("test",))
    assert ozet["kaynak_hatalari"] == {}
    assert ozet["kaynaklar"]["test"]["cozumlenemeyen"] == 1
    assert ozet["kaynaklar"]["test"]["nedenler"] == {"poligon_yok": 1}
    assert len(_aktif_test_sigmetleri()) == 4


def test_hic_basarili_cekim_yapilmamis_kaynak_bayat_sayilir(test_veritabani):
    assert ss.son_guncelleme_zamani(kaynaklar=("test_yok",)) is None
    assert ss.sorunlu_kaynaklar(kaynaklar=("test_yok",)) == ["test_yok"]

    def hatali(kaynak):
        raise TimeoutError("AWC yanıt vermedi")

    ss.sigmetleri_guncelle(getirici=hatali, kaynaklar=("test_yok",))
    ss.sigmetleri_guncelle(getirici=hatali, kaynaklar=("test_yok",))
    durum = ss.kaynak_saglik_durumlari(kaynaklar=("test_yok",))[0]
    assert durum["ardisik_hata_sayisi"] == 2 and durum["son_basari_zamani"] is None
    assert durum["son_hata"].startswith("TimeoutError")


@pytest.mark.parametrize(
    "alanlar, beklenen",
    [
        ({"dir": "NE", "spd": "25"}, (45.0, 25.0)),
        ({"dir": "-", "spd": "0"}, (None, None)),
        ({"dir": "E", "spd": "0"}, (None, None)),
        ({"dir": "WNW", "spd": "UNK"}, (292.5, None)),
        ({"dir": "E", "spd": "20", "rawSigmet": "LTAA SIGMET T01 ... MOV E 20KMH NC="}, (90.0, 20 / 1.852)),
        ({}, (None, None)),
    ],
    ids=["kuzeydogu_25kt", "duragan", "hiz_sifir", "hiz_bilinmiyor", "kmh", "bilgi_yok"],
)
def test_uluslararasi_sigmet_hareketi_yoneldigi_yon_olarak_okunur(alanlar, beklenen):
    kayit = ss.sigmet_kaydini_normalize_et("isigmet", {**ULUSLARARASI_ORNEK, **alanlar})
    assert kayit["hareket_yonu_derece"] == beklenen[0]
    assert kayit["hareket_hizi_kt"] == (pytest.approx(beklenen[1]) if beklenen[1] is not None else None)


def test_abd_sigmet_hareketi_geldigi_yondan_yoneldigi_yone_cevrilir():
    kayit = ss.sigmet_kaydini_normalize_et(
        "airsigmet", {**ABD_ORNEK, "movementDir": 260, "movementSpd": 25, "rawAirSigmet": "MOV FROM 26025KT"}
    )
    assert (kayit["hareket_yonu_derece"], kayit["hareket_hizi_kt"]) == (80.0, 25.0)
    az = ss.sigmet_kaydini_normalize_et("airsigmet", {**ABD_ORNEK, "movementDir": 260, "rawAirSigmet": "MOV LTL"})
    assert (az["hareket_yonu_derece"], az["hareket_hizi_kt"]) == (None, None)


# --- FIR sınır yedeği: koordinatsız SIGMET'ler (bkz. fir_sinirlari.py) ---

_FIR_KARESI = shapely.Polygon([(28.0, 36.0), (36.0, 36.0), (36.0, 42.0), (28.0, 42.0), (28.0, 36.0)])


def test_koordinati_olmayan_sigmet_fir_bilinmiyorsa_yine_elenir():
    """fir_geometrisi None dönerse (varsayılan mock) eski davranış korunur."""
    koordinatsiz = {**ULUSLARARASI_ORNEK, "coords": []}
    assert ss.sigmet_kayitlarini_cozumle("isigmet", koordinatsiz) == ([], "poligon_yok")


def test_koordinati_olmayan_sigmet_fir_biliniyorsa_firin_tamamina_genisler(monkeypatch):
    monkeypatch.setattr(ss, "fir_geometrisi", lambda fir_kodu: _FIR_KARESI if fir_kodu == "LTAA" else None)
    koordinatsiz = {**ULUSLARARASI_ORNEK, "coords": [], "rawSigmet": "LTAA SIGMET T01 ENTIRE FIR SEV TURB"}
    kayitlar, neden = ss.sigmet_kayitlarini_cozumle("isigmet", koordinatsiz)
    assert neden == "fir_poligonu"
    assert len(kayitlar) == 1
    assert kayitlar[0]["fir_kodu"] == "LTAA"
    assert (kayitlar[0]["enlem_min"], kayitlar[0]["enlem_maks"]) == (36.0, 42.0)
    assert (kayitlar[0]["boylam_min"], kayitlar[0]["boylam_maks"]) == (28.0, 36.0)
    # Bilinmeyen FIR kodu için hâlâ eski (elenen) davranış.
    assert ss.sigmet_kayitlarini_cozumle("isigmet", {**koordinatsiz, "firId": "ZZZZ"}) == ([], "poligon_yok")


def test_fir_yedegi_gecerli_kayittan_farkli_cok_parcali_firda_parca_basina_kayit(monkeypatch):
    ikinci_parca = shapely.Polygon([(100.0, 10.0), (110.0, 10.0), (110.0, 20.0), (100.0, 20.0), (100.0, 10.0)])
    coklu = shapely.union_all([_FIR_KARESI, ikinci_parca])
    monkeypatch.setattr(ss, "fir_geometrisi", lambda fir_kodu: coklu)
    kayitlar, neden = ss.sigmet_kayitlarini_cozumle("isigmet", {**ULUSLARARASI_ORNEK, "coords": []})
    assert neden == "fir_poligonu"
    assert len(kayitlar) == 2
    assert len({k["dis_kimlik"] for k in kayitlar}) == 2  # kimlikler benzersiz üretildi


def test_fir_yedegi_esik_hesabinda_cozumlenemeyen_gibi_sayilir(test_veritabani, monkeypatch):
    """FIR'a genişletme çözümlenemeyen gibi sayılmazsa, AWC koordinatları TOPTAN
    kaldırsa bile her SIGMET FIR'a genişleyip 'akış sağlıklı' görünebilirdi --
    bu da gerçek şema bozulmasını (madde 1'in koruduğu senaryo) maskelerdi."""
    monkeypatch.setattr(ss, "fir_geometrisi", lambda fir_kodu: _FIR_KARESI if fir_kodu == "LTAA" else None)
    hepsi_koordinatsiz = [{**ULUSLARARASI_ORNEK, "seriesId": f"T{i:02d}", "coords": []} for i in range(4)]
    ozet = ss.sigmetleri_guncelle(getirici=lambda k: hepsi_koordinatsiz, kaynaklar=("test",))
    assert "şema uyuşmazlığı" in ozet["kaynak_hatalari"]["test"]
    assert ozet["kaynaklar"]["test"]["fir_poligonu"] == 4
    # Kayıtlar hesaplanıp DB'ye yazılsa da (dürüst geçici bilgi), akış "tamam" sayılmaz.
    assert ozet["kaynaklar"]["test"]["durum"] == "hata"
