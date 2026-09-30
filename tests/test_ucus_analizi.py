import pandas as pd
import pytest

from turbulans_radar.analiz import ucus_analizi
from turbulans_radar.depo.veritabani import VeritabaniKayitHatasi


@pytest.fixture
def sahte_akis(monkeypatch, tmp_path):
    rota_df = pd.DataFrame({"zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]), "enlem": [40.0], "boylam": [30.0]})
    eslesmis_df = rota_df.assign(ti1_indeksi=[1e-7])
    monkeypatch.setattr(ucus_analizi.config, "CIKTI_KLASORU", str(tmp_path))
    monkeypatch.setattr(ucus_analizi.config, "OPENSKY_ONBELLEK_KLASORU", str(tmp_path / "opensky"))
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


def test_eski_haritalar_silinir_yeni_harita_ve_diger_dosyalar_kalir(tmp_path):
    import os

    simdi = 1_000_000_000.0
    eski = tmp_path / "turbulans_haritasi_ESKI_2019-01-01.html"
    yeni = tmp_path / "turbulans_haritasi_YENI_2019-01-02.html"
    ozet = tmp_path / "toplu_analiz_ozeti.csv"
    for dosya in (eski, yeni, ozet):
        dosya.write_text("x", encoding="utf-8")
    os.utime(eski, (simdi - 31 * 86400,) * 2)
    os.utime(yeni, (simdi - 1 * 86400,) * 2)
    os.utime(ozet, (simdi - 365 * 86400,) * 2)

    assert ucus_analizi.eski_haritalari_temizle(tmp_path, gun=30, simdi=simdi) == 1
    assert not eski.exists() and yeni.exists() and ozet.exists()
    assert ucus_analizi.eski_haritalari_temizle(tmp_path, gun=0, simdi=simdi + 10**9) == 0
    assert yeni.exists()


def test_onbellekteki_rota_trinoya_gitmeden_kullanilir(sahte_akis, monkeypatch):
    rota_df = pd.DataFrame({"zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]), "enlem": [41.0], "boylam": [29.0]})
    monkeypatch.setattr(ucus_analizi, "rota_onbellekten_oku", lambda u, t: rota_df)
    monkeypatch.setattr(ucus_analizi, "trino_baglantisi_olustur", lambda: pytest.fail("Trino'ya bağlanılmamalı"))
    kullanilan = []
    monkeypatch.setattr(ucus_analizi, "rotayi_hava_durumuyla_eslestir", lambda r, k: kullanilan.append(r) or sahte_akis)
    ucus_analizi.calistir("TESTX", "2019-01-01", harita_uret=False)
    assert kullanilan == [rota_df]


def test_trinodan_gelen_rota_onbellege_yazilir_ve_ikinci_calistirmada_okunur(sahte_akis, monkeypatch):
    sorgular = []
    rota_df = pd.DataFrame({"zaman": pd.to_datetime(["2019-01-01T00:00:00Z"]), "enlem": [40.0], "boylam": [30.0]})
    monkeypatch.setattr(ucus_analizi, "ucus_numarasi_ile_rota_cek", lambda b, u, t: sorgular.append(u) or rota_df)
    ucus_analizi.calistir("TESTX", "2019-01-01", harita_uret=False)
    ucus_analizi.calistir("TESTX", "2019-01-01", harita_uret=False)
    assert sorgular == ["TESTX"]


@pytest.fixture
def kup_secimi(monkeypatch):
    rota_df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2019-01-15T20:00:00Z"]),
            "enlem": [40.0],
            "boylam": [30.0],
            "geo_irtifa_m": [10000.0],
        }
    )
    durum = {"yerel": "yerel_kup", "kapsam_disi": False, "era5": "era5_dilimi", "cagrilar": []}
    monkeypatch.setattr(ucus_analizi.config, "ERA5_OTOMATIK_INDIRME", True)
    monkeypatch.setattr(ucus_analizi, "veri_kupunu_sec", lambda *a, **k: durum["yerel"])
    monkeypatch.setattr(ucus_analizi, "kapsam_disi_maskesi", lambda kup, *a, **k: pd.Series([durum["kapsam_disi"]]))

    def _era5(enlemler, boylamlar, zamanlar):
        durum["cagrilar"].append(len(enlemler))
        if isinstance(durum["era5"], Exception):
            raise durum["era5"]
        return durum["era5"]

    monkeypatch.setattr(ucus_analizi, "ucus_hava_dilimi_hazirla", _era5)
    monkeypatch.setattr(ucus_analizi, "hava_durumu_onbellekli_yukle", lambda yol: "ana_kup")
    return rota_df, durum


def test_yerel_kup_tam_kapsiyorsa_era5_indirilmez(kup_secimi):
    rota_df, durum = kup_secimi
    assert ucus_analizi._veri_kupunu_sec(rota_df) == "yerel_kup"
    assert durum["cagrilar"] == []


def test_yerel_kup_eksik_kapsiyorsa_ucusa_ozel_era5_dilimi_kullanilir(kup_secimi):
    rota_df, durum = kup_secimi
    durum["kapsam_disi"] = True
    assert ucus_analizi._veri_kupunu_sec(rota_df) == "era5_dilimi"
    assert durum["cagrilar"] == [1]


def test_hic_yerel_kup_yoksa_era5_dilimi_indirilir(kup_secimi):
    rota_df, durum = kup_secimi
    durum["yerel"] = None
    assert ucus_analizi._veri_kupunu_sec(rota_df) == "era5_dilimi"


def test_era5_alinamazsa_eldeki_kupe_ya_da_ana_kupe_dusulur(kup_secimi):
    rota_df, durum = kup_secimi
    durum["kapsam_disi"], durum["era5"] = True, RuntimeError("CDS ve ARCO kapalı")
    assert ucus_analizi._veri_kupunu_sec(rota_df) == "yerel_kup"
    durum["yerel"] = None
    assert ucus_analizi._veri_kupunu_sec(rota_df) == "ana_kup"


def test_otomatik_indirme_kapaliysa_era5_denenmez(kup_secimi, monkeypatch):
    rota_df, durum = kup_secimi
    durum["yerel"] = None
    monkeypatch.setattr(ucus_analizi.config, "ERA5_OTOMATIK_INDIRME", False)
    assert ucus_analizi._veri_kupunu_sec(rota_df) == "ana_kup"
    assert durum["cagrilar"] == []
