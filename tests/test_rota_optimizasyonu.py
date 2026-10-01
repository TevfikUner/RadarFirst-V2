"""
test_rota_optimizasyonu.py
-----------------------------
rota_optimizasyonu.py için birim testleri:
  - Küresel geometri (büyük daire mesafesi/rotası) doğruluğu.
  - ERA5 kapsam dışı durumda dürüst geri düşüş davranışı (bu test .nc
    dosyası olsun/olmasın çalışır -- New York, projenin veri küpünün
    kapsadığı Türkiye/Doğu Akdeniz bölgesinin kesinlikle dışındadır).
  - Gerçek ERA5 verisiyle uçtan uca simülasyon + CZML üretimi (sadece
    'ocak_2019_turbulans.nc' bulunursa çalışır, yoksa atlanır -- bkz.
    test_eslestirme.py'deki aynı desen).
"""

import json

import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.rota.rota_optimizasyonu import (
    CO2_KG_PER_KG_YAKIT,
    buyuk_daire_mesafesi_km,
    buyuk_daire_rotasi_olustur,
    rota_simulasyonu_olustur,
    simulasyonu_czml_e_cevir,
)

xr = pytest.importorskip("xarray")


def test_istanbul_ankara_mesafesi_gercek_degere_yakin():
    # Gerçek büyük daire mesafesi ~351 km'dir (kamuya açık kaynaklarla doğrulanabilir).
    mesafe = buyuk_daire_mesafesi_km(41.0, 28.9, 39.9, 32.8)
    assert 340 < mesafe < 360


def test_ayni_baslangic_bitis_hata_verir():
    with pytest.raises(ValueError):
        buyuk_daire_rotasi_olustur(41.0, 28.9, 41.0, 28.9, 10)


def test_buyuk_daire_rotasi_uclari_dogru_baslar_biter():
    enlemler, boylamlar = buyuk_daire_rotasi_olustur(41.0, 28.9, 37.0, 35.3, 21)
    assert enlemler[0] == pytest.approx(41.0)
    assert boylamlar[0] == pytest.approx(28.9)
    assert enlemler[-1] == pytest.approx(37.0)
    assert boylamlar[-1] == pytest.approx(35.3)
    assert len(enlemler) == 21


def test_bilinmeyen_ucak_modeli_hata_verir():
    with pytest.raises(ValueError):
        rota_simulasyonu_olustur(41.0, 28.9, 37.0, 35.3, 34000, "2019-01-15T10:00:00", "UCAK_YOK")


def test_co2_yakitla_dogru_orantili():
    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 40.7, -74.0, 34000, "2019-01-15T10:00:00", "A320")
    beklenen_co2 = sonuc["normal_rota"]["tahmini_yakit_kg"] * CO2_KG_PER_KG_YAKIT
    assert sonuc["normal_rota"]["tahmini_co2_kg"] == pytest.approx(beklenen_co2)
    assert sonuc["co2_farki_kg"] == pytest.approx(
        sonuc["normal_rota"]["tahmini_co2_kg"] - sonuc["optimize_rota"]["tahmini_co2_kg"]
    )


def test_kapsam_disi_bolge_durustce_ruzgarsiz_sonuc_doner():
    # New York, projenin ERA5 küpünün kapsadığı bölgenin (enlem 36-42,
    # boylam 26-45) kesinlikle dışında -- .nc dosyası bu ortamda bulunsun/
    # bulunmasın sonuç aynı olmalı.
    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 40.7, -74.0, 34000, "2019-01-15T10:00:00", "A320")
    assert sonuc["ruzgar_verisi_kaynagi"] == "era5_kapsam_disi"
    assert sonuc["yakit_tasarrufu_yuzde"] == 0.0
    assert sonuc["optimize_rota"]["toplam_sure_dk"] == sonuc["normal_rota"]["toplam_sure_dk"]
    assert sonuc["normal_rota"]["mesafe_km"] > 8000  # İstanbul-New York büyük daire mesafesi ~8065 km


