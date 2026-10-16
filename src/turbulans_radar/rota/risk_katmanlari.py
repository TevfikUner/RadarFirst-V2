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
  - SigmetKisitKatmani : aktif SIGMET'ler (kaçınılan tehlike türleri), yanal ve
                         dikey tamponla (config.SIGMET_YANAL_TAMPON_NM, _DIKEY_TAMPON_FT)
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
from turbulans_radar.fizik.ti1_esigi import etkin_ti1_esigi
from turbulans_radar.veri.saha_aktivasyonu import aktif_maskesi

TURBULANS_CEZASI_SANIYE = 6 * 3600.0
_KM_PER_DERECE = 111.2
_KT_KM_SAAT = 1.852
_NM_KM = 1.852


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


def rota_eslesmesi(enlemler, boylamlar, irtifa_m, zamanlar, veri_kupu) -> pd.DataFrame:
    """Noktaların hava eşleşmesi -- projenin ANA analiz koduyla
    (eslestirme.rotayi_hava_durumuyla_eslestir), ayrı bir türbülans mantığı
    icat etmemek için."""
    rota_df = pd.DataFrame({"zaman": list(zamanlar), "enlem": enlemler, "boylam": boylamlar, "geo_irtifa_m": irtifa_m})
    return rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)


def rota_ti1_degerleri(enlemler, boylamlar, irtifa_m, zamanlar, veri_kupu) -> np.ndarray:
    return rota_eslesmesi(enlemler, boylamlar, irtifa_m, zamanlar, veri_kupu)["ti1_indeksi"].to_numpy(dtype=float)


class Ti1CezaKatmani:
    ad = "ti1"

    def __init__(self, veri_kupu, esik=None, ceza_saniye=TURBULANS_CEZASI_SANIYE, onbellek=None):
        """onbellek: aynı küp ve aynı ızgara için TI1'i paylaşan sözlük (tek rota isteği
        içinde, yalnız ceza düzeyi farklı katmanlar arasında)."""
        self.veri_kupu = veri_kupu
        self.esik = etkin_ti1_esigi() if esik is None else esik
        self.ceza_saniye = ceza_saniye
        self.onbellek = onbellek

    def degerlendir(self, konumlar, zamanlar, kenarlar, irtifa_m, zaman_belirsizligi=None) -> RiskDegerlendirmesi:
        dugumler = list(konumlar)
        if not dugumler:
            return RiskDegerlendirmesi()
        anahtar = None
        if self.onbellek is not None:
            anahtar = (float(irtifa_m), tuple(konumlar[d] for d in dugumler), tuple(zamanlar[d] for d in dugumler))
        ti1 = None if anahtar is None else self.onbellek.get(anahtar)
        if ti1 is None:
            ti1 = rota_ti1_degerleri(
                np.array([konumlar[d][0] for d in dugumler]),
                np.array([konumlar[d][1] for d in dugumler]),
                irtifa_m,
                [zamanlar[d] for d in dugumler],
                self.veri_kupu,
            )
            if anahtar is not None:
                self.onbellek[anahtar] = ti1
        return RiskDegerlendirmesi(
            dugum_cezasi={
                d: self.ceza_saniye for d, t in zip(dugumler, ti1, strict=True) if not np.isnan(t) and t >= self.esik
            }
        )


def km_tamponla(geometri, tampon_km):
    """Geometriyi yerel eşdikdörtgen km düzleminde tamponlar (negatifse
    daraltır). Boylam ölçeği geometrinin EN YÜKSEK mutlak enleminden (75°'ye
    kelepçeli) alınır: derece cinsinden en geniş tampon, her noktada en az
    `|tampon_km|` verir (bkz. rota_optimizasyonu._km_boylam_derecesine_cevir)."""
    if tampon_km == 0 or geometri.is_empty:
        return geometri
    _, enlem0, _, enlem1 = shapely.bounds(geometri)
    kos_enlem = np.cos(np.radians(min(max(abs(enlem0), abs(enlem1)), 75.0)))
    olcek = (_KM_PER_DERECE * kos_enlem, _KM_PER_DERECE)
    km = shapely.affinity.scale(geometri, *olcek, origin=(0.0, 0.0))
    tamponlu = shapely.buffer(km, tampon_km, quad_segs=8)
    return shapely.affinity.scale(tamponlu, 1.0 / olcek[0], 1.0 / olcek[1], origin=(0.0, 0.0))


