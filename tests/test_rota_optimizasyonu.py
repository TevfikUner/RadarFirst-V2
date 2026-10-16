"""
test_rota_optimizasyonu.py
-----------------------------
rota_optimizasyonu.py için birim testleri:
  - Küresel geometri (büyük daire mesafesi/rotası) doğruluğu.
  - ERA5 kapsam dışı durumda dürüst geri düşüş davranışı (bu test .nc
    dosyası olsun/olmasın çalışır -- New York, projenin veri küpünün
    kapsadığı Türkiye/Doğu Akdeniz bölgesinin kesinlikle dışındadır).
  - Gerçek ERA5 verisiyle uçtan uca simülasyon + CZML üretimi: depodaki
    demo küpüyle (THY322, 2019-01-15 18-23 UTC) her ortamda, yerel Ocak 2019
    küpü varsa onun senaryolarıyla da çalışır; atlanmaz (bkz. ci.yml).
"""

import json
import os

import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.rota.rota_optimizasyonu import (
    CO2_KG_PER_KG_YAKIT,
    buyuk_daire_mesafesi_km,
    buyuk_daire_rotasi_olustur,
    rota_simulasyonu_olustur,
    simulasyonu_czml_e_cevir,
    yanal_sapma_yonu,
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
    assert sonuc["normal_rota"]["riskli_nokta_sayisi"] is None
    assert sonuc["normal_rota"]["riskli_bolumler"] is None and sonuc["kabin_onerisi"] is None
    assert sonuc["brifing_karti"] == [
        "Rota: FL340; türbülans riski hesaplanamadı (era5_kapsam_disi).",
        "Kalan risk: hesaplanamadı.",
        "Kabin: ek öneri yok.",
    ]
    assert all(n["riskli"] is None for n in sonuc["normal_rota"]["noktalar"])


def test_ti1_guvenilirlik_notu_her_yanitta_bulunur():
    """Madde 6 (bkz. konuşma geçmişi): TI1 bağımsız olarak doğrulanmadığı için
    bu not, kapsam içi/dışı fark etmeksizin HER rota yanıtında bulunmalı."""
    from turbulans_radar.fizik.turbulans_indeksleri import TI1_GUVENILIRLIK_NOTU

    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 40.7, -74.0, 34000, "2019-01-15T10:00:00", "A320")
    assert sonuc["ti1_guvenilirlik_notu"] == TI1_GUVENILIRLIK_NOTU
    assert "KANITLANMAMIŞTIR" in sonuc["ti1_guvenilirlik_notu"]


# Her senaryo gerçek ERA5 verisiyle doğrulandı. "ana": yerel Ocak 2019 küpü;
# "demo": depodaki THY322 küpü (yalnızca o yüklenir). Seviyeler yarım daire
# kuralına uygun (hepsi doğu yönü: tek FL).
GERCEK_SENARYOLAR = {
    "ana": {
        "riskisiz": (38.4, 27.1, 38.5, 43.4, 35000, "2019-01-31T00:00:00"),
        "riskli": (40.9, 29.3, 40.6, 43.1, 35000, "2019-01-15T19:00:00"),
        "kismi": (41.0, 28.9, 36.9, 30.7, 31000, "2019-01-01T06:00:00"),
        "sigmet": ((38.2, 39.6, 34.5, 35.5), "2019-01-31"),
    },
    "demo": {
        "riskisiz": (41.0, 28.9, 40.1, 32.99, 37000, "2019-01-15T19:00:00"),
        "riskli": (40.9, 29.3, 40.6, 43.1, 35000, "2019-01-15T19:00:00"),
        "kismi": (41.0, 28.9, 39.9, 41.3, 31000, "2019-01-15T19:00:00"),
        "sigmet": ((40.2, 41.0, 30.6, 31.4), "2019-01-15"),
    },
}


@pytest.fixture(params=["demo"] + (["ana"] if os.path.isfile(config.HAVA_DURUMU_DOSYASI) else []))
def gercek_senaryo(request, monkeypatch, tmp_path):
    if request.param == "demo":
        monkeypatch.setattr(config, "HAVA_DURUMU_DOSYASI", str(tmp_path / "yok.nc"))
        monkeypatch.setattr(config, "EK_HAVA_DURUMU_KLASORU", "")
        monkeypatch.setattr(config, "ERA5_UCUS_KLASORU", "")
        monkeypatch.setattr(
            config, "DEMO_VERI_KLASORU", os.path.join(os.path.dirname(os.path.dirname(__file__)), "demo")
        )
        monkeypatch.setattr(config, "ERA5_OTOMATIK_INDIRME", False)
        monkeypatch.setattr(config, "CANLI_HAVA_VERISI_ETKIN", False)
    return GERCEK_SENARYOLAR[request.param]


