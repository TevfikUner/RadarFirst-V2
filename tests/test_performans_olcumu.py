import asyncio

import httpx
import pytest

from turbulans_radar.cli import performans_olcumu as po


def test_ozet_istatistik_yuzdelikleri():
    ozet = po.ozet_istatistik(range(1, 101))
    assert (ozet["adet"], ozet["p50_ms"], ozet["maks_ms"]) == (100, 50.5, 100.0)
    assert 95 <= ozet["p95_ms"] <= 96 and 99 <= ozet["p99_ms"] <= 100
    assert po.ozet_istatistik([]) == {"adet": 0}


def test_senaryo_eszamanli_istekleri_sayar_ve_hata_kodlarini_ayirir():
    sayac = {"n": 0}

    def isle(istek):
        sayac["n"] += 1
        assert istek.headers["X-API-Key"] == "anahtar"
        return httpx.Response(429 if sayac["n"] % 5 == 0 else 200, json={})

    async def calistir():
        async with httpx.AsyncClient(transport=httpx.MockTransport(isle), base_url="http://test") as istemci:
            return await po._senaryo_calistir(istemci, "POST", "/x", lambda i: {"i": i}, 4, 20, "anahtar")

    sonuc = asyncio.run(calistir())
    assert sonuc["istek"] == 20 and sonuc["durum_kodlari"] == {"200": 16, "429": 4}
    assert sonuc["adet"] == 16 and sonuc["eszamanlilik"] == 4


def test_markdown_tablosu_tum_bolumleri_icerir():
    sonuc = {
        "analiz": {
            "ucus": "THY322 / 2019-01-15",
            "nokta_sayisi": 1614,
            "tekrar": 3,
            "soguk_toplam_ms": 900.0,
            "asamalar": {"eslestirme": po.ozet_istatistik([10, 20])},
        },
        "api": {
            "senaryolar": {
                "saglik": [
                    {
                        "eszamanlilik": 1,
                        "istek": 10,
                        "verim_istek_sn": 5.0,
                        "durum_kodlari": {"200": 10},
                        **po.ozet_istatistik([1, 2]),
                    }
                ]
            }
        },
        "gorev": {
            "gorev_turu": "ucus",
            "adet": 2,
            "tamamlanan": 2,
            "isci_is_parcacigi": 2,
            "toplam_sn": 4.0,
            "gorev_dakika": 30.0,
            "gorev_suresi": po.ozet_istatistik([1000, 2000]),
        },
        "gece": {
            "calismalar": [
                {
                    "tarih": "2026-09-30T21:18+00:00",
                    "sure_dk": 68.0,
                    "cds_istek": 60,
                    "eslesen": 1596,
                    "istek_basina_sn": 68.0,
                }
            ]
        },
    }
    tablo = po.markdown_tablosu(sonuc)
    for parca in ("Tek uçuş analizi", "| eslestirme |", "| saglik | 1 |", "İşçi görev hızı", "| 2026-09-30T21:18"):
        assert parca in tablo


def test_api_anahtari_yoksa_acik_hata(monkeypatch):
    monkeypatch.delenv("TURBULANS_API_ANAHTARI", raising=False)
    monkeypatch.delenv("API_ANAHTARI", raising=False)
    with pytest.raises(SystemExit, match="TURBULANS_API_ANAHTARI"):
        po.api_olc("http://localhost:1")


def test_rota_olc_a_yildizi_ayri_zamanlar_ve_geri_yukler(monkeypatch):
    from turbulans_radar.rota import rota_optimizasyonu as ro

    asil = ro._a_yildiz_ile_rota_ara
    monkeypatch.setattr(ro, "_a_yildiz_ile_rota_ara", lambda *a, **k: None)
    yerlesik = ro._a_yildiz_ile_rota_ara
    cagrilar = []

    def sahte_rota(*girdi, sigmetler=None, kisitli_sahalar=None):
        cagrilar.append((girdi, len(sigmetler), len(kisitli_sahalar)))
        if sigmetler or kisitli_sahalar:
            ro._a_yildiz_ile_rota_ara()
        return {
            "ruzgar_verisi_kaynagi": "era5_gercek",
            "normal_rota": {"mesafe_km": 1000.4},
            "kacinma_stratejisi": "yok",
        }

    monkeypatch.setattr(ro, "rota_simulasyonu_olustur", sahte_rota)
    from turbulans_radar import config

    canli_once = config.CANLI_HAVA_VERISI_ETKIN
    sonuc = po.rota_olc(tekrar=2)
    assert ro._a_yildiz_ile_rota_ara is yerlesik and asil is not None
    assert config.CANLI_HAVA_VERISI_ETKIN == canli_once
    assert len(cagrilar) == 2 * len(po.ROTA_SENARYOLARI)
    senaryolar = {s["ad"][:2]: s for s in sonuc["senaryolar"]}
    assert senaryolar["S6"]["a_yildiz_medyan_ms"] is not None and senaryolar["S2"]["a_yildiz_medyan_ms"] is None
    assert senaryolar["S4"]["mesafe_km"] == 1000
    tablo = po.markdown_tablosu({"rota": sonuc})
    assert "### Rota kararı (2 tekrar" in tablo and "| S2 İzmir→Van FL350 | era5_gercek |" in tablo
    assert "çağrılmadı" in tablo


