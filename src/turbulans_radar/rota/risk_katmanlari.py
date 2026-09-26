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
  - PoligonKisitKatmani: poligon + irtifa bandı + geçerlilik penceresiyle
                         tanımlı SERT kısıtların ortak tabanı (4 boyutlu:
                         yatay poligon + irtifa bandı + uçağın o noktaya
                         VARIŞ zamanında geçerlilik). Kenar kontrolü, iki
                         düğüm arasındaki bacağın poligonu KESİP KESMEDİĞİNE
                         de bakar -- seyrek ızgarada küçük bir alan iki düğüm
                         arasından "atlanmasın" diye.
  - SigmetKisitKatmani : aktif SIGMET'ler (kaçınılan tehlike türleri)
  - KisitliSahaKatmani : çatışma bölgesi / yasak / kısıtlı sahalar (süresiz
                         olabilir -- boş geçerlilik sınırı = sınırsız)
"""

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd
import shapely
import shapely.affinity

from turbulans_radar import config
from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir

TURBULANS_CEZASI_SANIYE = 6 * 3600.0


@dataclass
class RiskDegerlendirmesi:
    yasak_dugumler: set = field(default_factory=set)
    yasak_kenarlar: set = field(default_factory=set)
    dugum_cezasi: dict = field(default_factory=dict)


class RiskKatmani(Protocol):
    ad: str

    def degerlendir(
        self, konumlar: dict, zamanlar: dict, kenarlar: list, irtifa_m: float, zaman_belirsizligi: dict | None = None
    ) -> RiskDegerlendirmesi: ...


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

    def degerlendir(self, konumlar, zamanlar, kenarlar, irtifa_m, zaman_belirsizligi=None) -> RiskDegerlendirmesi:
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


def sigmet_geometrisi(poligon):
    """SIGMET köşelerinden -180..180 boylam uzayında GEÇERLİ bir geometri.
    Kendini kesen halkalar (AWC akışında gerçekten görülüyor) make_valid ile
    onarılır; 180°'yi aşan (antimeridyen, bkz. sigmet_saglayici) parça -360
    kaydırılarak batı yarım küreye taşınır."""
    geometri = shapely.make_valid(shapely.Polygon(poligon))
    if max(boylam for boylam, _ in poligon) <= 180.0:
        return geometri
    dogu = shapely.intersection(geometri, shapely.box(-180.0, -90.0, 180.0, 90.0))
    bati = shapely.affinity.translate(
        shapely.intersection(geometri, shapely.box(180.0, -90.0, 540.0, 90.0)), xoff=-360.0
    )
    return shapely.union(dogu, bati)


class PoligonKisitKatmani:
    """kayitlar: 'poligon', 'taban_ft', 'tavan_ft', 'gecerlilik_baslangic',
    'gecerlilik_bitis' alanlı sözlükler; None taban = yer, None tavan =
    sınırsız, None geçerlilik sınırı = o yönde süresiz."""

    ad = "poligon"

    def __init__(self, kayitlar):
        self.kayitlar = list(kayitlar)
        self._poligonlar = [sigmet_geometrisi(k["poligon"]) for k in self.kayitlar]
        for poligon in self._poligonlar:
            shapely.prepare(poligon)

    @staticmethod
    def _irtifada_mi(kayit, irtifa_ft) -> bool:
        taban = kayit["taban_ft"] if kayit["taban_ft"] is not None else 0
        tavan = kayit["tavan_ft"] if kayit["tavan_ft"] is not None else float("inf")
        return taban <= irtifa_ft <= tavan

    @staticmethod
    def _aktif_maskesi(kayit, zamanlar, belirsizlikler=None) -> np.ndarray:
        """Düğüm zamanı belirsizse ([z - d, z + d]) aralık geçerlilikle
        kesiştiğinde aktif sayılır -- muhafazakâr."""
        baslangic, bitis = kayit.get("gecerlilik_baslangic"), kayit.get("gecerlilik_bitis")
        baslangic = _utc(baslangic) if baslangic is not None else None
        bitis = _utc(bitis) if bitis is not None else None
        belirsizlikler = belirsizlikler or [pd.Timedelta(0)] * len(zamanlar)
        return np.array(
            [
                (baslangic is None or baslangic <= z + d) and (bitis is None or z - d <= bitis)
                for z, d in zip(zamanlar, belirsizlikler)
            ],
            dtype=bool,
        )

    def degerlendir(self, konumlar, zamanlar, kenarlar, irtifa_m, zaman_belirsizligi=None) -> RiskDegerlendirmesi:
        """zaman_belirsizligi: düğüm -> Timedelta; A* rüzgarsız nominal
        zamanlarla aradığı için gerçek (rüzgarlı) varış bu kadar kayabilir."""
        dugumler = list(konumlar)
        if not self.kayitlar or not dugumler:
            return RiskDegerlendirmesi()
        irtifa_ft = irtifa_m / 0.3048
        indeks = {d: i for i, d in enumerate(dugumler)}
        boylam = np.array([konumlar[d][1] for d in dugumler])
        enlem = np.array([konumlar[d][0] for d in dugumler])
        dugum_zamanlari = [_utc(zamanlar[d]) for d in dugumler]
        belirsizlikler = [zaman_belirsizligi[d] for d in dugumler] if zaman_belirsizligi else None
        cizgiler = (
            shapely.linestrings(
                [[(konumlar[a][1], konumlar[a][0]), (konumlar[b][1], konumlar[b][0])] for a, b in kenarlar]
            )
            if kenarlar
            else np.array([])
        )

        yasak_dugum = np.zeros(len(dugumler), dtype=bool)
        yasak_kenar = np.zeros(len(kenarlar), dtype=bool)
        for kayit, poligon in zip(self.kayitlar, self._poligonlar):
            if not self._irtifada_mi(kayit, irtifa_ft):
                continue
            aktif = self._aktif_maskesi(kayit, dugum_zamanlari, belirsizlikler)
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
        """Bir rotanın aktif kısıta giren nokta + bacak sayısı (0 = kısıt sağlanıyor)."""
        konumlar = {(i, 0): (float(e), float(b)) for i, (e, b) in enumerate(zip(enlemler, boylamlar))}
        zaman_sozlugu = {(i, 0): z for i, z in enumerate(zamanlar)}
        kenarlar = [((i, 0), (i + 1, 0)) for i in range(len(konumlar) - 1)]
        sonuc = self.degerlendir(konumlar, zaman_sozlugu, kenarlar, irtifa_m)
        return len(sonuc.yasak_dugumler) + len(sonuc.yasak_kenarlar)

    def noktayi_iceren_kayitlar(self, enlem, boylam) -> list[dict]:
        return [k for k, p in zip(self.kayitlar, self._poligonlar) if shapely.intersects_xy(p, boylam, enlem)]


class SigmetKisitKatmani(PoligonKisitKatmani):
    ad = "sigmet"

    def __init__(self, sigmetler, tehlikeler=None):
        tehlikeler = {t.upper() for t in (tehlikeler or config.SIGMET_KACINILACAK_TEHLIKELER)}
        tehlikeler.add(config.SIGMET_BILINMEYEN_TEHLIKE)
        super().__init__(s for s in sigmetler if s["tehlike"].upper() in tehlikeler)

    @property
    def sigmetler(self) -> list[dict]:
        return self.kayitlar


class KisitliSahaKatmani(PoligonKisitKatmani):
    ad = "kisitli_saha"
