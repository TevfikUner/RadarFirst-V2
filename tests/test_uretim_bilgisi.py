import pytest

from turbulans_radar.uretim_bilgisi import uretim_bilgisi, yazilim_surumu

pytestmark = pytest.mark.birim


def test_surum_pyprojectten_ya_da_paketten_okunur():
    assert yazilim_surumu() not in ("", "bilinmiyor")


def test_model_bilgisi_verilince_surum_ve_ozet_tasinir():
    bilgi = uretim_bilgisi(model_bilgisi={"secilen_model": "RF", "egitim_zamani": "t", "model_sha256": "ab", "x": 1})
    assert bilgi["model"] == {"secilen_model": "RF", "egitim_zamani": "t", "model_sha256": "ab"}
    assert bilgi["hava_verisi"] is None and bilgi["parametreler"] == {}
