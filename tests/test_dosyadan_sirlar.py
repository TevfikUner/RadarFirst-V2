import pytest

from turbulans_radar import config

pytestmark = pytest.mark.birim


def test_file_degiskeni_sirri_dosyadan_yukler_ve_varsayilani_ezer(tmp_path):
    dosya = tmp_path / "api_anahtari"
    dosya.write_text("dosyadaki-anahtar\n", encoding="utf-8")
    ortam = {"API_ANAHTARI": "compose-varsayilani", "API_ANAHTARI_FILE": str(dosya)}
    assert config.dosyadan_sirlari_yukle(ortam) == ["API_ANAHTARI"]
    assert ortam["API_ANAHTARI"] == "dosyadaki-anahtar"


def test_file_degiskeni_yoksa_ortam_degismez():
    ortam = {"POSTGRES_PASSWORD": "ortamdaki"}
    assert config.dosyadan_sirlari_yukle(ortam) == []
    assert ortam == {"POSTGRES_PASSWORD": "ortamdaki"}


def test_okunamayan_sir_dosyasi_baslamayi_durdurur_ve_degeri_yazmaz(tmp_path):
    with pytest.raises(RuntimeError, match="POSTGRES_PASSWORD_FILE"):
        config.dosyadan_sirlari_yukle({"POSTGRES_PASSWORD_FILE": str(tmp_path / "yok")})


def test_listede_olmayan_degisken_dosyadan_okunmaz(tmp_path):
    dosya = tmp_path / "x"
    dosya.write_text("gizli", encoding="utf-8")
    ortam = {"TI1_ESIK_HAFIF_FILE": str(dosya)}
    assert config.dosyadan_sirlari_yukle(ortam) == []
    assert "TI1_ESIK_HAFIF" not in ortam


def test_bos_sir_dosyasi_reddedilir(tmp_path):
    dosya = tmp_path / "bos"
    dosya.write_text(" \t ", encoding="utf-8")
    with pytest.raises(RuntimeError, match="boş"):
        config.dosyadan_sirlari_yukle({"API_ANAHTARI": "eski", "API_ANAHTARI_FILE": str(dosya)})
