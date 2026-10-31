"""
kesifsel_gostergeler.py
--------------------------
docs/deney_protokolu.md §13.1–13.4: §10'un sabit 79 test gününde TEK SEFERLİK keşifsel karşılaştırmalar.
Eğitim ml/dondurma_gunleri.json (163 gün). Birincil sonucu, model aktivasyonunu ve rota kararını değiştirmez.

  13.1 Fikir 10: komşuluk maksimumu (ti1_komsu_maks; yalnız yatay ±1 hücre) − TI1
  13.2 Fikir 11 devamı: çoklu /TB grubunun en şiddetlisiyle etiket; aynı skorlarla AUC(y_çok) − AUC(y)
  13.3 Fikir 24: AUC² ağırlıklı birleşik EDR − eşit ağırlıklı ve − TI1
  13.4 Fikir 19: frontogenez, |∇T|, PV (NCSU1 yok: birincil kaynak elde değil)

    turbulans-kesifsel-gostergeler --cikti docs/sonuclar/2026-10-31_kesifsel_gostergeler

Çıktı kesifsel_gostergeler.json + README.md; dosya varsa üzerine yazılmaz (bir kez kuralı).
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import json
import os
import re
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.dogrulama.bagimsiz_kanit import pirep_siddet_sinifi
from turbulans_radar.fizik.birim_donusumleri import irtifa_metre_to_basinc_hpa
from turbulans_radar.fizik.edr_esleme import gosterge_edr, gosterge_tablosu, katsayilari_yukle
from turbulans_radar.fizik.eslestirme import cevreleyen_katman_seviyeleri
from turbulans_radar.fizik.turbulans_indeksleri import (
    R_CP_KURU_HAVA,
    frontogenez_hesapla,
    potansiyel_vortisite_hesapla,
    yatay_gradyan_buyuklugu_hesapla,
    yatay_vortisite_hesapla,
)
from turbulans_radar.ml.degerlendirme import (
    _auc,
    _bootstrap_ornekleri,
    eslestirilmis_auc_farki,
    ikili_metrikler,
    peirce_esigi,
)
from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI, ozellikleri_cikar

CIKTI_ADI = "kesifsel_gostergeler.json"
TI1_KURAL_ESIGI = 7e-7
TESHIS_SUTUNLARI = ["ti1_yatay_maks", "frontogenez", "sicaklik_gradyani", "potansiyel_vortisite"]
EK_SET = MODEL_OZELLIK_SUTUNLARI + ["frontogenez", "sicaklik_gradyani", "potansiyel_vortisite"]
UYARI = "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır."

_ALAN_KODU = re.compile(r"^(OV|TM|FL|TP|SK|WX|TA|WV|TB|IC|RM)(\s|\d|$)")


def tb_gruplari(rapor) -> list[str] | None:
    """Ham PIREP'te /TB alanı ve onu izleyen, bilinen alan koduyla başlamayan '/' grupları; /TB yoksa None."""
    if not isinstance(rapor, str):
        return None
    parcalar = [p.strip() for p in rapor.upper().split("/")]
    for i, parca in enumerate(parcalar):
        if re.match(r"^TB(\s|$)", parca):
            gruplar = [parca[2:].strip()]
            for sonraki in parcalar[i + 1 :]:
                if _ALAN_KODU.match(sonraki):
                    break
                gruplar.append(sonraki)
            gruplar = [g for g in gruplar if g]
            return gruplar or None
    return None


def cok_grup_sinifi(rapor) -> int | None:
    gruplar = tb_gruplari(rapor)
    return None if gruplar is None else pirep_siddet_sinifi(" ".join(gruplar))


