import numpy as np
import pytest

from turbulans_radar.analiz import ekonomik_deger as ed

pytestmark = pytest.mark.birim


def test_kusursuz_tahmin_her_alfada_bir_rastgele_tahmin_sifirin_altinda():
    alfa = np.array([0.05, 0.2, 0.5, 0.8])
    assert np.allclose(ed.rev(1.0, 0.0, 0.3, alfa), 1.0)
    assert np.all(ed.rev(0.4, 0.4, 0.3, alfa) <= 1e-12)


def test_en_yuksek_rev_taban_oranda_peirce_e_esittir():
    egri = ed.rev(0.62, 0.37, 0.476, ed.ALFALAR)
    ozet = ed.egri_ozeti(egri)
    assert float(ed.rev(0.62, 0.37, 0.476, 0.476)) == pytest.approx(0.62 - 0.37)
    assert 0.62 - 0.37 - 0.01 < ozet["maks_rev"] <= 0.62 - 0.37 + 1e-12
    assert ozet["maks_rev_alfa"] == pytest.approx(0.476, rel=0.02)
    alt, ust = ozet["deger_kattigi_alfa"]
    assert alt < 0.476 < ust


def test_zarf_her_alfada_en_iyi_esigi_alir_ve_kayip_sinirini_hesaplar():
    noktalar = [(0.9, 0.6), (0.5, 0.2), (0.2, 0.05)]
    z = ed.zarf(noktalar, 0.3)
    for h, f in noktalar:
        assert np.all(z >= ed.rev(h, f, 0.3, ed.ALFALAR) - 1e-12)
    paket = {
        "pirep_test": {"taban_oran": 0.3},
        "esik_taramasi": {
            "tarama": [{"test_pod": h, "test_pofd": f} for h, f in noktalar],
            "config_esikleri": {"TI1_ESIK_ORTA_SIDDETLI": {"esik": 7e-7, "test": {"pod": 0.5, "pofd": 0.2}}},
        },
        "model_olasilik_test": {"esik": 0.5, "pod": 0.6, "pofd": 0.3},
    }
    sonuc = ed.hesapla(paket, kacinma_bedeli_yuzde=2.0)
    satir = sonuc["PIREP altın günler (ölçülen)"]["seriler"]["TI1 risk eşiği (7e-07)"]
    assert satir["en_az_kayip_yakit_yuzdesi"] == pytest.approx(2.0 / satir["deger_kattigi_alfa"][1])


def test_calistir_depodaki_paketle_json_markdown_ve_sekil_yazar(tmp_path):
    pytest.importorskip("matplotlib")
    rapor = ed.calistir(str(tmp_path))
    assert rapor["kacinma_bedeli_yuzde"] is not None
    assert {"PIREP altın günler (ölçülen)"} <= set(rapor["sonuc"])
    for ad in ("ekonomik_deger.json", "README.md", "rev_egrileri.png"):
        assert (tmp_path / ad).stat().st_size > 0
    metin = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Göreli ekonomik değer" in metin and "sertifikalı EDR değildir" in metin


def test_kacinma_bedeli_yoksa_kayip_araligi_bos(tmp_path):
    pytest.importorskip("matplotlib")
    rapor = ed.calistir(str(tmp_path), uyari_orani_yolu=str(tmp_path / "yok.json"))
    assert rapor["kacinma_bedeli_yuzde"] is None
    ozet = next(iter(rapor["sonuc"].values()))["seriler"]
    assert all(o["en_az_kayip_yakit_yuzdesi"] is None for o in ozet.values())
    assert "—–—" in ed.markdown_ozeti(rapor)
