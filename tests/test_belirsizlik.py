import numpy as np
import pytest

from turbulans_radar.ml import belirsizlik as bl


def test_esik_kalibrasyon_skorlarinin_duzeltilmis_yuzdeligidir():
    y = np.array([1, 1, 0, 0, 1, 0, 1, 0, 1])
    p = np.array([0.9, 0.8, 0.1, 0.3, 0.6, 0.4, 0.95, 0.2, 0.7])
    skorlar = np.sort(bl.uyumsuzluk_skorlari(y, p))
    assert bl.konformal_esik(y, p, alfa=0.2) == pytest.approx(skorlar[int(np.ceil(10 * 0.8)) - 1])
    assert bl.konformal_esik(y, p, alfa=0.01) == 1.0


def test_durumlar_tahmin_kumesinden_turetilir():
    durumlar = bl.risk_durumlari([0.05, 0.95, 0.5, np.nan], esik=0.3)
    assert durumlar.tolist() == [bl.DUSUK_RISK, bl.YUKSEK_RISK, bl.BELIRSIZ, None]
    assert bl.risk_durumlari([0.5], esik=0.6).tolist() == [bl.BELIRSIZ]


def test_degistirilebilir_veride_kapsama_hedefi_saglanir():
    rng = np.random.default_rng(0)
    n = 6000
    gercek_p = rng.uniform(0, 1, n)
    y = (rng.uniform(0, 1, n) < gercek_p).astype(int)
    tahmin = np.clip(gercek_p + rng.normal(0, 0.1, n), 0, 1)
    esik = bl.konformal_esik(y[:3000], tahmin[:3000], alfa=0.1)
    rapor = bl.kapsama_raporu(y[3000:], tahmin[3000:], esik, alfa=0.1)
    assert rapor["kapsama"] >= 0.88 and rapor["hedef_kapsama"] == pytest.approx(0.9)
    assert 0 < rapor["belirsiz_orani"] < 1
    assert rapor["belirsiz_orani"] + rapor["yuksek_risk_orani"] + rapor["dusuk_risk_orani"] == pytest.approx(1)


def test_bos_kalibrasyon_acik_hata_verir():
    with pytest.raises(ValueError):
        bl.konformal_esik([], [], 0.1)
