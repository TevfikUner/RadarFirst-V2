import json
import os

import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml import ml_otomatik_egitim as me
from turbulans_radar.ml import turbulans_ml_modeli as tm


def _veri(gun_sayisi=80, gunluk=6, ayrim=2.0, tohum=0, ti1_ayrimi=0.3):
    rng = np.random.default_rng(tohum)
    n = gun_sayisi * gunluk
    y = pd.Series(rng.integers(0, 2, n))
    X = pd.DataFrame(
        {
            "ti1_indeksi": (rng.normal(0, 1, n) + ti1_ayrimi * ayrim * y) * 1e-7 + 5e-7,
            "richardson_sayisi": rng.normal(2, 1, n) - ayrim * y,
            "ruzgar_hizi_ms": rng.normal(30, 5, n),
            "basinc_hpa": rng.choice([200.0, 250.0, 300.0], n),
            **{s: rng.normal(0, 1, n) for s in tm.EK_OZELLIK_SUTUNLARI},
        }
    )[tm.MODEL_OZELLIK_SUTUNLARI]
    gunler = pd.Series(np.repeat(pd.date_range("2019-01-01", periods=gun_sayisi).strftime("%Y-%m-%d"), gunluk))
    return X, y, gunler


@pytest.fixture
def gecici_model_klasoru(monkeypatch, tmp_path):
    model, bilgi = str(tmp_path / "model.joblib"), str(tmp_path / "model_bilgisi.json")
    monkeypatch.setattr(me, "MODEL_DOSYA_YOLU", model)
    monkeypatch.setattr(me, "MODEL_BILGI_DOSYA_YOLU", bilgi)
    monkeypatch.setattr(tm, "MODEL_VERSIYONLARI_KLASORU", str(tmp_path / "versiyonlar"))
    monkeypatch.setattr(tm, "MODEL_VERSIYONLARI_MANIFEST_YOLU", str(tmp_path / "versiyonlar" / "manifest.json"))
    return tmp_path


def test_zamansal_holdout_en_son_gunleri_ayirir():
    gunler = pd.Series(["2019-01-03", "2019-01-01", "2019-01-02", "2019-01-05", "2019-01-04", "2019-01-05"])
    assert me.zamansal_holdout(gunler, oran=0.4).tolist() == [False, False, False, True, True, True]


_GECER = {"fark": 0.05, "alt": 0.01, "ust": 0.09}


@pytest.mark.parametrize(
    "sampiyon_farki,beklenen",
    [
        (None, True),
        (_GECER, True),
        ({"fark": 0.05, "alt": -0.01, "ust": 0.1}, False),
        ({"fark": 0.015, "alt": 0.001, "ust": 0.03}, False),
        ({"fark": float("nan"), "alt": float("nan"), "ust": float("nan")}, False),
    ],
)
def test_terfi_aktif_modele_karsi_eslestirilmis_auc_kapisi(sampiyon_farki, beklenen):
    y = pd.Series([1] * 40 + [0] * 40)
    assert me.terfi_karari(y, _GECER, sampiyon_farki)[0] is beklenen


def test_holdout_yetersizse_hic_terfi_edilmez():
    terfi, gerekce = me.terfi_karari(pd.Series([1] * 30 + [0] * 2), _GECER)
    assert not terfi and "yetersiz" in gerekce.lower()


def test_yetersiz_ornek_ya_da_gun_varsa_egitim_atlanir(monkeypatch, gecici_model_klasoru):
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: _veri(gun_sayisi=10, gunluk=50))
    assert me.otomatik_egitim_calistir()["karar"] == "atlandi"
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: _veri(gun_sayisi=80, gunluk=2))
    sonuc = me.otomatik_egitim_calistir()
    assert sonuc["karar"] == "atlandi" and "örnek" in sonuc["gerekce"]
    assert not os.path.exists(me.MODEL_DOSYA_YOLU)


