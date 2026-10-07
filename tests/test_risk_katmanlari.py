from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from turbulans_radar.rota.risk_katmanlari import (
    KisitliSahaKatmani,
    RiskDegerlendirmesi,
    SigmetKisitKatmani,
    degerlendirmeleri_birlestir,
)

SIMDI = pd.Timestamp(datetime.now(UTC))


def _kare_sigmet(tehlike="TURB", taban=20000, tavan=40000, baslangic=None, bitis=None):
    return {
        "id": 1,
        "fir_kodu": "LTAA",
        "tehlike": tehlike,
        "taban_ft": taban,
        "tavan_ft": tavan,
        "gecerlilik_baslangic": baslangic or SIMDI - timedelta(hours=2),
        "gecerlilik_bitis": bitis or SIMDI + timedelta(hours=2),
        "poligon": [[30.0, 38.0], [32.0, 38.0], [32.0, 40.0], [30.0, 40.0], [30.0, 38.0]],
    }


def _degerlendir(katman, irtifa_ft=34000, zaman=SIMDI):
    konumlar = {"ic": (39.0, 31.0), "dis_bati": (39.0, 29.0), "dis_dogu": (39.0, 33.0)}
    zamanlar = dict.fromkeys(konumlar, zaman)
    kenarlar = [("dis_bati", "dis_dogu")]
    return katman.degerlendir(konumlar, zamanlar, kenarlar, irtifa_ft * 0.3048)


def test_aktif_sigmet_icindeki_dugum_ve_onu_kesen_kenar_yasak():
    sonuc = _degerlendir(SigmetKisitKatmani([_kare_sigmet()]))
    assert sonuc.yasak_dugumler == {"ic"}
    assert sonuc.yasak_kenarlar == {("dis_bati", "dis_dogu")}


@pytest.mark.parametrize(
    "sigmet, irtifa_ft, zaman",
    [
        (_kare_sigmet(), 42000, SIMDI),
        (_kare_sigmet(taban=None, tavan=None), 1000, SIMDI - timedelta(hours=3)),
        (_kare_sigmet(tehlike="ICE"), 34000, SIMDI),
    ],
    ids=["tavanin_dikey_tampon_ustunde", "gecerlilik_disinda", "kacinilmayan_tehlike"],
)
def test_irtifa_zaman_ve_tehlike_disinda_kalan_sigmet_uygulanmaz(sigmet, irtifa_ft, zaman):
    sonuc = _degerlendir(SigmetKisitKatmani([sigmet]), irtifa_ft=irtifa_ft, zaman=zaman)
    assert not sonuc.yasak_dugumler and not sonuc.yasak_kenarlar


def test_tabani_bos_sigmet_yerden_baslar():
    sonuc = _degerlendir(SigmetKisitKatmani([_kare_sigmet(taban=None)]), irtifa_ft=1000)
    assert sonuc.yasak_dugumler == {"ic"}


def test_rota_ihlal_sayisi_nokta_ve_bacaklari_sayar():
    katman = SigmetKisitKatmani([_kare_sigmet()])
    zamanlar = [SIMDI] * 3
    assert katman.rota_ihlal_sayisi([39.0, 39.0, 39.0], [29.0, 31.0, 33.0], zamanlar, 10000.0) == 3
    assert katman.rota_ihlal_sayisi([37.0, 37.0], [29.0, 33.0], zamanlar[:2], 10000.0) == 0


def test_degerlendirmeler_birlestirilirken_cezalar_toplanir():
    a = RiskDegerlendirmesi(yasak_dugumler={1}, dugum_cezasi={2: 10.0})
    b = RiskDegerlendirmesi(yasak_kenarlar={(1, 2)}, dugum_cezasi={2: 5.0, 3: 1.0})
    toplam = degerlendirmeleri_birlestir([a, b])
    assert toplam.yasak_dugumler == {1}
    assert toplam.yasak_kenarlar == {(1, 2)}
    assert toplam.dugum_cezasi == {2: 15.0, 3: 1.0}


