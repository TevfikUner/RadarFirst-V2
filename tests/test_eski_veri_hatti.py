import runpy

import pytest

from turbulans_radar.ml.turbulans_ml_modeli import ESKI_VERI_HATTI_MESAJI


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_eski_egitim_betigi_calistirilinca_yeni_hatta_yonlendirir():
    with pytest.raises(SystemExit) as cikis:
        runpy.run_module("turbulans_radar.ml.ml_egitimi", run_name="__main__")
    assert str(cikis.value) == ESKI_VERI_HATTI_MESAJI
