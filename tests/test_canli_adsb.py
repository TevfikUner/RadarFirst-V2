"""Canlı ADS-B oturumu. Ağ çağrıları ve uçak verisi SENTETİKTİR; gerçek sağlayıcıya istek gitmez."""

import contextlib

import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.veri import canli_adsb as ca


@pytest.fixture(autouse=True)
def etkin(monkeypatch):
    monkeypatch.setattr(config, "CANLI_ADSB_ETKIN", True)


def _yanit(now_ms, ucaklar):
    return {"now": now_ms, "ac": ucaklar}


def test_normalize_konumsuz_ve_yerdekileri_atar_birimleri_cevirir():
    df = ca.yaniti_normalize_et(
        _yanit(
            1_700_000_000_000,
            [
                {
                    "hex": "4B1234",
                    "flight": "THY1  ",
                    "lat": 40.0,
                    "lon": 30.0,
                    "alt_baro": 36000,
                    "baro_rate": 600,
                    "seen_pos": 2.0,
                },
                {"hex": "4b9999", "lat": 40.0, "lon": 30.0, "alt_baro": "ground"},
                {"hex": "4b8888", "alt_baro": 30000},
            ],
        )
    )
    assert list(df["icao24"]) == ["4b1234"] and df["ucus_numarasi"].iloc[0] == "THY1"
    assert round(df["baro_irtifa_m"].iloc[0], 1) == round(36000 * 0.3048, 1)
    assert round(df["dikey_hiz"].iloc[0], 3) == round(600 * 0.3048 / 60, 3)
    assert df["zaman"].iloc[0] == pd.Timestamp(1_700_000_000_000, unit="ms", tz="UTC") - pd.Timedelta(seconds=2)


def test_429_veren_saglayici_atlanir_sonraki_kullanilir_ve_kota_uygulanir():
    istenen, saat = [], [0.0]

    def getirici(url):
        istenen.append(url)
        return (429, None) if "adsb.fi" in url else (200, _yanit(0, []))

    s = ca.BolgeSorgulayici(["adsb_fi", "adsb_lol"], getirici=getirici, sayac=lambda: 1, saat=lambda: saat[0])
    _, ad = s.sorgula(39.0, 35.0, 250)
    assert ad == "adsb_lol" and "opendata.adsb.fi/api/v3/lat/39.0000/lon/35.0000/dist/250" in istenen[0]
    istenen.clear()
    s.sorgula(39.0, 35.0, 250)
    assert len(istenen) == 1 and "adsb.lol" in istenen[0]
    saat[0] = config.CANLI_ADSB_429_BEKLEME_SANIYE + 1
    istenen.clear()
    s.sorgula(39.0, 35.0, 250)
    assert "adsb.fi" in istenen[0]
    kotali = ca.BolgeSorgulayici(["adsb_fi"], getirici=getirici, sayac=lambda: config.CANLI_ADSB_GUNLUK_MAKS_ISTEK + 1)
    with pytest.raises(ca.CanliAdsbKotaHatasi):
        kotali.sorgula(39.0, 35.0, 250)


def test_oturum_araligi_alt_sinira_cekilir_izleri_ucak_bazinda_uretir():
    sira = iter(range(1000))

    class Sahte:
        kullanilan = {"adsb_fi"}

        def sorgula(self, enlem, boylam, yaricap_nm):
            i = next(sira)
            return ca.yaniti_normalize_et(
                _yanit(
                    1_700_000_000_000 + i * 10_000,
                    [
                        {"hex": "aaa111", "flight": "TST1", "lat": 40.0, "lon": 30.0 + i / 100, "alt_baro": 36000},
                        {"hex": "bbb222", "lat": 41.0, "lon": 31.0, "alt_baro": 34000} if i < 2 else {},
                    ],
                )
            ), "adsb_fi"

    saat, uykular, uretilen = [0.0], [], []

    def uyku(s):
        uykular.append(s)
        saat[0] += s

    ozet = ca.canli_oturum(
        sure_dk=1,
        aralik_saniye=1,
        sorgulayici=Sahte(),
        uyku=uyku,
        saat=lambda: saat[0],
        kilit=contextlib.nullcontext(),
        pirep_uretici=lambda iz, kaynak, yayinla, icao24, ucus_numarasi: (
            uretilen.append((icao24, len(iz), ucus_numarasi)) or {"kaydedilen": 1}
        ),
    )
    assert set(uykular) == {config.CANLI_ADSB_MIN_ARALIK_SANIYE}
    assert ozet["istek"] == 60 / config.CANLI_ADSB_MIN_ARALIK_SANIYE + 1
    assert uretilen == [("aaa111", ozet["istek"], "TST1")] and ozet["olay"] == 1 and ozet["ucak"] == 2
    assert ozet["atif"] == [ca.ATIF["adsb_fi"]]


def test_kapaliyken_oturum_baslamaz(monkeypatch):
    monkeypatch.setattr(config, "CANLI_ADSB_ETKIN", False)
    with pytest.raises(ca.CanliAdsbKapaliHatasi):
        ca.canli_oturum(sorgulayici=object(), kilit=contextlib.nullcontext())