def test_ti1_guvenilirlik_notu_her_yanitta_bulunur():
    """Madde 6 (bkz. konuşma geçmişi): TI1 bağımsız olarak doğrulanmadığı için
    bu not, kapsam içi/dışı fark etmeksizin HER rota yanıtında bulunmalı."""
    from turbulans_radar.fizik.turbulans_indeksleri import TI1_GUVENILIRLIK_NOTU

    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 40.7, -74.0, 34000, "2019-01-15T10:00:00", "A320")
    assert sonuc["ti1_guvenilirlik_notu"] == TI1_GUVENILIRLIK_NOTU
    assert "KANITLANMAMIŞTIR" in sonuc["ti1_guvenilirlik_notu"]


@pytest.fixture(scope="module")
def veri_kupu_mevcut_mu():
    try:
        xr.open_dataset(config.HAVA_DURUMU_DOSYASI).close()
        return True
    except FileNotFoundError:
        return False


def test_gercek_era5_turbulans_yoksa_optimize_normalle_birebir_ayni(veri_kupu_mevcut_mu):
    if not veri_kupu_mevcut_mu:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı, gerçek veri gerektiren test atlanıyor.")

    # İzmir -> Van, 31 Ocak 2019: bu rotada gerçek ERA5 verisiyle riskli
    # türbülans tespit EDİLMİYOR -- bu durumda optimize rota, kullanıcıyla
    # netleştirilen ilkeyle, uydurma bir sapma göstermeden normal rotayla
    # BİREBİR AYNI olmalı (aynı koordinatlar, aynı süre/yakıt).
    sonuc = rota_simulasyonu_olustur(38.4, 27.1, 38.5, 43.4, 34000, "2019-01-31T00:00:00", "A320")
    assert sonuc["ruzgar_verisi_kaynagi"] == "era5_gercek"
    assert sonuc["normal_rota"]["riskli_nokta_sayisi"] == 0
    assert sonuc["turbulanstan_kacinildi_mi"] is False
    assert sonuc["optimize_rota"]["noktalar"] == sonuc["normal_rota"]["noktalar"]
    assert sonuc["yakit_tasarrufu_yuzde"] == 0.0


def test_gercek_era5_turbulans_varsa_tamamen_atlatilir(veri_kupu_mevcut_mu):
    if not veri_kupu_mevcut_mu:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı, gerçek veri gerektiren test atlanıyor.")

    # İstanbul -> Antalya, 5 Ocak 2019, 28000ft: normal rotada TAM OLARAK 1
    # riskli TI1 noktası var ve denenen adaylardan biri onu tamamen atlatıyor
    # (gerçek ERA5 verisiyle doğrulandı, bkz. konuşma geçmişi).
    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 36.9, 30.7, 28000, "2019-01-05T12:00:00", "A320")
    assert sonuc["ruzgar_verisi_kaynagi"] == "era5_gercek"
    assert sonuc["normal_rota"]["riskli_nokta_sayisi"] > 0
    assert sonuc["optimize_rota"]["riskli_nokta_sayisi"] == 0
    assert sonuc["turbulanstan_kacinildi_mi"] is True
    # Güvenlik için rota değişti -- bu bazen yakıt/süre AÇISINDAN PAHALI
    # olabilir (gerçek dünyada da türbülanstan kaçış fazladan yakıt yakar);
    # "optimize rota her zaman ucuzdur" diye YANLIŞ bir varsayım yapılmaz.
    assert sonuc["optimize_rota"]["noktalar"] != sonuc["normal_rota"]["noktalar"]
    # Çok faktörlü karşılaştırma (yanal A* vs irtifa değişimi) gerçek
    # ERA5 verisiyle bu rotada İRTİFA stratejisinin (tırmanma) daha ucuz
    # olduğunu buluyor -- bkz. konuşma geçmişi (yanal: -%7.1, irtifa: -%2.7).
    assert sonuc["kacinma_stratejisi"] in ("yanal", "irtifa_yukari", "irtifa_asagi")
    if sonuc["kacinma_stratejisi"] != "yanal":
        assert sonuc["optimize_rota"]["irtifa_ft"] != sonuc["normal_rota"]["irtifa_ft"]


