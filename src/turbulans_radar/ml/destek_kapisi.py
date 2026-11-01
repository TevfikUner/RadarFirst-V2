"""
destek_kapisi.py
----------------
Kurul raporu #29 (VER-08 devamı): dağılım dışı (OOD) kapısı. Aktif modelin eğitim örneklerinden
özellik başına %0,5–%99,5 destek aralığı tutulur; bir girdinin herhangi bir özelliği bu aralığın
dışındaysa ML olasılığı ve konformal durum verilmez, "kapsam dışı" yazılır (#10: Türkiye girdileri
ABD eğitim verisine göre kaymış, Türkiye'de beceri ölçülmedi).

Aralık yeni modellerde bilgi JSON'undaki 'destek_araligi'dadır. Bu alan olmadan eğitilmiş aktif
model için `turbulans-ml-destek` aralığı model dosyasına dokunmadan ayrı bir dosyaya yazar; dosya
aktif modelin SHA-256'sına bağlıdır, model değişince kendiliğinden geçersiz olur.

Sınır: tek tek özellik aralığına bakar (marjinal destek); özelliklerin birlikte görülmemiş
birleşimlerini yakalamaz. Kapının içinde kalmak Türkiye'de becerinin kanıtı değildir.
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

from turbulans_radar import config

DESTEK_YUZDELIKLERI = (0.5, 99.5)
DESTEK_DOSYA_YOLU = os.path.join(config.MODEL_KLASORU, "destek_araligi.json")
ORNEK_FARKI_TOLERANSI = 0.01


def destek_araligi_hesapla(X: pd.DataFrame, yuzdelikler=DESTEK_YUZDELIKLERI) -> dict:
    return {
        "yuzdelikler": list(yuzdelikler),
        "ornek_sayisi": int(len(X)),
        "ozellikler": {
            str(s): [float(v) for v in np.nanpercentile(X[s].to_numpy(dtype=float), yuzdelikler)] for s in X.columns
        },
    }


def aktif_destek_araligi(bilgi: dict | None, yol: str | None = None) -> dict | None:
    """Önce bilginin kendi aralığı; yoksa SHA'sı aynı olan ayrı dosya; ikisi de yoksa None."""
    if not bilgi:
        return None
    if bilgi.get("destek_araligi"):
        return bilgi["destek_araligi"]
    try:
        with open(yol or DESTEK_DOSYA_YOLU, encoding="utf-8") as dosya:
            kayit = json.load(dosya)
    except (FileNotFoundError, ValueError):
        return None
    sha = bilgi.get("model_sha256")
    return kayit.get("destek_araligi") if sha and kayit.get("model_sha256") == sha else None


def destek_disi_ozellikler(ozellikler: pd.DataFrame, destek: dict) -> list[list[str]]:
    """Her satır için aralık dışındaki özellik adları (boş liste: destek içinde)."""
    sonuc: list[list[str]] = [[] for _ in range(len(ozellikler))]
    for sutun, (alt, ust) in destek["ozellikler"].items():
        if sutun not in ozellikler:
            continue
        degerler = ozellikler[sutun].to_numpy(dtype=float)
        for i in np.flatnonzero((degerler < alt) | (degerler > ust)):
            sonuc[i].append(sutun)
    return sonuc


