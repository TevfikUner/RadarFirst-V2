"""
demo_goster.py
--------------
Çalışan Türbülans Radar API'sine bağlanıp denetim senaryolarını sırayla
çalıştırır, sonuçları terminalde renkli tablolar olarak basar. Yalnızca
standart kütüphane kullanır; API anahtarlarını .env'den okur, ekrana basmaz.

    python scripts/demo_goster.py --bekle
    python scripts/demo_goster.py --senaryo simulasyon --kaydet test_raporu/2026-10-06/api

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil,
karar destek aracıdır.
"""

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
SENARYOLAR = ["simulasyon", "turbulans", "veri", "ucus", "ml", "backtest", "guvenlik"]

RENK = {
    "kalin": "\033[1m",
    "mavi": "\033[36m",
    "yesil": "\033[32m",
    "sari": "\033[33m",
    "kirmizi": "\033[31m",
    "gri": "\033[90m",
    "son": "\033[0m",
}


class Gosterici:
    def __init__(self, taban_url, bekle, kaydet, renkli):
        self.taban_url = taban_url.rstrip("/")
        self.bekle = bekle
        self.kaydet = Path(kaydet) if kaydet else None
        self.renkli = renkli
        self.anahtarlar = env_oku(KOK / ".env")
        self.kayitlar = []
        if self.kaydet:
            self.kaydet.mkdir(parents=True, exist_ok=True)

    def r(self, metin, *renkler):
        if not self.renkli:
            return str(metin)
        return "".join(RENK[x] for x in renkler) + str(metin) + RENK["son"]

    def adim(self, metin):
        print("\n" + self.r("▶ " + metin, "kalin", "mavi"))

    def duraklat(self):
        if self.bekle:
            input(self.r("  [devam için Enter]", "gri"))

    def istek(self, yontem, yol, govde=None, rol="yonetici", zaman_asimi=180, ham=False):
        basliklar = {"Content-Type": "application/json"}
        anahtar_adi = {"yonetici": "API_ANAHTARI", "pilot": "API_PILOT_ANAHTARI"}.get(rol)
        if anahtar_adi:
            basliklar["X-API-Key"] = self.anahtarlar.get(anahtar_adi, "")
        elif rol == "yanlis":
            basliklar["X-API-Key"] = "yanlis-anahtar"
        veri = json.dumps(govde).encode() if govde is not None else None
        istek = urllib.request.Request(self.taban_url + yol, data=veri, headers=basliklar, method=yontem)
        baslangic = time.perf_counter()
        try:
            with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
                kod, icerik = yanit.status, yanit.read()
        except urllib.error.HTTPError as hata:
            kod, icerik = hata.code, hata.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as hata:
            return 0, time.perf_counter() - baslangic, {"hata": str(hata)}
        sure = time.perf_counter() - baslangic
        if ham:
            return kod, sure, icerik
        try:
            return kod, sure, json.loads(icerik) if icerik else None
        except ValueError:
            return kod, sure, icerik.decode(errors="replace")[:500]

    def kaydet_yanit(self, ad, yontem, yol, kod, sure, yanit, govde=None, ozet=""):
        self.kayitlar.append(
            {"senaryo": ad, "yontem": yontem, "yol": yol, "http": kod, "sure_sn": round(sure, 3), "ozet": ozet}
        )
        if self.kaydet:
            (self.kaydet / f"{ad}.json").write_text(
                json.dumps(
                    {
                        "istek": {"yontem": yontem, "yol": yol, "govde": govde},
                        "http": kod,
                        "sure_sn": round(sure, 3),
                        "yanit": yanit,
                    },
                    ensure_ascii=False,
                    indent=1,
                    default=str,
                ),
                encoding="utf-8",
            )

    def tablo(self, basliklar, satirlar):
        satirlar = [[kisalt(h) for h in s] for s in satirlar]
        genislik = [
            max(len(str(b)), *(len(s[i]) for s in satirlar)) if satirlar else len(str(b))
            for i, b in enumerate(basliklar)
        ]
        cizgi = "  +" + "+".join("-" * (g + 2) for g in genislik) + "+"
        print(cizgi)
        print("  | " + " | ".join(self.r(str(b).ljust(g), "kalin") for b, g in zip(basliklar, genislik)) + " |")
        print(cizgi)
        for s in satirlar:
            print("  | " + " | ".join(self.renklendir(h, g) for h, g in zip(s, genislik)) + " |")
        print(cizgi)

    def renklendir(self, hucre, genislik):
        metin = hucre.ljust(genislik)
        if hucre.startswith(("✅", "evet")):
            return self.r(metin, "yesil")
        if hucre.startswith(("❌", "HATA")):
            return self.r(metin, "kirmizi")
        if hucre.startswith(("⚠", "hayır")):
            return self.r(metin, "sari")
        return metin

    def http_isareti(self, kod, beklenen=(200,)):
        return ("✅ " if kod in beklenen else "❌ ") + str(kod)


