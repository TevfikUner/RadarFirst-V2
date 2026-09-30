import os

import pandas as pd
import pytest

from turbulans_radar.dogrulama import bagimsiz_kanit as bk

T0 = pd.Timestamp("2026-09-20T10:00:00", tz="UTC")
KUTU_TURKIYE = (33.0, 45.0, 24.0, 40.0)
KUTU_ABD = (35.0, 45.0, -80.0, -70.0)


def _turb_sigmet(tehlike="TURB", taban=None, tavan=None):
    return {
        "id": 1,
        "fir_kodu": "LTAA",
        "tehlike": tehlike,
        "taban_ft": taban,
        "tavan_ft": tavan,
        "gecerlilik_baslangic": T0 - pd.Timedelta(hours=1),
        "gecerlilik_bitis": T0 + pd.Timedelta(hours=3),
        "poligon": [[30.5, 38.5], [31.5, 38.5], [31.5, 39.5], [30.5, 39.5], [30.5, 38.5]],
    }


def _pirepler(*satirlar):
    return pd.DataFrame(satirlar, columns=["zaman", "enlem", "boylam", "irtifa_ft", "sinif"])


def _rota(enlem=39.0, irtifa_ft=34000):
    boylamlar = [29.0 + 0.5 * i for i in range(9)]
    zamanlar = [T0 + pd.Timedelta(minutes=5 * i) for i in range(9)]
    return [enlem] * 9, boylamlar, zamanlar, [irtifa_ft] * 9


@pytest.mark.parametrize(
    "metin, sinif",
    [("NEG", 0), ("LGT CHOP", 0), ("LGT-MOD", 1), ("MDT BLO 100FT", 1), ("MOD-SEV", 2), ("EXTM", 2), ("None", None)],
)
def test_pirep_siddet_sinifi(metin, sinif):
    assert bk.pirep_siddet_sinifi(metin) == sinif


@pytest.mark.gercek_veri
def test_pirep_siniflamasi_ml_egitim_etiketleriyle_tutarli():
    if not os.path.exists("pirep_ust_seviye_siniflandirilmis.csv"):
        pytest.skip("ML PIREP etiket dosyası yok.")
    etiketli = pd.read_csv("pirep_ust_seviye_siniflandirilmis.csv")
    tahmin = etiketli["TURBULENCE"].map(bk.pirep_siddet_sinifi)
    assert ((tahmin >= 1) == (etiketli["sinif"] >= 1)).mean() == 1.0


def test_iem_csv_satirlari_normalize_edilir():
    ham = pd.DataFrame(
        {
            "VALID": ["201901151200", "201901151201", "bozuk"],
            "LAT": ["30.39", "65.5", "40"],
            "LON": ["-84.35", "-156.7", "-80"],
            "FL": ["32000", "37000", "30000"],
            "TURBULENCE": ["LGT CHOP", "None", "MOD"],
        }
    )
    df = bk.pirepleri_normalize_et(ham)
    assert len(df) == 1
    assert df.loc[0, "zaman"] == pd.Timestamp("2019-01-15T12:00:00", tz="UTC")
    assert (df.loc[0, "irtifa_ft"], df.loc[0, "sinif"]) == (32000, 0)


def test_rotanin_turb_sigmet_ve_pirep_maruziyeti_sayilir():
    kanit = bk.BagimsizKanit(
        kaynaklar=["test"],
        turb_sigmetleri=[_turb_sigmet()],
        pirepler=_pirepler(
            (T0 + pd.Timedelta(minutes=10), 39.2, 30.0, 34000, 1),
            (T0 + pd.Timedelta(minutes=15), 38.9, 31.0, 35000, 0),
            (T0 + pd.Timedelta(minutes=15), 38.9, 31.0, 25000, 2),
            (T0 + pd.Timedelta(hours=3), 39.0, 30.5, 34000, 2),
            (T0, 41.0, 30.0, 34000, 2),
        ),
    )
    icinden = bk.rota_maruziyeti(kanit, *_rota())
    assert icinden["turb_sigmet"] > 0
    assert (icinden["pirep_raporu"], icinden["mog_pirep"]) == (2, 1)

    uzaktan = bk.rota_maruziyeti(kanit, *_rota(enlem=36.0))
    assert uzaktan == {"turb_sigmet": 0, "pirep_raporu": 0, "mog_pirep": None}


