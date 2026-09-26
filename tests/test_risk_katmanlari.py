from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from turbulans_radar.rota.risk_katmanlari import RiskDegerlendirmesi, SigmetKisitKatmani, degerlendirmeleri_birlestir

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
        (_kare_sigmet(), 41000, SIMDI),
        (_kare_sigmet(taban=None, tavan=None), 1000, SIMDI - timedelta(hours=3)),
        (_kare_sigmet(tehlike="ICE"), 34000, SIMDI),
    ],
    ids=["tavanin_ustunde", "gecerlilik_disinda", "kacinilmayan_tehlike"],
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