def env_oku(yol):
    anahtarlar = {}
    if not yol.exists():
        return anahtarlar
    for satir in yol.read_text(encoding="utf-8").splitlines():
        if "=" in satir and not satir.lstrip().startswith("#"):
            ad, deger = satir.split("=", 1)
            anahtarlar[ad.strip()] = deger.strip().strip('"').strip("'")
    return anahtarlar


def kisalt(deger, uzunluk=70):
    if deger is None:
        return "—"
    if isinstance(deger, bool):
        return "evet" if deger else "hayır"
    if isinstance(deger, float):
        return f"{deger:.3g}" if abs(deger) < 1e-3 and deger != 0 else f"{deger:,.2f}".rstrip("0").rstrip(".")
    metin = str(deger).replace("\n", " ")
    return metin if len(metin) <= uzunluk else metin[: uzunluk - 1] + "…"


def canli_zaman(saat_sonra=1):
    simdi = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=saat_sonra)
    return simdi.strftime("%Y-%m-%dT%H:%M:%S")


def simulasyon_senaryolari():
    return [
        (
            "sim_1_istanbul_antalya",
            "Demo: İstanbul → Antalya, 2019-01-05 12:00, 28000 ft, A320 (ERA5 içinde)",
            {
                "baslangic_enlem": 40.98,
                "baslangic_boylam": 28.82,
                "bitis_enlem": 36.90,
                "bitis_boylam": 30.80,
                "irtifa_ft": 28000,
                "zaman": "2019-01-05T12:00:00",
                "ucak_modeli": "A320",
            },
        ),
        (
            "sim_2_istanbul_ankara",
            "İstanbul → Ankara, 2019-01-15 10:00, 34000 ft (ERA5 içinde)",
            {
                "baslangic_enlem": 40.98,
                "baslangic_boylam": 28.82,
                "bitis_enlem": 40.13,
                "bitis_boylam": 32.99,
                "irtifa_ft": 34000,
                "zaman": "2019-01-15T10:00:00",
                "ucak_modeli": "A320",
            },
        ),
        (
            "sim_3_kapsam_disi",
            "Kapsam dışı: İstanbul → Ankara, 2018-06-15 (Türkiye küpü yok) → uydurma iyileşme olmamalı",
            {
                "baslangic_enlem": 40.98,
                "baslangic_boylam": 28.82,
                "bitis_enlem": 40.13,
                "bitis_boylam": 32.99,
                "irtifa_ft": 35000,
                "zaman": "2018-06-15T12:00:00",
                "ucak_modeli": "A320",
            },
        ),
        (
            "sim_4_malatya_musul_canli",
            "Malatya → Musul, şimdi+1 sa, FL350: kısıtlı saha (Suriye), canlı GFS ve canlı SIGMET",
            {
                "baslangic_enlem": 38.35,
                "baslangic_boylam": 38.31,
                "bitis_enlem": 36.34,
                "bitis_boylam": 43.13,
                "irtifa_ft": 35000,
                "zaman": canli_zaman(1),
                "ucak_modeli": "A320",
            },
        ),
    ]