def pencere_teshisleri(kup, zaman, enlem, boylam, irtifa_m) -> dict:
    """Tek nokta: yalnız yatay ±1 hücre TI1 maksimumu ve en yakın seviyede FRONT, |∇T|, PV (PVU)."""
    zaman = pd.Timestamp(zaman)
    komsu = pd.DataFrame(
        [
            {"zaman": zaman, "enlem": enlem + de, "boylam": boylam + db, "irtifa_m": irtifa_m}
            for de in (-0.25, 0.0, 0.25)
            for db in (-0.25, 0.0, 0.25)
        ]
    )
    ti1 = ozellikleri_cikar(komsu, kup)["ti1_indeksi"].to_numpy(dtype=float)
    seviyeler = np.sort(kup[config.BASINC_BOYUTU].values.astype(float))
    basinc = float(irtifa_metre_to_basinc_hpa(np.array([irtifa_m]))[0])
    p0 = float(seviyeler[np.argmin(np.abs(seviyeler - basinc))])
    p_ust, p_alt = (float(x[0]) for x in cevreleyen_katman_seviyeleri(np.array([basinc]), seviyeler))
    zaman_kup = (zaman.tz_convert(None) if zaman.tzinfo else zaman).round("h")
    an = kup.sel(valid_time=zaman_kup, method="nearest")
    dilim = an.sel({config.BASINC_BOYUTU: p0})
    theta = dilim["t"] * (1000.0 / p0) ** R_CP_KURU_HAVA
    nokta = {"latitude": enlem, "longitude": boylam, "method": "nearest"}
    vortisite = float(yatay_vortisite_hesapla(dilim["u"], dilim["v"]).sel(**nokta))
    theta_ust = float(an["t"].sel({config.BASINC_BOYUTU: p_ust}).sel(**nokta)) * (1000.0 / p_ust) ** R_CP_KURU_HAVA
    theta_alt = float(an["t"].sel({config.BASINC_BOYUTU: p_alt}).sel(**nokta)) * (1000.0 / p_alt) ** R_CP_KURU_HAVA
    return {
        "ti1_yatay_maks": float(np.nanmax(ti1)) if np.isfinite(ti1).any() else np.nan,
        "frontogenez": float(frontogenez_hesapla(theta, dilim["u"], dilim["v"]).sel(**nokta)),
        "sicaklik_gradyani": float(yatay_gradyan_buyuklugu_hesapla(dilim["t"]).sel(**nokta)),
        "potansiyel_vortisite": float(
            potansiyel_vortisite_hesapla(vortisite, enlem, theta_ust, theta_alt, p_ust, p_alt)
        ),
    }


def pencere_teshislerini_hesapla(ornekler: pd.DataFrame) -> pd.DataFrame:
    from turbulans_radar.ml.ozellik_deposu import ozellik_kupu, pencere_dosyasini_ac, pencereden_kup

    parcalar = []
    for goreli_yol, grup in ornekler.dropna(subset=["pencere_dosyasi"]).groupby("pencere_dosyasi", sort=False):
        pencereler = pencere_dosyasini_ac(goreli_yol)
        for satir in grup.itertuples(index=False):
            kup = ozellik_kupu(pencereden_kup(pencereler, satir.id))
            parcalar.append(
                {
                    "id": satir.id,
                    **pencere_teshisleri(kup, satir.zaman, satir.enlem, satir.boylam, satir.irtifa_ft * 0.3048),
                }
            )
    return pd.DataFrame(parcalar, columns=["id", *TESHIS_SUTUNLARI]).set_index("id")


def pencere_teshisleri_onbellekli(ornekler: pd.DataFrame) -> pd.DataFrame:
    onbellek = os.path.join(config.ML_DEPO_KLASORU, "kesifsel_teshisler.parquet")
    if os.path.exists(onbellek):
        teshis = pd.read_parquet(onbellek)
        eksik = ornekler.loc[~ornekler["id"].isin(teshis.index)]
        if len(eksik):
            teshis = pd.concat([teshis, pencere_teshislerini_hesapla(eksik)])
    else:
        teshis = pencere_teshislerini_hesapla(ornekler)
    os.makedirs(config.ML_DEPO_KLASORU, exist_ok=True)
    teshis.to_parquet(onbellek)
    return teshis


def _sonlu(*diziler) -> np.ndarray:
    return np.all([np.isfinite(np.asarray(d, dtype=float)) for d in diziler], axis=0)


def _okuma(fark: dict) -> str:
    if np.isfinite(fark["alt"]) and fark["alt"] > 0:
        return "daha iyi ayırıyor"
    if np.isfinite(fark["ust"]) and fark["ust"] < 0:
        return "daha kötü ayırıyor"
    return "fark gösterilemedi"