def test_irtifa_degisimi_maliyeti_tirmanma_pahali_alcalma_ucuz():
    from turbulans_radar.rota.rota_optimizasyonu import _irtifa_degisimi_maliyeti

    tirmanma_saniye, tirmanma_ek_yakit = _irtifa_degisimi_maliyeti(9000.0, 10000.0, 2400.0)
    alcalma_saniye, alcalma_ek_yakit = _irtifa_degisimi_maliyeti(10000.0, 9000.0, 2400.0)

    assert tirmanma_saniye > 0 and alcalma_saniye > 0
    assert tirmanma_ek_yakit > 0  # tırmanma EKSTRA yakıt gerektirir
    assert alcalma_ek_yakit < 0  # alçalma yakıt TASARRUFU sağlar
    assert _irtifa_degisimi_maliyeti(9000.0, 9000.0, 2400.0) == (0.0, 0.0)


def test_gercek_era5_kismi_atlatma_durustce_raporlanir(veri_kupu_mevcut_mu):
    if not veri_kupu_mevcut_mu:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı, gerçek veri gerektiren test atlanıyor.")

    # İstanbul -> Antalya, 1 Ocak 2019, 34000ft: normal rotada 5 riskli nokta
    # var ve denenen hiçbir aday riski TAMAMEN ortadan kaldıramıyor (gerçek
    # ERA5 verisiyle doğrulandı) -- yine de riski azaltan aday dürüstçe
    # seçilmeli, "tamamen güvenli" diye YALAN söylenmemeli.
    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 36.9, 30.7, 34000, "2019-01-01T06:00:00", "A320")
    assert sonuc["ruzgar_verisi_kaynagi"] == "era5_gercek"
    assert sonuc["normal_rota"]["riskli_nokta_sayisi"] > 0
    assert 0 < sonuc["optimize_rota"]["riskli_nokta_sayisi"] < sonuc["normal_rota"]["riskli_nokta_sayisi"]
    assert sonuc["turbulanstan_kacinildi_mi"] is True


def test_gercek_era5_ile_czml_yapisi_gecerli(veri_kupu_mevcut_mu):
    if not veri_kupu_mevcut_mu:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı, gerçek veri gerektiren test atlanıyor.")

    sonuc = rota_simulasyonu_olustur(38.4, 27.1, 38.5, 43.4, 34000, "2019-01-31T00:00:00", "B738")
    czml = simulasyonu_czml_e_cevir(sonuc)

    assert czml[0]["id"] == "document"
    assert "clock" in czml[0]

    ucak_varliklari = [v for v in czml[1:] if "model" in v]
    on_izleme_varliklari = [v for v in czml[1:] if "polyline" in v]
    assert len(ucak_varliklari) == 2
    assert len(on_izleme_varliklari) == 2

    for varlik in ucak_varliklari:
        assert varlik["model"]["gltf"] == "/harita/models/ucak.glb"
        konumlar = varlik["position"]["cartographicDegrees"]
        assert len(konumlar) % 4 == 0
        assert len(konumlar) // 4 == config.ROTA_SIMULASYONU_NOKTA_SAYISI

    for varlik in on_izleme_varliklari:
        duz_koordinatlar = varlik["polyline"]["positions"]["cartographicDegrees"]
        assert len(duz_koordinatlar) % 3 == 0
        assert len(duz_koordinatlar) // 3 == config.ROTA_SIMULASYONU_NOKTA_SAYISI


# --- SIGMET sert kısıtı (risk_katmanlari.SigmetKisitKatmani) ---


def _kare_sigmet(enlem0, enlem1, boylam0, boylam1, taban=None, tavan=45000, gun="2019-01-31"):
    baslangic = pd.Timestamp(gun, tz="UTC") - pd.Timedelta(days=1)
    return {
        "id": 99,
        "fir_kodu": "LTAA",
        "tehlike": "TURB",
        "taban_ft": taban,
        "tavan_ft": tavan,
        "gecerlilik_baslangic": baslangic,
        "gecerlilik_bitis": baslangic + pd.Timedelta(days=2),
        "poligon": [[boylam0, enlem0], [boylam1, enlem0], [boylam1, enlem1], [boylam0, enlem1], [boylam0, enlem0]],
    }


