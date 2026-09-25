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

import pytest

import config
from rota_optimizasyonu import (
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
    from rota_optimizasyonu import _irtifa_degisimi_maliyeti

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