def test_aktif_model_yokken_aday_aktiflestirilir_ve_versiyonlanir(monkeypatch, gecici_model_klasoru):
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: _veri())
    sonuc = me.otomatik_egitim_calistir(sampiyon_yukleyici=lambda: None, kat_sayisi=3, tekrar_sayisi=1)
    assert sonuc["karar"] == "aktiflestirildi"
    assert os.path.isfile(me.MODEL_DOSYA_YOLU)
    with open(me.MODEL_BILGI_DOSYA_YOLU, encoding="utf-8") as dosya:
        bilgi = json.load(dosya)
    assert bilgi["aktiflestirildi"] is True and bilgi["farkli_gun_sayisi"] == 80
    assert [v["versiyon_id"] for v in tm.model_versiyonlarini_listele()] == [sonuc["versiyon_id"]]
    assert not [d for d in os.listdir(gecici_model_klasoru) if d.endswith(".aday")]


def test_aday_aktif_modeli_gecemezse_aktif_model_degismez(monkeypatch, gecici_model_klasoru):
    X, y, gunler = _veri(ayrim=0.0)
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: (X, y, gunler))

    class _Kahin:
        def predict_proba(self, X_):
            p = y.loc[X_.index].to_numpy(dtype=float)
            return np.column_stack([1 - p, p])

    with open(me.MODEL_DOSYA_YOLU, "wb") as dosya:
        dosya.write(b"aktif")
    sonuc = me.otomatik_egitim_calistir(sampiyon_yukleyici=_Kahin, kat_sayisi=3, tekrar_sayisi=1)
    assert sonuc["karar"] == "saklandi" and "geçemedi" in sonuc["gerekce"]
    with open(me.MODEL_DOSYA_YOLU, "rb") as dosya:
        assert dosya.read() == b"aktif"
    assert not os.path.exists(me.MODEL_BILGI_DOSYA_YOLU)
    surum = tm.model_versiyonlarini_listele()[0]
    assert surum["aktiflestirildi"] is False and surum["holdout"]["aktif_model"]["roc_auc"] == 1.0


def test_tek_basina_ti1_kadar_iyi_olmayan_aday_aktiflestirilmez(monkeypatch, gecici_model_klasoru):
    X, y, gunler = _veri(ayrim=2.0, ti1_ayrimi=1.0)
    X["richardson_sayisi"] = 2.0
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: (X, y, gunler))
    sonuc = me.otomatik_egitim_calistir(sampiyon_yukleyici=lambda: None, kat_sayisi=3, tekrar_sayisi=1)
    assert sonuc["karar"] == "saklandi" and "TI1 referansını geçemedi" in sonuc["gerekce"]
    assert sonuc["ti1_referansi_holdout"]["roc_auc"] > 0.8
    assert not os.path.exists(me.MODEL_DOSYA_YOLU)


def test_aday_olasiliklari_kalibre_edilir_ve_brier_raporlanir(monkeypatch, gecici_model_klasoru):
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: _veri())
    sonuc = me.otomatik_egitim_calistir(sampiyon_yukleyici=lambda: None, kat_sayisi=3, tekrar_sayisi=1)
    aday = sonuc["aday_holdout"]
    assert 0.0 <= aday["brier"] < 0.25 and aday["brier_becerisi"] > 0
    assert {"pod", "pofd", "peirce"} <= set(aday)
    farki = sonuc["holdout_guven_araliklari"]["model_eksi_ti1_roc_auc"]
    assert farki["alt"] <= farki["fark"] <= farki["ust"] and 0.0 <= farki["p_degeri"] <= 1.0
    konformal = sonuc["konformal"]
    assert 0.0 <= konformal["esik"] <= 1.0 and konformal["alfa"] == 0.1
    dogrulama = konformal["holdout_dogrulamasi"]
    assert dogrulama["ornek"] == sonuc["holdout_ornek"] and 0.0 <= dogrulama["kapsama"] <= 1.0
    surum = tm.model_versiyonlarini_listele()[0]
    assert surum["olasilik_kalibrasyonu"].startswith("sigmoid")
    assert tm.risk_durumlarini_hesapla([0.0, 1.0], surum)[0] in ("dusuk_risk", "belirsiz")