def test_antimeridyeni_kesen_sigmet_sadece_kendi_bolgesini_yasaklar():
    sigmet = {**_kare_sigmet(), "poligon": [[175.0, 30.0], [185.0, 30.0], [185.0, 40.0], [175.0, 40.0], [175.0, 30.0]]}
    katman = SigmetKisitKatmani([sigmet])
    konumlar = {"bati_ic": (35.0, -178.0), "dogu_ic": (35.0, 178.0), "turkiye": (35.0, 32.0), "greenwich": (35.0, 0.0)}
    sonuc = katman.degerlendir(konumlar, dict.fromkeys(konumlar, SIMDI), [], 34000 * 0.3048)
    assert sonuc.yasak_dugumler == {"bati_ic", "dogu_ic"}


def test_kendini_kesen_sigmet_poligonu_onarilarak_uygulanir():
    papyon = [[30.0, 38.0], [32.0, 40.0], [32.0, 38.0], [30.0, 40.0], [30.0, 38.0]]
    katman = SigmetKisitKatmani([{**_kare_sigmet(), "poligon": papyon}])
    konumlar = {"sol_lob": (39.0, 30.4), "sag_lob": (39.0, 31.6), "disarida": (37.0, 31.0)}
    sonuc = katman.degerlendir(konumlar, dict.fromkeys(konumlar, SIMDI), [], 34000 * 0.3048)
    assert sonuc.yasak_dugumler == {"sol_lob", "sag_lob"}


def test_tehlikesi_bilinmeyen_sigmetten_muhafazakar_olarak_kacinilir():
    sonuc = _degerlendir(SigmetKisitKatmani([_kare_sigmet(tehlike="BILINMIYOR")]))
    assert sonuc.yasak_dugumler == {"ic"}


def test_suresiz_kisitli_saha_her_zaman_ve_her_irtifada_uygulanir():
    saha = {**_kare_sigmet(taban=None, tavan=None), "gecerlilik_baslangic": None, "gecerlilik_bitis": None}
    sonuc = _degerlendir(KisitliSahaKatmani([saha]), irtifa_ft=41000, zaman=SIMDI + timedelta(days=3650))
    assert sonuc.yasak_dugumler == {"ic"}
    assert sonuc.yasak_kenarlar == {("dis_bati", "dis_dogu")}


def test_gecici_kisitli_saha_sadece_penceresinde_uygulanir():
    saha = {**_kare_sigmet(), "gecerlilik_baslangic": SIMDI + timedelta(hours=1), "gecerlilik_bitis": None}
    assert not _degerlendir(KisitliSahaKatmani([saha])).yasak_dugumler
    assert _degerlendir(KisitliSahaKatmani([saha]), zaman=SIMDI + timedelta(hours=2)).yasak_dugumler == {"ic"}


def test_zaman_belirsizligi_icinde_baslayan_sigmet_muhafazakar_olarak_uygulanir():
    sigmet = _kare_sigmet(baslangic=SIMDI + timedelta(minutes=20), bitis=SIMDI + timedelta(hours=3))
    konumlar = {"ic": (39.0, 31.0)}
    katman = SigmetKisitKatmani([sigmet])
    zamanlar = {"ic": SIMDI}
    assert not katman.degerlendir(konumlar, zamanlar, [], 34000 * 0.3048).yasak_dugumler
    sonuc = katman.degerlendir(konumlar, zamanlar, [], 34000 * 0.3048, zaman_belirsizligi={"ic": timedelta(minutes=30)})
    assert sonuc.yasak_dugumler == {"ic"}


def _hareketli(yon, hiz):
    return {**_kare_sigmet(), "hareket_yonu_derece": yon, "hareket_hizi_kt": hiz}


def test_hareketli_sigmet_varis_zamanindaki_konumuyla_uygulanir():
    # 2 saat önce yayınlanmış, doğuya 60 kt: alan ~2.57° doğuya kaymış (32.6-34.6°D).
    sonuc = _degerlendir(SigmetKisitKatmani([_hareketli(90.0, 60.0)]))
    assert sonuc.yasak_dugumler == {"dis_dogu"}
    assert sonuc.yasak_kenarlar == {("dis_bati", "dis_dogu")}


def test_hizi_bilinmeyen_sigmet_olasi_tum_konumlari_supurur():
    sonuc = _degerlendir(SigmetKisitKatmani([_hareketli(90.0, None)]))
    assert sonuc.yasak_dugumler == {"ic", "dis_dogu"}


def test_rota_ihlali_hareketli_sigmetin_konumuna_gore_sayilir():
    katman = SigmetKisitKatmani([_hareketli(90.0, 60.0)])
    zamanlar = [SIMDI] * 2
    assert katman.rota_ihlal_sayisi([39.0, 39.0], [30.5, 31.5], zamanlar, 10000.0) == 0
    assert katman.rota_ihlal_sayisi([39.0, 39.0], [33.0, 34.0], zamanlar, 10000.0) == 3


