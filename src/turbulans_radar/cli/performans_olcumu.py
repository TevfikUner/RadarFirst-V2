"""
performans_olcumu.py
-----------------------
Tekrarlanabilir performans ölçümü (bitirme komitesi E9; sonuçlar
docs/PERFORMANS_RAPORU.md). Dört bölüm, her biri ayrı çalıştırılabilir:

  analiz : tek uçuş analizinin aşama süreleri (demo THY322, süreç içinde, ağsız)
  api    : eşzamanlı istek altında uç nokta gecikmesi (p50/p95/p99) ve verim
  gorev  : işçi kuyruğunun görev hızı (N uçuş analizi doğrudan kuyruğa)
  gece   : ML gece işinin CDS isteği başına süresi (analiz_gorevleri kayıtları)

    turbulans-performans analiz --tekrar 5
    TURBULANS_API_ANAHTARI=... turbulans-performans api --taban-url http://localhost:18000
    turbulans-performans gorev --adet 20
    turbulans-performans gece
    turbulans-performans hepsi --json sonuc.json

API anahtarı komut satırından değil TURBULANS_API_ANAHTARI (yoksa API_ANAHTARI)
ortam değişkeninden okunur. Veritabanı bağlantısı POSTGRES_* değişkenlerinden.
"""

import argparse
import asyncio
import json
import os
import platform
import statistics
import tempfile
import time
from datetime import UTC, datetime

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

import numpy as np

from turbulans_radar import config

DEMO_UCUSU, DEMO_TARIHI = "THY322", "2019-01-15"


def donanim_bilgisi() -> dict:
    bilgi = {
        "isletim_sistemi": platform.platform(),
        "python": platform.python_version(),
        "mantiksal_cekirdek": os.cpu_count(),
    }
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as dosya:
            bilgi["islemci"] = next(s.split(":", 1)[1].strip() for s in dosya if s.startswith("model name"))
        with open("/proc/meminfo", encoding="utf-8") as dosya:
            kb = int(next(s.split()[1] for s in dosya if s.startswith("MemTotal")))
            bilgi["bellek_gb"] = round(kb / 1024**2, 1)
    except (OSError, StopIteration):
        bilgi["islemci"] = platform.processor() or None
    return bilgi


def ozet_istatistik(sureler_ms) -> dict:
    dizi = np.asarray(sureler_ms, dtype=float)
    if not len(dizi):
        return {"adet": 0}
    return {
        "adet": len(dizi),
        "p50_ms": round(float(np.percentile(dizi, 50)), 1),
        "p95_ms": round(float(np.percentile(dizi, 95)), 1),
        "p99_ms": round(float(np.percentile(dizi, 99)), 1),
        "ort_ms": round(float(dizi.mean()), 1),
        "maks_ms": round(float(dizi.max()), 1),
    }


# --- analiz ---------------------------------------------------------------


def _sure(fonksiyon, *argumanlar, **anahtarlar):
    baslangic = time.perf_counter()
    sonuc = fonksiyon(*argumanlar, **anahtarlar)
    return sonuc, (time.perf_counter() - baslangic) * 1000


def analiz_olc(tekrar=5, veritabanina_yaz=True) -> dict:
    """Demo uçuşunun her aşaması ayrı ölçülür. İlk tekrar soğuk başlangıçtır
    (dosya açma, küp önbelleği); raporda ayrı verilir."""
    from turbulans_radar.analiz import ucus_analizi
    from turbulans_radar.arayuz.harita import zaman_kaydiricili_harita_olustur
    from turbulans_radar.depo.veritabani import ucus_ve_olcumleri_kaydet
    from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
    from turbulans_radar.veri.opensky_onbellegi import rota_onbellekten_oku

    config.ERA5_OTOMATIK_INDIRME = False
    config.CANLI_HAVA_VERISI_ETKIN = False
    asamalar = {"rota_okuma": [], "kup_secimi": [], "eslestirme": [], "harita": [], "veritabani": [], "toplam": []}
    nokta_sayisi = None
    with tempfile.TemporaryDirectory() as gecici:
        for _ in range(tekrar):
            toplam_bas = time.perf_counter()
            rota_df, ms = _sure(rota_onbellekten_oku, DEMO_UCUSU, DEMO_TARIHI)
            asamalar["rota_okuma"].append(ms)
            kup, ms = _sure(ucus_analizi._veri_kupunu_sec, rota_df)
            asamalar["kup_secimi"].append(ms)
            eslesmis, ms = _sure(rotayi_hava_durumuyla_eslestir, rota_df, kup)
            asamalar["eslestirme"].append(ms)
            nokta_sayisi = len(eslesmis)
            _, ms = _sure(zaman_kaydiricili_harita_olustur, eslesmis, dosya_adi=os.path.join(gecici, "harita.html"))
            asamalar["harita"].append(ms)
            if veritabanina_yaz:
                try:
                    _, ms = _sure(ucus_ve_olcumleri_kaydet, eslesmis, DEMO_UCUSU, DEMO_TARIHI)
                    asamalar["veritabani"].append(ms)
                except Exception as hata:
                    veritabanina_yaz = False
                    print(f"[Uyarı] Veritabanı yazımı ölçülemedi: {hata}")
            asamalar["toplam"].append((time.perf_counter() - toplam_bas) * 1000)
    return {
        "ucus": f"{DEMO_UCUSU} / {DEMO_TARIHI}",
        "nokta_sayisi": nokta_sayisi,
        "tekrar": tekrar,
        "soguk_toplam_ms": round(asamalar["toplam"][0], 1),
        "asamalar": {ad: ozet_istatistik(s[1:] or s) for ad, s in asamalar.items() if s},
    }


