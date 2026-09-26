"""
test_pirep_kalibrasyon_verisi_uret.py
-----------------------------------------
kalibrasyon_verisini_hazirla, ml_egitimi.veriyi_hazirla ile AYNI gerçek IEM
PIREP + ERA5 verisini kullanır (pirep_ust_seviye_siniflandirilmis.csv,
era5_egitim_verisi/*.nc -- ml_veri_indir.py ile indirilir); bu dosyalar
yoksa (diğer "gerçek veri" testleriyle AYNI desen) atlanır.
"""

import glob
import os

import pytest

from turbulans_radar.ml.pirep_kalibrasyon_verisi_uret import (
    ERA5_KLASORU,
    PIREP_DOSYASI,
    SINIF_MAKS_DEGERI,
    kalibrasyon_verisini_hazirla,
)


@pytest.fixture(scope="module")
def gercek_veri_var_mi():
    if not os.path.exists(PIREP_DOSYASI) or not glob.glob(f"{ERA5_KLASORU}/*.nc"):
        pytest.skip(
            f"'{PIREP_DOSYASI}' veya '{ERA5_KLASORU}/*.nc' bulunamadı -- "
            "ml_veri_indir.py ile indirilmedikçe bu test atlanır."
        )


def test_kalibrasyon_verisini_hazirla_beklenen_sutunlari_uretir(gercek_veri_var_mi):
    df = kalibrasyon_verisini_hazirla()
    assert set(df.columns) == {"ti1_indeksi", "pirep_edr"}
    assert len(df) > 0


def test_pirep_edr_dogru_araliktadir(gercek_veri_var_mi):
    """pirep_edr, PIREP 'sinif' sütununun (0/1/2) [0,1]'e ölçeklenmiş hali --
    bu yüzden sadece {0, 0.5, 1.0} değerlerini alabilir, aralık dışına
    çıkamaz (kalibrasyon.py'nin beklediği [0,1] sözleşmesiyle uyumlu)."""
    df = kalibrasyon_verisini_hazirla()
    olasi_degerler = {i / SINIF_MAKS_DEGERI for i in range(SINIF_MAKS_DEGERI + 1)}
    assert set(df["pirep_edr"].unique()) <= olasi_degerler
    assert df["pirep_edr"].between(0, 1).all()


def test_ti1_indeksi_pozitif_gercek_degerlerdir(gercek_veri_var_mi):
    df = kalibrasyon_verisini_hazirla()
    assert (df["ti1_indeksi"] >= 0).all()
    assert df["ti1_indeksi"].notna().all()
