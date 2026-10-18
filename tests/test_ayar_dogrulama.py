import types

import pytest

from turbulans_radar import config
from turbulans_radar.ayar_dogrulama import AyarHatasi, AyarSemasi, ag_acilis_sorunlari, ayarlari_dogrula

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


_GUCLU = "g" * 40


def _ag_ortami(**degisen):
    return {
        "API_YAYIN_ADRESI": "0.0.0.0",
        "API_ANAHTARI": _GUCLU,
        "POSTGRES_USER": "turbulans_uygulama",
        "POSTGRES_PASSWORD": _GUCLU,
        **degisen,
    }


def _uretim_ayari(**degisen):
    return types.SimpleNamespace(KISITLI_SAHA_ORNEK_VERI_YUKLE=False, MODEL_BUTUNLUK_ZORUNLU=True, **degisen)


def test_yerel_yayinda_ag_kurallari_uygulanmaz():
    assert ag_acilis_sorunlari({"API_ANAHTARI": "demo", "POSTGRES_PASSWORD": "postgres"}, _uretim_ayari()) == []


def test_guclu_uretim_ayarlariyla_ag_acilisi_serbest():
    assert ag_acilis_sorunlari(_ag_ortami(), _uretim_ayari()) == []
    assert ag_acilis_sorunlari(_ag_ortami(API_YAYIN_ADRESI="", AG_ACILISI="true"), _uretim_ayari()) == []


@pytest.mark.parametrize(
    "ortam_degisen,ayar_degisen,parca",
    [
        ({"API_ANAHTARI": "kisa"}, {}, "API_ANAHTARI"),
        ({"API_ANAHTARI": "demo" + _GUCLU}, {}, "API_ANAHTARI"),
        ({"API_ANAHTARI": ""}, {}, "API_ANAHTARI"),
        ({"API_PILOT_ANAHTARI": "demo-pilot"}, {}, "API_PILOT_ANAHTARI"),
        ({"API_ANAHTARLARI": "tablet:pilot:kisa"}, {}, "API_ANAHTARLARI[tablet]"),
        ({"POSTGRES_PASSWORD": "postgres"}, {}, "POSTGRES_PASSWORD"),
        ({"POSTGRES_PASSWORD": "demo123"}, {}, "POSTGRES_PASSWORD"),
        ({"POSTGRES_USER": "postgres"}, {}, "POSTGRES_USER"),
        ({"POSTGRES_USER": "turbulans", "DB_SUPER_KULLANICI": "turbulans"}, {}, "POSTGRES_USER"),
        ({}, {"KISITLI_SAHA_ORNEK_VERI_YUKLE": True}, "KISITLI_SAHA_ORNEK_VERI_YUKLE"),
        ({}, {"MODEL_BUTUNLUK_ZORUNLU": False}, "MODEL_BUTUNLUK_ZORUNLU"),
        ({"API_YAYIN_ADRESI": "", "AG_ACILISI": "1", "API_ANAHTARI": "kisa"}, {}, "API_ANAHTARI"),
    ],
)
def test_ag_acik_kurulumda_zayif_ayar_reddedilir(ortam_degisen, ayar_degisen, parca):
    kaynak = types.SimpleNamespace(
        **{"KISITLI_SAHA_ORNEK_VERI_YUKLE": False, "MODEL_BUTUNLUK_ZORUNLU": True, **ayar_degisen}
    )
    sorunlar = ag_acilis_sorunlari(_ag_ortami(**ortam_degisen), kaynak)
    assert len(sorunlar) == 1 and sorunlar[0].startswith(parca)


def test_isci_anahtarsiz_ag_kurallarindan_gecer_ama_db_kurallari_kalir():
    ortam = _ag_ortami(API_ANAHTARI="", POSTGRES_USER="postgres")
    sorunlar = ag_acilis_sorunlari(ortam, _uretim_ayari(), anahtarlari_denetle=False)
    assert len(sorunlar) == 1 and sorunlar[0].startswith("POSTGRES_USER")


def test_ag_sorunlari_sema_hatalariyla_tek_mesajda_ve_degersiz():
    kaynak = _kopya(ML_HOLDOUT_ORANI=0.0, KISITLI_SAHA_ORNEK_VERI_YUKLE=False, MODEL_BUTUNLUK_ZORUNLU=True)
    with pytest.raises(AyarHatasi) as hata:
        ayarlari_dogrula(kaynak, _ag_ortami(API_ANAHTARI="gizli-ama-kisa"))
    mesaj = str(hata.value)
    assert "ML_HOLDOUT_ORANI" in mesaj and "ağa açık kurulum: API_ANAHTARI" in mesaj
    assert "gizli-ama-kisa" not in mesaj