@pytest.mark.parametrize(
    "fark,beklenen",
    [
        ({"fark": 0.03, "alt": 0.01, "ust": 0.05}, True),
        ({"fark": 0.01, "alt": 0.001, "ust": 0.02}, False),
        ({"fark": 0.03, "alt": -0.01, "ust": 0.07}, False),
        ({"fark": 0.03, "alt": 0.0, "ust": 0.07}, False),
        ({}, False),
        (None, False),
    ],
)
def test_terfi_ti1_farkinin_nokta_ve_guven_araligina_gore_kapilidir(fark, beklenen):
    y = pd.Series([1] * 40 + [0] * 40)
    terfi, gerekce = me.terfi_karari(y, fark)
    assert terfi is beklenen
    if not beklenen:
        assert "TI1 referansını geçemedi" in gerekce


def test_aday_1se_kuraliyla_secilir_ve_tum_ozellikleri_kullanir(monkeypatch, gecici_model_klasoru):
    X, y, gunler = _veri()
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: (X, y, gunler))
    yakalanan = {}
    gercek = me.modelleri_egit_ve_karsilastir

    def _kayitli(*args, **kwargs):
        sonuclar, degerlendirme = gercek(*args, **kwargs)
        yakalanan.update({ad: m for ad, (_, m, _) in sonuclar.items()})
        return sonuclar, degerlendirme

    monkeypatch.setattr(me, "modelleri_egit_ve_karsilastir", _kayitli)
    sonuc = me.otomatik_egitim_calistir(sampiyon_yukleyici=lambda: None, kat_sayisi=3, tekrar_sayisi=1)
    assert sonuc["secilen_model"] == me.bir_se_kurali_ile_sec(yakalanan)
    surum = tm.model_versiyonlarini_listele()[0]
    assert surum["ozellik_sutunlari"] == tm.MODEL_OZELLIK_SUTUNLARI
    assert surum["secim_olcutu"].startswith("gün gruplu CV ROC-AUC, 1-SE")


def test_esikler_egitim_gunlerinde_peirce_ile_secilir_ve_kalibre_ti1_raporlanir(monkeypatch, gecici_model_klasoru):
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: _veri())
    sonuc = me.otomatik_egitim_calistir(sampiyon_yukleyici=lambda: None, kat_sayisi=3, tekrar_sayisi=1)
    esikler = sonuc["esikler"]
    assert 0.0 < esikler["model"] < 1.0 and 1e-8 < esikler["ti1"] < 1e-5
    assert sonuc["aday_holdout"]["esik"] == pytest.approx(esikler["model"])
    assert sonuc["ti1_referansi_holdout"]["esik"] == pytest.approx(esikler["ti1"])
    assert 0.0 <= sonuc["kalibre_ti1_holdout"]["brier"] <= 0.25
    assert tm.ml_karar_esigi(tm.model_versiyonlarini_listele()[0]) == pytest.approx(esikler["model"])


def test_altin_test_gunleri_bir_kez_dondurulur(tmp_path):
    yol = str(tmp_path / "altin.json")
    gunler = pd.Series(pd.date_range("2019-01-01", periods=80).strftime("%Y-%m-%d"))
    kayit = me.altin_test_gunlerini_dondur(gunler, yol=yol)
    assert len(kayit["gunler"]) == 16 and set(kayit["gunler"]) <= set(gunler)
    assert kayit["gunler"] == me.altin_test_gunlerini_sec(gunler) == me.altin_test_gunleri(yol)
    assert kayit["gunler"] != sorted(gunler)[-16:]
    with pytest.raises(FileExistsError):
        me.altin_test_gunlerini_dondur(gunler, yol=yol)


