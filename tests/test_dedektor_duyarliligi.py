import numpy as np

from turbulans_radar.analiz import dedektor_duyarliligi as d


def test_buyuk_sapma_yakalanir_kucuk_sapma_kacar_temiz_izde_alarm_yok():
    taban = d.taban_iz()
    rng = np.random.default_rng(1)
    assert d.tespit_orani(taban, 300, 5.0, 4, rng)["tespit_orani"] == 1.0
    assert d.tespit_orani(taban, 30, 5.0, 4, rng)["tespit_orani"] == 0.0
    alarm = d.yanlis_alarm(taban, 5.0, 2, rng)
    assert alarm["olay"] == 0 and alarm["seyir_saati"] > 1


def test_faz_uyumu_oranlari_gecerli():
    uyum = d.faz_uyumu(d.taban_iz(), np.random.default_rng(0))
    assert 0 <= uyum["dedektor_seyirinin_openap_cr_orani"] <= 1
    assert uyum["dedektor_seyir_noktasi"] > 0 and uyum["openap_seyir_noktasi"] > 0
