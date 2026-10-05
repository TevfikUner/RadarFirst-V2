from contextlib import contextmanager

import pytest

from turbulans_radar import config
from turbulans_radar.depo import dagitik_kilit
from turbulans_radar.veri import veri_yukleme as vy


class _SahteImlec:
    def __init__(self, kayit):
        self.kayit = kayit

    def execute(self, sorgu, parametreler):
        self.kayit.append(("sorgu", parametreler))

    def fetchall(self):
        return [(1, "a")]


class _SahteBaglanti:
    def __init__(self):
        self.kayit = []

    def cursor(self):
        return _SahteImlec(self.kayit)


@pytest.fixture
def kilit_kaydi(monkeypatch):
    kayit = []

    @contextmanager
    def _kilit(ad, zaman_asimi_saniye=None, **k):
        kayit.append((ad, zaman_asimi_saniye))
        yield True

    monkeypatch.setattr(dagitik_kilit, "dagitik_kilit", _kilit)
    return kayit


def test_sorgu_dagitik_kilit_altinda_ve_kota_sayilarak_calisir(monkeypatch, kilit_kaydi):
    sayac = iter(range(1, 100))
    monkeypatch.setattr("turbulans_radar.depo.hiz_siniri.istegi_say_senkron", lambda anahtar, pencere: next(sayac))
    baglanti = _SahteBaglanti()
    df = vy._sorgu_calistir(baglanti, "SELECT ?", ["x", "y"], [1])
    assert list(df.columns) == ["x", "y"] and baglanti.kayit == [("sorgu", [1])]
    assert kilit_kaydi == [("opensky_trino_sorgusu", config.OPENSKY_SORGU_KILIDI_BEKLEME_SANIYE)]


def test_gunluk_kota_dolunca_opensky_a_sorgu_gitmez(monkeypatch, kilit_kaydi):
    monkeypatch.setattr(config, "OPENSKY_GUNLUK_MAKS_SORGU", 5)
    monkeypatch.setattr("turbulans_radar.depo.hiz_siniri.istegi_say_senkron", lambda anahtar, pencere: 6)
    baglanti = _SahteBaglanti()
    with pytest.raises(vy.OpenSkyKotaAsildiHatasi):
        vy._sorgu_calistir(baglanti, "SELECT 1", ["x"])
    assert baglanti.kayit == []


def test_veritabani_yokken_kota_sayilamaz_sorgu_gitmez(monkeypatch, kilit_kaydi):
    def _db_yok(anahtar, pencere):
        raise ConnectionError("db yok")

    monkeypatch.setattr("turbulans_radar.depo.hiz_siniri.istegi_say_senkron", _db_yok)
    baglanti = _SahteBaglanti()
    with pytest.raises(vy.OpenSkyKotaAsildiHatasi, match="ulaşılamadı"):
        vy._sorgu_calistir(baglanti, "SELECT 1", ["x", "y"])
    assert baglanti.kayit == []


def test_veritabani_kapaliyken_opensky_sorgusu_kilitsiz_calismaz(monkeypatch):
    class _BozukMotor:
        def connect(self):
            raise ConnectionError("db yok")

    monkeypatch.setattr(dagitik_kilit, "_kilit_motoru", lambda: _BozukMotor())
    monkeypatch.setattr(
        "turbulans_radar.depo.hiz_siniri.istegi_say_senkron", lambda *a: pytest.fail("kilitsiz kota sayıldı")
    )
    baglanti = _SahteBaglanti()
    with pytest.raises(dagitik_kilit.KilitAlinamadiHatasi):
        vy._sorgu_calistir(baglanti, "SELECT 1", ["x"])
    assert baglanti.kayit == []