def senaryo_simulasyon(g):
    g.adim("Uçak profilleri listesi alınıyor (GET /simulasyon/ucak-profilleri)")
    kod, sure, profiller = g.istek("GET", "/api/v1/simulasyon/ucak-profilleri", rol="pilot")
    g.kaydet_yanit(
        "sim_5_ucak_profilleri",
        "GET",
        "/api/v1/simulasyon/ucak-profilleri",
        kod,
        sure,
        profiller,
        ozet=f"{len(profiller or [])} profil",
    )
    if kod == 200:
        g.tablo(
            ["kod", "etiket", "TAS m/s", "yakıt kg/sa"],
            [[p["kod"], p["etiket"], p["tas_ms"], p["yakit_akisi_kg_saat"]] for p in profiller],
        )
    g.duraklat()
    for ad, aciklama, govde in simulasyon_senaryolari():
        g.adim(aciklama)
        toplam_sure, deneme = 0.0, 0
        while True:
            kod, sure, y = g.istek("POST", "/api/v1/simulasyon/rota", govde, rol="pilot")
            toplam_sure += sure
            deneme += 1
            if kod == 200 and y.get("ruzgar_verisi_kaynagi") == "canli_veri_hazirlaniyor" and deneme < 8:
                print(g.r(f"  canlı GFS indiriliyor, {deneme}. deneme; 10 sn sonra tekrar…", "gri"))
                time.sleep(10)
                continue
            break
        if kod != 200:
            print(g.r(f"  HATA HTTP {kod}: {kisalt(y, 300)}", "kirmizi"))
            g.kaydet_yanit(ad, "POST", "/api/v1/simulasyon/rota", kod, sure, y, govde, ozet="hata")
            g.duraklat()
            continue
        n, o = y["normal_rota"], y["optimize_rota"]
        g.kaydet_yanit(
            ad,
            "POST",
            "/api/v1/simulasyon/rota",
            kod,
            sure,
            {k: v for k, v in y.items() if k != "czml"},
            govde,
            ozet=f"{y['ruzgar_verisi_kaynagi']} / {y['kacinma_stratejisi']} / riskli {n.get('riskli_nokta_sayisi')}→{o.get('riskli_nokta_sayisi')}",
        )
        g.tablo(
            ["ölçüt", "normal (büyük daire)", "optimize (öneri)"],
            [
                ["süre (dk)", n["toplam_sure_dk"], o["toplam_sure_dk"]],
                ["mesafe (km)", n["mesafe_km"], o["mesafe_km"]],
                ["yakıt (kg)", n["tahmini_yakit_kg"], o["tahmini_yakit_kg"]],
                ["CO2 (kg)", n["tahmini_co2_kg"], o["tahmini_co2_kg"]],
                ["seviye (FL)", n.get("fl"), o.get("fl")],
                ["maks TI1 (s⁻²)", n.get("maks_ti1"), o.get("maks_ti1")],
                ["riskli nokta", n.get("riskli_nokta_sayisi"), o.get("riskli_nokta_sayisi")],
                ["maks yanal sapma (km)", n.get("maks_yanal_sapma_km"), o.get("maks_yanal_sapma_km")],
                ["SIGMET ihlali", n.get("sigmet_ihlali_sayisi"), o.get("sigmet_ihlali_sayisi")],
                ["kısıtlı saha ihlali", n.get("kisitli_saha_ihlali_sayisi"), o.get("kisitli_saha_ihlali_sayisi")],
            ],
        )
        sk, kk = y.get("sigmet_kontrolu") or {}, y.get("kisitli_saha_kontrolu") or {}
        g.tablo(
            ["alan", "değer"],
            [
                ["rüzgâr verisi kaynağı", y["ruzgar_verisi_kaynagi"]],
                ["kaçınma stratejisi", y["kacinma_stratejisi"]],
                ["türbülanstan kaçınıldı mı", y["turbulanstan_kacinildi_mi"]],
                ["güvenli rota bulundu mu", y["guvenli_rota_bulundu_mu"]],
                [
                    "SIGMET kontrolü",
                    f"{sk.get('durum')} (aktif {sk.get('aktif_sigmet_sayisi')}, bayat={sk.get('bayat_mi')})",
                ],
                [
                    "kısıtlı saha kontrolü",
                    f"{kk.get('durum')} (uygulanan {kk.get('uygulanan_saha_sayisi')}, örnek veri={kk.get('ornek_veri_mi')}, muaf={kk.get('muaf_tutulanlar')})",
                ],
                ["süre tasarrufu (dk) / yakıt %", f"{y['sure_tasarrufu_dk']} / {y['yakit_tasarrufu_yuzde']}"],
                [
                    "uyarı/kritik bulgular",
                    ", ".join(b["kod"] for b in y.get("bulgular", []) if b["seviye"] != "bilgi") or "—",
                ],
                ["yanıt süresi (sn)", f"{toplam_sure:.2f} ({deneme} istek)"],
            ],
        )
        print(g.r("  açıklama: ", "gri") + kisalt(y["aciklama"], 400))
        print(g.r("  TI1 notu: ", "gri") + kisalt(y["ti1_guvenilirlik_notu"], 200))
        g.duraklat()