def _antimeridyende_bol(geometri):
    """-180..180 dışına taşan parçaları 360° kaydırarak karşı yarım küreye taşır."""
    minx, _, maxx, _ = shapely.bounds(geometri)
    if minx >= -180.0 and maxx <= 180.0:
        return geometri
    parcalar = [
        shapely.affinity.translate(shapely.intersection(geometri, shapely.box(x0, -90.0, x1, 90.0)), xoff=kayma)
        for x0, x1, kayma in ((-540.0, -180.0, 360.0), (-180.0, 180.0, 0.0), (180.0, 540.0, -360.0))
    ]
    return shapely.union_all([p for p in parcalar if not p.is_empty])


def sigmet_geometrisi(poligon, tampon_km=0.0, geometri=None):
    """SIGMET köşelerinden (ya da hazır `geometri`den) -180..180 boylam
    uzayında GEÇERLİ bir geometri. Kendini kesen halkalar (AWC akışında
    gerçekten görülüyor) make_valid ile onarılır. Tampon, antimeridyen
    bölmesinden ÖNCE kesintisiz boylam uzayında uygulanır; 180°'yi aşan
    (antimeridyen, bkz. sigmet_saglayici) ya da tamponla taşan parça 360°
    kaydırılarak karşı yarım küreye taşınır."""
    if geometri is None:
        geometri = shapely.make_valid(shapely.Polygon(poligon))
    return _antimeridyende_bol(km_tamponla(geometri, tampon_km))