def _fark(y, a, b, gunler, tekrar) -> dict:
    sonuc = eslestirilmis_auc_farki(y, a, b, gunler, tekrar)
    return {**sonuc, "okuma": _okuma(sonuc)}


def etiket_auc_farki(y_yeni, y_eski, skor, gunler, tekrar=None, tohum=0, guven=0.95) -> dict:
    """Aynı skorla ROC-AUC(y_yeni) − ROC-AUC(y_eski); gün bloklu bootstrap."""
    tekrar = config.ML_BOOTSTRAP_TEKRAR if tekrar is None else tekrar
    y_yeni, y_eski, skor = np.asarray(y_yeni, int), np.asarray(y_eski, int), np.asarray(skor, float)
    farklar = np.array(
        [_auc(y_yeni[i], skor[i]) - _auc(y_eski[i], skor[i]) for i in _bootstrap_ornekleri(gunler, tekrar, tohum)]
    )
    farklar = farklar[np.isfinite(farklar)]
    alfa = (1 - guven) / 2
    sonuc = {
        "fark": _auc(y_yeni, skor) - _auc(y_eski, skor),
        "alt": float(np.quantile(farklar, alfa)) if len(farklar) else float("nan"),
        "ust": float(np.quantile(farklar, 1 - alfa)) if len(farklar) else float("nan"),
        "gecerli_tekrar": int(len(farklar)),
    }
    return {**sonuc, "okuma": _okuma(sonuc)}


def komsuluk_analizi(egitim: pd.DataFrame, test: pd.DataFrame, tekrar=None) -> dict:
    """§13.1. A = ti1_komsu_maks, B = ti1_yatay_maks; iki sınıfa birlikte."""
    sutunlar = {"TI1": "ti1_indeksi", "A_komsu_maks": "ti1_komsu_maks", "B_yatay_maks": "ti1_yatay_maks"}
    t = test[_sonlu(*(test[s] for s in sutunlar.values()))]
    e = egitim[_sonlu(*(egitim[s] for s in sutunlar.values()))]
    y, gunler = t["y"].to_numpy(), t["gun"].to_numpy()
    esikler = {ad: peirce_esigi(e["y"], e[s]) for ad, s in sutunlar.items()}
    return {
        "test_ornek": int(len(t)),
        "test_disi_kalan": int(len(test) - len(t)),
        "roc_auc": {ad: _auc(y, t[s]) for ad, s in sutunlar.items()},
        "farklar": {
            f"{ad} - TI1": _fark(y, t[sutunlar[ad]], t["ti1_indeksi"], gunler, tekrar)
            for ad in ("A_komsu_maks", "B_yatay_maks")
        },
        "peirce_esiginde": {ad: ikili_metrikler(y, t[s], esikler[ad]) for ad, s in sutunlar.items()},
        "kural_esiginde_7e-7": {
            ad: ikili_metrikler(y, t[sutunlar[ad]], TI1_KURAL_ESIGI) for ad in ("TI1", "A_komsu_maks")
        },
    }


def rapor_haritasi(metinler: pd.DataFrame) -> pd.Series:
    """anahtar -> ham rapor; aynı anahtarda farklı rapor metni varsa anahtar atılır."""
    if metinler is None or metinler.empty:
        return pd.Series(dtype=object)
    cesit = metinler.groupby("anahtar")["rapor"].nunique()
    tek = metinler.drop_duplicates("anahtar").set_index("anahtar")["rapor"]
    return tek[cesit[tek.index] == 1]