def senaryo_turbulans(g):
    noktalar = [
        (
            "turb_1_era5",
            "ERA5 kapsamında (Ankara üstü, 2019-01-15 12:00, 35000 ft)",
            {"enlem": 40.0, "boylam": 33.0, "irtifa_ft": 35000, "zaman": "2019-01-15T12:00:00"},
        ),
        (
            "turb_2_kapsam_disi",
            "Kapsam dışı (aynı nokta, 2018-06-15)",
            {"enlem": 40.0, "boylam": 33.0, "irtifa_ft": 35000, "zaman": "2018-06-15T12:00:00"},
        ),
        (
            "turb_3_canli_gfs",
            "Canlı GFS (Doğu Anadolu, şimdi+1 sa)",
            {"enlem": 37.5, "boylam": 40.5, "irtifa_ft": 35000, "zaman": canli_zaman(1)},
        ),
    ]
    g.adim("Nokta türbülans tahmini: TI1 (fizik) + ML olasılığı (POST /turbulans/tahmin)")
    satirlar = []
    for ad, aciklama, govde in noktalar:
        kod, sure, y = g.istek("POST", "/api/v1/turbulans/tahmin", govde, rol="pilot")
        y = y if isinstance(y, dict) else {"aciklama": y}
        g.kaydet_yanit(
            ad,
            "POST",
            "/api/v1/turbulans/tahmin",
            kod,
            sure,
            y,
            govde,
            ozet=f"kapsam={y.get('kapsam_icinde_mi')} ti1={y.get('ti1_indeksi')} ml={y.get('ml_olasilik')}",
        )
        satirlar.append(
            [
                aciklama,
                g.http_isareti(kod),
                f"{sure:.2f}",
                y.get("kapsam_icinde_mi"),
                y.get("ti1_indeksi"),
                y.get("ti1_riskli_mi"),
                y.get("ml_olasilik"),
                y.get("ml_risk_durumu"),
            ]
        )
    g.tablo(["nokta", "HTTP", "sn", "kapsamda", "TI1", "TI1 riskli", "ML olasılık", "ML durum"], satirlar)
    print(g.r("  TI1 notu: ", "gri") + kisalt(y.get("ti1_guvenilirlik_notu"), 200))
    g.duraklat()


