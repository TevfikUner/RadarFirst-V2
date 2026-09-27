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


def test_harita_uret_false_haritayi_atlar_ve_cikti_klasoru_olusturmaz(sahte_akis, monkeypatch, tmp_path):
    """Görev kuyruğundan (n8n) tetiklenen çalıştırmalar için: sunucuda
    kimsenin açmayacağı bir HTML dosyası/klasörü hiç oluşturulmamalı."""
    import os

    cagrilar = []
    monkeypatch.setattr(ucus_analizi, "zaman_kaydiricili_harita_olustur", lambda df, dosya_adi: cagrilar.append(df))
    bos_cikti = tmp_path / "kullanilmayan_cikti_klasoru"
    monkeypatch.setattr(ucus_analizi.config, "CIKTI_KLASORU", str(bos_cikti))

    sonuc = ucus_analizi.calistir("TESTX", "2019-01-01", harita_uret=False)

    assert sonuc is sahte_akis
    assert cagrilar == []
    assert not os.path.exists(bos_cikti)


def test_harita_uret_varsayilani_true_haritayi_uretir(sahte_akis, monkeypatch):
    """Varsayılan davranış (CLI: turbulans-analiz) korunmalı: harita_uret
    hiç verilmezse harita yine üretilir."""
    cagrilar = []
    monkeypatch.setattr(
        ucus_analizi, "zaman_kaydiricili_harita_olustur", lambda df, dosya_adi: cagrilar.append(dosya_adi)
    )

    assert ucus_analizi.calistir("TESTX", "2019-01-01") is sahte_akis

    assert len(cagrilar) == 1 and cagrilar[0].endswith("turbulans_haritasi_TESTX_2019-01-01.html")
