import runpy

import pytest

from turbulans_radar.ml.pirep_kalibrasyon_verisi_uret import kalibrasyon_verisini_hazirla
from turbulans_radar.ml.turbulans_ml_modeli import ESKI_VERI_HATTI_MESAJI, EskiVeriHattiHatasi


def test_eski_kalibrasyon_verisi_hatti_kilitlidir():
    with pytest.raises(EskiVeriHattiHatasi, match="kullanım dışıdır"):
        kalibrasyon_verisini_hazirla()


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.parametrize(
    "modul",
    [
        "turbulans_radar.ml.ml_veri_indir",
        "turbulans_radar.ml.pirep_kalibrasyon_verisi_uret",
        "turbulans_radar.ml.ml_egitimi",
    ],
)
def test_eski_betikler_calistirilinca_yeni_hatta_yonlendirir(modul):
    with pytest.raises(SystemExit) as cikis:
        runpy.run_module(modul, run_name="__main__")
    assert str(cikis.value) == ESKI_VERI_HATTI_MESAJI