def senaryo_veri(g):
    g.adim("Sağlık raporu (GET /saglik?derin=true) ve sistem durumu (GET /sistem/durum)")
    kod, sure, y = g.istek("GET", "/saglik?derin=true", rol=None)
    g.kaydet_yanit("saglik_derin", "GET", "/saglik?derin=true", kod, sure, y, ozet=str((y or {}).get("durum")))
    kod2, sure2, y2 = g.istek("GET", "/api/v1/sistem/durum")
    g.kaydet_yanit("sistem_durum", "GET", "/api/v1/sistem/durum", kod2, sure2, y2, ozet=str((y2 or {}).get("durum")))
    if kod == 200:
        print(
            f"  genel durum: {g.r(y['durum'], 'yesil' if y['durum'] == 'ayakta' else 'sari')} · veritabanı: {y.get('veritabani')}"
        )
        g.tablo(["kontrol", "durum"], [[ad, d.get("durum")] for ad, d in (y.get("kontroller") or {}).items()])
        for u in y.get("uyarilar") or []:
            print(g.r("  uyarı: ", "sari") + kisalt(u, 200))
    g.duraklat()

    g.adim("Hava durumu küpü kataloğu (GET /veri/kupler)")
    kod, sure, kupler = g.istek("GET", "/api/v1/veri/kupler")
    g.kaydet_yanit("veri_kupler", "GET", "/api/v1/veri/kupler", kod, sure, kupler, ozet=f"{len(kupler or [])} küp")
    if kod == 200:
        g.tablo(
            ["kaynak", "geçerlilik", "kutu", "seviye", "durum", "MB"],
            [
                [
                    k["kaynak"],
                    f"{k['gecerlilik_baslangic'][:13]} → {k['gecerlilik_bitis'][:13]}",
                    f"{k['enlem_min']:.0f}..{k['enlem_maks']:.0f} / {k['boylam_min']:.0f}..{k['boylam_maks']:.0f}",
                    len(k["basinc_seviyeleri_hpa"]),
                    k["durum"],
                    round((k.get("boyut_bayt") or 0) / 1e6, 1),
                ]
                for k in kupler[:15]
            ],
        )
        if len(kupler) > 15:
            print(g.r(f"  … toplam {len(kupler)} küp", "gri"))
    g.duraklat()

    g.adim("AWC'den canlı SIGMET güncelle (POST /sigmet/guncelle) ve listele (GET /sigmet)")
    kod, sure, y = g.istek("POST", "/api/v1/sigmet/guncelle")
    g.kaydet_yanit(
        "sigmet_guncelle",
        "POST",
        "/api/v1/sigmet/guncelle",
        kod,
        sure,
        y,
        ozet=f"kaydedilen={(y or {}).get('kaydedilen')}",
    )
    kod2, sure2, sigmetler = g.istek("GET", "/api/v1/sigmet", rol="pilot")
    sigmetler = sigmetler if isinstance(sigmetler, list) else []
    firler = {}
    for s in sigmetler:
        firler[s.get("fir_kodu")] = firler.get(s.get("fir_kodu"), 0) + 1
    g.kaydet_yanit(
        "sigmet_liste",
        "GET",
        "/api/v1/sigmet",
        kod2,
        sure2,
        sigmetler,
        ozet=f"{len(sigmetler)} SIGMET, LTAA={firler.get('LTAA', 0)}",
    )
    g.tablo(
        ["ölçüt", "değer"],
        [
            ["güncelleme HTTP / süre", f"{g.http_isareti(kod)} / {sure:.2f} sn"],
            [
                "kaydedilen / sonlandırılan / silinen",
                f"{(y or {}).get('kaydedilen')} / {(y or {}).get('sonlandirilan')} / {(y or {}).get('silinen')}",
            ],
            ["kaynak hataları", (y or {}).get("kaynak_hatalari") or "yok"],
            ["şu an geçerli SIGMET", len(sigmetler)],
            ["Ankara FIR (LTAA) SIGMET", firler.get("LTAA", 0)],
            ["İstanbul FIR (LTBB) SIGMET", firler.get("LTBB", 0)],
            [
                "en çok SIGMET olan FIR'lar",
                ", ".join(f"{k}:{v}" for k, v in sorted(firler.items(), key=lambda x: -x[1])[:6]),
            ],
        ],
    )
    g.duraklat()

    g.adim("Kısıtlı hava sahaları (GET /kisitli-sahalar)")
    kod, sure, sahalar = g.istek("GET", "/api/v1/kisitli-sahalar", rol="pilot")
    sahalar = sahalar if isinstance(sahalar, list) else []
    g.kaydet_yanit("kisitli_sahalar", "GET", "/api/v1/kisitli-sahalar", kod, sure, sahalar, ozet=f"{len(sahalar)} saha")
    kaynaklar = {}
    for s in sahalar:
        kaynaklar[s.get("kaynak")] = kaynaklar.get(s.get("kaynak"), 0) + 1
    g.tablo(["kaynak", "saha sayısı"], [[k, v] for k, v in kaynaklar.items()] or [["—", 0]])
    g.duraklat()

    g.adim("Canlı GFS küpünü hazırla: Türkiye kutusu, 6 saat (POST /veri/canli/hazirla) ve görev izle")
    govde = {
        "enlem_min": 36.0,
        "enlem_maks": 42.0,
        "boylam_min": 26.0,
        "boylam_maks": 45.0,
        "baslangic": canli_zaman(0),
        "saat_sayisi": 6,
    }
    kod, sure, y = g.istek("POST", "/api/v1/veri/canli/hazirla", govde)
    baslangic = time.perf_counter()
    durum = y
    if kod == 202 and isinstance(y, dict):
        while time.perf_counter() - baslangic < 300:
            _, _, durum = g.istek("GET", f"/api/v1/analiz/durum/{y['gorev_id']}")
            if durum.get("durum") not in ("kuyrukta", "calisiyor"):
                break
            time.sleep(2)
    gecen = time.perf_counter() - baslangic
    g.kaydet_yanit(
        "canli_hazirla",
        "POST",
        "/api/v1/veri/canli/hazirla",
        kod,
        sure + gecen,
        {"baslatma": y, "son_durum": durum},
        govde,
        ozet=f"{(durum or {}).get('durum')} {gecen:.1f} sn",
    )
    g.tablo(
        ["ölçüt", "değer"],
        [
            ["başlatma HTTP", g.http_isareti(kod, (202,))],
            ["son durum", (durum or {}).get("durum")],
            ["toplam süre (sn)", f"{gecen:.1f}"],
            ["özet", kisalt((durum or {}).get("ozet"), 150)],
            ["açıklama", kisalt((durum or {}).get("aciklama"), 150)],
        ],
    )
    g.duraklat()