# --- api ------------------------------------------------------------------


def api_senaryolari():
    """(ad, yöntem, yol, gövde üretici). Ağır uçlarda her istek biraz farklıdır
    ki rota önbelleği ölçümü bozmasın; '_onbellekli' senaryo bilerek aynıdır."""

    def rota(i):
        return {
            "baslangic_enlem": 41.0,
            "baslangic_boylam": 29.0,
            "bitis_enlem": 40.5,
            "bitis_boylam": round(43.5 - 0.01 * i, 3),
            "irtifa_ft": 36000,
            "zaman": "2019-01-15T20:00:00",
            "ucak_modeli": "A320",
        }

    return [
        ("saglik", "GET", "/saglik", None),
        ("ucus_listesi", "GET", "/api/v1/ucuslar?limit=50", None),
        ("ucus_detayi", "GET", f"/api/v1/ucuslar/{DEMO_UCUSU}/{DEMO_TARIHI}", None),
        (
            "tahmin",
            "POST",
            "/api/v1/turbulans/tahmin",
            lambda i: {
                "enlem": round(40.0 + 0.01 * (i % 100), 3),
                "boylam": 34.0,
                "irtifa_ft": 36000,
                "zaman": "2019-01-15T20:00:00",
            },
        ),
        ("rota_simulasyonu", "POST", "/api/v1/simulasyon/rota", rota),
        ("rota_simulasyonu_onbellekli", "POST", "/api/v1/simulasyon/rota", lambda i: rota(0)),
    ]


async def _senaryo_calistir(istemci, yontem, yol, govde, eszamanlilik, adet, anahtar):
    import httpx

    sureler, durumlar = [], {}
    sayac = iter(range(adet))
    kilit = asyncio.Lock()

    async def calisan():
        while True:
            async with kilit:
                i = next(sayac, None)
            if i is None:
                return
            bas = time.perf_counter()
            try:
                yanit = await istemci.request(
                    yontem, yol, headers={"X-API-Key": anahtar}, json=govde(i) if govde else None
                )
                kod = yanit.status_code
            except httpx.HTTPError as hata:
                kod = type(hata).__name__
            sure = (time.perf_counter() - bas) * 1000
            durumlar[str(kod)] = durumlar.get(str(kod), 0) + 1
            if kod == 200:
                sureler.append(sure)

    bas = time.perf_counter()
    await asyncio.gather(*(calisan() for _ in range(eszamanlilik)))
    gecen = time.perf_counter() - bas
    return {
        **ozet_istatistik(sureler),
        "eszamanlilik": eszamanlilik,
        "istek": adet,
        "verim_istek_sn": round(len(sureler) / gecen, 2) if gecen else None,
        "durum_kodlari": durumlar,
    }


async def _api_olc(taban_url, anahtar, eszamanliliklar, istek_carpani, isinma):
    import httpx

    sonuc = {}
    limitler = httpx.Limits(max_connections=max(eszamanliliklar) + 4)
    async with httpx.AsyncClient(base_url=taban_url, timeout=120.0, limits=limitler) as istemci:
        for ad, yontem, yol, govde in api_senaryolari():
            for i in range(isinma):
                await istemci.request(
                    yontem, yol, headers={"X-API-Key": anahtar}, json=govde(10_000 + i) if govde else None
                )
            sonuc[ad] = [
                await _senaryo_calistir(istemci, yontem, yol, govde, c, max(10, istek_carpani * c), anahtar)
                for c in eszamanliliklar
            ]
            print(f"  {ad}: " + ", ".join(f"c={s['eszamanlilik']} p95={s.get('p95_ms')} ms" for s in sonuc[ad]))
    return sonuc


