import json

import numpy as np
import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.dogrulama.bagimsiz_kanit import cat_disi_mi
from turbulans_radar.ml import sonuc_disa_aktarimi as sda
from turbulans_radar.ml.degerlendirme import bootstrap_guven_araligi
from turbulans_radar.ml.ml_veri_hatti import pirep_anahtari
from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI


@pytest.mark.parametrize(
    "rapor, beklenen",
    [
        ("UA /OV ABC/TB MOD/RM CB W", True),
        ("UA /WX +TSRA/TB MOD", True),
        ("UA /TB MOD/RM VCTS", True),
        ("UA /TB MOD/RM TSTMS", True),
        ("UA /TB MOD CHOP/RM MTN WAVE", True),
        ("UA /RM LLWS +-15KT", True),
        ("UA /OV TSE/TB MOD", False),
        ("UA /TP CBSA/TB MOD", False),
        ("UA /TB NEG/RM SMOOTH", False),
        ("", None),
        (None, None),
    ],
)
def test_cat_disi_mi_konvektif_ve_dag_dalgasini_ayirir(rapor, beklenen):
    assert cat_disi_mi(rapor) == beklenen


def _sentetik(gun_sayisi=8, gunluk=60, tohum=0, guc=1.0):
    rng = np.random.default_rng(tohum)
    n = gun_sayisi * gunluk
    y = rng.integers(0, 2, n)
    gunler = np.repeat([f"2019-01-{i + 1:02d}" for i in range(gun_sayisi)], gunluk)
    return y, y * guc + rng.normal(0, 1, n), gunler


def test_bootstrap_pr_auc_ve_ozel_metrik():
    y, skor, gunler = _sentetik()
    pr = bootstrap_guven_araligi(y, skor, gunler, "pr_auc", tekrar=30)
    assert pr["metrik"] == "pr_auc" and pr["alt"] <= pr["deger"] <= pr["ust"]
    ozel = bootstrap_guven_araligi(y, skor, gunler, ("ortalama", lambda yy, ss: float(ss.mean())), tekrar=30)
    assert ozel["metrik"] == "ortalama" and ozel["deger"] == pytest.approx(skor.mean())


def test_skor_ozeti_ga_pr_auc_ve_ti1_farki():
    y, ti1, gunler = _sentetik()
    model = y * 2.0 + np.random.default_rng(5).normal(0, 1, len(y))
    ozet = sda.skor_ozeti(y, {"Model": model, "TI1": ti1}, gunler, tekrar=30)
    assert ozet["gun"] == 8 and "not" not in ozet
    m = ozet["skorlar"]["Model"]
    assert {"roc_auc", "roc_auc_ga", "pr_auc", "pr_auc_ga", "ti1_farki"} <= set(m)
    assert m["ti1_farki"]["fark"] > 0 and "ti1_farki" not in ozet["skorlar"]["TI1"]
    az = sda.skor_ozeti(y[:120], {"TI1": ti1[:120]}, gunler[:120], tekrar=30)
    assert "not" in az and "roc_auc_ga" not in az["skorlar"]["TI1"]


def test_skor_ozeti_gecersiz_satirlari_ortak_atar():
    y = np.array([0, 1, 0, 1, 1, 0])
    ozet = sda.skor_ozeti(y, {"TI1": np.array([0.1, 0.9, np.nan, 0.8, 0.7, 0.2]), "B": np.arange(6.0)}, list("aabbcc"))
    assert ozet["ornek"] == 5


def test_esik_taramasi_egitimde_secip_testte_uygular_seviyeye_ayirir():
    y, ti1, gunler = _sentetik(gun_sayisi=14, gunluk=80, guc=2.0)
    seviye = np.where(np.arange(len(y)) % 10 == 0, 350.0, 250.0)
    tablo = pd.DataFrame({"y": y, "ti1": ti1, "seviye": seviye, "gun": gunler})
    egitim, test = tablo[tablo["gun"] < "2019-01-08"], tablo[tablo["gun"] >= "2019-01-08"]
    sonuc = sda.esik_taramasi(egitim, test, tekrar=20)
    assert 0 < sonuc["peirce_esigi"] < 2
    assert sonuc["test"]["peirce"] > 0.5 and len(sonuc["test"]["peirce_ga"]) == 2
    assert len(sonuc["tarama"]) == len(sda.TARAMA_YUZDELIKLERI)
    assert set(sonuc["config_esikleri"]) == {"TI1_ESIK_HAFIF", "TI1_ESIK_ORTA_SIDDETLI"}
    bs = sonuc["bir_se"]
    assert bs["peirce_max_esigi"] == pytest.approx(sonuc["peirce_esigi"]) and bs["se"] > 0
    assert bs["esik"] >= bs["peirce_max_esigi"] and sonuc["bir_se_test"]["esik"] == bs["esik"]
    seviyeler = {s["seviye_hpa"]: s for s in sonuc["seviyeye_gore"]}
    assert "seviye_esigi" in seviyeler[250.0] and "test_seviye_esigi" in seviyeler[250.0]
    assert seviyeler[350.0]["egitim_ornek"] == 56