def senaryo_ucus(g, ucus="THY322", tarih="2019-01-15"):
    g.adim("Veritabanındaki kayıtlı uçuşlar (GET /ucuslar)")
    kod, sure, y = g.istek("GET", "/api/v1/ucuslar?limit=50", rol="pilot")
    g.kaydet_yanit("ucuslar_liste", "GET", "/api/v1/ucuslar", kod, sure, y, ozet=f"{(y or {}).get('toplam_sayi')} uçuş")
    if kod == 200:
        g.tablo(
            ["uçuş", "tarih", "kalkış", "varış", "kayıt zamanı"],
            [
                [
                    u["ucus_numarasi"],
                    u["tarih"],
                    u.get("kalkis_havaalani"),
                    u.get("varis_havaalani"),
                    u["olusturulma_zamani"][:19],
                ]
                for u in y["ucuslar"]
            ],
        )
    g.duraklat()

    g.adim(f"{ucus} {tarih}: ölçümler, CSV, GeoJSON ve SIGMET doğrulaması")
    satirlar = []
    kod, sure, y = g.istek("GET", f"/api/v1/ucuslar/{ucus}/{tarih}?olcum_limit=5000", rol="pilot")
    olcumler = (y or {}).get("olcumler", []) if isinstance(y, dict) else []
    ti1 = [o["ti1_indeksi"] for o in olcumler if o.get("ti1_indeksi") is not None]
    g.kaydet_yanit(
        "ucus_detay",
        "GET",
        f"/api/v1/ucuslar/{ucus}/{tarih}",
        kod,
        sure,
        {
            "ucus": (y or {}).get("ucus") if isinstance(y, dict) else y,
            "toplam_olcum_sayisi": (y or {}).get("toplam_olcum_sayisi") if isinstance(y, dict) else None,
            "ilk_5_olcum": olcumler[:5],
        },
        ozet=f"{len(olcumler)} ölçüm, TI1'li {len(ti1)}",
    )
    satirlar.append(
        [
            "detay (JSON)",
            g.http_isareti(kod),
            f"{sure:.2f}",
            f"{len(olcumler)} ölçüm; TI1 hesaplanan {len(ti1)}; maks TI1 {max(ti1) if ti1 else '—'}",
        ]
    )
    for uzanti in ("csv", "geojson"):
        kod, sure, icerik = g.istek("GET", f"/api/v1/ucuslar/{ucus}/{tarih}/{uzanti}", rol="pilot", ham=True)
        g.kaydet_yanit(
            f"ucus_{uzanti}",
            "GET",
            f"/api/v1/ucuslar/{ucus}/{tarih}/{uzanti}",
            kod,
            sure,
            {"bayt": len(icerik) if isinstance(icerik, bytes) else None},
            ozet=f"{len(icerik) if isinstance(icerik, bytes) else 0} bayt",
        )
        satirlar.append(
            [uzanti, g.http_isareti(kod), f"{sure:.2f}", f"{len(icerik) if isinstance(icerik, bytes) else 0} bayt"]
        )
    kod, sure, y = g.istek("GET", f"/api/v1/ucuslar/{ucus}/{tarih}/sigmet-dogrulama", rol="pilot", zaman_asimi=120)
    g.kaydet_yanit(
        "ucus_sigmet_dogrulama",
        "GET",
        f"/api/v1/ucuslar/{ucus}/{tarih}/sigmet-dogrulama",
        kod,
        sure,
        y,
        ozet=kisalt(y, 80),
    )
    satirlar.append(
        [
            "sigmet-dogrulama",
            g.http_isareti(kod),
            f"{sure:.2f}",
            kisalt({k: v for k, v in y.items() if k != "sigmetler"} if isinstance(y, dict) else y, 90),
        ]
    )
    g.tablo(["uç nokta", "HTTP", "sn", "sonuç"], satirlar)
    g.duraklat()


def senaryo_ml(g):
    g.adim("ML model bilgisi, sürümleri ve veri hattı durumu")
    kod, sure, bilgi = g.istek("GET", "/api/v1/turbulans/model-bilgisi", rol="pilot")
    g.kaydet_yanit(
        "ml_model_bilgisi",
        "GET",
        "/api/v1/turbulans/model-bilgisi",
        kod,
        sure,
        bilgi,
        ozet=f"{(bilgi or {}).get('secilen_model')}",
    )
    kod2, sure2, surumler = g.istek("GET", "/api/v1/turbulans/model-versiyonlari", rol="pilot")
    g.kaydet_yanit(
        "ml_model_versiyonlari",
        "GET",
        "/api/v1/turbulans/model-versiyonlari",
        kod2,
        sure2,
        surumler,
        ozet=f"{len(surumler or [])} sürüm",
    )
    kod3, sure3, durum = g.istek("GET", "/api/v1/ml/durum")
    g.kaydet_yanit(
        "ml_durum",
        "GET",
        "/api/v1/ml/durum",
        kod3,
        sure3,
        durum,
        ozet=f"eşleşmiş gün {(durum or {}).get('eslesmis_gun_sayisi')}",
    )
    m = (bilgi or {}).get("metrikler") or {}
    duz = {k: v for k, v in m.items() if isinstance(v, (int, float))}
    g.tablo(
        ["alan", "değer"],
        [
            ["eğitildi mi / kullanımda", f"{(bilgi or {}).get('egitildi_mi')} / {(bilgi or {}).get('kullanimda')}"],
            ["seçilen model", (bilgi or {}).get("secilen_model")],
            ["eğitim zamanı", (bilgi or {}).get("egitim_zamani")],
            [
                "eğitim / test örnek",
                f"{(bilgi or {}).get('egitim_orneklem_sayisi')} / {(bilgi or {}).get('test_orneklem_sayisi')}",
            ],
            *[[f"metrik: {k}", v] for k, v in list(duz.items())[:10]],
            ["kayıtlı sürüm sayısı", len(surumler or [])],
            [
                "örnekler (eşleşti/bekliyor/kapsam dışı)",
                f"{((durum or {}).get('ornekler') or {}).get('eslesti')} / {((durum or {}).get('ornekler') or {}).get('bekliyor')} / {((durum or {}).get('ornekler') or {}).get('kapsam_disi')}",
            ],
            [
                "eşleşmiş gün / gereken",
                f"{(durum or {}).get('eslesmis_gun_sayisi')} / {(durum or {}).get('egitim_icin_gereken_gun')}",
            ],
            [
                "bugün veri (MB) / bütçe",
                f"{(durum or {}).get('veri_bugun_mb')} / {(durum or {}).get('veri_gunluk_butce_mb')}",
            ],
            ["aktif sürüm", ((durum or {}).get("aktif_model") or {}).get("versiyon_id")],
            ["son görev", ", ".join(f"{x['tur']}:{x['durum']}" for x in ((durum or {}).get("son_gorevler") or [])[:3])],
        ],
    )
    if bilgi and bilgi.get("uyari"):
        print(g.r("  uyarı: ", "sari") + kisalt(bilgi["uyari"], 300))
    g.duraklat()