def test_gercek_era5_turbulans_yoksa_optimize_normalle_birebir_ayni(gercek_senaryo):
    # "riskisiz" senaryo: rotada gerçek ERA5 verisiyle riskli
    # türbülans tespit EDİLMİYOR -- bu durumda optimize rota, kullanıcıyla
    # netleştirilen ilkeyle, uydurma bir sapma göstermeden normal rotayla
    # BİREBİR AYNI olmalı (aynı koordinatlar, aynı süre/yakıt).
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskisiz"], "A320")
    assert sonuc["ruzgar_verisi_kaynagi"] == "era5_gercek"
    assert sonuc["normal_rota"]["riskli_nokta_sayisi"] == 0
    assert sonuc["turbulanstan_kacinildi_mi"] is False
    assert sonuc["optimize_rota"]["noktalar"] == sonuc["normal_rota"]["noktalar"]
    assert sonuc["yakit_tasarrufu_yuzde"] == 0.0
    assert sonuc["optimize_rota"]["riskli_bolumler"] == [] and sonuc["kabin_onerisi"] is None
    assert sonuc["brifing_karti"][0].startswith("Rota: planlanan rota korunur")
    assert sonuc["brifing_karti"][1:] == ["Kalan risk: önerilen rotada riskli bölüm yok.", "Kabin: ek öneri yok."]


def test_gercek_era5_turbulans_varsa_tamamen_atlatilir(gercek_senaryo):
    # "riskli" senaryo: normal rotada riskli TI1 noktası var ve denenen
    # adaylardan biri onu tamamen atlatıyor (gerçek ERA5 verisiyle doğrulandı).
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskli"], "A320")
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


def test_referans_karsilastirmasi_kapsam_disinda_yok():
    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 40.7, -74.0, 34000, "2019-01-15T10:00:00", "A320")
    assert sonuc["referans_karsilastirmasi"] is None


def test_referans_karsilastirmasi_riskisizde_ruzgar_kazanci_var_kacinma_bedeli_yok(gercek_senaryo):
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskisiz"], "A320", sigmetler=[], kisitli_sahalar=[])
    ref = sonuc["referans_karsilastirmasi"]
    assert ref["referans"] == "ruzgar_optimum_koridor"
    assert ref["kacinma_bedeli"] is None
    assert ref["ruzgar_kazanci"]["sure_dk"] >= -1e-6
    assert ref["ruzgar_optimum_rota"]["toplam_sure_dk"] <= sonuc["normal_rota"]["toplam_sure_dk"] + 1e-6


def test_referans_karsilastirmasi_kazanci_ruzgar_ve_kacinmaya_ayirir(gercek_senaryo):
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskli"], "A320", sigmetler=[], kisitli_sahalar=[])
    ref = sonuc["referans_karsilastirmasi"]
    ruzgar_dk = sonuc["normal_rota"]["toplam_sure_dk"] - ref["ruzgar_optimum_rota"]["toplam_sure_dk"]
    kacinma_dk = sonuc["optimize_rota"]["toplam_sure_dk"] - ref["ruzgar_optimum_rota"]["toplam_sure_dk"]
    assert ref["ruzgar_kazanci"]["sure_dk"] == pytest.approx(ruzgar_dk)
    assert ref["kacinma_bedeli"]["ek_sure_dk"] == pytest.approx(kacinma_dk)
    assert sonuc["sure_tasarrufu_dk"] == pytest.approx(ruzgar_dk - kacinma_dk)


def test_uretim_bilgisi_kapsam_disinda_hava_verisi_yok():
    sonuc = rota_simulasyonu_olustur(41.0, 28.9, 40.7, -74.0, 34000, "2019-01-15T10:00:00", "A320")
    bilgi = sonuc["uretim_bilgisi"]
    assert bilgi["hava_verisi"] is None and bilgi["yazilim_surumu"]
    assert bilgi["esikler"]["ti1_orta_siddetli"] == config.TI1_ESIK_ORTA_SIDDETLI


