"""
uyari_alani.py
-----------------
docs/deney_protokolu.md §13.5–13.6 (keşifsel, bir kez): NE-ABD ERA5 küplerinde (era5_egitim_verisi/)
ızgara düzeyinde uyarı alanı oranı ve POD–alan eğrisi (Fikir 9) ile TI3 = TI1 + 0,01·|DIV(t) − DIV(t−6 sa)|
(Fikir 15). Birincil: ml/dondurma_gunleri.json'daki günler çıkarılmış bağımsız günler. Ağ yok, indirme yok.

    turbulans-uyari-alani --cikti docs/sonuclar/2026-10-31_uyari_alani

Çıktı uyari_alani.json + README.md + pod_alan_egrisi.png; dosya varsa üzerine yazılmaz.
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import glob
import os
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.dogrulama.bagimsiz_backtest import KUTU, VARSAYILAN_KUP_KLASORU, arsiv_pireplerini_oku
from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
from turbulans_radar.fizik.turbulans_indeksleri import ti3_indeksi_hesapla, yatay_diverjans_hesapla
from turbulans_radar.ml.degerlendirme import _auc, eslestirilmis_auc_farki

CIKTI_ADI = "uyari_alani.json"
FL_LISTESI = (300, 330, 360, 390)
PIREP_FL_ARALIGI = (30000.0, 39000.0)
YUZDELIKLER = np.round(np.arange(0.50, 0.9951, 0.005), 3)
KURAL_ESIKLERI = {"TI1": 7e-7, "birlesik_edr": 0.0757}
SKORLAR = ("TI1", "birlesik_edr", "TI3")
TI3_ZAMAN_FARKI = pd.Timedelta(hours=6)
PIREP_ZAMAN_TOLERANSI = pd.Timedelta(minutes=90)
BOOTSTRAP_TEKRARI = 2000
UYARI = "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır."


def kupleri_birlestir(klasor=VARSAYILAN_KUP_KLASORU) -> xr.Dataset:
    parcalar = []
    for dosya in sorted(glob.glob(os.path.join(klasor, "*.nc"))):
        with xr.open_dataset(dosya) as kup:
            parcalar.append(kup[["u", "v", "t"]].load())
    if not parcalar:
        raise FileNotFoundError(f"NE-ABD küpü bulunamadı: {klasor}")
    return xr.concat(parcalar, dim="valid_time").sortby("valid_time")


def diverjans_kupu(kup: xr.Dataset) -> xr.DataArray:
    return yatay_diverjans_hesapla(kup["u"], kup["v"])


def skorlari_hesapla(noktalar: pd.DataFrame, kup: xr.Dataset, diverjans: xr.DataArray) -> pd.DataFrame:
    """noktalar: zaman, enlem, boylam, baro_irtifa_m. TI1/birleşik EDR eslestirme ile; TI3 aynı (en yakın)
    seviyede ve küp zamanında, t − 6 sa küpte yoksa NaN."""
    eslesme = rotayi_hava_durumuyla_eslestir(noktalar.reset_index(drop=True), kup)
    zaman_dizini = pd.DatetimeIndex(kup["valid_time"].values)
    zamanlar = pd.DatetimeIndex(pd.to_datetime(noktalar["zaman"], utc=True)).tz_convert(None)
    kup_zamani = zaman_dizini[zaman_dizini.get_indexer(zamanlar, method="nearest")]
    onceki = kup_zamani - TI3_ZAMAN_FARKI
    var = onceki.isin(zaman_dizini)
    basinc = eslesme["basinc_hpa"].to_numpy(dtype=float)
    gecerli = np.isfinite(basinc)
    secim = {
        "latitude": xr.DataArray(noktalar["enlem"].to_numpy(dtype=float), dims="n"),
        "longitude": xr.DataArray(noktalar["boylam"].to_numpy(dtype=float), dims="n"),
        config.BASINC_BOYUTU: xr.DataArray(np.where(gecerli, basinc, float(kup[config.BASINC_BOYUTU][0])), dims="n"),
    }
    simdi = diverjans.sel({"valid_time": xr.DataArray(kup_zamani.values, dims="n"), **secim}, method="nearest").values
    alti_once = diverjans.sel(
        {"valid_time": xr.DataArray(np.where(var, onceki.values, kup_zamani.values), dims="n"), **secim},
        method="nearest",
    ).values
    ti1 = eslesme["ti1_indeksi"].to_numpy(dtype=float)
    ti3 = np.where(var & gecerli, ti3_indeksi_hesapla(ti1, simdi, alti_once), np.nan)
    return pd.DataFrame(
        {
            "gun": pd.DatetimeIndex(kup_zamani).strftime("%Y-%m-%d"),
            "kup_zaman_farki_dk": np.abs((zamanlar - kup_zamani).total_seconds()) / 60.0,
            "TI1": ti1,
            "birlesik_edr": eslesme["birlesik_edr"].to_numpy(dtype=float),
            "TI3": ti3,
            "dvt_ti1_orani": np.where(var & gecerli, (ti3 - ti1) / ti1, np.nan),
        }
    )


def izgara_noktalari(kup: xr.Dataset, gun: str) -> pd.DataFrame:
    """Kutunun iç hücreleri (kenar satır/sütun hariç: türev tek yönlü) × günün küp zamanları × FL_LISTESI."""
    zamanlar = [z for z in pd.DatetimeIndex(kup["valid_time"].values) if z.strftime("%Y-%m-%d") == gun]
    enlemler, boylamlar = kup["latitude"].values[1:-1], kup["longitude"].values[1:-1]
    z, fl, en, by = np.meshgrid(np.arange(len(zamanlar)), FL_LISTESI, enlemler, boylamlar, indexing="ij")
    return pd.DataFrame(
        {
            "zaman": pd.DatetimeIndex(zamanlar)[z.ravel()].tz_localize("UTC"),
            "enlem": en.ravel().astype(float),
            "boylam": by.ravel().astype(float),
            "baro_irtifa_m": fl.ravel() * 100.0 * 0.3048,
        }
    )


def pirep_noktalari(gunler, klasor=None) -> pd.DataFrame:
    pirep = arsiv_pireplerini_oku(gunler, klasor)
    enlem_min, enlem_maks, boylam_min, boylam_maks = KUTU
    pirep = pirep[
        pirep["enlem"].between(enlem_min, enlem_maks)
        & pirep["boylam"].between(boylam_min, boylam_maks)
        & pirep["irtifa_ft"].between(*PIREP_FL_ARALIGI)
    ].reset_index(drop=True)
    return pirep.assign(baro_irtifa_m=pirep["irtifa_ft"].to_numpy(dtype=float) * 0.3048)


def esikleri_belirle(izgara: pd.DataFrame) -> dict:
    """Her skor için birleşik ızgara dağılımının yüzdelikleri; kural eşikleri ayrıca."""
    return {ad: np.quantile(izgara[ad].to_numpy(dtype=float), YUZDELIKLER) for ad in SKORLAR}


def gunluk_sayimlar(izgara: pd.DataFrame, pirep: pd.DataFrame, ad: str, esikler, gunler) -> dict:
    """gün × eşik sayımları: ızgara, M (sınıf ≥ 1) ve N (sınıf 0) için toplam ve eşik üstü."""
    esikler = np.asarray(esikler, dtype=float)
    sonuc: dict[str, np.ndarray] = {k: np.zeros((len(gunler), len(esikler))) for k in ("izgara_ust", "m_ust", "n_ust")}
    sonuc |= {k: np.zeros(len(gunler)) for k in ("izgara_n", "m_n", "n_n")}
    for i, gun in enumerate(gunler):
        g = izgara.loc[izgara["gun"] == gun, ad].to_numpy(dtype=float)
        p = pirep[pirep["gun"] == gun]
        for anahtar, degerler in (
            ("izgara", g),
            ("m", p.loc[p["sinif"] >= 1, ad].to_numpy(dtype=float)),
            ("n", p.loc[p["sinif"] == 0, ad].to_numpy(dtype=float)),
        ):
            sonuc[f"{anahtar}_n"][i] = len(degerler)
            sonuc[f"{anahtar}_ust"][i] = (degerler[:, None] >= esikler[None, :]).sum(axis=0)
    return sonuc


def _oranlar(s: dict, satirlar=None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sec = slice(None) if satirlar is None else satirlar
    with np.errstate(invalid="ignore", divide="ignore"):
        alan = s["izgara_ust"][sec].sum(axis=0) / s["izgara_n"][sec].sum()
        pod = s["m_ust"][sec].sum(axis=0) / s["m_n"][sec].sum()
        pofd = s["n_ust"][sec].sum(axis=0) / s["n_n"][sec].sum()
    return alan, pod, pofd


def egri_ozeti(alan, pod) -> dict:
    """POD–alan eğrisinin altındaki alan ((0,0) ve (1,1) uçlarıyla yamuk) ve A = %10, %20'de POD."""
    sira = np.argsort(alan)
    a = np.concatenate([[0.0], np.asarray(alan)[sira], [1.0]])
    p = np.concatenate([[0.0], np.asarray(pod)[sira], [1.0]])
    return {
        "auc_alan": float(np.sum(np.diff(a) * (p[1:] + p[:-1]) / 2)),
        "pod_alan_10": float(np.interp(0.10, a, p)),
        "pod_alan_20": float(np.interp(0.20, a, p)),
    }