def _izmir_van(sigmetler):
    return rota_simulasyonu_olustur(38.4, 27.1, 38.5, 43.4, 34000, "2019-01-31T00:00:00", "A320", sigmetler=sigmetler)


def test_rota_ortasindaki_sigmetten_yanal_sapmayla_kacinilir(veri_kupu_mevcut_mu):
    if not veri_kupu_mevcut_mu:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı, gerçek veri gerektiren test atlanıyor.")
    sonuc = _izmir_van([_kare_sigmet(38.2, 39.6, 34.5, 35.5)])
    assert sonuc["sigmet_kontrolu"]["durum"] == "uygulandi"
    assert sonuc["normal_rota"]["sigmet_ihlali_sayisi"] > 0
    assert sonuc["optimize_rota"]["sigmet_ihlali_sayisi"] == 0
    assert sonuc["guvenli_rota_bulundu_mu"] is True
    assert sonuc["sigmetten_kacinildi_mi"] is True
    assert sonuc["kacinma_stratejisi"] == "yanal"
    assert sonuc["optimize_rota"]["maks_yanal_sapma_km"] > 0


def test_baslangic_sigmet_icindeyse_rota_onerilmez():
    sonuc = _izmir_van([_kare_sigmet(37.9, 38.9, 26.6, 27.6)])
    assert sonuc["guvenli_rota_bulundu_mu"] is False
    assert sonuc["optimize_rota"]["noktalar"] == sonuc["normal_rota"]["noktalar"]
    assert "ÖNERİ YOK" in sonuc["aciklama"]
    bulgular = {b["kod"]: b for b in sonuc["bulgular"]}
    assert bulgular["guvenli_rota_yok"]["seviye"] == "kritik"
    assert bulgular["sigmet_uygulandi"]["parametreler"]["normal_rota_ihlali"] > 0


def test_bulgular_aciklama_ile_ayni_siradadir_ve_metin_tasimaz():
    sigmet = _kare_sigmet(4.3, 5.9, 17.0, 18.0, gun="2019-01-15")
    sonuc = rota_simulasyonu_olustur(5.0, 10.0, 5.0, 25.0, 36000, "2019-01-15T00:00:00", "A320", sigmetler=[sigmet])
    kodlar = [b["kod"] for b in sonuc["bulgular"]]
    assert kodlar[0] == "ruzgar_hesaba_katilamadi"
    assert sonuc["bulgular"][0]["parametreler"] == {"neden": "kapsam_disi"}
    assert "sigmet_uygulandi" in kodlar
    assert kodlar[-1] == "kacinma_sert_kisit"
    assert all(set(b) == {"kod", "seviye", "parametreler"} for b in sonuc["bulgular"])
    assert all(b["seviye"] in ("bilgi", "uyari", "kritik") for b in sonuc["bulgular"])


def test_ucusun_irtifa_bandi_disindaki_sigmet_rotayi_degistirmez():
    sonuc = _izmir_van([_kare_sigmet(38.2, 39.6, 34.5, 35.5, taban=10000, tavan=25000)])
    assert sonuc["normal_rota"]["sigmet_ihlali_sayisi"] == 0
    assert sonuc["optimize_rota"]["noktalar"] == sonuc["normal_rota"]["noktalar"]


def test_hava_verisi_olmayan_bolgede_de_sigmetten_kacinilir():
    sigmet = _kare_sigmet(4.3, 5.9, 17.0, 18.0, gun="2019-01-15")
    sonuc = rota_simulasyonu_olustur(5.0, 10.0, 5.0, 25.0, 36000, "2019-01-15T00:00:00", "A320", sigmetler=[sigmet])
    assert sonuc["ruzgar_verisi_kaynagi"] == "era5_kapsam_disi"
    assert sonuc["sigmetten_kacinildi_mi"] is True
    assert sonuc["optimize_rota"]["sigmet_ihlali_sayisi"] == 0

    sigmet_varliklari = [v for v in simulasyonu_czml_e_cevir(sonuc) if "polygon" in v]
    assert [v["id"] for v in sigmet_varliklari] == ["sigmet-99"]
    assert sigmet_varliklari[0]["polygon"]["extrudedHeight"] == pytest.approx(45000 * 0.3048)


