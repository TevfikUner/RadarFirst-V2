import json

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from turbulans_radar.ml import yeni_gun_degerlendirmesi as yg


def _veri(gun_sayisi, baslangic="2018-01-01", ornek=20, tohum=0):
    rng = np.random.default_rng(tohum)
    gunler = pd.date_range(baslangic, periods=gun_sayisi, freq="3D").strftime("%Y-%m-%d")
    n = gun_sayisi * ornek
    df = pd.DataFrame({c: rng.random(n) for c in yg.SETLER["genis"]})
    df["ruzgar_hizi_ms"] = rng.uniform(10, 60, n)
    df["gun"] = np.repeat(gunler, ornek)
    df["y"] = (df["ti1_indeksi"] + df["ri_kolon_min"] + 0.5 * rng.random(n) > 1.2).astype(int)
    df["anahtar"] = [f"k{i}" for i in range(n)]
    return df


def test_dondurma_gunleri_163_ve_altin_gunleri_kapsar():
    donmus = yg.dondurma_gunleri()
    assert len(donmus) == 163
    altin = json.loads(yg.DONDURMA_DOSYASI.with_name("altin_test_gunleri.json").read_text(encoding="utf-8"))
    assert set(altin["gunler"]) <= donmus


@pytest.mark.parametrize(
    ("metin", "beklenen"),
    [
        ("LGT", True),
        ("LGT CHOP", True),
        ("LIGHT", True),
        ("NEG", False),
        ("SMOOTH", False),
        ("LGT-MOD", False),
        ("", None),
    ],
)
def test_hafif_mi(metin, beklenen):
    assert yg.hafif_mi(metin) is beklenen


def test_mevsim_ve_komsu_gun():
    assert [yg.mevsim(g) for g in ("2019-01-05", "2019-04-01", "2019-07-31", "2019-10-10", "2019-12-31")] == [
        "DJF",
        "MAM",
        "JJA",
        "SON",
        "DJF",
    ]
    donmus = {"2019-01-10"}
    assert yg.komsu_gun_mu("2019-01-11", donmus) and yg.komsu_gun_mu("2019-01-09", donmus)
    assert not yg.komsu_gun_mu("2019-01-12", donmus)


def test_yeterlilik_yeni_gun_esigi():
    az = yg.yeterlilik(_veri(yg.MIN_YENI_GUN - 1))
    assert not az["yeterli"] and az["yeni_gun"] == yg.MIN_YENI_GUN - 1
    assert yg.yeterlilik(_veri(yg.MIN_YENI_GUN))["yeterli"]


def _hizli_protokol(monkeypatch):
    def protokol_adayi(Xe, ye, ge):
        model = LogisticRegression(max_iter=500).fit(Xe, ye)
        return "Lojistik Regresyon", {"Lojistik Regresyon": (model, {"roc_auc": 0.7, "roc_auc_se": 0.01}, None)}, model

    monkeypatch.setattr(yg, "protokol_adayi", protokol_adayi)
    monkeypatch.setattr(yg, "kat_disi_olasiliklar", lambda model, X, y, g: model.predict_proba(X)[:, 1])


def test_degerlendir_birincil_ve_ikincil_bolumleri_uretir(monkeypatch):
    _hizli_protokol(monkeypatch)
    egitim, test = _veri(40), _veri(32, baslangic="2019-06-01", tohum=1)
    donmus = set(egitim["gun"])
    test.loc[test["gun"] == test["gun"].iloc[0], "gun"] = "2018-01-02"
    metinler = pd.DataFrame({"anahtar": test["anahtar"], "metin": np.where(test.index % 3 == 0, "LGT", "NEG")})
    rapor = yg.degerlendir(egitim, test, donmus, metinler, tekrar=20)
    assert set(rapor["modeller"]) == {"temel", "genis"}
    assert {"fark", "alt", "ust", "destekleniyor"} <= set(rapor["h1"])
    assert set(rapor["ti1_kapisi"]) == {"temel", "genis"}
    assert any(k.startswith("mevsim=") for k in rapor["tabakalar"])
    assert any(k.startswith("ruzgar=") for k in rapor["tabakalar"])
    hafif = rapor["hafif_duyarliligi"]
    beklenen = int(((test.index % 3 == 0) & (test["y"] == 0)).sum())
    assert hafif["hafif_negatif"] == beklenen
    assert hafif["hafif_cikarilmis"]["ornek"] == len(test) - beklenen
    assert rapor["komsu_gunsuz_h1"]["cikarilan_gun"] == 1


