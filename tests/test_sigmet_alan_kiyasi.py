import json

import numpy as np
import pandas as pd
import pytest

from turbulans_radar.dogrulama import sigmet_alan_kiyasi as sak


def _sigmet(taban=26000, tavan=38000, bas="2026-10-13T09:10Z", son="2026-10-13T12:40Z", fir="LTAA"):
    return {
        "id": 7,
        "fir_kodu": fir,
        "seri_no": "A01",
        "taban_ft": taban,
        "tavan_ft": tavan,
        "gecerlilik_baslangic": pd.Timestamp(bas),
        "gecerlilik_bitis": pd.Timestamp(son),
        "poligon": [[32.0, 38.0], [34.0, 38.0], [34.0, 40.0], [32.0, 40.0], [32.0, 38.0]],
    }


def test_tam_saatler_pencere_icindeki_saatler():
    saatler = sak.tam_saatler(_sigmet())
    assert [s.hour for s in saatler] == [10, 11, 12]


@pytest.mark.parametrize(
    "taban, tavan, beklenen",
    [(26000, 38000, (280.0, 380.0)), (None, None, (280.0, 430.0)), (10000, 25000, None), (30000, None, (300.0, 430.0))],
)
def test_fl_bandi_kup_araligiyla_kesisir(taban, tavan, beklenen):
    assert sak.fl_bandi(_sigmet(taban, tavan)) == beklenen


def test_ornekleme_bolgeleri_ve_bant():
    sigmet = _sigmet()
    noktalar = sak.ornekle(sigmet, sak.tam_saatler(sigmet), (280.0, 380.0), nokta_sayisi=4000)
    ic = noktalar[noktalar.bolge == "iceride"]
    assert ic.enlem.between(38, 40).all() and ic.boylam.between(32, 34).all()
    halka = noktalar[noktalar.bolge == "halka"]
    assert len(ic) > 200 and len(halka) > len(ic)
    assert not (halka.enlem.between(38.01, 39.99) & halka.boylam.between(32.01, 33.99)).any()
    fl = noktalar.baro_irtifa_m / 0.3048 / 100
    assert fl.between(280, 380).all()
    assert set(noktalar.zaman.dt.hour) <= {10, 11, 12} and noktalar.zaman.dt.tz is None


def test_sigmet_olcumu_fark_ve_nan():
    noktalar = pd.DataFrame({"bolge": ["iceride"] * 4 + ["halka"] * 4 + ["disarida"]})
    ti1 = np.array([2e-6, 2e-6, 1e-7, np.nan, 1e-7, 1e-7, 2e-6, 1e-7, 5e-6])
    olcu = sak.sigmet_olcumu(noktalar, ti1, 7e-7)
    assert olcu["iceride_nokta"] == 3 and olcu["halka_nokta"] == 4
    assert olcu["iceride_riskli_orani"] == pytest.approx(2 / 3)
    assert olcu["fark"] == pytest.approx(2 / 3 - 1 / 4)
    assert olcu["medyan_log10_farki"] == pytest.approx(np.log10(2e-6) - np.log10(1e-7))


def test_bolge_bossa_fark_yok():
    olcu = sak.sigmet_olcumu(pd.DataFrame({"bolge": ["halka"] * 2}), np.array([1e-6, 1e-7]), 7e-7)
    assert olcu["iceride_riskli_orani"] is None and olcu["fark"] is None


def test_havuzlama_ve_okuma():
    havuz = sak.havuzla([0.3, 0.2, 0.4, None], tekrar=2000)
    assert havuz["sigmet"] == 3 and havuz["pozitif_sigmet"] == 3
    assert havuz["ortalama_fark"] == pytest.approx(0.3)
    assert 0.2 - 1e-9 <= havuz["ga95"][0] <= havuz["ga95"][1] <= 0.4 + 1e-9
    assert sak.okuma(havuz).startswith("TI1 Türk")
    assert sak.okuma(sak.havuzla([0.3, -0.2, 0.0], tekrar=2000)) == "fark gösterilemedi"
    assert sak.okuma(sak.havuzla([])) == "SIGMET yok"


def test_calistir_sahte_kup_ile(monkeypatch):
    istekler = []

    def kup_getir(gun, saatler, kutu):
        istekler.append((gun, tuple(saatler), kutu))
        return "kup"

    monkeypatch.setattr(
        sak,
        "_ti1",
        lambda kup, n: np.where(
            sak.shapely.contains_xy(
                sak.sigmet_geometrisi(_sigmet()["poligon"]), n.boylam.to_numpy(), n.enlem.to_numpy()
            ),
            2e-6,
            1e-7,
        ),
    )
    sigmetler = [_sigmet(), _sigmet(10000, 20000), _sigmet(bas="2026-10-14T22:30Z", son="2026-10-15T01:30Z")]
    sonuc = sak.calistir(sigmetler, kup_getir, 7e-7, nokta_sayisi=1500, tekrar=500)
    k = sonuc["kayitlar"]
    assert k[0]["fark"] == pytest.approx(1.0) and "dustu" in k[1] and k[2]["fark"] == pytest.approx(1.0)
    assert sonuc["havuz"]["sigmet"] == 2 and sonuc["okuma"].startswith("TI1 Türk")
    gunler = [(g.day, s) for g, s, _ in istekler]
    assert gunler == [(13, (10, 11, 12)), (14, (23,)), (15, (0, 1))]
    enlem_min, enlem_maks, boylam_min, boylam_maks = istekler[0][2]
    assert enlem_min < 38 - 2.5 and enlem_maks > 40 + 2.5 and boylam_min < 32 - 3


def test_sigmetleri_getir_fir_ve_tarih_suzgeci(monkeypatch):
    from turbulans_radar.veri import sigmet_saglayici

    def sahte(bas, bit, tehlikeler=None, motor=None):
        assert tehlikeler == ["TURB"]
        return [_sigmet(), _sigmet(fir="LYBA"), _sigmet(bas="2026-11-10T00:00Z", son="2026-11-10T04:00Z")]

    monkeypatch.setattr(sigmet_saglayici, "gecerli_sigmetleri_getir", sahte)
    sonuc = sak.sigmetleri_getir(pd.Timestamp("2026-11-07T12:00Z"))
    assert [s["fir_kodu"] for s in sonuc] == ["LTAA"]


def test_ana_var_olan_raporun_uzerine_yazmaz(tmp_path):
    (tmp_path / "sigmet_alan.json").write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(SystemExit, match="üzerine yazılmaz"):
        sak.ana(["--cikti", str(tmp_path)])
