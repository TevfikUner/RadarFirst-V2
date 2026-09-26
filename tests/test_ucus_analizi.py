import pandas as pd
import pytest

from turbulans_radar.analiz import ucus_analizi
from turbulans_radar.depo.veritabani import VeritabaniKayitHatasi


@pytest.fixture
def sahte_akis(monkeypatch, tmp_path):
    rota_df = pd.DataFrame({"zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]), "enlem": [40.0], "boylam": [30.0]})
    eslesmis_df = rota_df.assign(ti1_indeksi=[1e-7])
    monkeypatch.setattr(ucus_analizi.config, "CIKTI_KLASORU", str(tmp_path))
    monkeypatch.setattr(ucus_analizi, "trino_baglantisi_olustur", lambda: object())
    monkeypatch.setattr(ucus_analizi, "ucus_numarasi_ile_rota_cek", lambda b, u, t: rota_df)
    monkeypatch.setattr(ucus_analizi, "_veri_kupunu_sec", lambda rota: None)
    monkeypatch.setattr(ucus_analizi, "veri_kupu_adi", lambda kup: "sahte.nc")
    monkeypatch.setattr(ucus_analizi, "rotayi_hava_durumuyla_eslestir", lambda r, k: eslesmis_df)
    monkeypatch.setattr(ucus_analizi, "zaman_kaydiricili_harita_olustur", lambda df, dosya_adi: None)

    def _kayit_hatasi(*args, **kwargs):
        raise ConnectionError("veritabanı kapalı")

    monkeypatch.setattr(ucus_analizi, "ucus_ve_olcumleri_kaydet", _kayit_hatasi)
    return eslesmis_df


def test_cli_kayit_hatasinda_haritayi_yine_uretir(sahte_akis):
    assert ucus_analizi.calistir("TESTX", "2019-01-01") is sahte_akis


def test_kayit_zorunluysa_kayit_hatasi_yukselir(sahte_akis):
    with pytest.raises(VeritabaniKayitHatasi):
        ucus_analizi.calistir("TESTX", "2019-01-01", kayit_zorunlu=True)