def destek_dosyasi_yaz(motor=None, yol: str | None = None) -> dict:
    """Aktif modelin eğitim günlerindeki örneklerden aralığı hesaplar (veritabanı yalnız okunur)."""
    from turbulans_radar.ml.ml_otomatik_egitim import _atomik_yaz_json, veritabanindan_veri_hazirla
    from turbulans_radar.ml.turbulans_ml_modeli import model_bilgisini_yukle

    bilgi = model_bilgisini_yukle()
    if not bilgi or not bilgi.get("model_sha256") or not bilgi.get("egitim_gunleri"):
        raise SystemExit("Aktif model bilgisi, model_sha256 ya da egitim_gunleri yok; aralık yazılmadı.")
    X, _, gunler = veritabanindan_veri_hazirla(motor)
    X = X.loc[gunler.isin(bilgi["egitim_gunleri"]).to_numpy(), bilgi["ozellik_sutunlari"]]
    beklenen = int(bilgi.get("egitim_orneklem_sayisi") or 0)
    if abs(len(X) - beklenen) > ORNEK_FARKI_TOLERANSI * beklenen:
        raise SystemExit(
            f"Eğitim günlerinde {len(X)} örnek var, model bilgisi {beklenen} diyor; veri değişmiş, aralık yazılmadı."
        )
    kayit = {
        "model_sha256": bilgi["model_sha256"],
        "destek_araligi": destek_araligi_hesapla(X),
        "model_egitim_orneklem_sayisi": beklenen,
        "not": "Aralık, aktif modelin eğitim günlerindeki güncel eşleşmiş örneklerden hesaplandı; model eğitildikten "
        "sonra bu günlere eklenen örnekler de dahildir (ornek_sayisi ile model_egitim_orneklem_sayisi farkı).",
    }
    _atomik_yaz_json(yol or DESTEK_DOSYA_YOLU, kayit)
    return kayit


def kapanma_ozeti(ozellikler: pd.DataFrame, destek: dict) -> dict:
    """Kapının (en az bir özellik destek dışı) kapandığı oran ve özellik başına dışarıda kalan sayı."""
    disarida = destek_disi_ozellikler(ozellikler, destek)
    sayac: dict[str, int] = {}
    for liste in disarida:
        for sutun in liste:
            sayac[sutun] = sayac.get(sutun, 0) + 1
    kapanan = sum(bool(liste) for liste in disarida)
    return {
        "nokta": len(disarida),
        "kapanan": kapanan,
        "kapanma_orani": round(kapanan / len(disarida), 4) if disarida else None,
        "ozellik_basina": dict(sorted(sayac.items(), key=lambda k: -k[1])),
    }


def ucus_kapanma_orani(ucus: str, tarih: str, kup_yolu: str, motor=None) -> dict:
    import xarray as xr

    from turbulans_radar.depo.veritabani import ucus_olcumlerini_dataframe_olarak_getir
    from turbulans_radar.ml.turbulans_ml_modeli import model_bilgisini_yukle, ozellikleri_cikar

    destek = aktif_destek_araligi(model_bilgisini_yukle())
    if destek is None:
        raise SystemExit("Aktif modelin destek aralığı yok (önce turbulans-ml-destek).")
    olcumler = ucus_olcumlerini_dataframe_olarak_getir(ucus, tarih, motor=motor)
    if olcumler is None or olcumler.empty:
        raise SystemExit(f"{ucus} / {tarih} veritabanında yok.")
    olcumler = olcumler[olcumler["ti1_indeksi"].notna()]
    with xr.open_dataset(kup_yolu) as kup:
        kup = kup.load()
    ozellikler = ozellikleri_cikar(olcumler[["zaman", "enlem", "boylam", "irtifa_m"]].reset_index(drop=True), kup)
    ozellikler = ozellikler[ozellikler["ti1_indeksi"].notna()].reset_index(drop=True)
    return {"ucus": ucus, "tarih": tarih, "kup": os.path.basename(kup_yolu), **kapanma_ozeti(ozellikler, destek)}


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="Aktif modelin özellik destek aralığını yazar (kurul #29).")
    ayristirici.add_argument("--ucus", help="UCUS:YYYY-AA-GG; aralık yazılmaz, uçuş noktalarında kapanma oranı ölçülür")
    ayristirici.add_argument("--kup", help="--ucus için ERA5 küpü (aktif modelin seviyeleriyle)")
    arg = ayristirici.parse_args(argv)
    if arg.ucus:
        if not arg.kup:
            ayristirici.error("--ucus için --kup gerekli")
        ucus, _, tarih = arg.ucus.partition(":")
        print(json.dumps(ucus_kapanma_orani(ucus, tarih, arg.kup), ensure_ascii=False, indent=2))
        return
    kayit = destek_dosyasi_yaz()
    print(json.dumps(kayit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