def _ga(degerler) -> list[float]:
    degerler = np.asarray(degerler, dtype=float)
    degerler = degerler[np.isfinite(degerler)]
    return [float(np.quantile(degerler, 0.025)), float(np.quantile(degerler, 0.975))] if len(degerler) else []


def egri_raporu(sayimlar: dict, esikler: dict, tekrar=BOOTSTRAP_TEKRARI, tohum=0) -> dict:
    gun_sayisi = len(next(iter(sayimlar.values()))["izgara_n"])
    rng = np.random.default_rng(tohum)
    ornekler = [rng.integers(0, gun_sayisi, gun_sayisi) for _ in range(tekrar)]
    rapor: dict = {"skorlar": {}, "farklar": {}}
    dagilimlar = {}
    for ad, s in sayimlar.items():
        alan, pod, pofd = _oranlar(s)
        nokta = egri_ozeti(alan, pod)
        boot = [egri_ozeti(*_oranlar(s, o)[:2]) for o in ornekler]
        dagilimlar[ad] = boot
        rapor["skorlar"][ad] = {
            **nokta,
            **{f"{k}_ga": _ga([b[k] for b in boot]) for k in nokta},
            "egri": [
                {"esik": float(e), "yuzdelik": float(q), "alan": float(a), "pod": float(p), "pofd": float(f)}
                for e, q, a, p, f in zip(esikler[ad], YUZDELIKLER, alan, pod, pofd, strict=True)
            ],
        }
    for ad in sayimlar:
        if ad == "TI1":
            continue
        farklar = [b["auc_alan"] - t["auc_alan"] for b, t in zip(dagilimlar[ad], dagilimlar["TI1"], strict=True)]
        fark = rapor["skorlar"][ad]["auc_alan"] - rapor["skorlar"]["TI1"]["auc_alan"]
        ga = _ga(farklar)
        rapor["farklar"][f"{ad} - TI1"] = {
            "fark": fark,
            "ga": ga,
            "okuma": "daha iyi" if ga and ga[0] > 0 else "daha kötü" if ga and ga[1] < 0 else "fark gösterilemedi",
        }
    return rapor


