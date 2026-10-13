import json

import joblib
import pytest

from turbulans_radar import config
from turbulans_radar.ml import model_butunlugu as mb
from turbulans_radar.ml import turbulans_ml_modeli as tm

pytestmark = pytest.mark.birim


@pytest.fixture
def klasor(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, "MODEL_DOSYA_YOLU", str(tmp_path / "m.joblib"))
    monkeypatch.setattr(tm, "MODEL_BILGI_DOSYA_YOLU", str(tmp_path / "m.json"))
    monkeypatch.setattr(tm, "MODEL_VERSIYONLARI_KLASORU", str(tmp_path / "v"))
    monkeypatch.setattr(tm, "MODEL_VERSIYONLARI_MANIFEST_YOLU", str(tmp_path / "v" / "manifest.json"))
    monkeypatch.setitem(tm._ONBELLEK_MODEL, "imza", None)
    return tmp_path


def _model_yaz(klasor, ozet_yaz=True):
    joblib.dump({"model": 1}, klasor / "m.joblib")
    bilgi = {"egitim_zamani": "2026-10-13T00:00:00+00:00"}
    if ozet_yaz:
        bilgi["model_sha256"] = mb.dosya_ozeti(str(klasor / "m.joblib"))
    (klasor / "m.json").write_text(json.dumps(bilgi), encoding="utf-8")
    return bilgi


def test_ozet_uyusuyorsa_yuklenir(klasor):
    bilgi = _model_yaz(klasor)
    assert mb.guvenle_yukle(tm.MODEL_DOSYA_YOLU, bilgi) == {"model": 1}


def test_degistirilmis_dosya_yuklenmez_ve_serviste_model_yok_sayilir(klasor):
    _model_yaz(klasor)
    joblib.dump({"model": 2}, klasor / "m.joblib")
    with pytest.raises(mb.ModelButunlukHatasi):
        mb.guvenle_yukle(tm.MODEL_DOSYA_YOLU, tm.model_bilgisini_yukle())
    assert tm._modeli_yukle() is None


def test_ozetsiz_eski_model_uyariyla_yuklenir_zorunluysa_reddedilir(klasor, monkeypatch):
    bilgi = _model_yaz(klasor, ozet_yaz=False)
    assert mb.guvenle_yukle(tm.MODEL_DOSYA_YOLU, bilgi) == {"model": 1}
    monkeypatch.setattr(config, "MODEL_BUTUNLUK_ZORUNLU", True)
    with pytest.raises(mb.ModelButunlukHatasi):
        mb.guvenle_yukle(tm.MODEL_DOSYA_YOLU, bilgi)


def test_muhurle_ozet_ekler_ve_degismisi_hata_sayar(klasor):
    _model_yaz(klasor, ozet_yaz=False)
    assert mb.muhurle()["aktif"] == "muhurlendi"
    assert "model_sha256" in tm.model_bilgisini_yukle()
    assert mb.muhurle()["aktif"] == "zaten_muhurlu"
    joblib.dump({"model": 3}, klasor / "m.joblib")
    sonuc = mb.muhurle()
    assert sonuc["aktif"] == "uyusmuyor" and sonuc["hatalar"] == ["aktif model"]


def test_geri_alma_degismis_surumu_reddeder(klasor):
    _model_yaz(klasor)
    bilgi = tm.model_bilgisini_yukle()
    versiyon_id = tm.versiyon_kaydet(tm.MODEL_DOSYA_YOLU, bilgi)
    surum_dosyasi = next((klasor / "v").glob("*.joblib"))
    joblib.dump({"model": 9}, surum_dosyasi)
    with pytest.raises(ValueError, match="geri alınmadı"):
        tm.versiyona_geri_don(versiyon_id)
