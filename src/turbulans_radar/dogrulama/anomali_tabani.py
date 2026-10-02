"""
anomali_tabani.py
--------------------
Sanal PIREP (M6) kurallarına denetimsiz karşılaştırma tabanı (fikir:
debjit450/skywatch-live): Isolation Forest ve LOF, seyirdeki ADS-B
noktalarında olağan dışı hareketi işaretler; aynı PIREP tüpü ve aynı POD/POFD
ölçütüyle (dogrulama/sanal_pirep_dogrulama.py) kural tabanlı tespitle
kıyaslanır.

Adillik: veri aynıdır (sanal PIREP doğrulamasının önbellekteki PIREP çevresi
izleri; yeni OpenSky sorgusu yok), PIREP etiketi modele hiç girmez, ve
denetimsiz yöntemlere kural tabanlı yöntemin işaretlediği seyir noktası oranı
kadar alarm hakkı verilir (eşit alarm bütçesi). Denetimsiz işaretler etiket
olarak KULLANILMAZ; doğrulanmış referansları yoktur.

Özellikler yalnızca ADS-B'den: seviyeden sapma, 60 sn irtifa oynaklığı,
düşey hız ve düşey hız değişimi.

    turbulans-anomali-tabani --pozitif 50 --negatif 50
"""

import argparse
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler

from turbulans_radar import config
from turbulans_radar.dogrulama.sanal_pirep_dogrulama import (
    _oran,
    pirep_cevresi_izleri,
    pirep_isabeti,
    pirepleri_sec,
)
from turbulans_radar.fizik.sanal_pirep import _iz_hazirla, coklu_izden_olaylar, seyir_maskesi, yakin_mi

OZELLIKLER = ["mutlak_sapma_ft", "irtifa_oynakligi_ft", "mutlak_dikey_hiz_ftdk", "dikey_hiz_degisimi_ftdk"]
MIN_ALARM_ORANI = 0.001


def seyir_noktalari(izler: pd.DataFrame) -> pd.DataFrame:
    """Uçak başına seyir noktaları ve özellikleri."""
    parcalar = []
    for icao24, iz in izler.groupby("icao24"):
        df = _iz_hazirla(iz)
        if len(df) < 3:
            continue
        df = seyir_maskesi(df)
        zamanli = df.set_index("zaman")["irtifa_ft"]
        df["irtifa_oynakligi_ft"] = zamanli.rolling("60s", center=True).std().to_numpy()
        df["mutlak_sapma_ft"] = df["sapma_ft"].abs()
        df["mutlak_dikey_hiz_ftdk"] = df["dikey_hiz_ftdk"].abs()
        df["dikey_hiz_degisimi_ftdk"] = df["dikey_hiz_ftdk"].diff().abs()
        df["icao24"] = str(icao24)
        parcalar.append(df[df["seyirde"]])
    if not parcalar:
        return pd.DataFrame(columns=["icao24", "zaman", "enlem", "boylam", "irtifa_ft", *OZELLIKLER])
    return pd.concat(parcalar, ignore_index=True)


def kural_nokta_orani(noktalar: pd.DataFrame, olaylar: pd.DataFrame) -> float:
    """Kural tabanlı olayların kapsadığı seyir noktası oranı (eşit alarm bütçesi)."""
    if noktalar.empty or olaylar.empty:
        return 0.0
    kapsanan = pd.Series(False, index=noktalar.index)
    for olay in olaylar.itertuples(index=False):
        kapsanan |= (
            (noktalar["icao24"] == str(olay.icao24))
            & (noktalar["zaman"] >= olay.baslangic)
            & (noktalar["zaman"] <= olay.bitis)
        )
    return float(kapsanan.mean())


def anomali_isaretle(noktalar: pd.DataFrame, oran: float, tohum: int = 0) -> dict[str, np.ndarray]:
    """{'isolation_forest': bool[], 'lof': bool[]} -- her yöntem en olağan dışı
    'oran' kadar noktayı işaretler."""
    oran = min(max(oran, MIN_ALARM_ORANI), 0.5)
    x = RobustScaler().fit_transform(noktalar[OZELLIKLER].fillna(0.0).to_numpy())
    adet = max(1, int(round(oran * len(x))))

    def _en_ust(skor):
        isaret = np.zeros(len(skor), dtype=bool)
        isaret[np.argsort(-skor)[:adet]] = True
        return isaret

    if_skor = -IsolationForest(n_estimators=200, random_state=tohum).fit(x).score_samples(x)
    lof = LocalOutlierFactor(n_neighbors=min(20, max(2, len(x) - 1)))
    lof.fit(x)
    return {"isolation_forest": _en_ust(if_skor), "lof": _en_ust(-lof.negative_outlier_factor_)}