def test_uretim_bilgisi_kullanilan_kupu_ve_parametreleri_kaydeder(gercek_senaryo):
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskisiz"], "A320", sigmetler=[], kisitli_sahalar=[])
    bilgi = sonuc["uretim_bilgisi"]
    assert bilgi["hava_verisi"]["kaynak"] == "era5" and bilgi["hava_verisi"]["dosya"]
    assert bilgi["hava_verisi"]["gecerlilik_baslangic"] <= bilgi["hava_verisi"]["gecerlilik_bitis"]
    assert bilgi["parametreler"]["arama_uzayi"] == "koridor"
    assert bilgi["model"] is None


def test_irtifa_degisimi_gidis_donus_maliyetlenir_ve_yone_gore_simetriktir():
    from turbulans_radar.rota.rota_optimizasyonu import _irtifa_degisimi_maliyeti

    tirmanma = _irtifa_degisimi_maliyeti(9000.0, 10000.0, 2400.0)
    alcalma = _irtifa_degisimi_maliyeti(10000.0, 9000.0, 2400.0)

    assert tirmanma == pytest.approx(alcalma)
    assert tirmanma[0] == 0.0 and tirmanma[1] > 0
    assert _irtifa_degisimi_maliyeti(9000.0, 9500.0, 2400.0)[1] == pytest.approx(tirmanma[1] / 2)
    assert _irtifa_degisimi_maliyeti(9000.0, 9000.0, 2400.0) == (0.0, 0.0)


def test_seviye_degisimi_secenekleri_yakit_tasarrufu_gostermez(gercek_senaryo, monkeypatch):
    monkeypatch.setattr(config, "ROTA_YAKIT_MODELI", "sabit")
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskli"], "A320", sigmetler=[], kisitli_sahalar=[])
    assert sonuc["yakit_modeli"]["kaynak"] == "sabit" and sonuc["normal_rota"]["tahmini_nox_kg"] is None
    for secenek in sonuc["secenekler"]:
        seyir_yakiti = 2400.0 * secenek["toplam_sure_dk"] / 60.0
        if secenek["strateji"].startswith("irtifa"):
            assert secenek["tahmini_yakit_kg"] > seyir_yakiti
        else:
            assert secenek["tahmini_yakit_kg"] == pytest.approx(seyir_yakiti)
    if sonuc["kacinma_stratejisi"].startswith("irtifa"):
        assert "seviyeye bağlı seyir yakıt akışı modellenmez" in sonuc["aciklama"]


def test_openap_yakit_modeli_seceneklerde_kutleye_bagli_yakit_ve_nox_verir(gercek_senaryo):
    from turbulans_radar.rota import performans_modeli

    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskli"], "A320", sigmetler=[], kisitli_sahalar=[])
    assert sonuc["yakit_modeli"]["kaynak"] == "openap" and sonuc["yakit_modeli"]["baslangic_kutle_kg"] > 0
    assert "kalibre edilmedi" in sonuc["yakit_modeli"]["kutle_orani_notu"]
    for secenek in sonuc["secenekler"]:
        seyir = performans_modeli.seyir_yakiti(
            "A320", secenek["toplam_sure_dk"] * 60.0, 230.0, secenek["irtifa_ft"] * 0.3048
        )
        if secenek["strateji"].startswith("irtifa"):
            assert secenek["tahmini_yakit_kg"] != pytest.approx(seyir["yakit_kg"])
        else:
            assert secenek["tahmini_yakit_kg"] == pytest.approx(seyir["yakit_kg"])
        assert secenek["tahmini_nox_kg"] > 0
    if sonuc["kacinma_stratejisi"].startswith("irtifa"):
        assert "OpenAP" in sonuc["aciklama"]