def api_olc(taban_url, eszamanliliklar=(1, 4, 16), istek_carpani=8, isinma=2) -> dict:
    anahtar = os.environ.get("TURBULANS_API_ANAHTARI") or os.environ.get("API_ANAHTARI")
    if not anahtar:
        raise SystemExit("TURBULANS_API_ANAHTARI (ya da API_ANAHTARI) ortam değişkeni gerekli.")
    return {
        "taban_url": taban_url,
        "senaryolar": asyncio.run(_api_olc(taban_url, anahtar, eszamanliliklar, istek_carpani, isinma)),
    }


# --- gorev ----------------------------------------------------------------


def gorev_olc(adet=20, zaman_asimi_saniye=900) -> dict:
    """N demo uçuş analizini kuyruğa doğrudan ekler (API'nin dakikalık analiz
    sınırını atlamak için) ve hepsi bitene kadar bekler."""
    import uuid

    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import AnalizGorevi
    from turbulans_radar.depo.veritabani import motor_al

    motor = motor_al()
    bas = datetime.now(UTC)
    idler = [str(uuid.uuid4()) for _ in range(adet)]
    with Session(motor) as oturum:
        oturum.add_all(
            AnalizGorevi(id=i, tur="ucus", durum="kuyrukta", ucus_numarasi=DEMO_UCUSU, tarih=DEMO_TARIHI) for i in idler
        )
        oturum.commit()
    sorgu = text("SELECT durum, baslama_zamani, bitis_zamani FROM analiz_gorevleri WHERE id = ANY(:idler)")
    son = time.monotonic() + zaman_asimi_saniye
    while time.monotonic() < son:
        with motor.connect() as baglanti:
            satirlar = baglanti.execute(sorgu, {"idler": idler}).all()
        if all(s.durum not in ("kuyrukta", "calisiyor") for s in satirlar):
            break
        time.sleep(1.0)
    tamam = [s for s in satirlar if s.durum == "tamamlandi"]
    sureler = [(s.bitis_zamani - s.baslama_zamani).total_seconds() * 1000 for s in tamam]
    bitis = max((s.bitis_zamani for s in tamam), default=datetime.now(UTC))
    toplam_sn = (bitis - bas).total_seconds()
    return {
        "gorev_turu": "ucus (demo THY322, OpenSky önbelleği + yerel ERA5)",
        "adet": adet,
        "tamamlanan": len(tamam),
        "durumlar": {d: sum(1 for s in satirlar if s.durum == d) for d in {s.durum for s in satirlar}},
        "isci_is_parcacigi": config.GOREV_ISCI_SAYISI,
        "toplam_sn": round(toplam_sn, 1),
        "gorev_dakika": round(len(tamam) / toplam_sn * 60, 1) if toplam_sn else None,
        "gorev_suresi": ozet_istatistik(sureler),
    }


# --- gece -----------------------------------------------------------------


def gece_olc(limit=10) -> dict:
    from sqlalchemy import text

    from turbulans_radar.depo.veritabani import motor_al

    with motor_al().connect() as baglanti:
        satirlar = baglanti.execute(
            text(
                "SELECT olusturulma_zamani, baslama_zamani, bitis_zamani, ozet FROM analiz_gorevleri "
                "WHERE tur = 'ml_veri' AND durum = 'tamamlandi' ORDER BY olusturulma_zamani DESC LIMIT :n"
            ),
            {"n": limit},
        ).all()
    calismalar = []
    for s in satirlar:
        ozet = (s.ozet or [{}])[0] if isinstance(s.ozet, list) else (s.ozet or {})
        istek = ozet.get("cds_istek") or 0
        sure = (s.bitis_zamani - s.baslama_zamani).total_seconds() if s.bitis_zamani and s.baslama_zamani else None
        calismalar.append(
            {
                "tarih": s.olusturulma_zamani.isoformat(timespec="minutes"),
                "sure_dk": round(sure / 60, 1) if sure else None,
                "cds_istek": istek,
                "eslesen": ozet.get("eslesti"),
                "istek_basina_sn": round(sure / istek, 1) if sure and istek else None,
            }
        )
    istek_basina = [c["istek_basina_sn"] for c in calismalar if c["istek_basina_sn"]]
    return {
        "calismalar": calismalar,
        "istek_basina_sn_medyan": statistics.median(istek_basina) if istek_basina else None,
    }


# --- rapor ----------------------------------------------------------------


