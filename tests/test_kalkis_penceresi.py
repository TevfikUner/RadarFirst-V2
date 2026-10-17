import pandas as pd
import pytest

from turbulans_radar.rota.kalkis_penceresi import kalkis_penceresi

pytestmark = pytest.mark.birim


def _sonuc(riskli):
    return {
        "ruzgar_verisi_kaynagi": "gfs_tahmin",
        "kacinma_stratejisi": "yanal",
        "guvenli_rota_bulundu_mu": True,
        "normal_rota": {"riskli_sure_dk": riskli},
        "optimize_rota": {"riskli_sure_dk": 0.0, "toplam_sure_dk": 60.0, "tahmini_yakit_kg": 2000.0},
    }


def test_her_fark_icin_yeniden_hesaplar_sirali_ve_hata_raporlar():
    cagrilar = []

    def sahte(*argumanlar, **anahtarlar):
        zaman = argumanlar[-1]
        cagrilar.append((zaman, anahtarlar["ucak_modeli_kodu"]))
        if zaman.endswith("13:00:00"):
            raise RuntimeError("/app/canli_veri/gizli_yol.nc okunamadı")
        return _sonuc(float(pd.Timestamp(zaman).hour))

    pencere = kalkis_penceresi(
        _sonuc(5.0), sahte, (41.0, 28.9, 36.9, 30.7, 29000), "2026-10-17T12:00:00", (-2, -1, 1), ucak_modeli_kodu="A320"
    )
    assert [z for z, _ in cagrilar] == ["2026-10-17T10:00:00", "2026-10-17T11:00:00", "2026-10-17T13:00:00"]
    assert [s["fark_saat"] for s in pencere["satirlar"]] == [-2, -1, 0]
    assert pencere["satirlar"][2]["normal_riskli_sure_dk"] == 5.0
    assert pencere["satirlar"][0]["normal_riskli_sure_dk"] == 10.0
    assert pencere["hatalar"] == [{"fark_saat": 1, "hata": "RuntimeError"}]
    assert "öneri değildir" in pencere["bilgi_notu"]