def test_cat_alt_kumesi_metinsiz_ve_cat_disi_ornekleri_ayirir():
    y, ti1, gunler = _sentetik(gun_sayisi=6, gunluk=20)
    bilgi = pd.DataFrame({"anahtar": [f"k{i}" for i in range(len(y))], "y": y, "gun": gunler})
    metinler = pd.DataFrame(
        {
            "anahtar": [f"k{i}" for i in range(100)] + ["k0"],
            "rapor": ["UA /TB MOD"] * 100 + ["UA /TB MOD/RM CB"],
        }
    )
    skorlar = {"Model": ti1, "TI1": ti1}
    sonuc = sda.cat_alt_kumesi(bilgi, metinler, skorlar, np.ones(len(y), bool), tekrar=10)
    assert (sonuc["ornek"], sonuc["metinli"], sonuc["cat_disi"]) == (120, 100, 1)
    assert sonuc["test_metinli"]["ornek"] == 100 and sonuc["test_cat"]["ornek"] == 99
    assert set(sonuc["tum_gunler_cat_fizik"]["skorlar"]) == {"TI1"}
    assert sda.cat_alt_kumesi(bilgi, pd.DataFrame(columns=["anahtar", "rapor"]), skorlar, None)["durum"] == "arsiv_yok"


@pytest.fixture
def motor():
    from sqlalchemy import text

    from turbulans_radar.depo import veritabani as vt

    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    yield motor
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM edr_ornekleri WHERE kaynak = 'sonuc_test'"))
        baglanti.execute(text("DELETE FROM ml_ornekleri WHERE kaynak = 'sonuc_test'"))


def _ozellikler(rng, etiket):
    ti1 = float(np.exp(rng.normal(-14.5 + 0.8 * etiket, 0.8)))
    return {
        "ti1_indeksi": ti1,
        "richardson_sayisi": float(np.exp(rng.normal(1.0 - 0.5 * etiket, 0.8))),
        "ruzgar_hizi_ms": float(rng.uniform(10, 60)),
        "basinc_hpa": float(rng.choice([200.0, 250.0])),
        "dusey_ruzgar_kaymasi": float(rng.normal(0.005 + 0.003 * etiket, 0.002)),
        "yatay_deformasyon": float(abs(rng.normal(3e-5, 1e-5))),
        "yatay_diverjans": float(rng.normal(0, 1e-5)),
        "ti2_indeksi": float(ti1 * rng.uniform(0.5, 1.5)),
    }