def kural_esigi_metrikleri(izgara: pd.DataFrame, pirep: pd.DataFrame) -> dict:
    sonuc = {}
    for ad, esik in KURAL_ESIKLERI.items():
        m, n = pirep.loc[pirep["sinif"] >= 1, ad], pirep.loc[pirep["sinif"] == 0, ad]
        sonuc[ad] = {
            "esik": esik,
            "alan": float((izgara[ad] >= esik).mean()),
            "pod": float((m >= esik).mean()),
            "pofd": float((n >= esik).mean()),
        }
    return sonuc


def ortak_gecerli(df: pd.DataFrame) -> pd.DataFrame:
    return df[np.all([np.isfinite(df[ad].to_numpy(dtype=float)) for ad in SKORLAR], axis=0)].reset_index(drop=True)


def pirep_auc(pirep: pd.DataFrame, tekrar=BOOTSTRAP_TEKRARI) -> dict:
    y, gunler = (pirep["sinif"] >= 1).astype(int).to_numpy(), pirep["gun"].to_numpy()
    return {
        "ornek": int(len(pirep)),
        "orta_ustu": int(y.sum()),
        "gun": int(pirep["gun"].nunique()),
        "roc_auc": {ad: _auc(y, pirep[ad].to_numpy(dtype=float)) for ad in SKORLAR},
        "TI3 - TI1": eslestirilmis_auc_farki(y, pirep["TI3"], pirep["TI1"], gunler, tekrar),
        "birlesik_edr - TI1": eslestirilmis_auc_farki(y, pirep["birlesik_edr"], pirep["TI1"], gunler, tekrar),
    }