# --- Kısıtlı hava sahası sert kısıtı (risk_katmanlari.KisitliSahaKatmani) ---


def _ornek_sahalar():
    from turbulans_radar.veri.kisitli_saha_saglayici import ORNEK_DOSYA, ORNEK_KAYNAK, geojson_kayitlarina_cevir

    return geojson_kayitlarina_cevir(json.loads(ORNEK_DOSYA.read_text(encoding="utf-8")), ORNEK_KAYNAK)


def _kare_saha(enlem0, enlem1, boylam0, boylam1, taban=None, tavan=None):
    return {
        "id": 7,
        "ad": "Deneme sahası",
        "tur": "YASAK",
        "kaynak": "test",
        "taban_ft": taban,
        "tavan_ft": tavan,
        "gecerlilik_baslangic": None,
        "gecerlilik_bitis": None,
        "poligon": [[boylam0, enlem0], [boylam1, enlem0], [boylam1, enlem1], [boylam0, enlem1], [boylam0, enlem0]],
    }


def _afrika_rotasi(kisitli_sahalar):
    return rota_simulasyonu_olustur(
        5.0, 10.0, 5.0, 25.0, 36000, "2019-01-15T00:00:00", "A320", sigmetler=[], kisitli_sahalar=kisitli_sahalar
    )


def test_malatya_musul_rotasi_suriyeden_kacinir_varis_ulkesi_muaf_tutulur():
    sonuc = rota_simulasyonu_olustur(
        38.435,
        38.091,
        36.306,
        43.147,
        34000,
        "2019-06-15T08:00:00",
        "A320",
        sigmetler=[],
        kisitli_sahalar=_ornek_sahalar(),
    )
    kontrol = sonuc["kisitli_saha_kontrolu"]
    assert kontrol["durum"] == "uygulandi" and kontrol["ornek_veri_mi"] is True
    assert kontrol["muaf_tutulanlar"] == ["Irak hava sahası (örnek çatışma bölgesi)"]
    assert sonuc["normal_rota"]["kisitli_saha_ihlali_sayisi"] > 0
    assert sonuc["optimize_rota"]["kisitli_saha_ihlali_sayisi"] == 0
    assert sonuc["kisitli_sahadan_kacinildi_mi"] is True and sonuc["guvenli_rota_bulundu_mu"] is True
    assert "ÖRNEK" in sonuc["aciklama"]
    saha_varliklari = [v for v in simulasyonu_czml_e_cevir(sonuc) if v["id"].startswith("kisitli-saha-")]
    assert saha_varliklari and all("availability" not in v for v in saha_varliklari)
    assert any("koridoru hariç" in v["name"] for v in saha_varliklari)


def test_varis_ulkesinde_planli_rota_koridoru_disina_sapilmaz():
    """Varış noktasını içeren saha tamamen muaf değil: koridor dışı yine yasak."""
    saha = _kare_saha(0.0, 10.0, 20.0, 30.0)
    sonuc = rota_simulasyonu_olustur(
        5.0, 10.0, 5.0, 25.0, 36000, "2019-01-15T00:00:00", "A320", sigmetler=[], kisitli_sahalar=[saha]
    )
    assert sonuc["kisitli_saha_kontrolu"]["muaf_tutulanlar"] == ["Deneme sahası"]
    assert sonuc["normal_rota"]["kisitli_saha_ihlali_sayisi"] == 0

    from turbulans_radar.rota.risk_katmanlari import KisitliSahaKatmani

    kalan = [s for s in sonuc["kisitli_saha_kontrolu"]["sahalar"]]
    katman = KisitliSahaKatmani(kalan)
    zaman = [pd.Timestamp("2019-01-15T03:00:00", tz="UTC")]
    assert katman.rota_ihlal_sayisi([5.3], [24.0], zaman, 11000.0) == 0
    assert katman.rota_ihlal_sayisi([8.0], [24.0], zaman, 11000.0) == 1