def test_kaynak_kapsamiyorsa_maruziyet_sifir_degil_none():
    assert bk.rota_maruziyeti(bk.BagimsizKanit(), *_rota()) == {
        "turb_sigmet": None,
        "pirep_raporu": None,
        "mog_pirep": None,
    }


def test_irtifa_bandi_disindaki_turb_sigmet_sayilmaz():
    kanit = bk.BagimsizKanit(turb_sigmetleri=[_turb_sigmet(taban=10000, tavan=25000)])
    assert bk.rota_maruziyeti(kanit, *_rota())["turb_sigmet"] == 0


def _iem_cagrilmamali(*args, **kwargs):
    raise AssertionError("Kapsam dışı bölge için IEM'e istek atılmamalı")


_IEM_YASAK = {"iem_sigmet_getirici": _iem_cagrilmamali, "iem_pirep_getirici": _iem_cagrilmamali}


@pytest.fixture
def sahte_arsiv(monkeypatch):
    cagrilar = []

    def sahte_getir(baslangic, bitis, *kutu, tehlikeler=None, motor=None):
        cagrilar.append(tehlikeler)
        return [_turb_sigmet()]

    monkeypatch.setattr(bk, "gecerli_sigmetleri_getir", sahte_getir)
    return cagrilar


def test_sigmet_arsivi_sadece_kapsadigi_ucus_icin_kanittir(monkeypatch, sahte_arsiv):
    monkeypatch.setattr(bk, "arsiv_baslangici", lambda motor=None: T0 - pd.Timedelta(days=2))
    kanit = bk.kanitlari_topla(T0, T0 + pd.Timedelta(hours=2), KUTU_TURKIYE, **_IEM_YASAK)
    assert kanit.kaynaklar == ["sigmet_arsivi"] and len(kanit.turb_sigmetleri) == 1
    assert sahte_arsiv == [bk.TURBULANS_TEHLIKELERI]

    eski = bk.kanitlari_topla(
        pd.Timestamp("2019-01-15T10:00:00", tz="UTC"),
        pd.Timestamp("2019-01-15T12:00:00", tz="UTC"),
        KUTU_TURKIYE,
        **_IEM_YASAK,
    )
    assert eski.kaynaklar == [] and eski.turb_sigmetleri is None and eski.pirepler is None


def test_abd_bolgesinde_iem_kaynaklari_eklenir_ve_hatasi_digerini_durdurmaz(monkeypatch):
    monkeypatch.setattr(bk, "arsiv_baslangici", lambda motor=None: None)
    iem_sigmet = {
        "baslangic": T0,
        "bitis": T0 + pd.Timedelta(hours=2),
        "turbulansla_ilgili": True,
        "poligon": [(40.0, -75.0), (41.0, -75.0), (41.0, -74.0)],
    }
    pirepler = _pirepler((T0, 40.5, -74.5, 34000, 1), (T0, 20.0, -74.5, 34000, 1))

    kanit = bk.kanitlari_topla(
        T0, T0, KUTU_ABD, iem_sigmet_getirici=lambda b, s: [iem_sigmet], iem_pirep_getirici=lambda b, s: pirepler
    )
    assert kanit.kaynaklar == ["iem_sigmet", "iem_pirep"]
    assert kanit.turb_sigmetleri[0]["poligon"][0] == kanit.turb_sigmetleri[0]["poligon"][-1] == [-75.0, 40.0]
    assert len(kanit.pirepler) == 1

    def cokuyor(baslangic, bitis):
        raise TimeoutError("IEM yanıt vermedi")

    kanit = bk.kanitlari_topla(T0, T0, KUTU_ABD, iem_sigmet_getirici=cokuyor, iem_pirep_getirici=lambda b, s: pirepler)
    assert kanit.kaynaklar == ["iem_pirep"] and kanit.turb_sigmetleri is None


def test_yeni_biten_ucusta_ileri_uzatilmis_pencere_arsiv_kapsamini_bozmaz(monkeypatch, sahte_arsiv):
    simdi = pd.Timestamp.now(tz="UTC")
    monkeypatch.setattr(bk, "arsiv_baslangici", lambda motor=None: simdi - pd.Timedelta(days=1))
    kanit = bk.kanitlari_topla(simdi - pd.Timedelta(hours=3), simdi + pd.Timedelta(hours=3), KUTU_TURKIYE, **_IEM_YASAK)
    assert kanit.kaynaklar == ["sigmet_arsivi"]
