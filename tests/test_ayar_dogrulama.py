import types

import pytest

from turbulans_radar import config
from turbulans_radar.ayar_dogrulama import AyarHatasi, AyarSemasi, ayarlari_dogrula

pytestmark = pytest.mark.birim


def _kopya(**degisen):
    degerler = {ad: getattr(config, ad) for ad in AyarSemasi.model_fields}
    return types.SimpleNamespace(**{**degerler, **degisen})


def test_varsayilan_ayarlar_gecerli():
    ayarlari_dogrula(_kopya())


@pytest.mark.parametrize(
    "degisen,parca",
    [
        ({"TI1_ESIK_HAFIF": 8e-7}, "TI1_ESIK_HAFIF"),
        ({"ML_KONFORMAL_ALFA": 1.5}, "ML_KONFORMAL_ALFA"),
        ({"CANLI_ISITMA_KUTUSU": (42.0, 36.0, 26.0, 45.0)}, "CANLI_ISITMA_KUTUSU"),
        ({"ML_GECE_ISI_SAATI": "25:00"}, "ML_GECE_ISI_SAATI"),
        ({"VERITABANI_HAVUZ_BOYUTU": 0}, "VERITABANI_HAVUZ_BOYUTU"),
        ({"DEVRE_KESICI_TABAN_SANIYE": 7200.0}, "DEVRE_KESICI_TABAN_SANIYE"),
        ({"CANLI_BASINC_SEVIYELERI_HPA": ()}, "CANLI_BASINC_SEVIYELERI_HPA"),
    ],
)
def test_gecersiz_ayar_adiyla_raporlanir(degisen, parca):
    with pytest.raises(AyarHatasi, match=parca):
        ayarlari_dogrula(_kopya(**degisen))


def test_birden_cok_sorun_tek_mesajda_listelenir():
    with pytest.raises(AyarHatasi) as hata:
        ayarlari_dogrula(_kopya(ML_HOLDOUT_ORANI=0.0, MAKS_ISTEK_GOVDESI_MB=-1.0))
    assert "ML_HOLDOUT_ORANI" in str(hata.value) and "MAKS_ISTEK_GOVDESI_MB" in str(hata.value)


@pytest.mark.parametrize(
    "deger,beklenen", [("true", True), (" Evet ", True), ("0", False), ("", False), ("off", False)]
)
def test_ortam_bool_tanidigi_degerler(monkeypatch, deger, beklenen):
    monkeypatch.setenv("DENEME_BAYRAGI", deger)
    assert config._ortam_bool("DENEME_BAYRAGI", None) is beklenen


def test_ortam_bool_tanimadigi_degerde_hata_verir(monkeypatch):
    monkeypatch.setenv("DENEME_BAYRAGI", "ture")
    with pytest.raises(ValueError, match="DENEME_BAYRAGI"):
        config._ortam_bool("DENEME_BAYRAGI", False)