def test_gercek_era5_kismi_atlatma_durustce_raporlanir(gercek_senaryo):
    # "kismi" senaryo, FL310: denenen hiçbir aday riski TAMAMEN ortadan
    # kaldıramıyor (çevreleyen katman fiziğiyle gerçek ERA5 verisinde doğrulandı:
    # ana küpte 6 -> 2, demo küpünde 6 -> 1) -- yine de riski
    # azaltan aday dürüstçe seçilmeli, "tamamen güvenli" diye YALAN söylenmemeli.
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["kismi"], "A320")
    assert sonuc["ruzgar_verisi_kaynagi"] == "era5_gercek"
    assert sonuc["normal_rota"]["riskli_nokta_sayisi"] > 0
    assert 0 < sonuc["optimize_rota"]["riskli_nokta_sayisi"] < sonuc["normal_rota"]["riskli_nokta_sayisi"]
    assert sonuc["turbulanstan_kacinildi_mi"] is True

    bolumler = sonuc["optimize_rota"]["riskli_bolumler"]
    assert bolumler and all(b["fl"] == 310 and b["uzunluk_nm"] > 0 and b["sure_dk"] > 0 for b in bolumler)
    assert pd.Timestamp(bolumler[0]["baslangic_utc"]) < pd.Timestamp(bolumler[0]["bitis_utc"])
    assert sonuc["optimize_rota"]["riskli_mesafe_nm"] == pytest.approx(sum(b["uzunluk_nm"] for b in bolumler))
    oneri = sonuc["kabin_onerisi"]
    assert oneri["metin"].startswith("Öneri (karar kaptanındır)") and "FL310" in oneri["metin"]
    assert pd.Timestamp(oneri["pencere_baslangic_utc"]) < pd.Timestamp(bolumler[0]["baslangic_utc"])
    assert len(sonuc["brifing_karti"]) == 3 and sonuc["brifing_karti"][2].startswith("Kabin: olası türbülans")


def test_gercek_era5_ile_czml_yapisi_gecerli(gercek_senaryo):
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskisiz"], "B738")
    czml = simulasyonu_czml_e_cevir(sonuc)

    assert czml[0]["id"] == "document"
    assert "clock" in czml[0]

    ucak_varliklari = [v for v in czml[1:] if "model" in v]
    on_izleme_varliklari = [v for v in czml[1:] if v["id"].endswith("-on-izleme")]
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
    return rota_simulasyonu_olustur(38.4, 27.1, 38.5, 43.4, 35000, "2019-01-31T00:00:00", "A320", sigmetler=sigmetler)


def test_rota_ortasindaki_sigmetten_yanal_sapmayla_kacinilir(gercek_senaryo):
    kutu, gun = gercek_senaryo["sigmet"]
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskisiz"], "A320", sigmetler=[_kare_sigmet(*kutu, gun=gun)])
    assert sonuc["sigmet_kontrolu"]["durum"] == "uygulandi"
    assert sonuc["sigmet_kontrolu"]["tampon"]["dikey_ft"] == 1000
    assert sonuc["sigmet_kontrolu"]["sigmetler"][0]["yanal_tampon_nm"] == 10
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
    sonuc = rota_simulasyonu_olustur(5.0, 10.0, 5.0, 25.0, 35000, "2019-01-15T00:00:00", "A320", sigmetler=[sigmet])
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
    sonuc = rota_simulasyonu_olustur(5.0, 10.0, 5.0, 25.0, 35000, "2019-01-15T00:00:00", "A320", sigmetler=[sigmet])
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
        5.0, 10.0, 5.0, 25.0, 35000, "2019-01-15T00:00:00", "A320", sigmetler=[], kisitli_sahalar=kisitli_sahalar
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
        5.0, 10.0, 5.0, 25.0, 35000, "2019-01-15T00:00:00", "A320", sigmetler=[], kisitli_sahalar=[saha]
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


def _pareto_adayi(strateji, saniye, riskli, sigmet=0, ekstra_yakit=0.0):
    return {
        "strateji": strateji,
        "enlem": [40.0, 41.0],
        "boylam": [30.0, 31.0],
        "irtifa_m": 10972.8,
        "zamanlar": [pd.Timestamp("2019-01-15T10:00Z"), pd.Timestamp("2019-01-15T10:10Z")],
        "saniye": saniye,
        "ekstra_saniye": 0.0,
        "ekstra_yakit_kg": ekstra_yakit,
        "maks_ti1": None,
        "riskli_sayisi": riskli,
        "sigmet_ihlali": sigmet,
        "kisitli_saha_ihlali": 0,
        "yanal_sapma_km": 0.0,
    }


def test_pareto_secenekleri_baskilananlari_ve_sert_kisit_ihlalini_eler():
    from turbulans_radar.rota.rota_optimizasyonu import pareto_secenekleri

    normal = _pareto_adayi("yok", 3600, 4)
    guvenli = _pareto_adayi("yanal", 3700, 0)
    ara = _pareto_adayi("irtifa_yukari", 3650, 1)
    kotu = _pareto_adayi("yanal_ceza_60", 3800, 2)
    sigmetli = _pareto_adayi("irtifa_asagi", 3500, 0, sigmet=3)
    kopya = _pareto_adayi("yanal_ceza_300", 3700, 0)
    yakit = lambda a: a["saniye"]  # noqa: E731
    secenekler = pareto_secenekleri([normal, guvenli, ara, kotu, sigmetli, kopya], guvenli, normal, yakit)
    assert [s["strateji"] for s in secenekler] == ["yanal", "irtifa_yukari", "yok"]
    assert secenekler[0]["onerilen"] and not secenekler[2]["onerilen"]
    assert round(secenekler[0]["ek_sure_dk"], 2) == round(100 / 60, 2) and secenekler[2]["ek_sure_dk"] == 0.0