def cok_grup_analizi(egitim: pd.DataFrame, test: pd.DataFrame, skorlar: dict, raporlar: pd.Series, tekrar=None) -> dict:
    """§13.2. skorlar: test satırlarıyla hizalı skor dizileri."""

    def etiketle(df):
        rapor = df["anahtar"].map(raporlar)
        gruplar, sinif = rapor.map(tb_gruplari), rapor.map(cok_grup_sinifi)
        var = sinif.notna().to_numpy()
        tek = var & gruplar.map(lambda g: g is not None and len(g) == 1).to_numpy()
        return var, tek, (sinif.fillna(-1).to_numpy() >= 1).astype(int)

    sayimlar = {}
    for ad, df in (("egitim", egitim), ("test", test)):
        var, tek, y_cok = etiketle(df)
        y = df["y"].to_numpy()
        sayimlar[ad] = {
            "ornek": int(len(df)),
            "rapor_bulunan": int(var.sum()),
            "cok_gruplu": int((var & ~tek).sum()),
            "degisen_0_1": int((var & (y == 0) & (y_cok == 1)).sum()),
            "degisen_1_0": int((var & (y == 1) & (y_cok == 0)).sum()),
            "kontrol_tek_grupta_farkli": int((tek & (y != y_cok)).sum()),
        }
    maske, _, y_cok = etiketle(test)
    y, gunler, y_cok = test["y"].to_numpy()[maske], test["gun"].to_numpy()[maske], y_cok[maske]
    return {
        "sayimlar": sayimlar,
        "roc_auc": {
            ad: {"y": _auc(y, np.asarray(s)[maske]), "y_cok": _auc(y_cok, np.asarray(s)[maske])}
            for ad, s in skorlar.items()
        },
        "farklar": {ad: etiket_auc_farki(y_cok, y, np.asarray(s)[maske], gunler, tekrar) for ad, s in skorlar.items()},
    }


def gosterge_edrleri(df: pd.DataFrame, katsayilar: dict) -> pd.DataFrame:
    tablo = gosterge_tablosu(df)
    c1, c2 = katsayilar["c1"], katsayilar["c2"]
    return pd.DataFrame(
        {
            ad: gosterge_edr(tablo[ad], k["ln_ortalama"], k["ln_ss"], c1, c2)
            for ad, k in katsayilar["gostergeler"].items()
        },
        index=df.index,
    )


def auc2_agirliklari(y, edrler: pd.DataFrame) -> dict:
    """w_i = AUC_i² / Σ AUC_j² (Gu ve Wang 2024); AUC_i eğitim günlerinde, gösterge tanımlı satırlarda."""
    y = np.asarray(y, dtype=int)
    auc = {ad: _auc(y[_sonlu(edrler[ad])], edrler[ad].to_numpy()[_sonlu(edrler[ad])]) for ad in edrler}
    toplam = sum(a**2 for a in auc.values())
    return {"egitim_roc_auc": auc, "agirlik": {ad: a**2 / toplam for ad, a in auc.items()}}


def agirlikli_birlesik_edr(edrler: pd.DataFrame, agirlik: dict) -> np.ndarray:
    degerler = edrler[list(agirlik)].to_numpy(dtype=float)
    w = np.array([agirlik[ad] for ad in agirlik])[None, :] * np.isfinite(degerler)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.nansum(np.nan_to_num(degerler) * w, axis=1) / w.sum(axis=1)


def auc2_analizi(egitim: pd.DataFrame, test: pd.DataFrame, katsayilar: dict, tekrar=None) -> dict:
    """§13.3."""
    from turbulans_radar.fizik.edr_esleme import birlesik_edr

    agirliklar = auc2_agirliklari(egitim["y"], gosterge_edrleri(egitim, katsayilar))
    agirlikli = agirlikli_birlesik_edr(gosterge_edrleri(test, katsayilar), agirliklar["agirlik"])
    esit = np.asarray(birlesik_edr(test, katsayilar), dtype=float)
    ti1 = test["ti1_indeksi"].to_numpy(dtype=float)
    m = _sonlu(agirlikli, esit, ti1)
    y, gunler = test["y"].to_numpy()[m], test["gun"].to_numpy()[m]
    return {
        **agirliklar,
        "test_ornek": int(m.sum()),
        "roc_auc": {"agirlikli": _auc(y, agirlikli[m]), "esit": _auc(y, esit[m]), "TI1": _auc(y, ti1[m])},
        "farklar": {
            "agirlikli - esit": _fark(y, agirlikli[m], esit[m], gunler, tekrar),
            "agirlikli - TI1": _fark(y, agirlikli[m], ti1[m], gunler, tekrar),
        },
    }