def analiz(izgara: pd.DataFrame, pirep: pd.DataFrame, gunler, tekrar=BOOTSTRAP_TEKRARI) -> dict:
    izgara = izgara[izgara["gun"].isin(set(gunler))]
    pirep = pirep[pirep["gun"].isin(set(gunler))]
    izgara_g, pirep_g = ortak_gecerli(izgara), ortak_gecerli(pirep)
    gunler = sorted(set(izgara_g["gun"]))
    esikler = esikleri_belirle(izgara_g)
    sayimlar = {ad: gunluk_sayimlar(izgara_g, pirep_g, ad, esikler[ad], gunler) for ad in SKORLAR}
    return {
        "veri": {
            "gun": len(gunler),
            "izgara_nokta": int(len(izgara)),
            "izgara_ortak_gecerli": int(len(izgara_g)),
            "pirep": int(len(pirep)),
            "pirep_ortak_gecerli": int(len(pirep_g)),
            "pirep_orta_ustu": int((pirep_g["sinif"] >= 1).sum()),
            "pirep_kontrol": int((pirep_g["sinif"] == 0).sum()),
        },
        "egri": egri_raporu(sayimlar, esikler, tekrar),
        "kural_esikleri": kural_esigi_metrikleri(izgara_g, pirep_g),
        "pirep_roc_auc": pirep_auc(pirep_g, tekrar),
        "dvt_ti1_orani_medyan": {
            "izgara": float(np.nanmedian(izgara_g["dvt_ti1_orani"])),
            "pirep": float(np.nanmedian(pirep_g["dvt_ti1_orani"])),
        },
    }