def test_calistir_yetersizse_skor_hesaplamaz_ve_bir_kez_yazar(monkeypatch, tmp_path):
    _hizli_protokol(monkeypatch)
    egitim = _veri(40)
    dosya = tmp_path / "donmus.json"
    dosya.write_text(json.dumps({"gunler": sorted(set(egitim["gun"]))}), encoding="utf-8")
    monkeypatch.setattr(yg, "DONDURMA_DOSYASI", dosya)
    monkeypatch.setattr("turbulans_radar.ml.duyarlilik_analizi.arsiv_metinleri", lambda klasor=None: pd.DataFrame())

    monkeypatch.setattr(
        yg, "_veriyi_hazirla", lambda motor=None, bagli=True: pd.concat([egitim, _veri(10, "2019-06-01")])
    )
    monkeypatch.setattr(yg, "degerlendir", lambda *a, **k: pytest.fail("yetersiz veride skor hesaplanmamalı"))
    with pytest.raises(SystemExit, match="yetersiz"):
        yg.calistir(str(tmp_path / "cikti"))
    assert yg.durum()["yeni_gun"] == 10

    monkeypatch.undo()
    _hizli_protokol(monkeypatch)
    monkeypatch.setattr(yg, "DONDURMA_DOSYASI", dosya)
    monkeypatch.setattr("turbulans_radar.ml.duyarlilik_analizi.arsiv_metinleri", lambda klasor=None: pd.DataFrame())
    monkeypatch.setattr(
        yg, "_veriyi_hazirla", lambda motor=None, bagli=True: pd.concat([egitim, _veri(32, "2019-06-01")])
    )
    rapor = yg.calistir(str(tmp_path / "cikti"), tekrar=10)
    assert rapor["veri"]["test_yeni_gun"] == 32 and rapor["hafif_duyarliligi"] == {"durum": "metin_yok"}
    with pytest.raises(SystemExit, match="bir kez"):
        yg.calistir(str(tmp_path / "cikti"))


def test_birlesik_kiyasi_bolum10_gunleriyle_sinirli_ve_bir_kez_yazar(monkeypatch, tmp_path):
    _hizli_protokol(monkeypatch)
    egitim, yeni = _veri(40), _veri(34, baslangic="2019-06-01", tohum=1)
    dosya = tmp_path / "donmus.json"
    dosya.write_text(json.dumps({"gunler": sorted(set(egitim["gun"]))}), encoding="utf-8")
    monkeypatch.setattr(yg, "DONDURMA_DOSYASI", dosya)
    monkeypatch.setattr(yg, "_veriyi_hazirla", lambda motor=None, bagli=True: pd.concat([egitim, yeni]))
    bolum10_gunleri = sorted(set(yeni["gun"]))[:32]
    bolum10 = tmp_path / "yeni_gun_degerlendirmesi.json"
    bolum10.write_text(
        json.dumps(
            {
                "veri": {"test_gunleri": bolum10_gunleri, "test_ornek": 640},
                "test": {"skorlar": {"temel": {"roc_auc": 0.7}}},
            }
        ),
        encoding="utf-8",
    )
    rapor = yg.birlesik_kiyasi_calistir(str(tmp_path / "cikti"), bolum10_json=bolum10, tekrar=10)
    assert rapor["veri"]["test_gun"] == 32 and rapor["veri"]["test_ornek"] == 640
    assert set(rapor["test"]["skorlar"]) == {"TI1", "temel", "genis", "birlesik_edr"}
    assert set(rapor["farklar"]) == {"temel - birlesik_edr", "genis - birlesik_edr", "birlesik_edr - TI1"}
    assert rapor["cikarilan_ornek"] == 0 and "birleşik EDR" in rapor["sonuc"]
    with pytest.raises(SystemExit, match="bir kez"):
        yg.birlesik_kiyasi_calistir(str(tmp_path / "cikti"), bolum10_json=bolum10)