def test_koridoru_tamamen_kesen_kisitli_saha_varsa_rota_onerilmez():
    sonuc = _afrika_rotasi([_kare_saha(-5.0, 15.0, 17.0, 18.0)])
    assert sonuc["guvenli_rota_bulundu_mu"] is False
    assert "ÖNERİ YOK" in sonuc["aciklama"] and "kısıtlı hava sahalarına" in sonuc["aciklama"]


def test_irtifa_bandi_disindaki_kisitli_saha_rotayi_degistirmez():
    sonuc = _afrika_rotasi([_kare_saha(4.3, 5.9, 17.0, 18.0, taban=0, tavan=20000)])
    assert sonuc["normal_rota"]["kisitli_saha_ihlali_sayisi"] == 0
    assert sonuc["optimize_rota"]["noktalar"] == sonuc["normal_rota"]["noktalar"]


def test_kisitli_saha_veritabanina_erisilemezse_uyari_verilir(monkeypatch):
    from turbulans_radar.rota import rota_optimizasyonu

    def erisilemez(*args, **kwargs):
        raise ConnectionError("veritabanı yok")

    monkeypatch.setattr(rota_optimizasyonu, "gecerli_kisitli_sahalari_getir", erisilemez)
    sonuc = _afrika_rotasi(None)
    assert sonuc["kisitli_saha_kontrolu"]["durum"] == "erisilemedi"
    assert "saha kontrolü YAPILAMADI" in sonuc["aciklama"]


# --- Yanal ızgara: sınırlar adım sayısıyla değil mesafe ve açıyla ---


