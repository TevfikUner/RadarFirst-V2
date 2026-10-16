import pytest

from turbulans_radar import config
from turbulans_radar.analiz import ayriklastirma as ay

pytestmark = pytest.mark.birim


def test_tarama_her_ayari_dener_referansa_gore_fark_ve_ayarlari_geri_yukler():
    eski = (config.ROTA_SIMULASYONU_NOKTA_SAYISI, config.ROTA_YANAL_IZGARA_KM, config.CANLI_HAVA_VERISI_ETKIN)
    cagrilar = []

    def sahte_rota(*girdi, sigmetler=None, kisitli_sahalar=None):
        nokta, izgara = config.ROTA_SIMULASYONU_NOKTA_SAYISI, config.ROTA_YANAL_IZGARA_KM
        cagrilar.append((nokta, izgara, config.CANLI_HAVA_VERISI_ETKIN))
        return {
            "kacinma_stratejisi": "yanal" if izgara < 30 else "yok",
            "ruzgar_verisi_kaynagi": "era5_gercek",
            "optimize_rota": {
                "toplam_sure_dk": 60.0 + izgara / 10,
                "tahmini_yakit_kg": 2000.0 + nokta,
                "riskli_sure_dk": None if nokta == 21 else 3.0,
                "mesafe_km": 500.0,
            },
        }

    senaryolar = [("S1", (41.0, 28.9, 36.9, 30.7, 29000, "2019-01-05T12:00:00"), [], [])]
    rapor = ay.tarama_yap(senaryolar, (21, 41), (10.0, 40.0), rota_fonksiyonu=sahte_rota)

    assert {(n, i) for n, i, _ in cagrilar} == {(21, 10.0), (21, 40.0), (41, 10.0), (41, 40.0)}
    assert not any(canli for _, _, canli in cagrilar)
    assert (config.ROTA_SIMULASYONU_NOKTA_SAYISI, config.ROTA_YANAL_IZGARA_KM, config.CANLI_HAVA_VERISI_ETKIN) == eski
    assert rapor["referans"] == {"nokta": 41, "izgara_km": 10.0}
    kayit = {(k["nokta"], k["izgara_km"]): k for k in rapor["kayitlar"]}
    assert kayit[(21, 40.0)]["tahmini_yakit_kg_fark"] == pytest.approx(-20.0)
    assert kayit[(21, 40.0)]["toplam_sure_dk_fark"] == pytest.approx(3.0)
    assert kayit[(21, 40.0)]["riskli_sure_dk_fark"] is None
    assert kayit[(41, 40.0)]["strateji_ayni_mi"] is False
    metin = ay.markdown_ozeti(rapor)
    assert "≠ ref" in metin and "| S1 | 41" in metin
