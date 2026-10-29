"""
bagimsiz_backtest.py
-----------------------
Bağımsız (döngüsel olmayan) rota backtest'i (kurul raporu #3, deney_protokolu.md §11).
NE-ABD ERA5 küplerinde (era5_egitim_verisi/), ağsız, sabit şehir çiftleri × küp günleri ×
kalkış saatleri × FL için büyük daire ve A* rotası üretilir; her rotanın PIREP tüpündeki
orta-üstü (M) ve kontrol (N) raporları yerel IEM arşivinden (pirep_ham/) sayılır.
Birincil ölçüt, sapmalı rotalarda göreli maruziyet oranı
GMO = (ΣM_A* / ΣN_A*) / (ΣM_BD / ΣN_BD), kalkış gününe göre bloklu bootstrap ile.
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import glob
import json
import os
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.dogrulama.bagimsiz_kanit import _KONUM_BILINMIYOR_DESENI, pirep_siddet_sinifi, tupteki_pirepler
from turbulans_radar.dogrulama.rota_backtest import _simulasyon_rotasi

SEHIR_CIFTLERI = (
    ("JFK→YUL", 40.64, -73.78, 45.47, -73.74),
    ("BOS→YYZ", 42.36, -71.01, 43.68, -79.63),
    ("EWR→YQB", 40.69, -74.17, 46.79, -71.39),
    ("YYZ→BDL", 43.68, -79.63, 41.94, -72.68),
    ("SYR→BOS", 43.11, -76.11, 42.36, -71.01),
    ("YOW→JFK", 45.32, -75.67, 40.64, -73.78),
    ("ROC→YQB", 43.12, -77.67, 46.79, -71.39),
    ("BUF→BOS", 42.94, -78.73, 42.36, -71.01),
)
VARSAYILAN_SAATLER = (12, 15, 18)
VARSAYILAN_SEVIYELER_FT = (34000, 37000)
VARSAYILAN_KUP_KLASORU = "era5_egitim_verisi"
KUTU = (40.0, 50.0, -80.0, -70.0)
_KUTU_PAYI_DERECE = 0.5
_ZAMAN_PENCERESI = (pd.Timedelta(hours=-2), pd.Timedelta(hours=5))
BOOTSTRAP_TEKRARI = 2000
EN_AZ_TUP_RAPORU = 30
ETIKETLER = ("proje", "net")


def kup_gunleri(klasor=VARSAYILAN_KUP_KLASORU) -> list[str]:
    import xarray as xr

    gunler: set[str] = set()
    for dosya in sorted(glob.glob(os.path.join(klasor, "*.nc"))):
        with xr.open_dataset(dosya) as kup:
            gunler |= set(pd.DatetimeIndex(kup["valid_time"].values).strftime("%Y-%m-%d"))
    return sorted(gunler)


def senaryolari_uret(gunler, saatler=VARSAYILAN_SAATLER, seviyeler_ft=VARSAYILAN_SEVIYELER_FT, ciftler=SEHIR_CIFTLERI):
    for gun in gunler:
        for saat in saatler:
            kalkis = (datetime.fromisoformat(gun) + timedelta(hours=saat)).strftime("%Y-%m-%dT%H:%M:%S")
            for ad, enlem1, boylam1, enlem2, boylam2 in ciftler:
                for seviye in seviyeler_ft:
                    yield ad, (enlem1, boylam1, enlem2, boylam2, seviye, kalkis)


def pirepleri_hazirla(ham: pd.DataFrame, gunler=None, kutu=KUTU) -> pd.DataFrame:
    """Ham IEM satırlarından tüp sayımı için PIREP tablosu: seyir irtifası, kutu (±0,5°) ve günler
    içinde, /OV UNK hariç, yinelenenler atılmış. sinif: proje etiketi; net: 1/0/NaN."""
    from turbulans_radar.ml.duyarlilik_analizi import net_etiket

    if "REPORT" in ham.columns:
        ham = ham[~ham["REPORT"].fillna("").str.contains(_KONUM_BILINMIYOR_DESENI)]
    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(ham["VALID"], format="%Y%m%d%H%M", utc=True, errors="coerce"),
            "enlem": pd.to_numeric(ham["LAT"], errors="coerce"),
            "boylam": pd.to_numeric(ham["LON"], errors="coerce"),
            "irtifa_ft": pd.to_numeric(ham["FL"], errors="coerce"),
            "metin": ham["TURBULENCE"],
        }
    ).dropna()
    enlem_min, enlem_maks, boylam_min, boylam_maks = kutu
    df = df[
        df["enlem"].between(enlem_min - _KUTU_PAYI_DERECE, enlem_maks + _KUTU_PAYI_DERECE)
        & df["boylam"].between(boylam_min - _KUTU_PAYI_DERECE, boylam_maks + _KUTU_PAYI_DERECE)
        & df["irtifa_ft"].between(config.ML_MIN_IRTIFA_FT, config.ML_MAKS_IRTIFA_FT)
    ]
    if gunler is not None:
        df = df[df["zaman"].dt.strftime("%Y-%m-%d").isin(set(gunler))]
    df = df.assign(sinif=df["metin"].map(pirep_siddet_sinifi), net=df["metin"].map(net_etiket))
    df = df[df["sinif"].notna()].drop_duplicates(["zaman", "enlem", "boylam", "irtifa_ft", "metin"])
    return df.astype({"sinif": int}).drop(columns="metin").reset_index(drop=True)


def arsiv_pireplerini_oku(gunler, klasor=None) -> pd.DataFrame:
    klasor = klasor or config.ML_PIREP_ARSIV_KLASORU
    sutunlar = {"VALID", "REPORT", "TURBULENCE", "FL", "LAT", "LON"}
    parcalar = [
        pirepleri_hazirla(pd.read_csv(d, dtype=str, on_bad_lines="skip", usecols=lambda s: s in sutunlar), gunler)
        for d in sorted(glob.glob(os.path.join(klasor, "*.csv")))
    ]
    if not parcalar:
        raise FileNotFoundError(f"IEM PIREP arşivi bulunamadı: {klasor}")
    tum = pd.concat(parcalar, ignore_index=True)
    return tum.drop_duplicates(["zaman", "enlem", "boylam", "irtifa_ft", "sinif", "net"]).reset_index(drop=True)


def _sayimlar(pirepler: pd.DataFrame, indeksler) -> dict:
    alt = pirepler.loc[sorted(indeksler)]
    return {
        "proje_m": int((alt["sinif"] >= 1).sum()),
        "proje_n": int((alt["sinif"] == 0).sum()),
        "net_m": int((alt["net"] == 1).sum()),
        "net_n": int((alt["net"] == 0).sum()),
    }


def kaydi_cikar(ad, girdi, sonuc, pirepler: pd.DataFrame) -> dict:
    kayit = {
        "cift": ad,
        "fl": int(girdi[4] // 100),
        "kalkis": girdi[5],
        "gun": girdi[5][:10],
        "veri": sonuc["ruzgar_verisi_kaynagi"],
        "strateji": sonuc["kacinma_stratejisi"],
        "sapma": sonuc["kacinma_stratejisi"] != "yok",
        "bd_riskli_nokta": sonuc["normal_rota"].get("riskli_nokta_sayisi"),
        "astar_riskli_nokta": sonuc["optimize_rota"].get("riskli_nokta_sayisi"),
        "astar_fl": sonuc["optimize_rota"].get("fl"),
    }
    kalkis = pd.Timestamp(girdi[5], tz="UTC")
    pencere = pirepler[pirepler["zaman"].between(kalkis + _ZAMAN_PENCERESI[0], kalkis + _ZAMAN_PENCERESI[1])]
    tupler = {
        rota: set(tupteki_pirepler(pencere, *_simulasyon_rotasi(sonuc[anahtar])).index)
        for rota, anahtar in (("bd", "normal_rota"), ("astar", "optimize_rota"))
    }
    for rota, kume in (
        ("bd", tupler["bd"]),
        ("astar", tupler["astar"]),
        ("kacinilan", tupler["bd"] - tupler["astar"]),
        ("girilen", tupler["astar"] - tupler["bd"]),
    ):
        kayit.update({f"{rota}_{k}": v for k, v in _sayimlar(pirepler, kume).items()})
    return kayit


def olcum_yap(senaryolar, pirepler: pd.DataFrame, rota_fonksiyonu=None) -> list[dict]:
    if rota_fonksiyonu is None:
        from turbulans_radar.rota.rota_optimizasyonu import rota_simulasyonu_olustur as rota_fonksiyonu
    eski = (config.ERA5_OTOMATIK_INDIRME, config.CANLI_HAVA_VERISI_ETKIN, config.ROTA_SECIM_KURALI)
    config.ERA5_OTOMATIK_INDIRME = config.CANLI_HAVA_VERISI_ETKIN = False
    config.ROTA_SECIM_KURALI = "sozluksel"
    kayitlar = []
    try:
        for ad, girdi in senaryolar:
            try:
                sonuc = rota_fonksiyonu(*girdi, "A320", sigmetler=[], kisitli_sahalar=[])
                kayitlar.append(kaydi_cikar(ad, girdi, sonuc, pirepler))
            except Exception as hata:
                kayitlar.append({"cift": ad, "fl": int(girdi[4] // 100), "kalkis": girdi[5], "hata": str(hata)})
    finally:
        config.ERA5_OTOMATIK_INDIRME, config.CANLI_HAVA_VERISI_ETKIN, config.ROTA_SECIM_KURALI = eski
    return kayitlar


def gecerli_kayitlar(kayitlar) -> list[dict]:
    return [
        k
        for k in kayitlar
        if "hata" not in k
        and k["veri"] == "era5_gercek"
        and k["bd_riskli_nokta"] is not None
        and k["astar_riskli_nokta"] is not None
    ]


def _oran(m, n):
    return None if n == 0 else m / n


def gmo(toplamlar) -> float | None:
    """toplamlar: (M_A*, N_A*, M_BD, N_BD); herhangi bir payda ya da M_BD 0 ise None."""
    m_a, n_a, m_b, n_b = toplamlar
    if n_a == 0 or n_b == 0 or m_b == 0:
        return None
    return (m_a / n_a) / (m_b / n_b)


def gmo_ozeti(kayitlar, etiket="proje", tekrar=BOOTSTRAP_TEKRARI, tohum=0) -> dict:
    sutunlar = [f"astar_{etiket}_m", f"astar_{etiket}_n", f"bd_{etiket}_m", f"bd_{etiket}_n"]
    gunler = sorted({k["gun"] for k in kayitlar})
    gunluk = np.zeros((len(gunler), 4))
    sira = {g: i for i, g in enumerate(gunler)}
    for k in kayitlar:
        gunluk[sira[k["gun"]]] += [k[s] for s in sutunlar]
    toplam = gunluk.sum(axis=0)
    ozet = {
        "rota": len(kayitlar),
        "gun": len(gunler),
        "astar_m": int(toplam[0]),
        "astar_n": int(toplam[1]),
        "bd_m": int(toplam[2]),
        "bd_n": int(toplam[3]),
        "astar_orta_ustu_payi": _oran(toplam[0], toplam[0] + toplam[1]),
        "bd_orta_ustu_payi": _oran(toplam[2], toplam[2] + toplam[3]),
        "gmo": gmo(toplam),
        "ga": None,
        "gecersiz_tekrar": None,
    }
    if ozet["gmo"] is None or len(gunler) < 2:
        return ozet
    rng = np.random.default_rng(tohum)
    degerler = []
    for _ in range(tekrar):
        secim = rng.integers(0, len(gunler), len(gunler))
        deger = gmo(gunluk[secim].sum(axis=0))
        if deger is not None:
            degerler.append(deger)
    ozet["gecersiz_tekrar"] = tekrar - len(degerler)
    if degerler:
        ozet["ga"] = [float(np.percentile(degerler, 2.5)), float(np.percentile(degerler, 97.5))]
    return ozet


def fark_tupu_ozeti(kayitlar, etiket="proje") -> dict:
    sonuc = {}
    for rota in ("kacinilan", "girilen"):
        m = sum(k[f"{rota}_{etiket}_m"] for k in kayitlar)
        n = sum(k[f"{rota}_{etiket}_n"] for k in kayitlar)
        sonuc[rota] = {"m": m, "n": n, "orta_ustu_payi": _oran(m, m + n)}
    return sonuc


def karar_okumasi(ozet) -> str:
    if (ozet["astar_m"] + ozet["astar_n"] + ozet["bd_m"] + ozet["bd_n"]) < EN_AZ_TUP_RAPORU or ozet["gmo"] is None:
        return "yetersiz_orneklem"
    if ozet["ga"] is None:
        return "yetersiz_orneklem"
    if ozet["ga"][1] < 1.0:
        return "azaltti"
    if ozet["ga"][0] > 1.0:
        return "artirdi"
    return "fark_gosterilemedi"


def ozetle(kayitlar, bagimli_gunler) -> dict:
    gecerli = gecerli_kayitlar(kayitlar)
    bagimli_gunler = set(bagimli_gunler)
    bagimsiz = [k for k in gecerli if k["gun"] not in bagimli_gunler]
    sapmali = [k for k in bagimsiz if k["sapma"]]
    birincil = gmo_ozeti(sapmali)
    ikincil = {
        "tum_gunler_sapmali": gmo_ozeti([k for k in gecerli if k["sapma"]]),
        "tum_senaryolar": gmo_ozeti(bagimsiz),
        "net_etiket_sapmali": gmo_ozeti(sapmali, "net"),
        "fark_tupu": fark_tupu_ozeti(sapmali),
        "fark_tupu_net": fark_tupu_ozeti(sapmali, "net"),
        "fl": {str(fl): gmo_ozeti([k for k in sapmali if k["fl"] == fl]) for fl in sorted({k["fl"] for k in sapmali})},
        "strateji": {
            s: gmo_ozeti([k for k in sapmali if k["strateji"] == s]) for s in sorted({k["strateji"] for k in sapmali})
        },
        "dongusel_ti1": {
            "bd_riskli_nokta": sum(k["bd_riskli_nokta"] for k in sapmali),
            "astar_riskli_nokta": sum(k["astar_riskli_nokta"] for k in sapmali),
        },
    }
    return {
        "senaryo": len(kayitlar),
        "hata": sum(1 for k in kayitlar if "hata" in k),
        "era5_disi_ya_da_risksiz": sum(1 for k in kayitlar if "hata" not in k) - len(gecerli),
        "gecerli": len(gecerli),
        "bagimsiz_gun_rotasi": len(bagimsiz),
        "sapmali_bagimsiz": len(sapmali),
        "sapma_orani": len(sapmali) / len(bagimsiz) if bagimsiz else None,
        "tupte_rapor_olan_sapmali": sum(
            1 for k in sapmali if k["bd_proje_m"] + k["bd_proje_n"] + k["astar_proje_m"] + k["astar_proje_n"] > 0
        ),
        "birincil": birincil,
        "karar": karar_okumasi(birincil),
        "ikincil": ikincil,
    }


def _sayi(x, bicim="{:.3f}"):
    return "—" if x is None else bicim.format(x)


def _ga(ozet):
    return "—" if ozet["ga"] is None else f"[{ozet['ga'][0]:.3f}; {ozet['ga'][1]:.3f}]"


def _satir(ad, o) -> str:
    return (
        f"| {ad} | {o['rota']} | {o['gun']} | {o['bd_m']} / {o['bd_n']} | {o['astar_m']} / {o['astar_n']} | "
        f"{_sayi(o['bd_orta_ustu_payi'])} | {_sayi(o['astar_orta_ustu_payi'])} | {_sayi(o['gmo'])} | {_ga(o)} |"
    )


_KARAR_METNI = {
    "azaltti": "bağımsız kanıt A*'ın orta-üstü maruziyetini azalttığını destekliyor (GA üst sınırı < 1)",
    "artirdi": "A* rotası tüpündeki raporlarda orta-üstü payı daha yüksek (GA alt sınırı > 1)",
    "fark_gosterilemedi": "fark gösterilemedi (GA 1'i içeriyor)",
    "yetersiz_orneklem": "yetersiz örneklem (tüpte 30'dan az rapor ya da payda 0)",
}


def markdown_ozeti(rapor) -> str:
    o, p = rapor["ozet"], rapor["parametreler"]
    i = o["ikincil"]
    fark = i["fark_tupu"]
    satirlar = [
        "# Bağımsız rota backtest'i (kurul #3, protokol §11)",
        "",
        f"Üretim: {rapor['uretim_zamani']} · commit `{rapor['commit'] or '—'}` · TI1 eşiği {p['ti1_esigi']:.1e} · "
        f"{len(p['ciftler'])} şehir çifti × {p['gun_sayisi']} küp günü × kalkış {p['saatler']} UTC × FL {p['fl']}; "
        "A320, koridor, `sozluksel` seçim kuralı; SIGMET/kısıtlı saha yok; ağsız (yerel NE-ABD ERA5 küpleri ve "
        "IEM PIREP arşivi). Tüp: 50 km, ±2000 ft, ±1 sa.",
        "",
        f"Senaryo {o['senaryo']}, geçerli {o['gecerli']} (hata {o['hata']}, ERA5 dışı/risk hesaplanmayan "
        f"{o['era5_disi_ya_da_risksiz']}). Bağımsız günlerde (dondurma günleri hariç) {o['bagimsiz_gun_rotasi']} "
        f"rota; sapmalı {o['sapmali_bagimsiz']} ({_sayi(o['sapma_orani'], '{:.1%}')}); tüpünde en az bir rapor "
        f"olan sapmalı rota {o['tupte_rapor_olan_sapmali']}.",
        "",
        f"**Birincil sonuç:** GMO = {_sayi(o['birincil']['gmo'])} {_ga(o['birincil'])} → {_KARAR_METNI[o['karar']]}.",
        "",
        "| Grup | Rota | Gün | BD tüpü M / N | A* tüpü M / N | BD orta-üstü payı | A* orta-üstü payı | GMO | %95 GA "
        "(gün bloklu) |",
        "|---|---|---|---|---|---|---|---|---|",
        _satir("**Birincil:** sapmalı, bağımsız günler", o["birincil"]),
        _satir("48 günün tamamı (sapmalı)", i["tum_gunler_sapmali"]),
        _satir("Tüm senaryolar (sapmasız dahil)", i["tum_senaryolar"]),
        _satir("Net etiket (LGT'siz MOD+ / NEG)", i["net_etiket_sapmali"]),
        *(_satir(f"FL{fl}", v) for fl, v in i["fl"].items()),
        *(_satir(f"Strateji: {s}", v) for s, v in i["strateji"].items()),
        "",
        f"**Fark tüpü** (sapmalı, bağımsız günler): yalnız büyük daire tüpündeki raporlar (kaçınılan) "
        f"{fark['kacinilan']['m']} / {fark['kacinilan']['n']} (orta-üstü payı "
        f"{_sayi(fark['kacinilan']['orta_ustu_payi'])}); yalnız A* tüpündekiler (girilen) "
        f"{fark['girilen']['m']} / {fark['girilen']['n']} ({_sayi(fark['girilen']['orta_ustu_payi'])}).",
        "",
        f"**Döngüsel referans (TI1):** aynı sapmalı rotalarda riskli nokta toplamı büyük daire "
        f"{i['dongusel_ti1']['bd_riskli_nokta']}, A* {i['dongusel_ti1']['astar_riskli_nokta']}.",
        "",
        "**Okuma.** M = orta-üstü (LGT-MOD dahil), N = NEG ve hafif (ML etiketiyle aynı). GMO < 1: A* tüpündeki "
        "raporlar arasında orta-üstü payı büyük daireninkinden düşük. Oran ölçütü trafik yoğunluğu farkını kısmen "
        "giderir, raporlama yanlılığını gidermez (pilotlar çoğunlukla türbülans görünce rapor verir). A* ve büyük "
        "daire tüpleri büyük ölçüde örtüşür; aynı rapor birden çok rotanın tüpüne girebilir (bu yüzden gün bloklu "
        "GA). Tek bölge, 48 gün, 3 seviyeli küp. Dondurma günleri (7) TI1 eşiğinin seçildiği PIREP'leri içerdiği "
        "için birincil sonuçtan çıkarıldı.",
        "",
        "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
    ]
    return "\n".join(satirlar) + "\n"


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="Bağımsız (PIREP tüpü) rota backtest'i, NE-ABD ERA5 küpleri (ağsız).")
    ayrac.add_argument("--kup-klasoru", default=VARSAYILAN_KUP_KLASORU)
    ayrac.add_argument("--saatler", default=",".join(str(s) for s in VARSAYILAN_SAATLER))
    ayrac.add_argument("--fl", default=",".join(str(s // 100) for s in VARSAYILAN_SEVIYELER_FT))
    ayrac.add_argument("--gun-siniri", type=int, default=None, help="Deneme için ilk N gün")
    ayrac.add_argument("--cikti", required=True, help="Rapor klasörü (örn. docs/sonuclar/2026-10-29_bagimsiz_backtest)")
    arg = ayrac.parse_args(argv)
    from turbulans_radar.fizik.ti1_esigi import etkin_ti1_esigi
    from turbulans_radar.ml.yeni_gun_degerlendirmesi import dondurma_gunleri
    from turbulans_radar.uretim_bilgisi import yazilim_commit

    gunler = kup_gunleri(arg.kup_klasoru)[: arg.gun_siniri]
    saatler = tuple(int(s) for s in arg.saatler.split(","))
    seviyeler = tuple(int(s) * 100 for s in arg.fl.split(","))
    dondurma = dondurma_gunleri()
    pirepler = arsiv_pireplerini_oku(gunler)
    kayitlar = olcum_yap(senaryolari_uret(gunler, saatler, seviyeler), pirepler)
    rapor = {
        "parametreler": {
            "gun_sayisi": len(gunler),
            "gunler": gunler,
            "bagimli_gunler": sorted(set(gunler) & set(dondurma)),
            "saatler": list(saatler),
            "fl": [s // 100 for s in seviyeler],
            "ciftler": [list(c) for c in SEHIR_CIFTLERI],
            "ti1_esigi": etkin_ti1_esigi(),
            "ucak": "A320",
            "secim_kurali": "sozluksel",
            "pirep_sayisi": len(pirepler),
            "bootstrap_tekrari": BOOTSTRAP_TEKRARI,
        },
        "commit": yazilim_commit(),
        "uretim_zamani": datetime.now(UTC).isoformat(),
        "ozet": ozetle(kayitlar, dondurma),
        "kayitlar": kayitlar,
    }
    os.makedirs(arg.cikti, exist_ok=True)
    with open(os.path.join(arg.cikti, "bagimsiz_backtest.json"), "w", encoding="utf-8") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2)
    with open(os.path.join(arg.cikti, "README.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    print(markdown_ozeti(rapor))
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