def test_altin_test_gunleri_hicbir_surumun_egitimine_girmez(monkeypatch, gecici_model_klasoru):
    X, y, gunler = _veri()
    altin = me.altin_test_gunlerini_dondur(gunler)["gunler"]
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: (X, y, gunler))
    ilk = me.otomatik_egitim_calistir(sampiyon_yukleyici=lambda: None, kat_sayisi=3, tekrar_sayisi=1)
    X2, y2, gunler2 = _veri(gun_sayisi=90, tohum=1)
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: (X2, y2, gunler2))
    me.otomatik_egitim_calistir(kat_sayisi=3, tekrar_sayisi=1)
    surumler = tm.model_versiyonlarini_listele()
    assert len(surumler) == 2 and ilk["holdout_yontemi"] == "altın test günleri"
    for surum in surumler:
        assert not set(altin) & set(surum["egitim_gunleri"])
        assert surum["holdout"]["gunler"] == sorted(altin)
        assert len(surum["egitim_gunleri"]) + len(altin) == surum["farkli_gun_sayisi"]


def test_altin_gunleri_goren_aktif_model_karsilastirmada_yok_sayilir(monkeypatch, gecici_model_klasoru):
    me.altin_test_gunlerini_dondur(pd.Series(["2019-01-01", "2019-01-02", "2019-01-03", "2019-01-04", "2019-01-05"]))
    altin = me.altin_test_gunleri()
    monkeypatch.setattr(me, "model_kullanilabilir_mi", lambda bilgi, model_var_mi: (True, None))
    monkeypatch.setattr(me.joblib, "load", lambda yol: "model")
    with open(me.MODEL_DOSYA_YOLU, "wb") as dosya:
        dosya.write(b"aktif")
    for egitim_gunleri, beklenen in [(None, None), (altin, None), (["2018-12-31"], "model")]:
        with open(me.MODEL_BILGI_DOSYA_YOLU, "w", encoding="utf-8") as dosya:
            json.dump({} if egitim_gunleri is None else {"egitim_gunleri": egitim_gunleri}, dosya)
        assert me._aktif_modeli_yukle() == beklenen


def test_gun_anahtari_utc_gunudur():
    assert me._utc_gunu(pd.Timestamp("2019-01-02T01:30:00+03:00")) == "2019-01-01"
    assert me._utc_gunu(pd.Timestamp("2019-01-02T01:30:00")) == "2019-01-02"


def test_cli_surumleri_listeler_ve_geri_alir(monkeypatch, gecici_model_klasoru, capsys):
    monkeypatch.setattr(me, "veritabanindan_veri_hazirla", lambda motor=None: _veri())
    ilk = me.otomatik_egitim_calistir(sampiyon_yukleyici=lambda: None, kat_sayisi=3, tekrar_sayisi=1)
    me.ana(["--listele"])
    assert ilk["versiyon_id"] in capsys.readouterr().out
    monkeypatch.setattr(tm, "MODEL_DOSYA_YOLU", me.MODEL_DOSYA_YOLU)
    monkeypatch.setattr(tm, "MODEL_BILGI_DOSYA_YOLU", me.MODEL_BILGI_DOSYA_YOLU)
    os.remove(me.MODEL_DOSYA_YOLU)
    me.ana(["--geri-al", ilk["versiyon_id"]])
    assert os.path.isfile(me.MODEL_DOSYA_YOLU) and ilk["versiyon_id"] in capsys.readouterr().out


def test_eski_hatla_egitilmis_aktif_model_karsilastirmada_yok_sayilir(monkeypatch, gecici_model_klasoru):
    with open(me.MODEL_DOSYA_YOLU, "wb") as dosya:
        dosya.write(b"eski")
    with open(me.MODEL_BILGI_DOSYA_YOLU, "w", encoding="utf-8") as dosya:
        json.dump({"secilen_model": "Random Forest"}, dosya)
    monkeypatch.setattr(me.config, "ML_ESKI_MODELI_KULLAN", False)
    assert me._aktif_modeli_yukle() is None