class PoligonKisitKatmani:
    """kayitlar: 'poligon', 'taban_ft', 'tavan_ft', 'gecerlilik_baslangic',
    'gecerlilik_bitis' alanlı sözlükler; None taban = yer, None tavan =
    sınırsız, None geçerlilik sınırı = o yönde süresiz."""

    ad = "poligon"
    dikey_tampon_ft = 0.0

    def __init__(self, kayitlar):
        self.kayitlar = list(kayitlar)
        self._poligonlar = [
            sigmet_geometrisi(k.get("poligon"), self.yanal_tampon_nm(k) * _NM_KM, k.get("_geometri"))
            for k in self.kayitlar
        ]
        for poligon in self._poligonlar:
            shapely.prepare(poligon)
        self._sinirlar = [shapely.bounds(p) for p in self._poligonlar]
        self._kos_enlemler = [max(np.cos(np.radians(shapely.centroid(p).y)), 0.05) for p in self._poligonlar]

    def yanal_tampon_nm(self, kayit) -> float:
        return 0.0

    @staticmethod
    def _saniye(zaman) -> float | None:
        return None if zaman is None else _utc(zaman).value / 1e9

    def _irtifada_mi(self, kayit, irtifa_ft) -> bool:
        taban = kayit["taban_ft"] - self.dikey_tampon_ft if kayit["taban_ft"] is not None else -float("inf")
        tavan = kayit["tavan_ft"] + self.dikey_tampon_ft if kayit["tavan_ft"] is not None else float("inf")
        return taban <= irtifa_ft <= tavan

    def _aktif_maskesi(self, kayit, t, d) -> np.ndarray:
        """Düğüm zamanı belirsizse ([t - d, t + d]) aralık geçerlilikle
        kesiştiğinde aktif sayılır -- muhafazakâr. t, d: saniye dizileri."""
        baslangic = self._saniye(kayit.get("gecerlilik_baslangic"))
        bitis = self._saniye(kayit.get("gecerlilik_bitis"))
        maske = np.ones(len(t), dtype=bool)
        if baslangic is not None:
            maske &= baslangic <= t + d
        if bitis is not None:
            maske &= t - d <= bitis
        if kayit.get("aktivasyon"):
            maske &= aktif_maskesi(kayit["aktivasyon"], t, d)
        return maske

    def _kayma_araliklari(self, kayit, kos_enlem, t, d):
        """Hareketli kayıt için düğüm başına (derece cinsinden) en küçük ve en
        büyük kayma vektörü: hız x (düğüm zamanı ± belirsizlik - geçerlilik
        başlangıcı). Hız bilinmiyorsa 0 ile SIGMET_BILINMEYEN_HIZ_KT arası.
        Durağansa None."""
        yon, hiz = kayit.get("hareket_yonu_derece"), kayit.get("hareket_hizi_kt")
        baslangic = self._saniye(kayit.get("gecerlilik_baslangic"))
        if yon is None or baslangic is None:
            return None
        hiz_min, hiz_maks = (hiz, hiz) if hiz is not None else (0.0, config.SIGMET_BILINMEYEN_HIZ_KT)
        if hiz_maks <= 0:
            return None
        saat_min = np.clip(t - d - baslangic, 0.0, None) / 3600.0
        saat_maks = np.clip(t + d - baslangic, 0.0, None) / 3600.0
        teta = np.radians(yon)
        birim = np.array([np.sin(teta) / kos_enlem, np.cos(teta)]) / _KM_PER_DERECE
        return (hiz_min * _KT_KM_SAAT * saat_min)[:, None] * birim, (hiz_maks * _KT_KM_SAAT * saat_maks)[
            :, None
        ] * birim

    @staticmethod
    def _kutu_kesisiyor(asgari, azami, sinir) -> np.ndarray:
        return (
            (asgari[:, 0] <= sinir[2])
            & (azami[:, 0] >= sinir[0])
            & (asgari[:, 1] <= sinir[3])
            & (azami[:, 1] >= sinir[1])
        )

    def degerlendir(self, konumlar, zamanlar, kenarlar, irtifa_m, zaman_belirsizligi=None) -> RiskDegerlendirmesi:
        """zaman_belirsizligi: düğüm -> Timedelta; A* rüzgarsız nominal
        zamanlarla aradığı için gerçek (rüzgarlı) varış bu kadar kayabilir.
        Hareketli SIGMET'te nokta, alanın o zamanki konumuna göre sınanır:
        noktayı hareketin tersine kaydıran doğru parçası (belirsizlik ve
        bilinmeyen hız aralığını kapsar) poligonu keserse yasaktır. Poligonun
        sınır kutusundan uzak düğüm/bacaklar geometri testine hiç girmez."""
        dugumler = list(konumlar)
        if not self.kayitlar or not dugumler:
            return RiskDegerlendirmesi()
        irtifa_ft = irtifa_m / 0.3048
        indeks = {d: i for i, d in enumerate(dugumler)}
        nokta = np.array([(konumlar[d][1], konumlar[d][0]) for d in dugumler], dtype=float)
        t = np.array([self._saniye(zamanlar[d]) for d in dugumler])
        d = (
            np.array([pd.Timedelta(zaman_belirsizligi[k]).total_seconds() for k in dugumler])
            if zaman_belirsizligi
            else np.zeros(len(dugumler))
        )
        ai = np.array([indeks[a] for a, _ in kenarlar], dtype=int)
        bi = np.array([indeks[b] for _, b in kenarlar], dtype=int)
        cizgiler = shapely.linestrings(np.stack([nokta[ai], nokta[bi]], axis=1)) if len(kenarlar) else None

        yasak_dugum = np.zeros(len(dugumler), dtype=bool)
        yasak_kenar = np.zeros(len(kenarlar), dtype=bool)
        for kayit, poligon, sinir, kos_enlem in zip(
            self.kayitlar, self._poligonlar, self._sinirlar, self._kos_enlemler, strict=True
        ):
            if not self._irtifada_mi(kayit, irtifa_ft):
                continue
            aktif = self._aktif_maskesi(kayit, t, d)
            if not aktif.any():
                continue
            kayma = self._kayma_araliklari(kayit, kos_enlem, t, d)
            # "- 1e-9": sabit (bilinen) hızlı ve zaman_belirsizligi=None/0 olan bir
            # SIGMET'te kayma[0] == kayma[1] olabilir (örn. rota_ihlal_sayisi ve her
            # backtest çağrısı) -- bu durumda ilk == son olur ve shapely.linestrings
            # SIFIR UZUNLUKLU, GEÇERSİZ bir çizgi üretir (doğrulandı: is_valid=False).
            # GEOS'un geçersiz geometride intersects() sonucu tanımsızdır. Bu payla
            # (~1e-10 km, gerçek SIGMET hassasiyetinin çok altında) çizgi her zaman
            # geçerli kalır; sonucu asla değiştirmez.
            ilk, son = (nokta, nokta) if kayma is None else (nokta - kayma[0], nokta - kayma[1] - 1e-9)
            aday = np.flatnonzero(aktif & self._kutu_kesisiyor(np.minimum(ilk, son), np.maximum(ilk, son), sinir))
            if len(aday):
                if kayma is None:
                    yasak_dugum[aday] |= shapely.intersects_xy(poligon, nokta[aday, 0], nokta[aday, 1])
                else:
                    parca = shapely.linestrings(np.stack([ilk[aday], son[aday]], axis=1))
                    yasak_dugum[aday] |= shapely.intersects(parca, poligon)
            if not len(kenarlar):
                continue
            koseler = np.stack([ilk[ai], son[ai], ilk[bi], son[bi]], axis=1)
            aday = np.flatnonzero(
                (aktif[ai] | aktif[bi]) & self._kutu_kesisiyor(koseler.min(axis=1), koseler.max(axis=1), sinir)
            )
            if len(aday):
                geometri = cizgiler[aday] if kayma is None else shapely.convex_hull(shapely.multipoints(koseler[aday]))
                yasak_kenar[aday] |= shapely.intersects(geometri, poligon)

        return RiskDegerlendirmesi(
            yasak_dugumler={dugumler[i] for i in np.flatnonzero(yasak_dugum)},
            yasak_kenarlar={kenarlar[i] for i in np.flatnonzero(yasak_kenar)},
        )

    def rota_ihlal_sayisi(self, enlemler, boylamlar, zamanlar, irtifa_m) -> int:
        """Bir rotanın aktif kısıta giren nokta + bacak sayısı (0 = kısıt sağlanıyor)."""
        konumlar = {(i, 0): (float(e), float(b)) for i, (e, b) in enumerate(zip(enlemler, boylamlar, strict=True))}
        zaman_sozlugu = {(i, 0): z for i, z in enumerate(zamanlar)}
        kenarlar = [((i, 0), (i + 1, 0)) for i in range(len(konumlar) - 1)]
        sonuc = self.degerlendir(konumlar, zaman_sozlugu, kenarlar, irtifa_m)
        return len(sonuc.yasak_dugumler) + len(sonuc.yasak_kenarlar)

    def noktayi_iceren_kayitlar(self, enlem, boylam) -> list[dict]:
        return [
            k for k, p in zip(self.kayitlar, self._poligonlar, strict=True) if shapely.intersects_xy(p, boylam, enlem)
        ]

    def geometri(self, kayit) -> object:
        return self._poligonlar[next(i for i, k in enumerate(self.kayitlar) if k is kayit)]