def test_antimeridyen_kesisimi_tespit_edilir_ve_rota_reddedilir():
    from turbulans_radar.rota.rota_optimizasyonu import AntimeridyenHatasi, antimeridyeni_kesiyor_mu

    _, tokyo_la = buyuk_daire_rotasi_olustur(35.5, 139.8, 33.9, -118.4, 41)
    _, istanbul_ny = buyuk_daire_rotasi_olustur(41.0, 28.9, 40.7, -74.0, 41)
    assert antimeridyeni_kesiyor_mu(tokyo_la) and not antimeridyeni_kesiyor_mu(istanbul_ny)
    with pytest.raises(AntimeridyenHatasi):
        rota_simulasyonu_olustur(35.5, 139.8, 33.9, -118.4, 37000, "2019-01-15T10:00:00", "B77W", sigmetler=[])


def _sentetik_aday(ti1):
    from turbulans_radar.rota.rota_optimizasyonu import buyuk_daire_rotasi_olustur

    n = len(ti1)
    enlemler, boylamlar = buyuk_daire_rotasi_olustur(41.0, 29.0, 41.0, 39.0, n)
    zamanlar = list(pd.date_range("2026-01-01T10:00Z", periods=n, freq="5min"))
    return {"enlem": enlemler, "boylam": boylamlar, "irtifa_m": 11277.6, "zamanlar": zamanlar, "ti1": ti1}


def test_riskli_bolumler_ardisik_noktalari_birlestirir_ve_min_nm_ile_suzer(monkeypatch):
    import numpy as np

    from turbulans_radar.rota.rota_optimizasyonu import kabin_onerisi, riskli_bolumler

    yuksek, dusuk = config.TI1_ESIK_ORTA_SIDDETLI * 2, 0.0
    aday = _sentetik_aday(np.array([dusuk, yuksek, yuksek, dusuk, np.nan, yuksek, dusuk, dusuk, dusuk, dusuk]))
    bolumler = riskli_bolumler(aday)
    assert len(bolumler) == 2
    assert bolumler[0]["fl"] == 370 and bolumler[0]["sure_dk"] == pytest.approx(10.0)
    assert bolumler[0]["uzunluk_nm"] > bolumler[1]["uzunluk_nm"] > 0
    assert bolumler[0]["baslangic_utc"].startswith("2026-01-01T10:02:30")
    oneri = kabin_onerisi(bolumler)
    assert "~09:47–10:17Z arasında" in oneri["metin"] and "FL370" in oneri["metin"]
    assert "durdurun" not in oneri["metin"] and "değerlendirilebilir" in oneri["metin"]
    assert oneri["pencere_payi_dk"] == config.KABIN_PENCERE_PAYI_DK and "kalibre edilmedi" in oneri["pencere_payi_notu"]
    monkeypatch.setattr(config, "KABIN_PENCERE_PAYI_DK", 30.0)
    assert "~09:32–10:32Z" in kabin_onerisi(bolumler)["metin"]

    monkeypatch.setattr(config, "RISKLI_BOLUM_MIN_NM", bolumler[1]["uzunluk_nm"] + 1)
    assert len(riskli_bolumler(aday)) == 1
    assert riskli_bolumler(_sentetik_aday(np.full(10, np.nan))) is None
    assert kabin_onerisi([]) is None


def test_yanal_sapma_yonu_seyir_yonune_gore_sol_sag():
    assert yanal_sapma_yonu([40.0, 41.0, 40.0], [30.0, 35.0, 40.0]) == "L"
    assert yanal_sapma_yonu([40.0, 39.0, 40.0], [30.0, 35.0, 40.0]) == "R"
    assert yanal_sapma_yonu([40.0, 39.0, 40.0], [40.0, 35.0, 30.0]) == "L"
    assert yanal_sapma_yonu([40.0, 40.0], [30.0, 40.0]) is None


