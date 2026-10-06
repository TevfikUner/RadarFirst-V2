import numpy as np
import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.dogrulama.ayirma_gostergesi import sorgu_irtifa_bandi_ft
from turbulans_radar.rota import rota_optimizasyonu as ro
from turbulans_radar.rota.ucus_seviyeleri import manyetik_iz, seviye_plani, yasal_seyir_seviyeleri


def test_rvsm_dogu_tek_bati_cift_ve_ustte_4000_ft():
    dogu = yasal_seyir_seviyeleri(88)
    bati = yasal_seyir_seviyeleri(268)
    assert [fl for fl in dogu if 290 <= fl <= 410] == [290, 310, 330, 350, 370, 390, 410]
    assert [fl for fl in bati if 290 <= fl <= 410] == [300, 320, 340, 360, 380, 400]
    assert [fl for fl in dogu if fl > 410][:2] == [450, 490]
    assert [fl for fl in bati if fl > 410][:2] == [430, 470]
    assert 270 in dogu and 280 in bati and 280 not in dogu
    assert yasal_seyir_seviyeleri(179.9) == dogu and yasal_seyir_seviyeleri(180.0) == bati


def test_manyetik_iz_sabit_sapmayla_hesaplanir():
    assert manyetik_iz(93.0, 5.0) == pytest.approx(88.0)
    assert manyetik_iz(2.0, 5.0) == pytest.approx(357.0)


def test_088_iz_fl360_en_yakin_yasal_fl_ye_yuvarlanir():
    plan = seviye_plani(36000, 88.0)
    assert plan["fl"] in (350, 370) and plan["duzeltildi"]
    assert {plan["asagi_fl"], plan["yukari_fl"]} <= {330, 350, 370, 390}
    assert plan["yukari_fl"] - plan["fl"] == 2000 / 100 and plan["fl"] - plan["asagi_fl"] == 20


def test_yasal_seviye_degismez_ve_tavan_uygulanir():
    plan = seviye_plani(35000, 88.0)
    assert plan["fl"] == 350 and not plan["duzeltildi"]
    tavanli = seviye_plani(41000, 88.0, azami_fl=398)
    assert tavanli["fl"] == 390 and tavanli["tavan_asildi"] and tavanli["yukari_fl"] is None


def test_rota_088_iz_fl360_uyari_verir_ve_tum_irtifalar_binin_kati():
    # Ekvatorda doğuya gerçek iz 090°, manyetik 085°: doğu yönü, tek FL.
    sonuc = ro.rota_simulasyonu_olustur(5.0, 10.0, 5.0, 25.0, 36000, "2019-01-15T00:00:00", "A320", sigmetler=[])
    assert sonuc["seviye_plani"]["fl"] in (350, 370)
    assert "ucus_seviyesi_duzeltildi" in [b["kod"] for b in sonuc["bulgular"]]
    assert "yarım daire kuralına aykırı" in sonuc["aciklama"]
    irtifalar = [sonuc["normal_rota"]["irtifa_ft"], sonuc["optimize_rota"]["irtifa_ft"]]
    irtifalar += [s["irtifa_ft"] for s in sonuc["secenekler"]]
    assert all(i % 1000 == 0 for i in irtifalar)


def test_alcalmaya_yakit_kredisi_verilmez():
    alcalma = ro._irtifa_degisimi_maliyeti(10668.0, 10058.4, 2400.0)
    tek_yon_saat = 2000.0 / ro.DIKEY_HIZ_FT_DK / 60.0
    assert alcalma == pytest.approx((0.0, 2400.0 * tek_yon_saat * ro.TIRMANMA_EK_YAKIT_ORANI))
    assert alcalma[1] > 0


def _sabit_ruzgar_kupu(u, v):
    zaman = pd.date_range("2019-01-15", periods=3, freq="6h")
    enlem = np.arange(10.0, -10.5, -0.5)
    boylam = np.arange(-1.0, 20.5, 0.5)
    seviye = np.array([200.0, 250.0, 300.0])
    sekil = (len(zaman), len(seviye), len(enlem), len(boylam))
    xr = pytest.importorskip("xarray")
    return xr.Dataset(
        {
            "u": (("valid_time", config.BASINC_BOYUTU, "latitude", "longitude"), np.full(sekil, u)),
            "v": (("valid_time", config.BASINC_BOYUTU, "latitude", "longitude"), np.full(sekil, v)),
        },
        coords={"valid_time": zaman, config.BASINC_BOYUTU: seviye, "latitude": enlem, "longitude": boylam},
    )


def test_100_kt_yan_ruzgar_yer_hizini_dusurur():
    tas = ro.UCAK_PROFILLERI["A320"]["tas_ms"]
    yan_ms = 100.0 * 1852.0 / 3600.0
    enlemler, boylamlar = np.zeros(16), np.linspace(0.0, 15.0, 16)
    mesafe_m = ro.buyuk_daire_mesafesi_km(0.0, 0.0, 0.0, 15.0) * 1000.0
    saniye, _ = ro._rotayi_zamanla(
        enlemler, boylamlar, 35000 * 0.3048, "2019-01-15T06:00:00", tas, _sabit_ruzgar_kupu(0.0, yan_ms), True
    )
    beklenen_saat = mesafe_m / np.sqrt(tas**2 - yan_ms**2) / 3600.0
    assert saniye / 3600.0 == pytest.approx(beklenen_saat, abs=0.005)
    assert saniye / 3600.0 - mesafe_m / tas / 3600.0 > 0.04


def test_yer_hizi_ruzgar_ucgeni():
    assert ro._yer_hizi_ms(230.0, 0.0, 0.0, 90.0) == pytest.approx(230.0)
    assert ro._yer_hizi_ms(230.0, 30.0, 0.0, 90.0) == pytest.approx(260.0)
    assert ro._yer_hizi_ms(230.0, 0.0, 30.0, 90.0) == pytest.approx(np.sqrt(230.0**2 - 30.0**2))


def test_ayirma_sorgu_bandi_seviye_degisikligini_kapsar():
    rotalar = {
        "gercek": ([0, 1], [0, 1], [0, 1], [35000.0, 35000.0]),
        "optimize": ([0, 1], [0, 1], [0, 1], [37000.0, 37000.0]),
    }
    alt, ust = sorgu_irtifa_bandi_ft(rotalar, 35000.0)
    assert alt <= 35000 - config.AYIRMA_DIKEY_FT and ust >= 37000 + config.AYIRMA_DIKEY_FT
