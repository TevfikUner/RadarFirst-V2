import pytest

from turbulans_radar import config
from turbulans_radar.analiz import uyari_orani as uo

pytestmark = pytest.mark.birim


def _secenek(strateji, ek_yakit, riskli, onerilen=False):
    return {"strateji": strateji, "ek_yakit_yuzde": ek_yakit, "riskli_nokta_sayisi": riskli, "onerilen": onerilen}


def _sonuc(normal_riskli, strateji="yok", secenekler=None, veri="era5_gercek", optimize_riskli=0, bedel=None):
    return {
        "ruzgar_verisi_kaynagi": veri,
        "kacinma_stratejisi": strateji,
        "guvenli_rota_bulundu_mu": True,
        "normal_rota": {
            "riskli_nokta_sayisi": normal_riskli,
            "riskli_sure_dk": None if normal_riskli is None else 4.0 * normal_riskli,
        },
        "optimize_rota": {"riskli_nokta_sayisi": optimize_riskli, "riskli_sure_dk": 4.0 * optimize_riskli},
        "secenekler": secenekler or [],
        "referans_karsilastirmasi": {"kacinma_bedeli": None if bedel is None else {"ek_yakit_yuzde": bedel}},
    }


def test_senaryolar_gun_saat_cift_ve_seviye_carpimidir():
    senaryolar = list(uo.senaryolari_uret("2019-01-01", 2, (0, 12), (35000,), uo.SEHIR_CIFTLERI[:3]))
    assert len(senaryolar) == 2 * 2 * 3
    assert senaryolar[0] == ("İstanbul→Van", (41.0, 28.9, 38.5, 43.4, 35000, "2019-01-01T00:00:00"))
    assert senaryolar[-1][1][5] == "2019-01-02T12:00:00"


def test_daha_ucuz_riskli_secenek_yalniz_daha_ucuz_ve_daha_riskli_olanlardir():
    sonuc = _sonuc(
        6,
        "yanal",
        [
            _secenek("yanal", 9.5, 0, onerilen=True),
            _secenek("ust_seviye", -2.0, 1),
            _secenek("yanal_ceza_60", 4.0, 2),
            _secenek("alt_seviye", 12.0, 3),
        ],
    )
    ucuz = uo._daha_ucuz_riskli_secenek(sonuc)
    assert ucuz["strateji"] == "ust_seviye"
    assert ucuz["yakit_avantaji_yuzde"] == pytest.approx(11.5)
    assert uo._daha_ucuz_riskli_secenek(_sonuc(0)) is None


def test_olcum_canli_veriyi_kapatir_hatayi_kaydeder_ve_ozet_oranlari_dogru():
    eski = (config.ERA5_OTOMATIK_INDIRME, config.CANLI_HAVA_VERISI_ETKIN)
    sonuclar = iter(
        [
            _sonuc(0),
            _sonuc(5, "yanal", [_secenek("yanal", 9.0, 0, True), _secenek("ust_seviye", -1.0, 1)], bedel=8.0),
            _sonuc(3, "ust_seviye", [_secenek("ust_seviye", 2.0, 1, True)], optimize_riskli=1, bedel=1.0),
            _sonuc(None, veri="kapsam_disi"),
        ]
    )
    canli_durumlari = []

    def sahte_rota(*girdi, sigmetler=None, kisitli_sahalar=None):
        canli_durumlari.append(
            (config.ERA5_OTOMATIK_INDIRME, config.CANLI_HAVA_VERISI_ETKIN, sigmetler, kisitli_sahalar)
        )
        sonuc = next(sonuclar, None)
        if sonuc is None:
            raise RuntimeError("küp yok")
        return sonuc

    senaryolar = list(uo.senaryolari_uret("2019-01-01", 1, (0,), (35000,), uo.SEHIR_CIFTLERI[:5]))
    kayitlar = uo.olcum_yap(senaryolar, rota_fonksiyonu=sahte_rota)

    assert all(d == (False, False, [], []) for d in canli_durumlari)
    assert (config.ERA5_OTOMATIK_INDIRME, config.CANLI_HAVA_VERISI_ETKIN) == eski
    ozet = uo.ozetle(kayitlar)
    g = ozet["genel"]
    assert (g["rota"], g["riskli_rota"], g["sapma"]) == (3, 2, 2)
    assert g["sapma_orani"] == pytest.approx(2 / 3)
    assert g["sapma_ek_yakit_yuzde_medyan"] == pytest.approx(5.5)
    assert g["kacinma_bedeli_yuzde_medyan"] == pytest.approx(4.5)
    assert g["sapmada_kalan_riskli_rota"] == 1
    assert g["daha_ucuz_riskli_secenekli_sapma"] == 1
    assert g["ucuz_secenek_yakit_avantaji_medyan"] == pytest.approx(10.0)
    assert (ozet["hata"], ozet["era5_disi"]) == (1, 1)

    rapor = {
        "parametreler": {
            "baslangic": "2019-01-01",
            "gun_sayisi": 1,
            "saatler": [0],
            "fl": [350],
            "ciftler": uo.SEHIR_CIFTLERI[:5],
            "ti1_esigi": 7e-7,
        },
        "commit": None,
        "uretim_zamani": "2026-10-28T00:00:00+00:00",
        "ozet": ozet,
    }
    metin = uo.markdown_ozeti(rapor)
    assert "| **Tümü** | 3 | %66.7 | %66.7 |" in metin
    assert "sertifikalı EDR değildir" in metin


