import os

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar import config
from turbulans_radar.veri.era5_saglayici import CdsEra5Saglayici
from turbulans_radar.veri.veri_saglayicilari import Kutu

pytestmark = [pytest.mark.ag, pytest.mark.gercek_veri]


def _cds_kimligi_var_mi():
    return bool(
        os.environ.get("CDSAPI_KEY")
        or os.path.isfile(os.environ.get("CDSAPI_RC", ""))
        and os.path.getsize(os.environ["CDSAPI_RC"]) > 0
        or os.path.isfile(os.path.expanduser("~/.cdsapirc"))
    )


def test_gercek_cds_dilimi_yerel_referans_kuple_ayni(tmp_path):
    pytest.importorskip("cdsapi")
    if not os.path.exists(config.HAVA_DURUMU_DOSYASI):
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı.")
    if not _cds_kimligi_var_mi():
        pytest.skip("CDS kimliği yok (CDSAPI_RC / ~/.cdsapirc / CDSAPI_KEY).")

    kutu = Kutu(40.0, 41.0, 29.0, 30.0)
    baslangic, bitis = pd.Timestamp("2019-01-15T20:00Z"), pd.Timestamp("2019-01-15T21:00Z")
    hedef = str(tmp_path / "cds.nc")
    CdsEra5Saglayici().kup_indir(kutu, baslangic, bitis, hedef)

    with xr.open_dataset(hedef) as cds, xr.open_dataset(config.HAVA_DURUMU_DOSYASI) as yerel:
        assert cds.attrs["era5_alt_kaynak"] == "cds"
        assert cds.sizes["valid_time"] == 2
        referans = yerel[["u", "v", "t"]].sel(
            valid_time=cds["valid_time"].values,
            latitude=cds["latitude"].values,
            longitude=cds["longitude"].values,
            **{config.BASINC_BOYUTU: cds[config.BASINC_BOYUTU].values},
        )
        for degisken in ("u", "v", "t"):
            np.testing.assert_allclose(cds[degisken].values, referans[degisken].values, atol=1e-3)


def test_gercek_cds_ml_depo_istegi_yedi_seviye_ve_bagil_nem_doner(tmp_path):
    pytest.importorskip("cdsapi")
    if not _cds_kimligi_var_mi():
        pytest.skip("CDS kimliği yok (CDSAPI_RC / ~/.cdsapirc / CDSAPI_KEY).")

    hedef = str(tmp_path / "ml_depo.nc")
    CdsEra5Saglayici(
        basinc_seviyeleri_hpa=config.ML_DEPO_BASINC_SEVIYELERI_HPA, ek_degiskenler=config.ML_DEPO_EK_DEGISKENLER
    ).kup_indir(
        Kutu(40.0, 40.5, 29.0, 29.5), pd.Timestamp("2019-01-15T20:00Z"), pd.Timestamp("2019-01-15T20:00Z"), hedef
    )

    with xr.open_dataset(hedef) as kup:
        assert set(kup.data_vars) == {"u", "v", "t", "r"}
        assert sorted(kup[config.BASINC_BOYUTU].values.tolist()) == sorted(config.ML_DEPO_BASINC_SEVIYELERI_HPA)
        assert float(kup["r"].min()) >= 0.0 and float(kup["r"].max()) <= 150.0