def test_disa_aktar_json_sayilar_ve_uc_sekil_yazar(motor, tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import EdrOrnegi, MlOrnegi

    rng = np.random.default_rng(0)
    gunler = [
        pd.Timestamp(f"2019-02-{g:02d}T12:00Z") + pd.Timedelta(minutes=i) for g in range(1, 21) for i in range(30)
    ]
    satirlar, arsiv = [], []
    for i, zaman in enumerate(gunler):
        sinif = int(rng.integers(0, 2))
        enlem, boylam = 40.0 + i * 1e-3, -100.0
        satirlar.append(
            MlOrnegi(
                pirep_anahtari=pirep_anahtari(zaman, enlem, boylam, 35000),
                kaynak="sonuc_test",
                zaman=zaman.to_pydatetime(),
                enlem=enlem,
                boylam=boylam,
                irtifa_ft=35000.0,
                sinif=sinif,
                durum="eslesti",
                ozellikler=_ozellikler(rng, sinif),
            )
        )
        rapor = "UA /TB MOD/RM CB" if i % 25 == 0 else "UA /TB MOD"
        arsiv.append([f"{zaman:%Y%m%d%H%M}", rapor, "MOD" if sinif else "NEG", "35000", str(enlem), str(boylam)])
    edr = [
        EdrOrnegi(
            gozlem_anahtari=f"sonuc-test-{i}",
            kaynak="sonuc_test",
            zaman=(pd.Timestamp(f"2019-02-{1 + i % 6:02d}T12:00Z")).to_pydatetime(),
            enlem=40.0,
            boylam=-100.0,
            irtifa_ft=35000.0,
            max_edr=0.1 if i % 10 == 0 else 0.02,
            med_edr=0.01,
            edr_sinifi=0,
            ozellikler=_ozellikler(rng, int(i % 10 == 0)),
        )
        for i in range(120)
    ]
    with Session(motor) as oturum:
        oturum.add_all(satirlar + edr)
        oturum.commit()
    pd.DataFrame(arsiv, columns=["VALID", "REPORT", "TURBULENCE", "FL", "LAT", "LON"]).to_csv(
        tmp_path / "a.csv", index=False
    )
    with open(config.ML_ALTIN_TEST_DOSYASI, "w", encoding="utf-8") as dosya:
        json.dump({"gunler": [f"2019-02-{g:02d}" for g in (3, 7, 11, 15, 19)]}, dosya)
    monkeypatch.setattr(sda, "pirep_ornekleri", _yalniz_test_kaynagi(sda.pirep_ornekleri))
    monkeypatch.setattr(sda, "madis_ornekleri", _yalniz_test_madis(sda.madis_ornekleri))

    cikti = tmp_path / "paket"
    paket = sda.disa_aktar(str(cikti), kesme=None, motor=motor, tekrar=10, arsiv_klasoru=str(tmp_path))

    assert (
        paket["meta"]["commit"]
        and paket["veri"]["test_gun"] == 5
        and paket["veri"]["test_yontemi"] == "altın test günleri"
    )
    assert set(paket["pirep_test"]["skorlar"]) == {"Model", "TI1", "1/Ri", "Birleşik EDR"}
    assert "ti1_farki" in paket["pirep_test"]["skorlar"]["Model"]
    assert paket["cat_alt_kumesi"]["cat_disi"] == 24
    assert paket["madis"]["pozitif"] == 12 and paket["madis"]["duzeltilen_sinif"] == 12
    assert sorted(paket["sekiller"]) == ["backtest_ucus_basina.png", "guvenilirlik_modeli.png", "roc_ti1_ri.png"]
    for ad in paket["sekiller"] + ["sonuc_paketi.json", "SAYILAR.md"]:
        assert (cikti / ad).stat().st_size > 0
    sayilar = (cikti / "SAYILAR.md").read_text(encoding="utf-8")
    assert "`pirep_test.skorlar.Model.roc_auc`" in sayilar and paket["meta"]["commit"] in sayilar
    assert json.loads((cikti / "sonuc_paketi.json").read_text(encoding="utf-8"))["veri"]["ornek"] == 600

    with pytest.raises(SystemExit):
        sda.disa_aktar(str(tmp_path / "bos"), kesme="2000-01-01", motor=motor, tekrar=10, arsiv_klasoru=str(tmp_path))


def _yalniz_test_kaynagi(asil):
    """Paylaşılan test veritabanındaki başka testlerin örnekleri sayımı bozmasın."""

    def sarmal(motor, kesme=None):
        X, bilgi = asil(motor, kesme)
        maske = bilgi["anahtar"].astype(str).str.startswith("201902").to_numpy()
        return X[maske].reset_index(drop=True), bilgi[maske].reset_index(drop=True)

    return sarmal


def _yalniz_test_madis(asil):
    def sarmal(motor, kesme=None):
        df = asil(motor, kesme)
        return df[df["gun"].str.startswith("2019-02")].reset_index(drop=True) if not df.empty else df

    return sarmal


def test_ozellik_sutunlari_sentetik_ornekle_uyumlu():
    assert set(_ozellikler(np.random.default_rng(0), 1)) == set(MODEL_OZELLIK_SUTUNLARI)


class _SorguYakalayan:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sorgu):
        _SorguYakalayan.son = str(sorgu)
        return self

    def all(self):
        return []


@pytest.mark.parametrize(
    "modul_adi,fonksiyon",
    [
        ("turbulans_radar.ml.sonuc_disa_aktarimi", "pirep_ornekleri"),
        ("turbulans_radar.ml.sonuc_disa_aktarimi", "madis_ornekleri"),
        ("turbulans_radar.ml.ml_otomatik_egitim", "veritabanindan_veri_hazirla"),
    ],
)
def test_ornek_sorgulari_birincil_anahtara_gore_sirali(monkeypatch, modul_adi, fonksiyon):
    import importlib

    modul = importlib.import_module(modul_adi)
    monkeypatch.setattr(modul, "Session", _SorguYakalayan)
    try:
        getattr(modul, fonksiyon)(object())
    except Exception:
        pass
    assert "ORDER BY" in _SorguYakalayan.son and ".id" in _SorguYakalayan.son.split("ORDER BY")[1]