def test_bacak_ruzgar_okuyucu_nokta_nokta_okumayla_birebir_ayni(monkeypatch):
    import numpy as np
    import xarray as xr

    from turbulans_radar.cli import demo
    from turbulans_radar.rota import rota_optimizasyonu as ro

    with xr.open_dataset(demo.demo_dosyalari()["era5"]) as kup:
        kup = kup.load()
    rotalar = [
        (np.linspace(40.9, 40.6, 40), np.linspace(29.3, 43.1, 40), 10668.0, "2019-01-15T19:00:00"),
        (np.linspace(41.0, 39.9, 25), np.linspace(28.9, 41.3, 25), 9449.0, "2019-01-15T17:40:00"),
        (np.linspace(60.0, 61.0, 5), np.linspace(10.0, 12.0, 5), 11000.0, "2019-01-14T00:00:00"),
    ]
    assert ro._bacak_ruzgar_okuyucu(kup, [40.0], [30.0], 250.0) is not None
    yeni = [ro._rotayi_zamanla(e, b, h, z, 230.0, kup, True) for e, b, h, z in rotalar]
    monkeypatch.setattr(ro, "_bacak_ruzgar_okuyucu", lambda *a, **k: None)
    eski = [ro._rotayi_zamanla(e, b, h, z, 230.0, kup, True) for e, b, h, z in rotalar]
    for (y_sn, y_z), (e_sn, e_z) in zip(yeni, eski, strict=True):
        assert y_sn == e_sn and y_z == e_z


def _zamansiz(sonuc):
    """uretim_zamani her çağrıda değişir; içerik karşılaştırmasında dışlanır."""
    return {**sonuc, "uretim_bilgisi": {**sonuc["uretim_bilgisi"], "uretim_zamani": None}}


def test_ti1_onbellegi_rota_yanitini_degistirmez_hesabi_azaltir(gercek_senaryo, monkeypatch):
    import json

    from turbulans_radar.rota import risk_katmanlari as rk
    from turbulans_radar.rota import rota_optimizasyonu as ro

    asil_ufuk = ro.planlama_ufku
    monkeypatch.setattr(ro, "planlama_ufku", lambda z, simdi=None: asil_ufuk(z, simdi="2026-10-08T00:00:00Z"))
    sayac = {"n": 0}
    asil = rk.rota_ti1_degerleri

    def sayan(*a, **k):
        sayac["n"] += 1
        return asil(*a, **k)

    monkeypatch.setattr(rk, "rota_ti1_degerleri", sayan)
    girdi = (*gercek_senaryo["kismi"], "A320")
    onbellekli = json.dumps(_zamansiz(rota_simulasyonu_olustur(*girdi, sigmetler=[], kisitli_sahalar=[])), default=str)
    onbellekli_sayi = sayac["n"]

    asil_init = rk.Ti1CezaKatmani.__init__
    monkeypatch.setattr(rk.Ti1CezaKatmani, "__init__", lambda self, *a, onbellek=None, **k: asil_init(self, *a, **k))
    sayac["n"] = 0
    onbelleksiz = json.dumps(_zamansiz(rota_simulasyonu_olustur(*girdi, sigmetler=[], kisitli_sahalar=[])), default=str)
    assert onbellekli == onbelleksiz
    assert onbellekli_sayi < sayac["n"]


def test_kutle_bandi_varsayilan_orani_icerir_ve_tek_degeri_kapsar(gercek_senaryo):
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskli"], "A320", sigmetler=[], kisitli_sahalar=[])
    bant = sonuc["yakit_tasarrufu_yuzde_araligi"]
    assert bant["kutle_oranlari"] == sorted({*config.ROTA_KUTLE_BANDI, config.ROTA_SEYIR_KUTLE_ORANI})
    varsayilan = bant["yakit_tasarrufu_yuzde"][bant["kutle_oranlari"].index(config.ROTA_SEYIR_KUTLE_ORANI)]
    assert varsayilan == pytest.approx(sonuc["yakit_tasarrufu_yuzde"], abs=1e-6)
    assert bant["en_dusuk"] <= sonuc["yakit_tasarrufu_yuzde"] + 1e-9 <= bant["en_yuksek"] + 2e-9
    assert "aralık" in bant["aciklama"]


def test_sabit_yakit_modelinde_kutle_bandi_yok(gercek_senaryo, monkeypatch):
    monkeypatch.setattr(config, "ROTA_YAKIT_MODELI", "sabit")
    sonuc = rota_simulasyonu_olustur(*gercek_senaryo["riskli"], "A320", sigmetler=[], kisitli_sahalar=[])
    assert sonuc["yakit_tasarrufu_yuzde_araligi"] is None
