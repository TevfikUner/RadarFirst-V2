import numpy as np
import pytest

from turbulans_radar.ml import degerlendirme as dg


def test_ikili_metrikler_karisiklik_tablosundan_dogru_hesaplanir():
    y = [1, 1, 1, 0, 0, 0, 0, 0]
    skor = [0.9, 0.8, 0.1, 0.7, 0.2, 0.1, 0.1, 0.0]
    m = dg.ikili_metrikler(y, skor, 0.5)
    assert (m["dogru_pozitif"], m["yanlis_negatif"], m["yanlis_pozitif"], m["dogru_negatif"]) == (2, 1, 1, 4)
    assert m["pod"] == pytest.approx(2 / 3) and m["pofd"] == pytest.approx(1 / 5)
    assert m["peirce"] == pytest.approx(2 / 3 - 1 / 5) and m["far"] == pytest.approx(1 / 3)
    assert m["csi"] == pytest.approx(2 / 4)


def test_brier_mukemmel_tahminde_sifir_iklimselde_beceri_sifir():
    y = np.array([1, 0, 1, 0])
    assert dg.olasilik_metrikleri(y, y.astype(float))["brier"] == 0.0
    iklimsel = dg.olasilik_metrikleri(y, np.full(4, 0.5))
    assert iklimsel["brier"] == pytest.approx(0.25) and iklimsel["brier_becerisi"] == pytest.approx(0.0)


def test_guvenilirlik_tablosu_kutulari_ve_gozlenen_oranlari():
    tablo = dg.guvenilirlik_tablosu([0, 1, 1, 1], [0.05, 0.95, 0.9, 1.0], kutu_sayisi=10)
    assert [(k["aralik"][0], k["adet"], k["gozlenen_oran"]) for k in tablo] == [(0.0, 1, 0.0), (0.9, 3, 1.0)]


def test_ti1_referansi_config_esigini_kullanir():
    from turbulans_radar import config

    esik = config.TI1_ESIK_ORTA_SIDDETLI
    m = dg.ti1_referansi([1, 0], [esik * 1.1, esik * 0.9])
    assert (m["esik"], m["pod"], m["pofd"]) == (esik, 1.0, 0.0)


def test_tek_sinifli_veride_auc_nan_olur():
    assert np.isnan(dg.ikili_metrikler([1, 1], [0.2, 0.9], 0.5)["roc_auc"])


def _gunluk_veri(gun_sayisi=40, gunluk=25, tohum=0, ayrim=1.5):
    rng = np.random.default_rng(tohum)
    gunler = np.repeat(
        [f"2020-01-{g:02d}" if g < 32 else f"2020-02-{g - 31:02d}" for g in range(1, gun_sayisi + 1)], gunluk
    )
    y = rng.integers(0, 2, len(gunler))
    iyi = y * ayrim + rng.normal(0, 1, len(y))
    zayif = y * 0.3 + rng.normal(0, 1, len(y))
    return y, iyi, zayif, gunler


def test_blok_bootstrap_gunleri_bolmeden_orneklenir():
    gunler = np.array(["a", "a", "b", "b", "b", "c"])
    for indeksler in dg._bootstrap_ornekleri(gunler, 20, 0):
        secilen_gunler = gunler[indeksler]
        for gun in set(secilen_gunler):
            assert (secilen_gunler == gun).sum() % (gunler == gun).sum() == 0


def test_guven_araligi_degeri_kapsar_ve_tekrarlanabilir():
    y, iyi, _, gunler = _gunluk_veri()
    ga = dg.bootstrap_guven_araligi(y, iyi, gunler, tekrar=300, tohum=1)
    assert ga["alt"] < ga["deger"] < ga["ust"] and ga["gun_sayisi"] == 40
    assert ga == dg.bootstrap_guven_araligi(y, iyi, gunler, tekrar=300, tohum=1)
    brier = dg.bootstrap_guven_araligi(y, 1 / (1 + np.exp(-iyi)), gunler, "brier", tekrar=200)
    assert 0.0 <= brier["alt"] <= brier["deger"] <= brier["ust"] <= 1.0