def teshis_skorlari(df: pd.DataFrame) -> dict:
    return {
        "FRONT": df["frontogenez"].to_numpy(dtype=float),
        "|FRONT|": np.abs(df["frontogenez"].to_numpy(dtype=float)),
        "TEMPG": df["sicaklik_gradyani"].to_numpy(dtype=float),
        "-PV": -df["potansiyel_vortisite"].to_numpy(dtype=float),
    }


def ek_teshis_analizi(egitim: pd.DataFrame, test: pd.DataFrame, tekrar=None) -> dict:
    """§13.4: tek başına teşhisler ve temel + 3 teşhis protokol modeli − temel (aynı satırlarda eğitilir)."""
    from turbulans_radar.ml.yeni_gun_degerlendirmesi import _set_modeli

    e = egitim[_sonlu(*(egitim[s] for s in EK_SET))].reset_index(drop=True)
    t = test[_sonlu(*(test[s] for s in EK_SET))].reset_index(drop=True)
    y, gunler = t["y"].to_numpy(), t["gun"].to_numpy()
    ti1 = t["ti1_indeksi"].to_numpy(dtype=float)
    teshis = teshis_skorlari(t)
    modeller = {"temel": _set_modeli(e, MODEL_OZELLIK_SUTUNLARI), "ek": _set_modeli(e, EK_SET)}
    olasilik = {
        "temel": modeller["temel"]["model"].predict_proba(t[MODEL_OZELLIK_SUTUNLARI])[:, 1],
        "ek": modeller["ek"]["model"].predict_proba(t[EK_SET])[:, 1],
    }
    pv = t["potansiyel_vortisite"].to_numpy(dtype=float)
    return {
        "egitim_ornek": int(len(e)),
        "test_ornek": int(len(t)),
        "test_disi_kalan": int(len(test) - len(t)),
        "roc_auc": {"TI1": _auc(y, ti1), **{ad: _auc(y, s) for ad, s in teshis.items()}},
        "ti1_farki": {ad: _fark(y, s, ti1, gunler, tekrar) for ad, s in teshis.items()},
        "pv_negatif_payi": {"orta_ustu": float(np.mean(pv[y == 1] < 0)), "kontrol": float(np.mean(pv[y == 0] < 0))},
        "modeller": {
            ad: {k: v for k, v in kayit.items() if k != "model"} | {"test_roc_auc": _auc(y, olasilik[ad])}
            for ad, kayit in modeller.items()
        },
        "ek - temel": _fark(y, olasilik["ek"], olasilik["temel"], gunler, tekrar),
    }


def _test_gunleri(yol=None) -> list[str]:
    from turbulans_radar.ml.yeni_gun_degerlendirmesi import BOLUM10_JSON

    with open(yol or BOLUM10_JSON, encoding="utf-8") as dosya:
        return json.load(dosya)["veri"]["test_gunleri"]


def degerlendir(egitim: pd.DataFrame, test: pd.DataFrame, raporlar: pd.Series, katsayilar: dict, tekrar=None) -> dict:
    from turbulans_radar.fizik.edr_esleme import birlesik_edr
    from turbulans_radar.ml.yeni_gun_degerlendirmesi import SETLER, _set_modeli

    modeller = {ad: _set_modeli(egitim, sutunlar) for ad, sutunlar in SETLER.items()}
    skorlar = {
        "TI1": test["ti1_indeksi"].to_numpy(dtype=float),
        "birlesik_edr": np.asarray(birlesik_edr(test, katsayilar), dtype=float),
        **{ad: kayit["model"].predict_proba(test[SETLER[ad]])[:, 1] for ad, kayit in modeller.items()},
    }
    sonlu = _sonlu(*skorlar.values())
    return {
        "kontrol_bolum10_temel_roc_auc": _auc(test["y"].to_numpy(), skorlar["temel"]),
        "fikir10_komsuluk": komsuluk_analizi(egitim, test, tekrar),
        "fikir11_cok_grup": cok_grup_analizi(
            egitim,
            test[sonlu].reset_index(drop=True),
            {ad: s[sonlu] for ad, s in skorlar.items()},
            raporlar,
            tekrar,
        ),
        "fikir24_auc2": auc2_analizi(egitim, test, katsayilar, tekrar),
        "fikir19_ek_teshisler": ek_teshis_analizi(egitim, test, tekrar),
    }


