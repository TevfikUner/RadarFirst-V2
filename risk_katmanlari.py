"""
risk_katmanlari.py
---------------------
A* rota aramasının (rota_optimizasyonu._a_yildiz_ile_rota_ara) MODÜLER
risk/maliyet katmanları. Her katman aynı düğüm/kenar grafı için bir
RiskDegerlendirmesi üretir:
  - yasak_dugumler / yasak_kenarlar : SERT kısıt -- A* asla geçmez
  - dugum_cezasi                    : YUMUŞAK kısıt -- düğüme girişe eklenen
                                      saniye cinsinden maliyet
Yeni bir risk kaynağı (örn. ML olasılığı) eklemek için sadece yeni bir
katman yazılır; A*'ın kendisi değişmez.

Katmanlar:
  - Ti1CezaKatmani     : ERA5/GFS'ten hesaplanan Ellrod TI1 >= eşik -> ceza
  - SigmetKisitKatmani : aktif SIGMET poligonu -> yasak (4 boyutlu: yatay
                         poligon + irtifa bandı + uçağın o noktaya VARIŞ
                         zamanında geçerlilik). Kenar kontrolü, iki düğüm
                         arasındaki bacağın poligonu KESİP KESMEDİĞİNE de
                         bakar -- seyrek ızgarada küçük bir SIGMET iki düğüm
                         arasından "atlanmasın" diye.
"""

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd
import shapely

import config
from eslestirme import rotayi_hava_durumuyla_eslestir

TURBULANS_CEZASI_SANIYE = 6 * 3600.0


@dataclass
class RiskDegerlendirmesi:
    yasak_dugumler: set = field(default_factory=set)
    yasak_kenarlar: set = field(default_factory=set)
    dugum_cezasi: dict = field(default_factory=dict)


class RiskKatmani(Protocol):
    ad: str

    def degerlendir(self, konumlar: dict, zamanlar: dict, kenarlar: list, irtifa_m: float) -> RiskDegerlendirmesi: ...


def degerlendirmeleri_birlestir(degerlendirmeler) -> RiskDegerlendirmesi:
    toplam = RiskDegerlendirmesi()
    for d in degerlendirmeler:
        toplam.yasak_dugumler |= d.yasak_dugumler
        toplam.yasak_kenarlar |= d.yasak_kenarlar
        for dugum, ceza in d.dugum_cezasi.items():
            toplam.dugum_cezasi[dugum] = toplam.dugum_cezasi.get(dugum, 0.0) + ceza
    return toplam


def _utc(zaman) -> pd.Timestamp:
    ts = pd.Timestamp(zaman)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def rota_ti1_degerleri(enlemler, boylamlar, irtifa_m, zamanlar, veri_kupu) -> np.ndarray:
    """Noktaların Ellrod TI1 değerleri -- projenin ANA analiz koduyla
    (eslestirme.rotayi_hava_durumuyla_eslestir), ayrı bir türbülans mantığı
    icat etmemek için."""
    rota_df = pd.DataFrame({"zaman": list(zamanlar), "enlem": enlemler, "boylam": boylamlar, "geo_irtifa_m": irtifa_m})
    return rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)["ti1_indeksi"].to_numpy(dtype=float)


class Ti1CezaKatmani:
    ad = "ti1"

    def __init__(self, veri_kupu, esik=None, ceza_saniye=TURBULANS_CEZASI_SANIYE):
        self.veri_kupu = veri_kupu
        self.esik = config.TI1_ESIK_ORTA_SIDDETLI if esik is None else esik
        self.ceza_saniye = ceza_saniye

    def degerlendir(self, konumlar, zamanlar, kenarlar, irtifa_m) -> RiskDegerlendirmesi:
        dugumler = list(konumlar)
        if not dugumler:
            return RiskDegerlendirmesi()
        ti1 = rota_ti1_degerleri(
            np.array([konumlar[d][0] for d in dugumler]),
            np.array([konumlar[d][1] for d in dugumler]),
            irtifa_m,
            [zamanlar[d] for d in dugumler],
            self.veri_kupu,
        )
        return RiskDegerlendirmesi(
            dugum_cezasi={d: self.ceza_saniye for d, t in zip(dugumler, ti1) if not np.isnan(t) and t >= self.esik}
        )