def markdown_tablosu(sonuc: dict) -> str:
    satirlar = []
    if "analiz" in sonuc:
        a = sonuc["analiz"]
        satirlar += [
            f"### Tek uçuş analizi ({a['ucus']}, {a['nokta_sayisi']} nokta, {a['tekrar']} tekrar)",
            "",
            f"Soğuk başlangıç toplamı: {a['soguk_toplam_ms']} ms. Sıcak tekrarlar:",
            "",
            "| Aşama | p50 (ms) | p95 (ms) | Maks (ms) |",
            "|---|---|---|---|",
        ]
        satirlar += [
            f"| {ad} | {s['p50_ms']} | {s['p95_ms']} | {s['maks_ms']} |" for ad, s in a["asamalar"].items() if s["adet"]
        ]
        satirlar.append("")
    if "api" in sonuc:
        satirlar += [
            "### API gecikmesi",
            "",
            "| Senaryo | Eşzamanlılık | İstek | p50 (ms) | p95 (ms) | p99 (ms) | Verim (istek/sn) | Durum kodları |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for ad, olcumler in sonuc["api"]["senaryolar"].items():
            for s in olcumler:
                kodlar = ", ".join(f"{k}: {v}" for k, v in sorted(s["durum_kodlari"].items()))
                satirlar.append(
                    f"| {ad} | {s['eszamanlilik']} | {s['istek']} | {s.get('p50_ms', '—')} | {s.get('p95_ms', '—')} "
                    f"| {s.get('p99_ms', '—')} | {s['verim_istek_sn']} | {kodlar} |"
                )
        satirlar.append("")
    if "gorev" in sonuc:
        g = sonuc["gorev"]
        s = g["gorev_suresi"]
        satirlar += [
            "### İşçi görev hızı",
            "",
            "| Görev | Adet | Tamamlanan | İş parçacığı | Toplam (sn) | Görev/dk | Görev süresi p50 / p95 (ms) |",
            "|---|---|---|---|---|---|---|",
            f"| {g['gorev_turu']} | {g['adet']} | {g['tamamlanan']} | {g['isci_is_parcacigi']} | {g['toplam_sn']} "
            f"| {g['gorev_dakika']} | {s.get('p50_ms', '—')} / {s.get('p95_ms', '—')} |",
            "",
        ]
    if "gece" in sonuc:
        satirlar += [
            "### ML gece işi",
            "",
            "| Başlangıç (UTC) | Süre (dk) | CDS isteği | Eşleşen örnek | İstek başına (sn) |",
            "|---|---|---|---|---|",
        ]
        satirlar += [
            f"| {c['tarih']} | {c['sure_dk']} | {c['cds_istek']} | {c['eslesen']} | {c['istek_basina_sn']} |"
            for c in sonuc["gece"]["calismalar"]
        ]
        satirlar.append("")
    return "\n".join(satirlar)


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Türbülans Radar performans ölçümü (bkz. docs/PERFORMANS_RAPORU.md)."
    )
    ayristirici.add_argument("bolum", choices=["analiz", "api", "gorev", "gece", "hepsi"])
    ayristirici.add_argument("--tekrar", type=int, default=5, help="analiz: tekrar sayısı")
    ayristirici.add_argument("--taban-url", default="http://localhost:8000", help="api: hedef sunucu")
    ayristirici.add_argument("--eszamanlilik", default="1,4,16", help="api: virgülle eşzamanlılık düzeyleri")
    ayristirici.add_argument(
        "--istek-carpani", type=int, default=8, help="api: düzey başına istek = çarpan x eşzamanlılık"
    )
    ayristirici.add_argument("--adet", type=int, default=20, help="gorev: kuyruğa eklenecek uçuş analizi")
    ayristirici.add_argument("--json", metavar="DOSYA", help="sonucu JSON olarak yaz")
    argumanlar = ayristirici.parse_args(argv)

    bolumler = ["analiz", "api", "gorev", "gece"] if argumanlar.bolum == "hepsi" else [argumanlar.bolum]
    sonuc = {"zaman": datetime.now(UTC).isoformat(timespec="seconds"), "donanim": donanim_bilgisi()}
    for bolum in bolumler:
        print(f"[{bolum}] ölçülüyor...")
        if bolum == "analiz":
            sonuc["analiz"] = analiz_olc(argumanlar.tekrar)
        elif bolum == "api":
            sonuc["api"] = api_olc(
                argumanlar.taban_url,
                tuple(int(c) for c in argumanlar.eszamanlilik.split(",")),
                argumanlar.istek_carpani,
            )
        elif bolum == "gorev":
            sonuc["gorev"] = gorev_olc(argumanlar.adet)
        else:
            sonuc["gece"] = gece_olc()
    if argumanlar.json:
        with open(argumanlar.json, "w", encoding="utf-8") as dosya:
            json.dump(sonuc, dosya, ensure_ascii=False, indent=2, default=str)
    print(markdown_tablosu(sonuc))


if __name__ == "__main__":
    ana()