def calistir(cikti: str, motor=None, tekrar=None, arsiv_klasoru=None) -> dict:
    from turbulans_radar.ml.duyarlilik_analizi import arsiv_metinleri
    from turbulans_radar.ml.ml_otomatik_egitim import _atomik_yaz_json, _json_guvenli
    from turbulans_radar.ml.sonuc_disa_aktarimi import git_bilgisi
    from turbulans_radar.ml.yeni_gun_degerlendirmesi import _veriyi_hazirla, bol, dondurma_gunleri

    yol = os.path.join(cikti, CIKTI_ADI)
    if os.path.exists(yol):
        raise SystemExit(f"{yol} var: §13 bir kez çalıştırılır, üzerine yazılmaz.")
    egitim, test = bol(_veriyi_hazirla(motor), dondurma_gunleri())
    test = test[test["gun"].isin(set(_test_gunleri()))].reset_index(drop=True)
    teshis = pencere_teshisleri_onbellekli(pd.concat([egitim, test], ignore_index=True))
    egitim, test = egitim.join(teshis, on="id"), test.join(teshis, on="id")
    katsayilar = katsayilari_yukle()
    if not katsayilar:
        raise SystemExit("edr_esleme_katsayilari.json yok; birleşik EDR hesaplanamaz.")
    rapor: dict[str, Any] = {
        "meta": {
            "protokol": "docs/deney_protokolu.md §13.1–13.4 (keşifsel)",
            "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
            **git_bilgisi(),
            "uyari": UYARI,
        },
        "veri": {
            "egitim_ornek": int(len(egitim)),
            "egitim_gun": int(egitim["gun"].nunique()),
            "test_ornek": int(len(test)),
            "test_gun": int(test["gun"].nunique()),
        },
        **degerlendir(egitim, test, rapor_haritasi(arsiv_metinleri(arsiv_klasoru)), katsayilar, tekrar),
    }
    rapor = _json_guvenli(rapor)
    os.makedirs(cikti, exist_ok=True)
    _atomik_yaz_json(yol, rapor)
    with open(os.path.join(cikti, "README.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    return rapor


def _f(x, bicim="{:.3f}") -> str:
    return "—" if x is None or not np.isfinite(x) else bicim.format(x)


def _fark_satiri(ad, f) -> str:
    return (
        f"| {ad} | {_f(f['fark'], '{:+.3f}')} | [{_f(f['alt'], '{:+.3f}')}; {_f(f['ust'], '{:+.3f}')}] | {f['okuma']} |"
    )


def markdown_ozeti(rapor) -> str:
    v, k10, k11 = rapor["veri"], rapor["fikir10_komsuluk"], rapor["fikir11_cok_grup"]
    k24, k19 = rapor["fikir24_auc2"], rapor["fikir19_ek_teshisler"]
    st = k11["sayimlar"]["test"]
    baslik = "| Karşılaştırma | ROC-AUC farkı | %95 GA | Okuma |\n|---|---|---|---|"
    satirlar = [
        "# Keşifsel göstergeler (protokol §13.1–13.4)",
        "",
        f"Üretim {rapor['meta']['uretim_zamani']} · commit `{rapor['meta'].get('commit') or '—'}`. Eğitim "
        f"{v['egitim_gun']} dondurma günü ({v['egitim_ornek']} örnek), test §10'un sabit {v['test_gun']} günü "
        f"({v['test_ornek']} örnek). Kontrol: temel set test ROC-AUC {_f(rapor['kontrol_bolum10_temel_roc_auc'])} "
        "(§10: 0,685). Hepsi keşifseldir; birincil sonuç, model ve rota kararı değişmez.",
        "",
        f"## Fikir 10: komşuluk maksimumu ({k10['test_ornek']} örnek)",
        "",
        f"ROC-AUC: TI1 {_f(k10['roc_auc']['TI1'])}, A (±1 hücre/seviye/saat) {_f(k10['roc_auc']['A_komsu_maks'])}, "
        f"B (yalnız yatay ±1 hücre) {_f(k10['roc_auc']['B_yatay_maks'])}.",
        "",
        baslik,
        *(_fark_satiri(ad, f) for ad, f in k10["farklar"].items()),
        "",
        "| 7e-7 kural eşiği | POD | POFD | Peirce |",
        "|---|---|---|---|",
        *(
            f"| {ad} | {_f(m['pod'])} | {_f(m['pofd'])} | {_f(m['peirce'])} |"
            for ad, m in k10["kural_esiginde_7e-7"].items()
        ),
        "",
        "| Eğitim Peirce-maks eşiği | Eşik | POD | POFD | Peirce |",
        "|---|---|---|---|---|",
        *(
            f"| {ad} | {m['esik']:.3g} | {_f(m['pod'])} | {_f(m['pofd'])} | {_f(m['peirce'])} |"
            for ad, m in k10["peirce_esiginde"].items()
        ),
        "",
        "## Fikir 11 devamı: çoklu /TB grubu etiketi",
        "",
        f"Test: {st['ornek']} örneğin {st['rapor_bulunan']}'inde ham rapor bulundu; {st['cok_gruplu']} çok gruplu; "
        f"etiket 0→1 {st['degisen_0_1']}, 1→0 {st['degisen_1_0']}; tek grupta ayrıştırma farkı "
        f"{st['kontrol_tek_grupta_farkli']}. Eğitim günlerinde 0→1 {k11['sayimlar']['egitim']['degisen_0_1']}, "
        f"1→0 {k11['sayimlar']['egitim']['degisen_1_0']} (eğitim yeniden yapılmadı).",
        "",
        baslik,
        *(_fark_satiri(f"{ad}: AUC(y_çok) − AUC(y)", f) for ad, f in k11["farklar"].items()),
        "",
        f"## Fikir 24: AUC² ağırlıklı birleşik EDR ({k24['test_ornek']} örnek)",
        "",
        "Ağırlıklar (eğitim AUC): "
        + ", ".join(f"{ad} {k24['agirlik'][ad]:.3f} ({k24['egitim_roc_auc'][ad]:.3f})" for ad in k24["agirlik"])
        + f". Test ROC-AUC: ağırlıklı {_f(k24['roc_auc']['agirlikli'])}, eşit {_f(k24['roc_auc']['esit'])}, "
        f"TI1 {_f(k24['roc_auc']['TI1'])}.",
        "",
        baslik,
        *(_fark_satiri(ad, f) for ad, f in k24["farklar"].items()),
        "",
        f"## Fikir 19: ek teşhisler ({k19['test_ornek']} örnek; NCSU1 hesaplanmadı)",
        "",
        "Tek başına ROC-AUC: " + ", ".join(f"{ad} {_f(a)}" for ad, a in k19["roc_auc"].items()) + ". PV < 0 payı: "
        f"orta-üstü {_f(k19['pv_negatif_payi']['orta_ustu'])}, kontrol {_f(k19['pv_negatif_payi']['kontrol'])}.",
        "",
        baslik,
        *(_fark_satiri(f"{ad} − TI1", f) for ad, f in k19["ti1_farki"].items()),
        _fark_satiri(
            f"temel + 3 teşhis ({k19['modeller']['ek']['secilen']}) − temel ({k19['modeller']['temel']['secilen']})",
            k19["ek - temel"],
        ),
        "",
        "Çoklu karşılaştırma düzeltmesi yapılmadı; satırlar keşifseldir. " + UYARI,
    ]
    return "\n".join(satirlar) + "\n"


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="Deney protokolü §13.1–13.4: keşifsel göstergeler (bir kez).")
    ayristirici.add_argument("--cikti", required=True, help=f"Sonuç klasörü ({CIKTI_ADI})")
    ayristirici.add_argument("--tekrar", type=int, default=None)
    argumanlar = ayristirici.parse_args(argv)
    print(markdown_ozeti(calistir(argumanlar.cikti, tekrar=argumanlar.tekrar)))


if __name__ == "__main__":
    ana()