def calistir(cikti: str, kup_klasoru=VARSAYILAN_KUP_KLASORU, arsiv_klasoru=None, tekrar=BOOTSTRAP_TEKRARI) -> dict:
    import contextlib
    import io

    from turbulans_radar.ml.ml_otomatik_egitim import _atomik_yaz_json, _json_guvenli
    from turbulans_radar.ml.sonuc_disa_aktarimi import git_bilgisi
    from turbulans_radar.ml.yeni_gun_degerlendirmesi import dondurma_gunleri

    yol = os.path.join(cikti, CIKTI_ADI)
    if os.path.exists(yol):
        raise SystemExit(f"{yol} var: §13.5–13.6 bir kez çalıştırılır, üzerine yazılmaz.")
    kup = kupleri_birlestir(kup_klasoru)
    diverjans = diverjans_kupu(kup)
    tum_gunler = sorted(set(pd.DatetimeIndex(kup["valid_time"].values).strftime("%Y-%m-%d")))
    bagimli = sorted(set(tum_gunler) & dondurma_gunleri())
    bagimsiz = [g for g in tum_gunler if g not in set(bagimli)]
    with contextlib.redirect_stdout(io.StringIO()):
        izgara = pd.concat(
            [skorlari_hesapla(izgara_noktalari(kup, g), kup, diverjans) for g in tum_gunler], ignore_index=True
        )
        pirep = pirep_noktalari(tum_gunler, arsiv_klasoru)
        pirep = pd.concat([pirep, skorlari_hesapla(pirep, kup, diverjans).drop(columns="gun")], axis=1)
    pirep["gun"] = pirep["zaman"].dt.strftime("%Y-%m-%d")
    zamani_uzak = pirep["kup_zaman_farki_dk"] > PIREP_ZAMAN_TOLERANSI.total_seconds() / 60
    rapor = {
        "meta": {
            "protokol": "docs/deney_protokolu.md §13.5–13.6 (keşifsel)",
            "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
            **git_bilgisi(),
            "kup_klasoru": kup_klasoru,
            "fl_listesi": list(FL_LISTESI),
            "pirep_fl_araligi": list(PIREP_FL_ARALIGI),
            "uygulama_notu": (
                f"Küp zamanına en yakın adımı {PIREP_ZAMAN_TOLERANSI.total_seconds() / 60:.0f} dakikadan uzak olan "
                "PIREP'ler (blok sınırında, sonraki gün küpte yok) atıldı."
            ),
            "uyari": UYARI,
        },
        "gunler": {"bagimsiz": bagimsiz, "bagimli_cikarilan": bagimli},
        "zamani_uzak_atilan_pirep": int(zamani_uzak.sum()),
        "birincil_bagimsiz": analiz(izgara, pirep[~zamani_uzak], bagimsiz, tekrar),
        "ikincil_tum_gunler": analiz(izgara, pirep[~zamani_uzak], tum_gunler, tekrar),
    }
    rapor = _json_guvenli(rapor)
    os.makedirs(cikti, exist_ok=True)
    _atomik_yaz_json(yol, rapor)
    with open(os.path.join(cikti, "README.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    sekil_ciz(rapor, os.path.join(cikti, "pod_alan_egrisi.png"))
    return rapor


def _f(x, bicim="{:.3f}") -> str:
    return "—" if x is None or not np.isfinite(x) else bicim.format(x).replace(".", ",")


def _ga_metni(ga, bicim="{:.3f}") -> str:
    return f"[{_f(ga[0], bicim)}; {_f(ga[1], bicim)}]" if ga else "—"


def _bolum(ad: str, b: dict) -> list[str]:
    v, e, p = b["veri"], b["egri"], b["pirep_roc_auc"]
    return [
        f"## {ad}",
        "",
        f"{v['gun']} gün; ızgara {v['izgara_ortak_gecerli']} nokta (üç skorun da tanımlı olduğu, {v['izgara_nokta']} "
        f"noktadan); PIREP {v['pirep_ortak_gecerli']} ({v['pirep_orta_ustu']} orta-üstü, {v['pirep_kontrol']} kontrol).",
        "",
        "| Skor | POD–alan AUC | %95 GA | POD @ alan %10 | POD @ alan %20 | PIREP ROC-AUC |",
        "|---|---|---|---|---|---|",
        *(
            f"| {ad_} | {_f(s['auc_alan'])} | {_ga_metni(s['auc_alan_ga'])} | {_f(s['pod_alan_10'])} "
            f"{_ga_metni(s['pod_alan_10_ga'])} | {_f(s['pod_alan_20'])} {_ga_metni(s['pod_alan_20_ga'])} "
            f"| {_f(p['roc_auc'][ad_])} |"
            for ad_, s in e["skorlar"].items()
        ),
        "",
        "| Fark (POD–alan AUC) | Fark | %95 GA | Okuma |",
        "|---|---|---|---|",
        *(
            f"| {ad_} | {_f(f['fark'], '{:+.3f}')} | {_ga_metni(f['ga'], '{:+.3f}')} | {f['okuma']} |"
            for ad_, f in e["farklar"].items()
        ),
        "",
        "| PIREP ROC-AUC farkı | Fark | %95 GA |",
        "|---|---|---|",
        *(
            f"| {ad_} | {_f(p[ad_]['fark'], '{:+.3f}')} | {_ga_metni([p[ad_]['alt'], p[ad_]['ust']], '{:+.3f}')} |"
            for ad_ in ("TI3 - TI1", "birlesik_edr - TI1")
        ),
        "",
        "| Kural eşiği | Eşik | Uyarı alanı | POD (orta-üstü) | POFD (kontrol) |",
        "|---|---|---|---|---|",
        *(
            f"| {ad_} | {_f(k['esik'], '{:.4g}')} | {_f(k['alan'])} | {_f(k['pod'])} | {_f(k['pofd'])} |"
            for ad_, k in b["kural_esikleri"].items()
        ),
        "",
        f"DVT/TI1 oranı medyanı: ızgara {_f(b['dvt_ti1_orani_medyan']['izgara'], '{:.2f}')}, PIREP "
        f"{_f(b['dvt_ti1_orani_medyan']['pirep'], '{:.2f}')}.",
        "",
    ]


def markdown_ozeti(rapor) -> str:
    m = rapor["meta"]
    return (
        "\n".join(
            [
                "# Uyarı alanı ve POD–alan eğrisi; TI3 (protokol §13.5–13.6, keşifsel)",
                "",
                f"Üretim {m['uretim_zamani']} · commit `{m.get('commit') or '—'}` · NE-ABD ERA5 küpleri "
                f"(`{m['kup_klasoru']}`, 300/250/200 hPa, 3 sa), ızgara FL{'/'.join(map(str, m['fl_listesi']))}, "
                f"PIREP FL{int(m['pirep_fl_araligi'][0] / 100)}–{int(m['pirep_fl_araligi'][1] / 100)}. Bağımlı "
                f"(dondurma) günler birincilden çıkarıldı: {', '.join(rapor['gunler']['bagimli_cikarilan']) or '—'}. "
                f"{m['uygulama_notu']} ({rapor['zamani_uzak_atilan_pirep']} PIREP)",
                "",
                "POD–alan AUC: uyarı alanı oranı (ızgaranın eşik üstü payı) eksenine karşı orta-üstü PIREP'lerin "
                "eşik üstü payı; rastgele 0,5. Eşikler her skorun ızgara dağılımının %50–%99,5 yüzdelikleri, "
                "%50'nin altı (1,1)'e düz çizgi. Gün bloklu bootstrap (2.000). TTS hesaplanmadı (gözlenen alan "
                "PIREP'ten bilinemez).",
                "",
                *_bolum("Birincil: bağımsız günler", rapor["birincil_bagimsiz"]),
                *_bolum("İkincil: tüm günler", rapor["ikincil_tum_gunler"]),
                "Tek bölge, 3 seviye, birkaç yüz PIREP; PIREP'ler trafik ve raporlama yanlılığı taşır. Keşifseldir; "
                "rota kararı ve eşikler değişmez. " + UYARI,
            ]
        )
        + "\n"
    )


def sekil_ciz(rapor: dict, yol: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    renkler = {"TI1": "#2a78d6", "birlesik_edr": "#d9822b", "TI3": "#2f9e6e"}
    b = rapor["birincil_bagimsiz"]
    fig, eksen = plt.subplots(figsize=(6.4, 5.0))
    for ad, s in b["egri"]["skorlar"].items():
        alan = [n["alan"] for n in s["egri"]]
        pod = [n["pod"] for n in s["egri"]]
        eksen.plot(
            alan, pod, color=renkler[ad], linewidth=1.8, label=f"{ad} (AUC {s['auc_alan']:.3f})".replace(".", ",")
        )
    for ad, k in b["kural_esikleri"].items():
        eksen.plot([k["alan"]], [k["pod"]], "o", color=renkler[ad], markeredgecolor="#fcfcfb", markersize=8)
    eksen.plot([0, 1], [0, 1], color="#52514e", linewidth=0.8, linestyle="--", label="Rastgele")
    eksen.set_xlim(0, 0.55)
    eksen.set_ylim(0, 1)
    eksen.set_xlabel("Uyarı alanı oranı (ızgaranın eşik üstü payı)")
    eksen.set_ylabel("POD (orta-üstü PIREP'lerin eşik üstü payı)")
    eksen.grid(True, color="#e1e0d9", linewidth=0.5)
    for kenar in ("top", "right"):
        eksen.spines[kenar].set_visible(False)
    eksen.legend(frameon=False, fontsize=8, loc="lower right")
    fig.suptitle("POD–uyarı alanı (NE-ABD, bağımsız günler; nokta: kural eşiği)", fontsize=10)
    fig.tight_layout()
    fig.savefig(yol, dpi=150, metadata={"Software": None}, bbox_inches="tight")
    plt.close(fig)


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="Protokol §13.5–13.6: uyarı alanı ve TI3 (bir kez, ağsız).")
    ayristirici.add_argument("--cikti", required=True)
    ayristirici.add_argument("--kup-klasoru", default=VARSAYILAN_KUP_KLASORU)
    ayristirici.add_argument("--tekrar", type=int, default=BOOTSTRAP_TEKRARI)
    argumanlar = ayristirici.parse_args(argv)
    print(markdown_ozeti(calistir(argumanlar.cikti, argumanlar.kup_klasoru, tekrar=argumanlar.tekrar)))


if __name__ == "__main__":
    ana()
