"""Ayırma göstergesi testleri: rota ve trafik SENTETİKTİR (geometri testi)."""

import numpy as np
import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.dogrulama import ayirma_gostergesi as ag

BAS = pd.Timestamp("2019-01-15T10:00Z")
NM_DERECE = 1.852 / 111.2


def _rota(dakika=20):
    zamanlar = [BAS, BAS + pd.Timedelta(minutes=dakika)]
    return [40.0, 40.0], [30.0, 32.0], zamanlar, 35000.0


def _trafik(icao24, enlem_kayma_nm, irtifa_ft, zaman_kayma_dk=0, boylam=31.0):
    zaman = BAS + pd.Timedelta(minutes=10 + zaman_kayma_dk)
    return {
        "zaman_unix": int(zaman.timestamp()),
        "icao24": icao24,
        "enlem": 40.0 + enlem_kayma_nm * NM_DERECE,
        "boylam": boylam,
        "baro_irtifa_m": irtifa_ft / ag.METRE_FT,
        "geo_irtifa_m": np.nan,
    }


def test_yorunge_adim_ve_uclar():
    yor = ag.yorunge(*_rota(), adim_sn=10)
    assert len(yor) == 121
    assert yor["boylam"].iloc[0] == 30.0 and yor["boylam"].iloc[-1] == pytest.approx(32.0)
    assert (yor["irtifa_ft"] == 35000.0).all()


def test_ihlal_yatay_ve_dikey_birlikte_aranir():
    trafik = pd.DataFrame(
        [
            _trafik("aaaaa1", 3, 35500),
            _trafik("aaaaa2", 3, 37000),
            _trafik("aaaaa3", 8, 35000),
            _trafik("aaaaa4", 1, 35000, zaman_kayma_dk=40),
            _trafik("kendisi", 0, 35000),
        ]
    )
    ihlaller = ag.ihlalleri_bul(ag.yorunge(*_rota()), trafik, haric_icao24="KENDISI")
    assert list(ihlaller["icao24"]) == ["aaaaa1"]
    satir = ihlaller.iloc[0]
    assert satir["min_yatay_nm"] < 5 and satir["min_dikey_ft"] == pytest.approx(500, abs=1)


def test_bos_trafik_ihlal_uretmez():
    assert ag.ihlalleri_bul(ag.yorunge(*_rota()), pd.DataFrame()).empty
    assert ag.ihlalleri_bul(ag.yorunge(*_rota()), None).empty


def test_rotalar_icin_ozet():
    trafik = pd.DataFrame([_trafik("aaaaa1", 2, 35200)])
    sonuc = ag.rotalar_icin_gosterge(
        {"optimize": _rota(), "uzak": ([45.0, 45.0], [30.0, 32.0], _rota()[2], 35000.0)}, trafik
    )
    assert sonuc["optimize"]["ihlal_eden_ucak"] == 1 and sonuc["optimize"]["en_yakin_dikey_ft"] == 200
    assert sonuc["uzak"] == {"ihlal_eden_ucak": 0, "en_yakin_yatay_nm": None, "en_yakin_dikey_ft": None, "ucaklar": []}


def test_trafik_sorgusu_bolum_ornekleme_ve_sinir():
    sorgu, p = ag.trafik_sorgusu((39.0, 41.0, 29.0, 33.0), BAS, BAS + pd.Timedelta(minutes=90), 32000, 38000)
    assert f"time % {config.AYIRMA_ADIM_SANIYE} = 0" in sorgu and f"LIMIT {config.MAKS_STATE_VECTOR_SATIRI}" in sorgu
    assert p[0] % 3600 == 0 and p[1] - p[0] <= 2 * 3600
    assert p[4:8] == [39.0, 41.0, 29.0, 33.0]
    assert p[8] == pytest.approx(32000 / ag.METRE_FT)


def test_trafik_izleri_varsayilan_sorgu_atmaz_izinle_tek_sorgu_ve_onbellek(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AYIRMA_ONBELLEK_KLASORU", str(tmp_path))
    sorgular = []

    def sahte(baglanti, sorgu, sutunlar, parametreler):
        sorgular.append(parametreler)
        return pd.DataFrame([_trafik("aaaaa1", 2, 35000)])[sutunlar]

    import turbulans_radar.veri.veri_yukleme as vy

    monkeypatch.setattr(vy, "_sorgu_calistir", sahte)
    argumanlar = ((39.0, 41.0, 29.0, 33.0), BAS, BAS + pd.Timedelta(minutes=30), 32000, 38000)
    assert ag.trafik_izleri(*argumanlar) is None and sorgular == []
    assert len(ag.trafik_izleri(*argumanlar, sorgu_izni=True, baglanti=object())) == 1
    assert len(ag.trafik_izleri(*argumanlar, sorgu_izni=True, baglanti=object())) == 1
    assert len(sorgular) == 1


def test_uzun_pencere_reddedilir():
    with pytest.raises(ValueError, match="saatten uzun"):
        ag.trafik_izleri((0, 1, 0, 1), BAS, BAS + pd.Timedelta(hours=5), 30000, 40000, sorgu_izni=True)


def test_kapsayan_onbellek_yeni_sorgu_atmadan_suzer(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AYIRMA_ONBELLEK_KLASORU", str(tmp_path))
    sorgular = []

    def sahte(baglanti, sorgu, sutunlar, parametreler):
        sorgular.append(parametreler)
        return pd.DataFrame([_trafik("aaaaa1", 2, 35000), _trafik("aaaaa2", 2, 35000, zaman_kayma_dk=-9)])[sutunlar]

    import turbulans_radar.veri.veri_yukleme as vy

    monkeypatch.setattr(vy, "_sorgu_calistir", sahte)
    genis = ((39.0, 41.0, 29.0, 33.0), BAS, BAS + pd.Timedelta(minutes=60), 30000, 40000)
    assert len(ag.trafik_izleri(*genis, sorgu_izni=True, baglanti=object())) == 2
    dar = ((39.5, 40.5, 30.0, 32.0), BAS + pd.Timedelta(minutes=5), BAS + pd.Timedelta(minutes=30), 32000, 38000)
    sonuc = ag.trafik_izleri(*dar)
    assert list(sonuc["icao24"]) == ["aaaaa1"] and len(sorgular) == 1
    disarida = ((39.5, 42.0, 30.0, 32.0), BAS, BAS + pd.Timedelta(minutes=30), 32000, 38000)
    assert ag.trafik_izleri(*disarida) is None
