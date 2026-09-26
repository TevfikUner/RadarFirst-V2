import pandas as pd
import pytest

from turbulans_radar.dogrulama import sigmet_dogrulama as sd


def test_metinden_poligon_cikar_dogru_koordinatlar():
    metin = (
        "PAZA SIGMET KILO 1 VALID 150859/151259 PANC-\n"
        "ANCHORAGE FIR OCNL SEV TURB OBS AT 0859Z WI N6142 W15413 - N6046\n"
        "W15126 - N5949 W15240 - N6026 W15509 - N6142 W15413. FL330/FL370."
    )
    poligon = sd._metinden_poligon_cikar(metin)
    assert len(poligon) == 5
    assert poligon[0] == pytest.approx((61.0 + 42 / 60, -(154.0 + 13 / 60)))


def test_metinden_poligon_cikar_guney_dogu_isaretleri():
    metin = "WI S3000 E15030 - S2000 E14000 - S1000 E15000"
    poligon = sd._metinden_poligon_cikar(metin)
    assert poligon[0] == pytest.approx((-30.0, 150.5))


def test_bos_df_hicbir_http_istegi_yapmaz(monkeypatch):
    def patlarsa_hata(*a, **kw):
        raise AssertionError("HTTP isteği yapılmamalıydı")

    monkeypatch.setattr(sd, "sigmetleri_getir", patlarsa_hata)
    sonuc = sd.ucus_sigmet_ile_karsilastir(pd.DataFrame())
    assert sonuc["orta_siddetli_nokta_sayisi"] == 0
    assert sonuc["sigmetler"] == []


def test_esik_altindaki_noktalar_http_istegi_yapmaz(monkeypatch):
    def patlarsa_hata(*a, **kw):
        raise AssertionError("HTTP isteği yapılmamalıydı")

    monkeypatch.setattr(sd, "sigmetleri_getir", patlarsa_hata)
    from turbulans_radar import config

    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-15T10:00:00Z"]),
            "enlem": [40.0],
            "boylam": [30.0],
            "ti1_indeksi": [config.TI1_ESIK_HAFIF / 2],
        }
    )
    sonuc = sd.ucus_sigmet_ile_karsilastir(df)
    assert sonuc["orta_siddetli_nokta_sayisi"] == 0


def _sahte_sigmet(etiket, poligon, baslangic, bitis, turbulansla_ilgili=True):
    return {
        "etiket": etiket,
        "tur": "T" if turbulansla_ilgili else "C",
        "baslangic": pd.Timestamp(baslangic, tz="UTC"),
        "bitis": pd.Timestamp(bitis, tz="UTC"),
        "turbulansla_ilgili": turbulansla_ilgili,
        "poligon": poligon,
        "metin": "...",
    }


def test_poligon_ve_zaman_icindeki_nokta_ortusur(monkeypatch):
    from turbulans_radar import config

    kare = [(60.0, -155.0), (60.0, -154.0), (61.0, -154.0), (61.0, -155.0)]
    sahte = [_sahte_sigmet("TEST1", kare, "2019-01-15T09:00Z", "2019-01-15T13:00Z")]
    monkeypatch.setattr(sd, "sigmetleri_getir", lambda *a, **kw: sahte)

    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-15T10:00:00Z", "2019-01-15T23:00:00Z"]),
            "enlem": [60.5, 60.5],  # ikisi de poligon içinde, ama ikincisi zaman dışında
            "boylam": [-154.5, -154.5],
            "ti1_indeksi": [config.TI1_ESIK_ORTA_SIDDETLI + 1e-8] * 2,
        }
    )
    sonuc = sd.ucus_sigmet_ile_karsilastir(df)
    assert sonuc["orta_siddetli_nokta_sayisi"] == 2
    assert sonuc["sigmetle_ortusen_nokta_sayisi"] == 1
    assert sonuc["ortusme_orani"] == pytest.approx(0.5)


def test_konvektif_sigmet_turbulans_sayilmaz(monkeypatch):
    from turbulans_radar import config

    kare = [(60.0, -155.0), (60.0, -154.0), (61.0, -154.0), (61.0, -155.0)]
    sahte = [_sahte_sigmet("KONVEKTIF", kare, "2019-01-15T09:00Z", "2019-01-15T13:00Z", turbulansla_ilgili=False)]
    monkeypatch.setattr(sd, "sigmetleri_getir", lambda *a, **kw: sahte)

    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-15T10:00:00Z"]),
            "enlem": [60.5],
            "boylam": [-154.5],
            "ti1_indeksi": [config.TI1_ESIK_ORTA_SIDDETLI + 1e-8],
        }
    )
    sonuc = sd.ucus_sigmet_ile_karsilastir(df)
    assert sonuc["toplam_turbulans_sigmeti"] == 0
    assert sonuc["sigmetle_ortusen_nokta_sayisi"] == 0


def test_sigmetleri_getir_gercek_csv_parse_eder(monkeypatch):
    ornek_csv = (
        "NAME,LABEL,TYPE,ISSUE,EXPIRE,PROD_ID,TEXT\n"
        "KILO 1 C,KILO 1,C,2019-01-15T09:02:00Z,2019-01-15T12:59:00Z,ID1,"
        '"PAZA SIGMET KILO 1 VALID 150859/151259 PANC- '
        "ANCHORAGE FIR OCNL SEV TURB OBS AT 0859Z WI N6142 W15413 - N6046 "
        'W15126 - N5949 W15240 - N6026 W15509 - N6142 W15413. FL330/FL370."\n'
    )

    class SahteYanit:
        text = ornek_csv

        def raise_for_status(self):
            pass

    monkeypatch.setattr(sd.httpx, "get", lambda *a, **kw: SahteYanit())

    sigmetler = sd.sigmetleri_getir(pd.Timestamp("2019-01-15T00:00Z"), pd.Timestamp("2019-01-15T12:00Z"))
    assert len(sigmetler) == 1
    assert sigmetler[0]["turbulansla_ilgili"] is True
    assert len(sigmetler[0]["poligon"]) == 5