class SigmetKisitKatmani:
    ad = "sigmet"

    def __init__(self, sigmetler, tehlikeler=None):
        tehlikeler = {t.upper() for t in (tehlikeler or config.SIGMET_KACINILACAK_TEHLIKELER)}
        self.sigmetler = [s for s in sigmetler if s["tehlike"].upper() in tehlikeler]
        self._poligonlar = [shapely.Polygon(s["poligon"]) for s in self.sigmetler]
        for poligon in self._poligonlar:
            shapely.prepare(poligon)

    @staticmethod
    def _irtifada_mi(sigmet, irtifa_ft) -> bool:
        taban = sigmet["taban_ft"] if sigmet["taban_ft"] is not None else 0
        tavan = sigmet["tavan_ft"] if sigmet["tavan_ft"] is not None else float("inf")
        return taban <= irtifa_ft <= tavan

    @staticmethod
    def _aktif_maskesi(sigmet, zamanlar) -> np.ndarray:
        baslangic, bitis = _utc(sigmet["gecerlilik_baslangic"]), _utc(sigmet["gecerlilik_bitis"])
        return np.array([baslangic <= z <= bitis for z in zamanlar], dtype=bool)

    def degerlendir(self, konumlar, zamanlar, kenarlar, irtifa_m) -> RiskDegerlendirmesi:
        dugumler = list(konumlar)
        if not self.sigmetler or not dugumler:
            return RiskDegerlendirmesi()
        irtifa_ft = irtifa_m / 0.3048
        indeks = {d: i for i, d in enumerate(dugumler)}
        boylam = np.array([konumlar[d][1] for d in dugumler])
        enlem = np.array([konumlar[d][0] for d in dugumler])
        dugum_zamanlari = [_utc(zamanlar[d]) for d in dugumler]
        cizgiler = (
            shapely.linestrings(
                [[(konumlar[a][1], konumlar[a][0]), (konumlar[b][1], konumlar[b][0])] for a, b in kenarlar]
            )
            if kenarlar
            else np.array([])
        )

        yasak_dugum = np.zeros(len(dugumler), dtype=bool)
        yasak_kenar = np.zeros(len(kenarlar), dtype=bool)
        for sigmet, poligon in zip(self.sigmetler, self._poligonlar):
            if not self._irtifada_mi(sigmet, irtifa_ft):
                continue
            aktif = self._aktif_maskesi(sigmet, dugum_zamanlari)
            if not aktif.any():
                continue
            yasak_dugum |= aktif & shapely.intersects_xy(poligon, boylam, enlem)
            if len(kenarlar):
                kenar_aktif = np.array([aktif[indeks[a]] or aktif[indeks[b]] for a, b in kenarlar], dtype=bool)
                yasak_kenar |= kenar_aktif & shapely.intersects(cizgiler, poligon)

        return RiskDegerlendirmesi(
            yasak_dugumler={d for d, y in zip(dugumler, yasak_dugum) if y},
            yasak_kenarlar={k for k, y in zip(kenarlar, yasak_kenar) if y},
        )

    def rota_ihlal_sayisi(self, enlemler, boylamlar, zamanlar, irtifa_m) -> int:
        """Bir rotanın aktif SIGMET'e giren nokta + bacak sayısı (0 = kısıt sağlanıyor)."""
        konumlar = {(i, 0): (float(e), float(b)) for i, (e, b) in enumerate(zip(enlemler, boylamlar))}
        zaman_sozlugu = {(i, 0): z for i, z in enumerate(zamanlar)}
        kenarlar = [((i, 0), (i + 1, 0)) for i in range(len(konumlar) - 1)]
        sonuc = self.degerlendir(konumlar, zaman_sozlugu, kenarlar, irtifa_m)
        return len(sonuc.yasak_dugumler) + len(sonuc.yasak_kenarlar)
