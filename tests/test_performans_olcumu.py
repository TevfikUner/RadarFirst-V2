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