def test_eslestirilmis_fark_gercek_ustunlugu_anlamli_esitligi_anlamsiz_bulur():
    y, iyi, zayif, gunler = _gunluk_veri()
    ustun = dg.eslestirilmis_auc_farki(y, iyi, zayif, gunler, tekrar=400)
    assert ustun["fark"] > 0.2 and ustun["alt"] > 0 and ustun["anlamli"] and ustun["p_degeri"] < 0.05
    ayni = dg.eslestirilmis_auc_farki(y, iyi, iyi + 1e-9, gunler, tekrar=200)
    assert abs(ayni["fark"]) < 1e-6 and not ayni["anlamli"]


def test_rapor_gun_verilince_guven_araliklarini_icerir():
    y, iyi, _, gunler = _gunluk_veri(gun_sayisi=10)
    rapor = dg.degerlendirme_raporu(y, iyi, 1 / (1 + np.exp(-iyi)), gunler=gunler)
    assert set(rapor["guven_araliklari"]) == {"ti1_roc_auc", "model_roc_auc", "model_brier", "model_eksi_ti1_roc_auc"}
    assert "guven_araliklari" not in dg.degerlendirme_raporu(y, iyi)


def test_peirce_esigi_pod_eksi_pofd_yi_maksimize_eder():
    y = [0, 0, 0, 1, 0, 1, 1, 1]
    skor = [0.1, 0.2, 0.3, 0.35, 0.4, 0.6, 0.7, 0.8]
    esik = dg.peirce_esigi(y, skor)
    assert esik == pytest.approx(0.6)
    assert dg.ikili_metrikler(y, skor, esik)["peirce"] == pytest.approx(0.75)
    assert np.isnan(dg.peirce_esigi([1, 1], [0.2, 0.3]))


def test_kalibre_ti1_olasilik_uretir_ve_monotondur():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 400)
    ti1 = 10 ** (-7 + 0.8 * y + rng.normal(0, 0.5, 400))
    model = dg.kalibre_ti1_egit(y, ti1)
    p = dg.kalibre_ti1_olasiligi(model, [1e-8, 1e-7, 1e-6])
    assert ((0 < p) & (p < 1)).all() and p[0] < p[1] < p[2]


def test_bir_se_esigi_esdeger_beceride_en_tutucu_esigi_secer():
    from turbulans_radar.ml.degerlendirme import bir_se_esigi, ikili_metrikler

    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, 2000)
    skor = y + rng.normal(0, 1, 2000)
    gunler = np.repeat([f"g{i}" for i in range(20)], 100)
    sonuc = bir_se_esigi(y, skor, gunler, tekrar=50)
    assert sonuc["esik"] > sonuc["peirce_max_esigi"] and sonuc["se"] > 0
    assert ikili_metrikler(y, skor, sonuc["esik"])["peirce"] >= sonuc["peirce_max"] - sonuc["se"] - 1e-12
    assert ikili_metrikler(y, skor, sonuc["esik"])["pofd"] < ikili_metrikler(y, skor, sonuc["peirce_max_esigi"])["pofd"]


def test_onsel_kayma_duzeltmesi_siralamayi_korur_ve_ortalamayi_yeni_tabana_ceker():
    from turbulans_radar.ml.degerlendirme import _auc, onsel_kayma_duzelt

    rng = np.random.default_rng(0)
    y = (rng.random(2000) < 0.03).astype(int)
    olasilik = np.clip(0.5 + 0.2 * y + rng.normal(0, 0.15, 2000), 0.01, 0.99)
    duzeltilmis = onsel_kayma_duzelt(olasilik, 0.52, 0.03)
    assert _auc(y, duzeltilmis) == pytest.approx(_auc(y, olasilik))
    assert duzeltilmis.mean() < 0.1 < olasilik.mean()
    assert onsel_kayma_duzelt(olasilik, 0.3, 0.3) == pytest.approx(olasilik)