def _noktali(sonuc, normal_edr, optimize_edr):
    sonuc["normal_rota"]["noktalar"] = [{"birlesik_edr": d} for d in normal_edr]
    sonuc["optimize_rota"]["noktalar"] = [{"birlesik_edr": d} for d in optimize_edr]
    return sonuc


def test_birlesik_riskli_nokta_esigi_sayar_degersiz_rotada_none():
    assert uo.birlesik_riskli_nokta({"noktalar": [{"birlesik_edr": 0.05}, {"birlesik_edr": 0.08}, {}]}, 0.0757) == 1
    assert uo.birlesik_riskli_nokta({"noktalar": [{"birlesik_edr": None}]}, 0.0757) is None
    assert uo.birlesik_riskli_nokta({}, 0.0757) is None


def test_birlesik_sutunu_yalniz_esik_verilince_ve_uyusma_oranlari():
    girdi = (41.0, 28.9, 38.5, 43.4, 35000, "2019-01-01T00:00:00")
    assert "normal_birlesik_riskli_nokta" not in uo.kaydi_cikar("A", girdi, _noktali(_sonuc(0), [0.1], [0.1]), 1.0)
    kayitlar = [
        uo.kaydi_cikar("A", girdi, _noktali(_sonuc(2, "yanal"), [0.1, 0.05], [0.05]), 1.0, 0.0757),
        uo.kaydi_cikar("A", girdi, _noktali(_sonuc(1, "yanal"), [0.05], [0.09]), 1.0, 0.0757),
        uo.kaydi_cikar("A", girdi, _noktali(_sonuc(0), [0.2], [0.2]), 1.0, 0.0757),
        uo.kaydi_cikar("A", girdi, _noktali(_sonuc(0), [0.01], [0.01]), 1.0, 0.0757),
    ]
    b = uo.ozetle(kayitlar)["birlesik"]["genel"]
    assert b["rota"] == 4 and b["ti1_uyari_orani"] == 0.5 and b["birlesik_uyari_orani"] == 0.5
    assert (b["ikisi_de"], b["yalniz_ti1"], b["yalniz_birlesik"], b["hicbiri"]) == (0.25, 0.25, 0.25, 0.25)
    assert b["ti1_sapmasi"] == 2
    assert (b["sapmadan_once_birlesik_riskli_orani"], b["sapmadan_sonra_birlesik_riskli_orani"]) == (0.5, 0.5)
    assert "birlesik" not in uo.ozetle([{k: v for k, v in kayitlar[0].items() if "birlesik" not in k}])