class SigmetKisitKatmani(PoligonKisitKatmani):
    """tamponlu=False: poligonun kendisi (bağımsız kanıt ölçümü gibi kaçınma
    dışı kullanımlar); True: config.SIGMET_YANAL_TAMPON_NM / SIGMET_DIKEY_TAMPON_FT."""

    ad = "sigmet"

    def __init__(self, sigmetler, tehlikeler=None, tamponlu=True):
        tehlikeler = {t.upper() for t in (tehlikeler or config.SIGMET_KACINILACAK_TEHLIKELER)}
        tehlikeler.add(config.SIGMET_BILINMEYEN_TEHLIKE)
        self.tamponlu = tamponlu
        self.dikey_tampon_ft = config.SIGMET_DIKEY_TAMPON_FT if tamponlu else 0.0
        super().__init__(s for s in sigmetler if s["tehlike"].upper() in tehlikeler)

    def yanal_tampon_nm(self, kayit) -> float:
        if not self.tamponlu:
            return 0.0
        tehlike = kayit["tehlike"].upper()
        if tehlike == config.SIGMET_BILINMEYEN_TEHLIKE:
            return max([config.SIGMET_YANAL_TAMPON_VARSAYILAN_NM, *config.SIGMET_YANAL_TAMPON_NM.values()])
        return config.SIGMET_YANAL_TAMPON_NM.get(tehlike, config.SIGMET_YANAL_TAMPON_VARSAYILAN_NM)

    def tampon_ozeti(self) -> dict:
        return {
            "yanal_nm": {**config.SIGMET_YANAL_TAMPON_NM, "DIGER": config.SIGMET_YANAL_TAMPON_VARSAYILAN_NM}
            if self.tamponlu
            else {},
            "dikey_ft": self.dikey_tampon_ft,
            "aciklama": "Parametrik varsayım, kalibre edilmedi (SIGMET poligonu kaba; hat pratiği payı).",
        }

    @property
    def sigmetler(self) -> list[dict]:
        return self.kayitlar


class KisitliSahaKatmani(PoligonKisitKatmani):
    ad = "kisitli_saha"