def senaryo_backtest(g):
    g.adim("Backtest: gerçek iz vs büyük daire vs A* (GET /backtest)")
    kod, sure, y = g.istek("GET", "/api/v1/backtest", rol="pilot")
    g.kaydet_yanit(
        "backtest", "GET", "/api/v1/backtest", kod, sure, y, ozet=f"{len((y or {}).get('sonuclar', []))} uçuş"
    )
    if kod != 200:
        print(g.r(f"  HATA HTTP {kod}", "kirmizi"))
        return
    g.tablo(
        ["uçuş", "tarih", "FL", "strateji", "riskli oran (gerçek / BD / A*)", "mesafe km (gerçek / BD / A*)", "kanıt"],
        [
            [
                s["ucus_numarasi"],
                s["tarih"],
                round(s["seyir_irtifasi_ft"] / 100),
                s["kacinma_stratejisi"],
                f"{kisalt(s['gercek_riskli_oran'])} / {kisalt(s['buyuk_daire_riskli_oran'])} / {kisalt(s['optimize_riskli_oran'])}",
                f"{s['gercek_mesafe_km']:.0f} / {s['buyuk_daire_mesafe_km']:.0f} / {s['optimize_mesafe_km']:.0f}",
                s.get("kanit_kaynaklari") or "yok",
            ]
            for s in y["sonuclar"]
        ],
    )
    g.tablo(["özet alanı", "değer"], [[k, v] for k, v in (y.get("ozet") or {}).items()])
    g.duraklat()


def ws_el_sikismasi(taban_url, sorgu=""):
    adres = taban_url.split("://", 1)[1].split("/")[0]
    ana, port = (adres.split(":") + ["80"])[:2]
    try:
        with socket.create_connection((ana, int(port)), timeout=10) as s:
            s.sendall(
                (
                    f"GET /ws/uyarilar{sorgu} HTTP/1.1\r\nHost: {adres}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                    "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n"  # gitleaks:allow
                ).encode()
            )
            return s.recv(200).decode(errors="replace").split("\r\n")[0]
    except OSError as hata:
        return f"bağlantı hatası: {hata}"