def _isabet(pirep, noktalar_isaretli: pd.DataFrame) -> bool:
    if noktalar_isaretli.empty:
        return False
    return bool(
        yakin_mi(
            pirep["enlem"],
            pirep["boylam"],
            pirep["zaman"],
            pirep["irtifa_ft"],
            noktalar_isaretli["enlem"].to_numpy(),
            noktalar_isaretli["boylam"].to_numpy(),
            noktalar_isaretli["zaman"],
            noktalar_isaretli["irtifa_ft"].to_numpy(),
            config.SANAL_PIREP_KUME_YARICAPI_KM,
            pd.Timedelta(minutes=config.SANAL_PIREP_DOGRULAMA_PENCERE_DAKIKA),
            config.SANAL_PIREP_KUME_IRTIFA_FARKI_FT,
        ).any()
    )


def karsilastir(pirep_izleri: list[tuple[dict, pd.DataFrame]], tohum: int = 0) -> dict:
    """pirep_izleri: (pirep, izler). Kural ve iki denetimsiz yöntem için POD/POFD."""
    satirlar, havuz, kural_olaylari = [], [], []
    for sira, (pirep, izler) in enumerate(pirep_izleri):
        kural = pirep_isabeti(pirep, izler)
        if not kural["degerlendirilebilir"]:
            continue
        noktalar = seyir_noktalari(izler).assign(_pirep=sira)
        olaylar, _ = coklu_izden_olaylar(izler)
        kural_olaylari.append((noktalar, olaylar))
        havuz.append(noktalar)
        satirlar.append({"sira": sira, "sinif": int(pirep["sinif"]), "kural": kural["isabet"], "pirep": pirep})
    if not satirlar:
        return {"durum": "degerlendirilebilir_pirep_yok"}
    tum = pd.concat(havuz, ignore_index=True)
    toplam_kapsanan = sum(kural_nokta_orani(n, o) * len(n) for n, o in kural_olaylari)
    oran = toplam_kapsanan / len(tum) if len(tum) else 0.0
    isaretler = anomali_isaretle(tum, oran, tohum)
    for satir in satirlar:
        maske = (tum["_pirep"] == satir["sira"]).to_numpy()
        for yontem, isaret in isaretler.items():
            satir[yontem] = _isabet(satir["pirep"], tum[maske & isaret])
    df = pd.DataFrame(satirlar)
    sonuc = {}
    for yontem in ("kural", "isolation_forest", "lof"):
        pod = _oran(int(df.loc[df["sinif"] >= 1, yontem].sum()), int((df["sinif"] >= 1).sum()))
        pofd = _oran(int(df.loc[df["sinif"] == 0, yontem].sum()), int((df["sinif"] == 0).sum()))
        sonuc[yontem] = {
            "pod": pod,
            "pofd": pofd,
            "peirce": None if pod["oran"] is None or pofd["oran"] is None else round(pod["oran"] - pofd["oran"], 4),
        }
    return {
        **sonuc,
        "degerlendirilebilir_pirep": len(df),
        "seyir_noktasi": int(len(tum)),
        "alarm_orani": round(max(oran, MIN_ALARM_ORANI), 5),
        "kural_ile_ayni_sonuc": {
            y: round(float((df[y] == df["kural"]).mean()), 3) for y in ("isolation_forest", "lof")
        },
        "not": "Denetimsiz işaretler etiket değildir; eşit alarm bütçesiyle karşılaştırma tabanıdır.",
    }


def calistir(pozitif=50, negatif=50, tohum=0, motor=None) -> dict:
    """Yalnızca önbellekteki izlerle (OpenSky'a sorgu gitmez)."""
    pirep_izleri = []
    for pirep in pirepleri_sec(pozitif, negatif, motor=motor):
        izler = pirep_cevresi_izleri(pirep, sorgu_izni=False)
        if izler is not None:
            pirep_izleri.append((pirep, izler))
    return {"izi_olan_pirep": len(pirep_izleri), **karsilastir(pirep_izleri, tohum)}


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Sanal PIREP kuralları vs denetimsiz anomali tabanı (önbellekten)."
    )
    ayristirici.add_argument("--pozitif", type=int, default=50)
    ayristirici.add_argument("--negatif", type=int, default=50)
    ayristirici.add_argument("--tohum", type=int, default=0)
    a = ayristirici.parse_args(argv)
    print(json.dumps(calistir(a.pozitif, a.negatif, a.tohum), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    ana()