_BES_NM_BOYLAM = 9.26 / (111.2 * 0.7771)


@pytest.mark.parametrize(
    "tehlike, tampon_nm, uzaklik_nm, yasak",
    [("TURB", 10, 5, True), ("TURB", 10, 15, False), ("TS", 20, 15, True), ("TS", 20, 25, False)],
)
def test_yanal_tampon_icinden_gecen_rota_ihlal_sayilir(tehlike, tampon_nm, uzaklik_nm, yasak):
    katman = SigmetKisitKatmani([_kare_sigmet(tehlike=tehlike)])
    assert katman.yanal_tampon_nm(katman.sigmetler[0]) == tampon_nm
    boylam = 32.0 + _BES_NM_BOYLAM * uzaklik_nm / 5
    ihlal = katman.rota_ihlal_sayisi([39.0, 41.0], [boylam, boylam], [SIMDI] * 2, 10000.0)
    assert (ihlal > 0) is yasak


def test_tamponsuz_katman_ve_kisitli_saha_poligonun_kendisini_kullanir():
    boylam = 32.0 + _BES_NM_BOYLAM
    sigmet = _kare_sigmet()
    assert SigmetKisitKatmani([sigmet], tamponlu=False).rota_ihlal_sayisi([39.0], [boylam], [SIMDI], 10000.0) == 0
    assert KisitliSahaKatmani([sigmet]).rota_ihlal_sayisi([39.0], [boylam], [SIMDI], 10000.0) == 0
    assert SigmetKisitKatmani([sigmet]).rota_ihlal_sayisi([39.0], [boylam], [SIMDI], 10000.0) == 1


@pytest.mark.parametrize("irtifa_ft, yasak", [(39000, True), (40000, False), (36500, True), (36000, False)])
def test_dikey_tampon_tavan_ustu_ve_taban_alti_payi_ekler(irtifa_ft, yasak):
    sonuc = _degerlendir(SigmetKisitKatmani([_kare_sigmet(taban=37500, tavan=38000)]), irtifa_ft=irtifa_ft)
    assert (sonuc.yasak_dugumler == {"ic"}) is yasak


def test_tampon_antimeridyeni_asarsa_karsi_yarim_kureye_tasinir():
    sigmet = {
        **_kare_sigmet(),
        "poligon": [[170.0, 30.0], [179.95, 30.0], [179.95, 40.0], [170.0, 40.0], [170.0, 30.0]],
    }
    konumlar = {"bati_tamponda": (35.0, -179.9), "bati_uzak": (35.0, -179.0), "dogu_ic": (35.0, 175.0)}
    sonuc = SigmetKisitKatmani([sigmet]).degerlendir(konumlar, dict.fromkeys(konumlar, SIMDI), [], 34000 * 0.3048)
    assert sonuc.yasak_dugumler == {"bati_tamponda", "dogu_ic"}


def test_antimeridyeni_kesen_sigmetin_tamponu_iki_yarim_kurede_uygulanir():
    sigmet = {**_kare_sigmet(), "poligon": [[175.0, 30.0], [185.0, 30.0], [185.0, 40.0], [175.0, 40.0], [175.0, 30.0]]}
    konumlar = {"bati_tamponda": (35.0, -174.9), "dogu_tamponda": (35.0, 174.9), "bati_uzak": (35.0, -174.0)}
    sonuc = SigmetKisitKatmani([sigmet]).degerlendir(konumlar, dict.fromkeys(konumlar, SIMDI), [], 34000 * 0.3048)
    assert sonuc.yasak_dugumler == {"bati_tamponda", "dogu_tamponda"}


def test_tampon_ozeti_yanitta_raporlanir():
    ozet = SigmetKisitKatmani([]).tampon_ozeti()
    assert ozet["yanal_nm"]["TS"] == 20 and ozet["yanal_nm"]["TURB"] == 10
    assert ozet["dikey_ft"] == 1000
    assert "kalibre edilmedi" in ozet["aciklama"]
    assert SigmetKisitKatmani([_kare_sigmet(tehlike="BILINMIYOR")]).yanal_tampon_nm({"tehlike": "BILINMIYOR"}) == 20
