import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.dogrulama import bagimsiz_backtest as bb

pytestmark = pytest.mark.birim


def _ham(satirlar):
    return pd.DataFrame(satirlar, columns=["VALID", "REPORT", "TURBULENCE", "FL", "LAT", "LON"])


def _pirepler():
    return pd.DataFrame(
        {
            "zaman": pd.to_datetime(["2018-01-13T15:20Z", "2018-01-13T15:30Z", "2018-01-13T15:40Z"], utc=True),
            "enlem": [42.0, 42.0, 43.5],
            "boylam": [-75.0, -74.0, -75.0],
            "irtifa_ft": [34000.0, 34000.0, 34000.0],
            "sinif": [1, 0, 1],
            "net": [1.0, 0.0, None],
        }
    )


def _rota(enlem, irtifa_ft=34000.0):
    zamanlar = pd.date_range("2018-01-13T15:00Z", periods=6, freq="10min")
    return {
        "noktalar": [
            {"enlem": enlem, "boylam": b, "zaman": z.isoformat(), "irtifa_m": irtifa_ft * 0.3048}
            for b, z in zip([-77.0, -76.0, -75.0, -74.0, -73.0, -72.0], zamanlar, strict=True)
        ],
        "riskli_nokta_sayisi": 0,
        "fl": int(irtifa_ft // 100),
    }


def _sonuc(bd_enlem=42.0, astar_enlem=43.5, strateji="yanal", veri="era5_gercek"):
    return {
        "ruzgar_verisi_kaynagi": veri,
        "kacinma_stratejisi": strateji,
        "normal_rota": {**_rota(bd_enlem), "riskli_nokta_sayisi": 4},
        "optimize_rota": _rota(astar_enlem),
    }


def test_senaryolar_gun_saat_cift_ve_seviye_carpimidir():
    senaryolar = list(bb.senaryolari_uret(["2018-01-12", "2018-01-13"], (12, 18), (34000,), bb.SEHIR_CIFTLERI[:2]))
    assert len(senaryolar) == 2 * 2 * 2
    assert senaryolar[0] == ("JFK→YUL", (40.64, -73.78, 45.47, -73.74, 34000, "2018-01-12T12:00:00"))
    assert senaryolar[-1][1][5] == "2018-01-13T18:00:00"


def test_sehir_ciftleri_kup_kutusunun_icindedir():
    enlem_min, enlem_maks, boylam_min, boylam_maks = bb.KUTU
    for _, *koordinatlar in bb.SEHIR_CIFTLERI:
        for enlem, boylam in (koordinatlar[:2], koordinatlar[2:]):
            assert enlem_min < enlem < enlem_maks and boylam_min < boylam < boylam_maks


def test_pirep_hazirlama_kutu_irtifa_gun_unk_ve_yinelenenleri_eler():
    ham = _ham(
        [
            ["201801131500", "BOS UA /OV BOS/TB MOD", "MOD", "34000", "42.0", "-71.5"],
            ["201801131500", "BOS UA /OV BOS/TB MOD", "MOD", "34000", "42.0", "-71.5"],
            ["201801131500", "X UA /OV UNK/TB MOD", "MOD", "34000", "42.0", "-71.5"],
            ["201801131500", "BOS UA /OV BOS/TB NEG", "NEG", "36000", "43.0", "-72.0"],
            ["201801131500", "BOS UA /OV BOS/TB LGT", "LGT", "36000", "43.0", "-72.5"],
            ["201801131500", "LAX UA /OV LAX/TB MOD", "MOD", "34000", "34.0", "-118.0"],
            ["201801131500", "BOS UA /OV BOS/TB MOD", "MOD", "300", "42.0", "-71.5"],
            ["201801140100", "BOS UA /OV BOS/TB MOD", "MOD", "34000", "42.0", "-71.5"],
            ["201801131500", "BOS UA /OV BOS/IC LGT", "None", "34000", "42.0", "-71.5"],
        ]
    )
    df = bb.pirepleri_hazirla(ham, gunler=["2018-01-13"])
    assert list(df["sinif"]) == [1, 0, 0]
    assert list(df["net"].fillna(-1)) == [1, 0, -1]


def test_kayit_tupleri_ve_fark_tupunu_ayri_sayar():
    kayit = bb.kaydi_cikar("X→Y", (42.0, -77.0, 42.0, -72.0, 34000, "2018-01-13T15:00:00"), _sonuc(), _pirepler())
    assert (kayit["bd_proje_m"], kayit["bd_proje_n"]) == (1, 1)
    assert (kayit["astar_proje_m"], kayit["astar_proje_n"]) == (1, 0)
    assert (kayit["kacinilan_proje_m"], kayit["kacinilan_proje_n"]) == (1, 1)
    assert (kayit["girilen_proje_m"], kayit["girilen_proje_n"]) == (1, 0)
    assert (kayit["bd_net_m"], kayit["bd_net_n"], kayit["astar_net_m"]) == (1, 1, 0)
    assert kayit["sapma"] and kayit["gun"] == "2018-01-13" and kayit["bd_riskli_nokta"] == 4


def test_tup_rotanin_kendi_irtifasini_kullanir():
    sonuc = _sonuc(astar_enlem=42.0)
    sonuc["optimize_rota"] = _rota(42.0, irtifa_ft=30000.0)
    kayit = bb.kaydi_cikar("X→Y", (42.0, -77.0, 42.0, -72.0, 34000, "2018-01-13T15:00:00"), sonuc, _pirepler())
    assert kayit["astar_proje_m"] + kayit["astar_proje_n"] == 0
    assert kayit["bd_proje_m"] + kayit["bd_proje_n"] == 2


def test_gmo_payda_sifirsa_none():
    assert bb.gmo((1, 1, 2, 1)) == pytest.approx(0.5)
    assert bb.gmo((1, 0, 2, 1)) is None
    assert bb.gmo((1, 1, 0, 1)) is None


def _kayit(gun, m_a, n_a, m_b, n_b, sapma=True, fl=340, strateji="yanal"):
    kayit = {"gun": gun, "sapma": sapma, "fl": fl, "strateji": strateji, "veri": "era5_gercek"}
    kayit.update(bd_riskli_nokta=3, astar_riskli_nokta=0)
    for etiket in bb.ETIKETLER:
        kayit.update({f"astar_{etiket}_m": m_a, f"astar_{etiket}_n": n_a, f"bd_{etiket}_m": m_b, f"bd_{etiket}_n": n_b})
        for rota in ("kacinilan", "girilen"):
            kayit.update({f"{rota}_{etiket}_m": 0, f"{rota}_{etiket}_n": 0})
    return kayit


def test_gmo_ozeti_gun_bloklu_bootstrap_ve_karar():
    kayitlar = [_kayit(f"2018-01-{g:02d}", 1, 4, 4, 1) for g in range(1, 11)]
    ozet = bb.gmo_ozeti(kayitlar, tekrar=200)
    assert ozet["gmo"] == pytest.approx((10 / 40) / (40 / 10))
    assert ozet["ga"][1] < 1.0 and ozet["gecersiz_tekrar"] == 0
    assert bb.karar_okumasi(ozet) == "azaltti"
    esit = bb.gmo_ozeti([_kayit(f"2018-01-{g:02d}", 2, 2, 2, 2) for g in range(1, 11)], tekrar=200)
    assert bb.karar_okumasi(esit) == "fark_gosterilemedi"
    az = bb.gmo_ozeti([_kayit("2018-01-01", 1, 1, 1, 1)], tekrar=50)
    assert bb.karar_okumasi(az) == "yetersiz_orneklem"


def test_ozet_bagimli_gunleri_ve_sapmasizlari_birincilden_cikarir():
    kayitlar = [_kayit(f"2018-01-{g:02d}", 1, 4, 4, 1) for g in range(1, 9)]
    kayitlar += [_kayit("2018-01-20", 9, 1, 1, 9), _kayit("2018-01-02", 5, 5, 5, 5, sapma=False)]
    kayitlar += [{"cift": "X", "fl": 340, "kalkis": "2018-01-03T12:00:00", "hata": "boom"}]
    kayitlar += [{**_kayit("2018-01-04", 1, 1, 1, 1), "veri": "era5_kapsam_disi"}]
    ozet = bb.ozetle(kayitlar, bagimli_gunler={"2018-01-20"})
    assert ozet["birincil"]["rota"] == 8 and ozet["birincil"]["gun"] == 8
    assert ozet["ikincil"]["tum_gunler_sapmali"]["rota"] == 9
    assert ozet["ikincil"]["tum_senaryolar"]["rota"] == 9
    assert (ozet["hata"], ozet["era5_disi_ya_da_risksiz"]) == (1, 1)
    rapor = {
        "ozet": ozet,
        "parametreler": {
            "ti1_esigi": 7e-7,
            "ciftler": bb.SEHIR_CIFTLERI,
            "gun_sayisi": 9,
            "saatler": [12],
            "fl": [340],
        },
        "uretim_zamani": "t",
        "commit": None,
    }
    assert "Bağımsız rota backtest" in bb.markdown_ozeti(rapor)


def test_olcum_canli_veriyi_ve_kurali_sabitler_hatayi_kaydeder():
    eski = (config.ERA5_OTOMATIK_INDIRME, config.CANLI_HAVA_VERISI_ETKIN, config.ROTA_SECIM_KURALI)
    gorulen = []

    def sahte(*girdi, **kw):
        gorulen.append((config.CANLI_HAVA_VERISI_ETKIN, config.ROTA_SECIM_KURALI, kw))
        if girdi[4] == 37000:
            raise RuntimeError("kapsam")
        return _sonuc()

    senaryolar = bb.senaryolari_uret(["2018-01-13"], (15,), (34000, 37000), bb.SEHIR_CIFTLERI[:1])
    kayitlar = bb.olcum_yap(senaryolar, _pirepler(), rota_fonksiyonu=sahte)
    assert gorulen[0][:2] == (False, "sozluksel") and gorulen[0][2] == {"sigmetler": [], "kisitli_sahalar": []}
    assert "hata" in kayitlar[1] and "hata" not in kayitlar[0]
    assert (config.ERA5_OTOMATIK_INDIRME, config.CANLI_HAVA_VERISI_ETKIN, config.ROTA_SECIM_KURALI) == eski


def test_sekil_yalniz_gecerli_satirlari_cizer(tmp_path):
    kayitlar = [_kayit(f"2018-01-{g:02d}", 1, 4, 4, 1) for g in range(1, 9)]
    rapor = {"ozet": bb.ozetle(kayitlar, bagimli_gunler=set())}
    yol = tmp_path / "sekil.png"
    bb.sekil_ciz(rapor, str(yol))
    assert yol.stat().st_size > 1000
    assert [s[0] for s in bb.sekil_satirlari(rapor["ozet"])][0].startswith("Birincil")