@pytest.mark.parametrize(
    "rota",
    [(41.0, 28.9, 36.9, 30.7), (38.4, 27.1, 38.5, 43.4), (41.0, 28.9, 40.7, -74.0)],
    ids=["istanbul_antalya_480km", "izmir_van_1400km", "istanbul_new_york_8000km"],
)
def test_izgaradaki_hicbir_bacak_sapma_acisi_sinirini_asmaz(rota):
    from turbulans_radar.rota import rota_optimizasyonu as ro

    enlemler, boylamlar = buyuk_daire_rotasi_olustur(*rota, config.ROTA_SIMULASYONU_NOKTA_SAYISI)
    izgara = ro._yanal_izgara_olustur(enlemler, boylamlar)
    konumlar = ro._yanal_izgara_dugum_konumlari(enlemler, boylamlar, izgara)
    en_dik = 0.0
    for dugum in konumlar:
        i = dugum[0]
        for komsu in ro._komsu_dugumler(dugum, izgara):
            rota_yonu = ro._ilk_yon_derece(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
            bacak_yonu = ro._ilk_yon_derece(*konumlar[dugum], *konumlar[komsu])
            en_dik = max(en_dik, abs((bacak_yonu - rota_yonu + 180.0) % 360.0 - 180.0))
    assert config.ROTA_MAKS_SAPMA_ACISI_DERECE * 0.8 < en_dik <= config.ROTA_MAKS_SAPMA_ACISI_DERECE + 1.0


def test_uzun_rotada_sapma_koridoru_mesafeyle_olceklenir_ve_sigmet_zincirinden_kacilir():
    from turbulans_radar.rota import rota_optimizasyonu as ro

    enlemler, boylamlar = buyuk_daire_rotasi_olustur(41.0, 28.9, 40.7, -74.0, config.ROTA_SIMULASYONU_NOKTA_SAYISI)
    izgara = ro._yanal_izgara_olustur(enlemler, boylamlar)
    # Eski sabit 20 km/adım ızgarada kalkıştan ~600 km sonra (i=3) en fazla 60 km sapılabiliyordu.
    assert izgara.zarf(3) * izgara.aralik_km >= 300.0
    sigmetler = [
        _kare_sigmet(enlemler[i] - 1, enlemler[i] + 1, boylamlar[i] - 1, boylamlar[i] + 1, gun="2019-01-15")
        for i in range(3, 38, 2)
    ]
    sonuc = rota_simulasyonu_olustur(
        41.0, 28.9, 40.7, -74.0, 34000, "2019-01-15T00:00:00", "A320", sigmetler=sigmetler, kisitli_sahalar=[]
    )
    assert sonuc["normal_rota"]["sigmet_ihlali_sayisi"] > 0
    assert sonuc["guvenli_rota_bulundu_mu"] is True
    assert sonuc["optimize_rota"]["sigmet_ihlali_sayisi"] == 0
    assert 0 < sonuc["optimize_rota"]["maks_yanal_sapma_km"] <= config.ROTA_MAKS_YANAL_SAPMA_KM


def test_a_yildiz_nominal_zamandan_sonra_baslayan_sigmetten_de_kacinir():
    """Rüzgarsız nominal zamanda henüz başlamamış ama gerçek (rüzgarlı) varışta
    aktif olabilecek SIGMET: A* belirsizlik payıyla ondan da kaçınmalı."""
    from turbulans_radar.rota import rota_optimizasyonu as ro
    from turbulans_radar.rota.risk_katmanlari import SigmetKisitKatmani

    enlemler, boylamlar = buyuk_daire_rotasi_olustur(5.0, 10.0, 5.0, 25.0, config.ROTA_SIMULASYONU_NOKTA_SAYISI)
    kalkis = pd.Timestamp("2019-01-15T00:00:00", tz="UTC")
    orta_varis = kalkis + pd.Timedelta(seconds=ro.buyuk_daire_mesafesi_km(5.0, 10.0, 5.0, 17.5) * 1000 / 230.0)
    sigmet = {
        **_kare_sigmet(4.3, 5.9, 17.0, 18.0, gun="2019-01-15"),
        "gecerlilik_baslangic": orta_varis + pd.Timedelta(minutes=15),
    }
    yol = ro._a_yildiz_ile_rota_ara(
        enlemler, boylamlar, 36000 * 0.3048, kalkis.isoformat(), 230.0, None, [SigmetKisitKatmani([sigmet])]
    )
    assert yol is not None and yol[2] > 0


def test_km_boylam_derecesine_cevir_yuksek_enlemde_daralmiyor():
    """Düz bir derece tamponu (km / 111.2) yüksek enlemde gerçek km'yi
    olduğundan dar gösterirdi (60°K'de "100 km" tamponu doğu-batı yönünde
    gerçekte sadece ~50 km'ye karşılık gelirdi, cos(enlem) küçüldüğü için)."""
    from turbulans_radar.rota.rota_optimizasyonu import (
        _KM_PER_DERECE_ENLEM,
        _km_boylam_derecesine_cevir,
        buyuk_daire_mesafesi_km,
    )

    for enlem in (0.0, 38.0, 60.0, -60.0, 74.0):
        derece = _km_boylam_derecesine_cevir(100.0, [enlem])
        gercek_km = buyuk_daire_mesafesi_km(enlem, 0.0, enlem, derece)
        assert gercek_km == pytest.approx(100.0, rel=0.02)

    # 75°'nin ötesinde kasıtlı olarak 75°'de kelepçelenir (kutba yakın patlamayı
    # önlemek için); bu yüzden 80°'de gerçek km hedefin altında kalır.
    assert _km_boylam_derecesine_cevir(100.0, [80.0]) == _km_boylam_derecesine_cevir(100.0, [75.0])

    # Kelepçelenmemiş düz yöntemle (eski davranış) karşılaştır: 60°K'de belirgin fark olmalı.
    duz_derece = 100.0 / _KM_PER_DERECE_ENLEM
    duz_gercek_km = buyuk_daire_mesafesi_km(60.0, 0.0, 60.0, duz_derece)
    assert duz_gercek_km < 60.0


def test_kisitli_saha_koridoru_yuksek_enlemde_hedeflenen_genisligi_korur():
    """Malatya-Musul testinin (38°K) aksine, yüksek enlemde bir rotada
    koridor genişliği düzeltilmeden ölçülürse hedeflenen km'nin çok altında
    kalırdı (bkz. test_km_boylam_derecesine_cevir_yuksek_enlemde_daralmiyor)."""
    saha = _kare_saha(55.0, 65.0, -10.0, 30.0)  # kalkış noktasını içeren büyük bir saha
    sonuc = rota_simulasyonu_olustur(
        60.0, 10.0, 60.0, 20.0, 34000, "2019-01-15T00:00:00", "A320", sigmetler=[], kisitli_sahalar=[saha]
    )
    kontrol = sonuc["kisitli_saha_kontrolu"]
    assert kontrol["muaf_tutulanlar"] == ["Deneme sahası"]
    # Kalan (kısıt uygulanan) geometri var olmalı ve tüm sahayı değil, sadece
    # koridorun DIŞINDAKİ kısmı kapsamalı (aksi halde koridor sıfıra yakın
    # daralmış demektir).
    (kalan_saha,) = kontrol["sahalar"]
    assert "koridoru hariç" in kalan_saha["ad"]


# --- Kapsam ve planlama ufku (hoca geri bildirimi, öneri 3 ve 5) ---


def test_sigmet_yayin_ufku_kismi_ve_tam(monkeypatch):
    from turbulans_radar.rota.rota_optimizasyonu import sigmet_ufku

    monkeypatch.setattr(config, "SIGMET_YAYIN_UFKU_SAAT", 4.0)
    simdi = pd.Timestamp("2026-10-02T00:00Z")
    saat = pd.Timedelta(hours=1)
    assert sigmet_ufku(simdi + saat, simdi + 3 * saat, simdi)["yayin_ufku_disi"] == "yok"
    assert sigmet_ufku(simdi + 2 * saat, simdi + 6 * saat, simdi)["yayin_ufku_disi"] == "kismi"
    assert sigmet_ufku(simdi + 5 * saat, simdi + 8 * saat, simdi)["yayin_ufku_disi"] == "tam"


def test_planlama_ufku_gecmis_ve_gelecek_uculari_ayirir():
    from turbulans_radar.rota.rota_optimizasyonu import planlama_ufku

    simdi = pd.Timestamp("2026-10-02T00:00Z")
    assert planlama_ufku("2019-01-15T20:00:00", simdi)["kullanim"] == "gecmis_analiz"
    ileri = planlama_ufku("2026-10-02T06:00:00", simdi)
    assert ileri["kullanim"] == "ucus_oncesi_planlama" and ileri["kalkisa_kalan_saat"] == 6.0
    assert not ileri["tahmin_ufku_disi"]
    assert planlama_ufku("2026-10-10T00:00:00", simdi)["tahmin_ufku_disi"]


def test_ileri_tarihli_ucusta_sigmet_ufku_uyarisi_ve_kapsam(monkeypatch):
    monkeypatch.setattr(config, "CANLI_HAVA_VERISI_ETKIN", False)
    monkeypatch.setattr(config, "ERA5_OTOMATIK_INDIRME", False)
    zaman = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%S")
    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 39.9, 32.8, 36000, zaman, "A320", sigmetler=[], kisitli_sahalar=[])
    kodlar = {b["kod"]: b for b in sonuc["bulgular"]}
    assert kodlar["sigmet_ufuk_disi"]["parametreler"]["kisim"] == "tam"
    assert sonuc["sigmet_kontrolu"]["yayin_ufku_disi"] == "tam"
    assert sonuc["kapsam"]["safha"] == "seyir"
    assert sonuc["planlama_ufku"]["kullanim"] == "ucus_oncesi_planlama"


def test_gecmis_tarihli_ucusta_sigmet_ufku_uyarisi_yok():
    sonuc = rota_simulasyonu_olustur(
        40.7, -74.0, 42.3, -71.0, 34000, "2019-01-15T10:00:00", "A320", sigmetler=[], kisitli_sahalar=[]
    )
    assert "sigmet_ufuk_disi" not in {b["kod"] for b in sonuc["bulgular"]}
    assert sonuc["planlama_ufku"]["kullanim"] == "gecmis_analiz"
