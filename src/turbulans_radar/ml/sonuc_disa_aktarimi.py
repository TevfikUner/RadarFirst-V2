"""
sonuc_disa_aktarimi.py
------------------------
Donmuş sonuç paketi (Uzman Madde 8). Kesme gününe kadar veritabanına girmiş
eşleşmiş PIREP'lerle protokol modeli (altın test günleri dışında, gün gruplu CV +
1-SE, sigmoid kalibrasyon) eğitilir. Altın günlerde model, TI1, 1/Ri ve birleşik
EDR için ROC-AUC ve PR-AUC (gün bazlı blok bootstrap %95 GA), TI1'e karşı
eşleştirilmiş ROC-AUC farkı ve p değeri; TI1 eşik taraması (eğitim günlerinde
Peirce, altın günlerde POD/POFD/CSI, seviyeye göre); yalnızca CAT alt kümesi
(PIREP metninde CB/TS/TCU/MTN WAVE/LLWS geçmeyenler); MADIS ölçülen EDR; rota
backtest'i. Hepsi commit hash'li tek JSON'a, üç PNG'ye ve SAYILAR.md'ye yazılır.

    turbulans-ml-degerlendirme --kesme 2026-10-18 --cikti docs/sonuclar/2026-10-18

Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import contextlib
import io
import os
import subprocess
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve
from sqlalchemy import select
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo.models import EdrOrnegi, MlOrnegi, RotaBacktesti, Ucus
from turbulans_radar.dogrulama.bagimsiz_kanit import cat_disi_mi
from turbulans_radar.fizik.edr_esleme import RI_TABANI, birlesik_edr
from turbulans_radar.ml.degerlendirme import (
    _auc,
    _pr_auc,
    bootstrap_guven_araligi,
    eslestirilmis_auc_farki,
    guvenilirlik_tablosu,
    ikili_metrikler,
    olasilik_metrikleri,
    peirce_esigi,
)
from turbulans_radar.ml.ml_otomatik_egitim import (
    _atomik_yaz_json,
    _json_guvenli,
    _utc_gunu,
    degerlendirme_gunleri_maskesi,
    protokol_adayi,
)
from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI, ozellikleri_temizle

GA_MIN_GUN = 5
SEVIYE_MIN_SINIF = 20
TARAMA_YUZDELIKLERI = tuple(range(5, 100, 5))
SKOR_ADLARI = ("Model", "TI1", "1/Ri", "Birleşik EDR")
CAT_DISI_ACIKLAMA = "PIREP metninde CB, CBS, TCU, TS (+TSRA, VCTS, TSTM...), MTN WAVE ya da LLWS geçenler"
MADIS_NOTU = (
    "Yalnızca hafif sınıf var (orta ve üstü ölçüm yok ya da çok az); örnekler PIREP pencerelerinden "
    "(±1°, ±1 sa) geldiği için seçim yanlılığı vardır; QC 'Z' ön veridir."
)


def git_bilgisi() -> dict:
    kok = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    def _git(*argumanlar):
        return subprocess.run(
            ["git", "-C", kok, *argumanlar], capture_output=True, text=True, timeout=30, check=True
        ).stdout.strip()

    try:
        return {
            "commit": _git("rev-parse", "HEAD"),
            "kirli": bool(_git("status", "--porcelain", "--untracked-files=no")),
        }
    except (OSError, subprocess.SubprocessError):
        return {"commit": os.environ.get("TURBULANS_COMMIT"), "kirli": None}


def _kesme_siniri(kesme):
    return None if kesme is None else pd.Timestamp(kesme, tz="UTC") + pd.Timedelta(days=1)


def pirep_ornekleri(motor, kesme=None):
    sorgu = select(MlOrnegi.pirep_anahtari, MlOrnegi.zaman, MlOrnegi.sinif, MlOrnegi.ozellikler).where(
        MlOrnegi.durum == "eslesti"
    )
    if kesme is not None:
        sorgu = sorgu.where(MlOrnegi.olusturulma_zamani < _kesme_siniri(kesme))
    with Session(motor) as oturum:
        satirlar = oturum.execute(sorgu).all()
    ozellikler = pd.DataFrame([s.ozellikler for s in satirlar]).reindex(columns=MODEL_OZELLIK_SUTUNLARI)
    bilgi = pd.DataFrame(
        {
            "anahtar": [s.pirep_anahtari for s in satirlar],
            "y": [int(s.sinif >= 1) for s in satirlar],
            "gun": [_utc_gunu(s.zaman) for s in satirlar],
        }
    )
    return ozellikleri_temizle(ozellikler, bilgi, sutunlar=MODEL_OZELLIK_SUTUNLARI)


def madis_ornekleri(motor, kesme=None) -> pd.DataFrame:
    sorgu = select(EdrOrnegi.zaman, EdrOrnegi.max_edr, EdrOrnegi.edr_sinifi, EdrOrnegi.ozellikler)
    if kesme is not None:
        sorgu = sorgu.where(EdrOrnegi.olusturulma_zamani < _kesme_siniri(kesme))
    with Session(motor) as oturum:
        satirlar = oturum.execute(sorgu).all()
    df = pd.DataFrame(satirlar, columns=["zaman", "max_edr", "edr_sinifi", "ozellikler"])
    if df.empty:
        return df
    df = df.drop(columns="ozellikler").join(pd.DataFrame(df["ozellikler"].tolist()))
    df["gun"] = df["zaman"].map(_utc_gunu)
    return df


def backtest_kayitlari(motor) -> list[dict]:
    sorgu = select(RotaBacktesti, Ucus.ucus_numarasi, Ucus.tarih).join(Ucus, Ucus.id == RotaBacktesti.ucus_id)
    with Session(motor) as oturum:
        satirlar = oturum.execute(sorgu.order_by(Ucus.tarih, Ucus.ucus_numarasi)).all()
    kayitlar = []
    for b, ucus_numarasi, tarih in satirlar:
        kayit = {"ucus": ucus_numarasi, "tarih": str(tarih), "veri_kaynagi": b.veri_kaynagi}
        kayit["kacinma_stratejisi"] = b.kacinma_stratejisi
        for rota in ("gercek", "buyuk_daire", "optimize"):
            for alan in ("riskli_oran", "sigmet_ihlali", "turb_sigmet", "mog_pirep"):
                kayit[f"{rota}_{alan}"] = getattr(b, f"{rota}_{alan}")
        kayit["kanit_kaynaklari"] = b.kanit_kaynaklari or []
        kayitlar.append(kayit)
    return kayitlar


def skorlari_hesapla(X: pd.DataFrame, model=None) -> dict:
    ri = pd.to_numeric(X["richardson_sayisi"], errors="coerce").to_numpy(dtype=float)
    skorlar = {
        "TI1": X["ti1_indeksi"].to_numpy(dtype=float),
        "1/Ri": 1.0 / np.maximum(ri, RI_TABANI),
        "Birleşik EDR": np.asarray(birlesik_edr(X), dtype=float),
    }
    if model is not None:
        skorlar = {"Model": model.predict_proba(X[MODEL_OZELLIK_SUTUNLARI])[:, 1], **skorlar}
    return skorlar


def skor_ozeti(y, skorlar: dict, gunler, tekrar=None) -> dict:
    """Ortak geçerli satırlarda her skor için ROC-AUC ve PR-AUC (GA'lı) ve TI1'e karşı eşleştirilmiş fark."""
    y, gunler = np.asarray(y, dtype=int), np.asarray(gunler)
    gecerli = np.all([np.isfinite(s) for s in skorlar.values()], axis=0) if skorlar else np.ones(len(y), bool)
    y, gunler = y[gecerli], gunler[gecerli]
    skorlar = {ad: np.asarray(s)[gecerli] for ad, s in skorlar.items()}
    ozet = {
        "ornek": int(len(y)),
        "pozitif": int(y.sum()),
        "taban_oran": float(y.mean()) if len(y) else float("nan"),
        "gun": int(len(set(gunler))),
        "skorlar": {},
    }
    ga_var = ozet["gun"] >= GA_MIN_GUN and 0 < ozet["pozitif"] < ozet["ornek"]
    if not ga_var:
        ozet["not"] = f"Gün bazlı GA için en az {GA_MIN_GUN} gün ve iki sınıf gerekli; yalnız nokta değerler."
    for ad, skor in skorlar.items():
        if ga_var:
            roc = bootstrap_guven_araligi(y, skor, gunler, tekrar=tekrar)
            pr = bootstrap_guven_araligi(y, skor, gunler, "pr_auc", tekrar=tekrar)
            kayit = {
                "roc_auc": roc["deger"],
                "roc_auc_ga": [roc["alt"], roc["ust"]],
                "pr_auc": pr["deger"],
                "pr_auc_ga": [pr["alt"], pr["ust"]],
            }
            if ad != "TI1" and "TI1" in skorlar:
                kayit["ti1_farki"] = eslestirilmis_auc_farki(y, skor, skorlar["TI1"], gunler, tekrar=tekrar)
        else:
            kayit = {"roc_auc": _auc(y, skor), "pr_auc": _pr_auc(y, skor)}
        ozet["skorlar"][ad] = kayit
    return ozet


def _peirce_ga(y, skor, esik, gunler, tekrar=None) -> list[float]:
    def peirce(yy, ss):
        m = ikili_metrikler(yy, ss, esik)
        return m["peirce"]

    ga = bootstrap_guven_araligi(y, skor, gunler, ("peirce", peirce), tekrar=tekrar)
    return [ga["alt"], ga["ust"]]


def esik_taramasi(egitim: pd.DataFrame, test: pd.DataFrame, tekrar=None) -> dict:
    """egitim/test: y, ti1, seviye, gun sütunları. Eşik eğitim günlerinde seçilir, test günlerine aynen uygulanır."""
    esik = peirce_esigi(egitim["y"], egitim["ti1"])
    test_metrik = ikili_metrikler(test["y"], test["ti1"], esik)
    if test["gun"].nunique() >= GA_MIN_GUN:
        test_metrik["peirce_ga"] = _peirce_ga(test["y"], test["ti1"], esik, test["gun"], tekrar)
    sonuc = {
        "yontem": "eğitim günlerinde Peirce (POD - POFD) maksimum; altın test günlerine aynen uygulanır",
        "peirce_esigi": esik,
        "egitim": ikili_metrikler(egitim["y"], egitim["ti1"], esik),
        "test": test_metrik,
        "config_esikleri": {
            ad: {"esik": deger, "test": ikili_metrikler(test["y"], test["ti1"], deger)}
            for ad, deger in (
                ("TI1_ESIK_HAFIF", config.TI1_ESIK_HAFIF),
                ("TI1_ESIK_ORTA_SIDDETLI", config.TI1_ESIK_ORTA_SIDDETLI),
            )
        },
    }
    tarama = []
    for yuzdelik in TARAMA_YUZDELIKLERI:
        deger = float(np.percentile(egitim["ti1"], yuzdelik))
        e, t = ikili_metrikler(egitim["y"], egitim["ti1"], deger), ikili_metrikler(test["y"], test["ti1"], deger)
        tarama.append(
            {
                "yuzdelik": yuzdelik,
                "esik": deger,
                "egitim_peirce": e["peirce"],
                "test_pod": t["pod"],
                "test_pofd": t["pofd"],
                "test_csi": t["csi"],
                "test_peirce": t["peirce"],
            }
        )
    sonuc["tarama"] = tarama
    seviyeler = []
    for seviye in sorted(set(egitim["seviye"]) | set(test["seviye"])):
        e, t = egitim[egitim["seviye"] == seviye], test[test["seviye"] == seviye]
        kayit = {"seviye_hpa": float(seviye), "egitim_ornek": len(e), "test_ornek": len(t)}
        yeterli = min(e["y"].sum(), (1 - e["y"]).sum()) >= SEVIYE_MIN_SINIF and t["y"].nunique() == 2
        if yeterli:
            seviye_esigi = peirce_esigi(e["y"], e["ti1"])
            kayit.update(
                {
                    "seviye_esigi": seviye_esigi,
                    "test_seviye_esigi": ikili_metrikler(t["y"], t["ti1"], seviye_esigi),
                    "test_genel_esik": ikili_metrikler(t["y"], t["ti1"], esik),
                }
            )
        else:
            kayit["not"] = f"Yetersiz örnek (eğitimde her sınıftan en az {SEVIYE_MIN_SINIF}, testte iki sınıf)."
        seviyeler.append(kayit)
    sonuc["seviyeye_gore"] = seviyeler
    return sonuc


def cat_alt_kumesi(bilgi: pd.DataFrame, metinler: pd.DataFrame, skorlar: dict, holdout, tekrar=None) -> dict:
    """bilgi: anahtar, y, gun. metinler: anahtar, rapor (arşiv). Aynı anahtarın raporlarından biri CAT dışıysa CAT dışı."""
    if metinler.empty:
        return {"durum": "arsiv_yok", "neden": "Yerel IEM arşivi (ML_PIREP_ARSIV_KLASORU) bulunamadı."}
    isaret = metinler.assign(cat_disi=metinler["rapor"].map(cat_disi_mi)).dropna(subset=["cat_disi"])
    isaret = isaret.groupby("anahtar")["cat_disi"].any()
    cat_disi = bilgi["anahtar"].map(isaret)
    metinli = cat_disi.notna().to_numpy()
    cat_disi_dizi = cat_disi.eq(True).to_numpy()
    cat = metinli & ~cat_disi_dizi
    holdout = np.asarray(holdout)
    y, gunler = bilgi["y"].to_numpy(), bilgi["gun"].to_numpy()
    fizik = {ad: s for ad, s in skorlar.items() if ad != "Model"}

    def alt(maske, kume):
        return skor_ozeti(y[maske], {ad: np.asarray(s)[maske] for ad, s in kume.items()}, gunler[maske], tekrar)

    return {
        "dislanan": CAT_DISI_ACIKLAMA,
        "ornek": int(len(y)),
        "metinli": int(metinli.sum()),
        "cat_disi": int(cat_disi_dizi.sum()),
        "cat_disi_pozitif_orani": float(y[cat_disi_dizi].mean()) if cat_disi_dizi.any() else float("nan"),
        "metinsiz_not": "Metni olmayan örnekler (Nisan 2020 sonrası günler) iki alt kümede de yok.",
        "test_metinli": alt(holdout & metinli, skorlar),
        "test_cat": alt(holdout & cat, skorlar),
        "tum_gunler_metinli_fizik": alt(metinli, fizik),
        "tum_gunler_cat_fizik": alt(cat, fizik),
    }


def madis_bolumu(madis: pd.DataFrame, model, tekrar=None) -> dict:
    from turbulans_radar.veri.madis_edr import edr_sinifi

    madis = madis.dropna(subset=MODEL_OZELLIK_SUTUNLARI + ["max_edr"]).reset_index(drop=True)
    if madis.empty:
        return {"durum": "veri_yok"}
    sinif = edr_sinifi(madis["max_edr"])
    y = (sinif >= 1).astype(int)
    skorlar = skorlari_hesapla(madis, model)
    ozet = skor_ozeti(y, skorlar, madis["gun"].to_numpy(), tekrar)
    olasilik = skorlar["Model"]
    return {
        "kaynak": "NOAA MADIS herkese açık ACARS maxEDR",
        "hedef": f"max EDR >= {config.EDR_ESIK_HAFIF} (hafif ve üstü), sınıflar madis_edr.edr_sinifi ile yeniden",
        "duzeltilen_sinif": int((sinif != madis["edr_sinifi"].to_numpy()).sum()),
        "orta_ve_ustu": int((sinif >= 2).sum()),
        "not": MADIS_NOTU,
        **ozet,
        "model_olasilik": olasilik_metrikleri(y, olasilik),
        "guvenilirlik": guvenilirlik_tablosu(y, olasilik),
    }


def _roc_noktasi(y, skor, esik) -> dict:
    m = ikili_metrikler(y, skor, esik)
    return {"pofd": m["pofd"], "pod": m["pod"]}


def sekilleri_ciz(klasor, test_y, test_skorlar, esikler, guvenilirlik: dict, backtest: list[dict]) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    yollar = []
    fig, eksen = plt.subplots(figsize=(6, 6))
    renkler = {"TI1": "#1f5fbf", "1/Ri": "#c45a1a", "Model": "#7a7a7a", "Birleşik EDR": "#2a9d5c"}
    for ad in ("TI1", "1/Ri", "Model"):
        if ad not in test_skorlar:
            continue
        yanlis, dogru, _ = roc_curve(test_y, test_skorlar[ad])
        cizgi = "--" if ad == "Model" else "-"
        etiket = "Ri (1/Ri sıralaması)" if ad == "1/Ri" else ad
        eksen.plot(yanlis, dogru, cizgi, color=renkler[ad], label=f"{etiket}: AUC {_auc(test_y, test_skorlar[ad]):.3f}")
    for (ad, etiket, isaret), esik in esikler.items():
        nokta = _roc_noktasi(test_y, test_skorlar[ad], esik)
        eksen.plot(nokta["pofd"], nokta["pod"], isaret, color=renkler[ad], markersize=9, label=etiket)
    eksen.plot([0, 1], [0, 1], ":", color="#999")
    eksen.set_xlabel("POFD (yanlış alarm oranı)")
    eksen.set_ylabel("POD (yakalama oranı)")
    eksen.set_title("ROC, altın test günleri (PIREP orta ve üstü)")
    eksen.legend(loc="lower right", fontsize=8)
    eksen.set_xlim(0, 1)
    eksen.set_ylim(0, 1)
    yollar.append(_kaydet(fig, klasor, "roc_ti1_ri.png"))

    fig, eksen = plt.subplots(figsize=(6, 6))
    eksen.plot([0, 1], [0, 1], ":", color="#999", label="Mükemmel kalibrasyon")
    for (ad, tablo), renk in zip(guvenilirlik.items(), ("#1f5fbf", "#c45a1a"), strict=False):
        if not tablo:
            continue
        toplam = sum(k["adet"] for k in tablo)
        x = [k["ortalama_tahmin"] for k in tablo]
        yy = [k["gozlenen_oran"] for k in tablo]
        boyut = [20 + 300 * k["adet"] / toplam for k in tablo]
        eksen.plot(x, yy, "-", color=renk, alpha=0.7)
        eksen.scatter(x, yy, s=boyut, color=renk, alpha=0.6, label=f"{ad} (n={toplam})")
    eksen.set_xlabel("Tahmin edilen olasılık")
    eksen.set_ylabel("Gözlenen oran")
    eksen.set_title("Güvenilirlik diyagramı (model olasılığı)")
    eksen.legend(loc="upper left", fontsize=8)
    eksen.set_xlim(0, 1)
    eksen.set_ylim(0, 1)
    yollar.append(_kaydet(fig, klasor, "guvenilirlik_modeli.png"))

    fig, eksen = plt.subplots(figsize=(7, 4.5))
    if backtest:
        etiketler = [f"{k['ucus']}\n{k['tarih']}" for k in backtest]
        x = np.arange(len(backtest))
        for i, (rota, ad, renk) in enumerate(
            (
                ("gercek", "Gerçek iz", "#7a7a7a"),
                ("buyuk_daire", "Büyük daire", "#1f5fbf"),
                ("optimize", "A*", "#2a9d5c"),
            )
        ):
            degerler = [k[f"{rota}_riskli_oran"] or 0.0 for k in backtest]
            cubuklar = eksen.bar(x + (i - 1) * 0.27, degerler, 0.27, color=renk, label=ad)
            eksen.bar_label(cubuklar, fmt="%.2f", fontsize=7)
        eksen.set_xticks(x, etiketler, fontsize=8)
        eksen.legend(fontsize=8)
    else:
        eksen.text(0.5, 0.5, "Backtest kaydı yok", ha="center", va="center")
    eksen.set_ylabel("Riskli nokta oranı (TI1 ≥ eşik)")
    eksen.set_title("Rota backtest'i, uçuş başına (TI1 ile ölçüm: döngüsel)", fontsize=10)
    yollar.append(_kaydet(fig, klasor, "backtest_ucus_basina.png"))
    return yollar


def _kaydet(fig, klasor, ad) -> str:
    import matplotlib.pyplot as plt

    yol = os.path.join(klasor, ad)
    fig.tight_layout()
    fig.savefig(yol, dpi=150, metadata={"Software": None})
    plt.close(fig)
    return ad


def _s(deger, basamak=3) -> str:
    if deger is None or (isinstance(deger, float) and not np.isfinite(deger)):
        return "—"
    if isinstance(deger, (int, np.integer)):
        return f"{int(deger):,}".replace(",", ".")
    return f"{deger:.{basamak}f}".replace(".", ",")


def _ga(kayit, ad) -> str:
    ga = kayit.get(f"{ad}_ga")
    return f"{_s(kayit[ad])} [{_s(ga[0])}–{_s(ga[1])}]" if ga else _s(kayit.get(ad))


def _fark(kayit) -> str:
    f = kayit.get("ti1_farki")
    if not f:
        return "—"
    if f.get("fark") is None:
        return "—"
    p = "< 0,001" if f["p_degeri"] == 0 else _s(f["p_degeri"])
    return f"{f['fark']:+.3f} [{f['alt']:+.3f}; {f['ust']:+.3f}], p {p}".replace(".", ",")


def sayilar_tablosu(paket: dict) -> str:
    """Raporda, sunumda ve posterde kullanılan her sayının tek kaynağı."""
    m = paket["meta"]
    satirlar = [
        "# Sayılar (sonuç paketi)",
        "",
        f"Kesme: {m['kesme'] or 'yok (tüm veri)'} · üretim: {m['uretim_zamani']} · commit `{m['commit']}`"
        + (" (çalışma ağacı kirli)" if m.get("kirli") else ""),
        "",
        "Bu dosya `turbulans-ml-degerlendirme --cikti` ile üretilir; elle düzenlenmez. Kaynak: "
        "`sonuc_paketi.json` (anahtar sütunu). GA: gün bazlı blok bootstrap %95. Çıktılar sertifikalı EDR "
        "değildir; sistem karar destek aracıdır.",
        "",
        "| Sayı | Değer | JSON anahtarı |",
        "|---|---|---|",
    ]

    def ekle(ad, deger, anahtar):
        satirlar.append(f"| {ad} | {deger} | `{anahtar}` |")

    v = paket["veri"]
    ekle("Eşleşmiş PIREP (seyir irtifası)", _s(v["ornek"]), "veri.ornek")
    ekle("Gün", _s(v["gun"]), "veri.gun")
    ekle("Pozitif oranı (orta ve üstü)", _s(v["pozitif_orani"]), "veri.pozitif_orani")
    ekle("Eğitim örnek / gün", f"{_s(v['egitim_ornek'])} / {_s(v['egitim_gun'])}", "veri.egitim_ornek, egitim_gun")
    ekle("Altın test örnek / gün", f"{_s(v['test_ornek'])} / {_s(v['test_gun'])}", "veri.test_ornek, test_gun")
    ekle("Protokol modeli (1-SE)", paket["model"]["secilen"], "model.secilen")
    t = paket["pirep_test"]
    for ad, kayit in t["skorlar"].items():
        k = f"pirep_test.skorlar.{ad}"
        ekle(f"{ad} ROC-AUC (altın günler)", _ga(kayit, "roc_auc"), f"{k}.roc_auc")
        ekle(f"{ad} PR-AUC (altın günler)", _ga(kayit, "pr_auc"), f"{k}.pr_auc")
        if "ti1_farki" in kayit:
            ekle(f"{ad} − TI1 ROC-AUC farkı", _fark(kayit), f"{k}.ti1_farki")
    mo = paket["model_olasilik_test"]
    ekle(
        "Model Brier / Brier becerisi (altın günler)",
        f"{_s(mo['brier'])} / {_s(mo['brier_becerisi'])}",
        "model_olasilik_test.brier, brier_becerisi",
    )
    ekle(
        "Model ortalama olasılık / gözlenen oran (altın günler)",
        f"{_s(mo['ortalama_olasilik'])} / {_s(mo['gozlenen_oran'])}",
        "model_olasilik_test",
    )
    tu = paket["pirep_tum_gunler_fizik"]
    for ad, kayit in tu["skorlar"].items():
        ekle(f"{ad} ROC-AUC (tüm günler)", _ga(kayit, "roc_auc"), f"pirep_tum_gunler_fizik.skorlar.{ad}.roc_auc")
    e = paket["esik_taramasi"]
    ekle("TI1 Peirce eşiği (eğitim günleri)", f"{e['peirce_esigi']:.2e}", "esik_taramasi.peirce_esigi")
    tm = e["test"]
    ekle(
        "Peirce eşiğinde test POD / POFD / CSI",
        f"{_s(tm['pod'])} / {_s(tm['pofd'])} / {_s(tm['csi'])}",
        "esik_taramasi.test",
    )
    if "peirce_ga" in tm:
        ekle(
            "Peirce eşiğinde test Peirce",
            f"{_s(tm['peirce'])} [{_s(tm['peirce_ga'][0])}–{_s(tm['peirce_ga'][1])}]",
            "esik_taramasi.test.peirce",
        )
    ri = e.get("ri_peirce_esigi") or {}
    if ri.get("ri"):
        ekle("Ri Peirce eşiği (eğitim günleri; Ri altı riskli)", _s(ri["ri"], 2), "esik_taramasi.ri_peirce_esigi.ri")
    for ad, kayit in e["config_esikleri"].items():
        ct = kayit["test"]
        ekle(
            f"{ad} ({kayit['esik']:.0e}) test POD / POFD / CSI",
            f"{_s(ct['pod'])} / {_s(ct['pofd'])} / {_s(ct['csi'])}",
            f"esik_taramasi.config_esikleri.{ad}.test",
        )
    for i, sv in enumerate(e["seviyeye_gore"]):
        if "seviye_esigi" not in sv:
            continue
        ts, tg = sv["test_seviye_esigi"], sv["test_genel_esik"]
        ekle(
            f"{sv['seviye_hpa']:.0f} hPa: eşik; test POD/POFD/CSI seviye eşiğiyle | genel eşikle",
            f"{sv['seviye_esigi']:.1e}; {_s(ts['pod'])}/{_s(ts['pofd'])}/{_s(ts['csi'])} | "
            f"{_s(tg['pod'])}/{_s(tg['pofd'])}/{_s(tg['csi'])} (test n={_s(sv['test_ornek'])})",
            f"esik_taramasi.seviyeye_gore[{i}]",
        )
    c = paket["cat_alt_kumesi"]
    if "test_cat" in c:
        ekle("Metni olan / CAT dışı işaretli örnek", f"{_s(c['metinli'])} / {_s(c['cat_disi'])}", "cat_alt_kumesi")
        ekle(
            "CAT dışı örneklerde pozitif oranı",
            _s(c["cat_disi_pozitif_orani"]),
            "cat_alt_kumesi.cat_disi_pozitif_orani",
        )
        ekle(
            "Altın günlerde metinli / yalnız CAT örnek",
            f"{_s(c['test_metinli']['ornek'])} / {_s(c['test_cat']['ornek'])}",
            "cat_alt_kumesi.test_metinli.ornek, test_cat.ornek",
        )
        for ad, kayit in c["test_cat"]["skorlar"].items():
            ekle(
                f"{ad} ROC-AUC, yalnız CAT (altın günler)",
                _ga(kayit, "roc_auc"),
                f"cat_alt_kumesi.test_cat.skorlar.{ad}.roc_auc",
            )
        for ad, kayit in c["tum_gunler_cat_fizik"]["skorlar"].items():
            ekle(
                f"{ad} ROC-AUC, yalnız CAT (tüm günler)",
                _ga(kayit, "roc_auc"),
                f"cat_alt_kumesi.tum_gunler_cat_fizik.skorlar.{ad}.roc_auc",
            )
    md = paket["madis"]
    if "skorlar" in md:
        ekle("MADIS ölçüm / pozitif / gün", f"{_s(md['ornek'])} / {_s(md['pozitif'])} / {_s(md['gun'])}", "madis")
        ekle("MADIS orta ve üstü ölçüm", _s(md["orta_ve_ustu"]), "madis.orta_ve_ustu")
        for ad, kayit in md["skorlar"].items():
            ekle(f"MADIS {ad} ROC-AUC", _ga(kayit, "roc_auc"), f"madis.skorlar.{ad}.roc_auc")
            ekle(f"MADIS {ad} PR-AUC", _ga(kayit, "pr_auc"), f"madis.skorlar.{ad}.pr_auc")
            if "ti1_farki" in kayit:
                ekle(f"MADIS {ad} − TI1 ROC-AUC farkı", _fark(kayit), f"madis.skorlar.{ad}.ti1_farki")
        ekle("MADIS taban oran (hafif ve üstü)", _s(md["taban_oran"]), "madis.taban_oran")
        ekle(
            "MADIS model ortalama olasılık",
            _s(md["model_olasilik"]["ortalama_olasilik"]),
            "madis.model_olasilik.ortalama_olasilik",
        )
        ekle(
            "MADIS model Brier becerisi",
            _s(md["model_olasilik"]["brier_becerisi"]),
            "madis.model_olasilik.brier_becerisi",
        )
    for i, b in enumerate(paket["backtest"]):
        ekle(
            f"Backtest {b['ucus']} {b['tarih']} riskli oran (gerçek / büyük daire / A*)",
            " / ".join(_s(b[f"{r}_riskli_oran"], 2) for r in ("gercek", "buyuk_daire", "optimize")),
            f"backtest[{i}]",
        )
    satirlar.append("")
    return "\n".join(satirlar)


def disa_aktar(cikti: str, kesme=None, motor=None, tekrar=None, arsiv_klasoru=None) -> dict:
    from turbulans_radar.depo.veritabani import motor_al
    from turbulans_radar.ml.duyarlilik_analizi import arsiv_metinleri

    motor = motor or motor_al()
    X, bilgi = pirep_ornekleri(motor, kesme)
    if X.empty:
        raise SystemExit("Kesme gününe kadar eşleşmiş örnek yok.")
    gunler = bilgi["gun"]
    holdout_maskesi, holdout_yontemi = degerlendirme_gunleri_maskesi(gunler)
    holdout = holdout_maskesi.to_numpy()
    egitim = ~holdout
    with contextlib.redirect_stdout(io.StringIO()):
        isim, sonuclar, model = protokol_adayi(X[egitim], bilgi["y"][egitim], gunler[egitim])
    skorlar = skorlari_hesapla(X, model)
    y = bilgi["y"].to_numpy()
    test_skorlar = {ad: s[holdout] for ad, s in skorlar.items()}
    fizik = {ad: s for ad, s in skorlar.items() if ad != "Model"}

    seviye = X["basinc_hpa"].round().to_numpy()
    tablo = pd.DataFrame({"y": y, "ti1": skorlar["TI1"], "seviye": seviye, "gun": gunler.to_numpy()})
    madis = madis_ornekleri(motor, kesme)
    madis_sonuc = madis_bolumu(madis, model, tekrar) if not madis.empty else {"durum": "veri_yok"}
    git = git_bilgisi()
    paket = {
        "meta": {
            "kesme": None if kesme is None else str(kesme),
            "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
            **git,
            "bootstrap_tekrar": config.ML_BOOTSTRAP_TEKRAR if tekrar is None else tekrar,
            "uyari": "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
        },
        "veri": {
            "kaynak": "ml_ornekleri: IEM PIREP, seyir irtifası, saatlik ERA5 özellikleri; etiket orta ve üstü",
            "ornek": int(len(y)),
            "gun": int(gunler.nunique()),
            "pozitif_orani": float(y.mean()),
            "egitim_ornek": int(egitim.sum()),
            "egitim_gun": int(gunler[egitim].nunique()),
            "test_ornek": int(holdout.sum()),
            "test_gun": int(gunler[holdout].nunique()),
            "test_yontemi": holdout_yontemi,
            "test_gunleri": sorted(gunler[holdout].unique().tolist()),
        },
        "model": {
            "secilen": isim,
            "secim": "gün gruplu CV ROC-AUC, 1-SE kuralı; sigmoid kalibrasyon; yalnız eğitim günleri",
            "cv": {ad: {k: m[k] for k in ("roc_auc", "roc_auc_se") if k in m} for ad, (_, m, _) in sonuclar.items()},
        },
        "pirep_test": skor_ozeti(y[holdout], test_skorlar, gunler[holdout].to_numpy(), tekrar),
        "pirep_tum_gunler_fizik": skor_ozeti(y, fizik, gunler.to_numpy(), tekrar),
        "model_olasilik_test": {
            **olasilik_metrikleri(y[holdout], test_skorlar["Model"]),
            "guvenilirlik": guvenilirlik_tablosu(y[holdout], test_skorlar["Model"]),
        },
        "esik_taramasi": esik_taramasi(tablo[egitim], tablo[holdout], tekrar),
        "cat_alt_kumesi": cat_alt_kumesi(bilgi, arsiv_metinleri(arsiv_klasoru), skorlar, holdout, tekrar),
        "madis": madis_sonuc,
        "backtest": backtest_kayitlari(motor),
        "backtest_notu": "Riskli oran TI1 ile ölçülür; A* de TI1'i düşürdüğü için ölçüm döngüseldir.",
    }
    ri_esigi = peirce_esigi(y[egitim], skorlar["1/Ri"][egitim])
    paket["esik_taramasi"]["ri_peirce_esigi"] = {"ters_ri": ri_esigi, "ri": 1.0 / ri_esigi if ri_esigi else None}

    os.makedirs(cikti, exist_ok=True)
    esikler = {
        ("TI1", f"TI1 Peirce eşiği {paket['esik_taramasi']['peirce_esigi']:.1e}", "o"): paket["esik_taramasi"][
            "peirce_esigi"
        ],
        ("TI1", f"TI1 config eşiği {config.TI1_ESIK_ORTA_SIDDETLI:.0e}", "s"): config.TI1_ESIK_ORTA_SIDDETLI,
        ("1/Ri", f"Ri Peirce eşiği {1.0 / ri_esigi:.2f}", "o"): ri_esigi,
    }
    guvenilirlik = {"PIREP altın günler": paket["model_olasilik_test"]["guvenilirlik"]}
    if "guvenilirlik" in madis_sonuc:
        guvenilirlik["MADIS EDR ≥ 0,1"] = madis_sonuc["guvenilirlik"]
    paket["sekiller"] = sekilleri_ciz(cikti, y[holdout], test_skorlar, esikler, guvenilirlik, paket["backtest"])
    paket = _json_guvenli(paket)
    _atomik_yaz_json(os.path.join(cikti, "sonuc_paketi.json"), paket)
    with open(os.path.join(cikti, "SAYILAR.md"), "w", encoding="utf-8") as dosya:
        dosya.write(sayilar_tablosu(paket))
    return paket