def test_donanim_bilgisi_temel_alanlari_verir():
    bilgi = po.donanim_bilgisi()
    assert bilgi["mantiksal_cekirdek"] and bilgi["python"] and "islemci" in bilgi


def test_analiz_olc_asamalari_olcer_db_hatasinda_yazimi_birakir(monkeypatch):
    import pandas as pd

    from turbulans_radar import config
    from turbulans_radar.analiz import ucus_analizi
    from turbulans_radar.arayuz import harita
    from turbulans_radar.depo import veritabani
    from turbulans_radar.fizik import eslestirme
    from turbulans_radar.veri import opensky_onbellegi

    monkeypatch.setattr(config, "ERA5_OTOMATIK_INDIRME", True)
    monkeypatch.setattr(config, "CANLI_HAVA_VERISI_ETKIN", True)
    rota = pd.DataFrame({"enlem": [41.0, 41.1]})
    monkeypatch.setattr(opensky_onbellegi, "rota_onbellekten_oku", lambda u, t: rota)
    monkeypatch.setattr(ucus_analizi, "_veri_kupunu_sec", lambda r: "kup")
    monkeypatch.setattr(eslestirme, "rotayi_hava_durumuyla_eslestir", lambda r, k: r)
    monkeypatch.setattr(harita, "zaman_kaydiricili_harita_olustur", lambda e, dosya_adi: None)

    def db_yok(*a):
        raise ConnectionError("db yok")

    monkeypatch.setattr(veritabani, "ucus_ve_olcumleri_kaydet", db_yok)
    sonuc = po.analiz_olc(tekrar=3)
    assert sonuc["nokta_sayisi"] == 2 and sonuc["tekrar"] == 3
    assert set(sonuc["asamalar"]) == {"rota_okuma", "kup_secimi", "eslestirme", "harita", "toplam"}
    assert sonuc["asamalar"]["toplam"]["adet"] == 2
    assert config.ERA5_OTOMATIK_INDIRME is False and config.CANLI_HAVA_VERISI_ETKIN is False


def test_api_olc_tum_senaryolari_isinmayla_calistirir(monkeypatch):
    istekler = []

    def isle(istek):
        istekler.append(istek.url.path)
        return httpx.Response(200, json={})

    asil = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **k: asil(transport=httpx.MockTransport(isle), **k))
    monkeypatch.setenv("TURBULANS_API_ANAHTARI", "anahtar")
    sonuc = po.api_olc("http://test", eszamanliliklar=(1, 2), istek_carpani=1, isinma=1)
    assert set(sonuc["senaryolar"]) == {ad for ad, *_ in po.api_senaryolari()}
    assert [s["istek"] for s in sonuc["senaryolar"]["saglik"]] == [10, 10]
    assert len(istekler) == len(po.api_senaryolari()) * (1 + 10 + 10)


class _Satir:
    def __init__(self, **alanlar):
        self.__dict__.update(alanlar)


class _SahteMotor:
    def __init__(self, satirlar):
        self.satirlar = satirlar

    def connect(self):
        motor = self

        class _Baglanti:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, *a, **k):
                class _Sonuc:
                    def all(self_):
                        return motor.satirlar

                return _Sonuc()

        return _Baglanti()


def test_gece_olc_istek_basina_sureyi_hesaplar(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from turbulans_radar.depo import veritabani

    t0 = datetime(2026, 10, 1, 3, tzinfo=UTC)
    satirlar = [
        _Satir(
            olusturulma_zamani=t0,
            baslama_zamani=t0,
            bitis_zamani=t0 + timedelta(minutes=60),
            ozet=[{"cds_istek": 30, "eslesti": 900}],
        ),
        _Satir(
            olusturulma_zamani=t0, baslama_zamani=t0, bitis_zamani=t0 + timedelta(minutes=20), ozet={"cds_istek": 10}
        ),
        _Satir(olusturulma_zamani=t0, baslama_zamani=None, bitis_zamani=None, ozet=None),
    ]
    monkeypatch.setattr(veritabani, "motor_al", lambda: _SahteMotor(satirlar))
    sonuc = po.gece_olc()
    assert [c["istek_basina_sn"] for c in sonuc["calismalar"]] == [120.0, 120.0, None]
    assert sonuc["calismalar"][0]["eslesen"] == 900 and sonuc["istek_basina_sn_medyan"] == 120.0


def test_ana_secilen_bolumu_olcer_ve_json_yazar(monkeypatch, tmp_path):
    import json

    monkeypatch.setattr(po, "gece_olc", lambda: {"calismalar": [], "istek_basina_sn_medyan": None})
    yol = tmp_path / "olcum.json"
    po.ana(["gece", "--json", str(yol)])
    sonuc = json.loads(yol.read_text(encoding="utf-8"))
    assert sonuc["gece"]["calismalar"] == [] and "donanim" in sonuc and "analiz" not in sonuc