def senaryo_guvenlik(g):
    g.adim("Güvenlik: anahtarsız, yanlış anahtar, pilot rolüyle yönetici işlemi, biletsiz WebSocket")
    denemeler = [
        ("anahtarsız GET /ucuslar", "GET", "/api/v1/ucuslar", None, (401,)),
        ("yanlış anahtar GET /ucuslar", "GET", "/api/v1/ucuslar", "yanlis", (401,)),
        ("pilot GET /sistem/durum", "GET", "/api/v1/sistem/durum", "pilot", (403,)),
        ("pilot POST /sigmet/guncelle", "POST", "/api/v1/sigmet/guncelle", "pilot", (403,)),
        ("pilot DELETE /kisitli-sahalar/yok", "DELETE", "/api/v1/kisitli-sahalar/denetim-yok", "pilot", (403,)),
        ("pilot DELETE /ucuslar (toplu)", "DELETE", "/api/v1/ucuslar?ucus_numarasi_arama=ZZZ", "pilot", (403,)),
        ("anahtarsız GET /saglik", "GET", "/saglik", None, (200,)),
    ]
    satirlar = []
    for ad, yontem, yol, rol, beklenen in denemeler:
        kod, sure, y = g.istek(yontem, yol, rol=rol)
        satirlar.append([ad, "/".join(map(str, beklenen)), g.http_isareti(kod, beklenen), f"{sure:.3f}"])
        g.kayitlar.append(
            {
                "senaryo": "guvenlik:" + ad,
                "yontem": yontem,
                "yol": yol,
                "http": kod,
                "sure_sn": round(sure, 3),
                "ozet": "beklenen " + "/".join(map(str, beklenen)),
            }
        )
    for ad, sorgu in (
        ("biletsiz WS /ws/uyarilar", ""),
        ("?api_key= ile WS", "?api_key=" + g.anahtarlar.get("API_ANAHTARI", "")),
        ("sahte bilet ile WS", "?bilet=sahte"),
    ):
        ilk_satir = ws_el_sikismasi(g.taban_url, sorgu)
        reddedildi = " 101 " not in ilk_satir + " "
        satirlar.append([ad, "red (101 değil)", ("✅ " if reddedildi else "❌ ") + ilk_satir[:40], "—"])
        g.kayitlar.append(
            {
                "senaryo": "guvenlik:" + ad,
                "yontem": "WS",
                "yol": "/ws/uyarilar",
                "http": ilk_satir[:40],
                "sure_sn": None,
                "ozet": "reddedildi" if reddedildi else "KABUL EDİLDİ",
            }
        )
    g.tablo(["deneme", "beklenen", "sonuç", "sn"], satirlar)
    if g.kaydet:
        (g.kaydet / "guvenlik.json").write_text(json.dumps(satirlar, ensure_ascii=False, indent=1), encoding="utf-8")
    g.duraklat()


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Türbülans Radar API demo/denetim senaryoları (terminal tabloları)."
    )
    ayristirici.add_argument("--senaryo", choices=[*SENARYOLAR, "hepsi"], default="hepsi")
    ayristirici.add_argument("--bekle", action="store_true", help="Her adımdan sonra Enter bekler (sunum modu)")
    ayristirici.add_argument("--taban-url", default=os.environ.get("TURBULANS_TABAN_URL", "http://localhost:8000"))
    ayristirici.add_argument("--kaydet", metavar="KLASOR", help="Her yanıtı KLASOR/<senaryo>.json olarak kaydeder")
    ayristirici.add_argument("--renksiz", action="store_true")
    argumanlar = ayristirici.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if os.name == "nt":
        os.system("")
    g = Gosterici(
        argumanlar.taban_url, argumanlar.bekle, argumanlar.kaydet, not argumanlar.renksiz and sys.stdout.isatty()
    )
    eksik = [a for a in ("API_ANAHTARI", "API_PILOT_ANAHTARI") if not g.anahtarlar.get(a)]
    print(
        g.r("Türbülans Radar — demo/denetim", "kalin")
        + f" · {g.taban_url} · anahtarlar: "
        + ("eksik " + ", ".join(eksik) if eksik else "tanımlı")
    )
    print(g.r("Çıktılar sertifikalı EDR değildir; karar destek aracıdır, operasyonel karar aracı değildir.", "gri"))
    kod, _, saglik = g.istek("GET", "/saglik", rol=None, zaman_asimi=10)
    if kod != 200:
        print(g.r(f"API'ye ulaşılamadı ({kod}: {kisalt(saglik, 120)}). Önce: docker compose up -d", "kirmizi"))
        return 2
    calisacaklar = SENARYOLAR if argumanlar.senaryo == "hepsi" else [argumanlar.senaryo]
    for ad in calisacaklar:
        print("\n" + g.r(f"══ {ad.upper()} ══", "kalin"))
        globals()[f"senaryo_{ad}"](g)
    print("\n" + g.r("══ ÖZET ══", "kalin"))
    g.tablo(
        ["senaryo", "yöntem", "HTTP", "sn", "özet"],
        [[k["senaryo"], k["yontem"], k["http"], k["sure_sn"], k["ozet"]] for k in g.kayitlar],
    )
    if g.kaydet:
        (g.kaydet / "_ozet.json").write_text(json.dumps(g.kayitlar, ensure_ascii=False, indent=1), encoding="utf-8")
        print(g.r(f"Yanıtlar kaydedildi: {g.kaydet}", "gri"))
    return 0


if __name__ == "__main__":
    sys.exit(ana())
