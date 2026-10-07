"""
hava_yolu_agi.py
-------------------
ATS yolları / Serbest Rota Sahası (FRA) üzerinde graf tabanlı A* (hoca önerisi 1,
Doç. Dr. Fulya Aybek Çetek). Önemli noktalar düğüm, hava yolu segmentleri kenar;
FRA noktaları arasında belirli bir mesafeye kadar doğrudan (DCT) kenarlar.

Veri: config.ATS_AGI_DOSYASI (JSON; AIP Türkiye ENR 3 ve ENR 4.4'ten elle
hazırlanır, bkz. docs/veri_hazirlama/ATS_AGI_HAZIRLAMA.md). Depoya konmaz; bu
modül uydurma bir ağ içermez.

    {
      "kaynak": "AIP Türkiye, AIRAC 2610",
      "noktalar": [{"ad": "ABCDE", "enlem": 40.1, "boylam": 30.2, "fra_rolleri": ["D", "I"]}, ...],
      "yollar": [{"ad": "UL123", "noktalar": ["ABCDE", "FGHIJ", ...],
                  "alt_fl": 245, "ust_fl": 460, "yon": "cift"}],
      "fra": {"noktalar": ["ABCDE", ...], "dct_maks_km": 400, "alt_fl": 245, "ust_fl": 660,
              "saatler_utc": [{"baslangic": "20:00", "bitis": "02:00"}],
              "firler": ["LTAA", "LTBB"], "sinir_tamponu_nm": 5}
    }

saatler_utc: FRA'nın uygulandığı UTC saat aralıkları (gece yarısını aşabilir);
yoksa her zaman. Türkiye'de FRATURK yalnızca 20:00-02:00 UTC (AIP ENR 1.3
§5.1.1, AIRAC 01/26). Bir FRA kenarı, uçağın kenara girişi pencere içinde ve
kenar sonuna varışı (belirsizlik payıyla) pencere kapanmadan önceyse aramaya
girer: FRA uçuşu FRATURK'tan kapanıştan önce çıkmalıdır (ENR 1.3 §5.5.2.1).

fra_rolleri (ENR 4.4): E yatay giriş, X yatay çıkış, I ara, A varış, D kalkış
bağlantısı. Rol verisi olan ağda ToC yalnız D/E, ToD yalnız A/X rollü FRA
noktalarına bağlanır; FRA alanı (firler) biliniyorsa FIR içindeki ToC yalnız D,
dışındaki yalnız E; ToD için A/X (ENR 1.3 §5.2.2-5.2.3). Rol verisi olmayan
noktalar kısıtsız.

firler/sinir_tamponu_nm: DCT kenarları bu FIR'ların birleşiminin sinir_tamponu_nm
içeri daraltılmış alanında tamamen kalmalı (ENR 1.3 §5.2.1.6, §5.2.5); kalmayanlar
ağa girmez. FIR sınırı VATSIM'in YAKLAŞIK çizimidir (bkz. veri/fir_sinirlari.py).

yon: "cift" (iki yön), "ileri" (listedeki sıra), "geri". alt_fl/ust_fl boşsa
sınır yok. Kalkış ve varış (ToC/ToD) ağa en yakın noktalara doğrudan bağlanır
(ATS_AGI_BAGLANTI_KM içinde en fazla ATS_AGI_BAGLANTI_SAYISI nokta).

Segmentler ATS_AGI_ARA_NOKTA_KM'den uzunsa ara noktalarla bölünür: TI1 ve
SIGMET/kısıtlı saha katmanları düğümlerde değerlendirildiği için uzun bir
segmentin ortasındaki risk atlanmasın diye.
"""

from __future__ import annotations

import heapq
import itertools
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from turbulans_radar import config

_YONLER = ("cift", "ileri", "geri")
_ROLLER = frozenset("EXIAD")
_NM_KM = 1.852
_DCT_ORNEK_KM = 20.0
_FIR_BOSLUK_DERECE2 = 1e-4
_UC_MUAFIYET_KATI = 2.0


class AtsAgiHatasi(ValueError):
    pass


@dataclass
class Kenar:
    hedef: str
    yol: str
    alt_fl: float | None
    ust_fl: float | None
    fra: bool = False


@dataclass
class HavaYoluAgi:
    kaynak: str
    noktalar: dict[str, tuple[float, float]]
    komsular: dict[str, list[Kenar]] = field(default_factory=dict)
    fra_saatleri: list[tuple[int, int]] = field(default_factory=list)
    fra_rolleri: dict[str, frozenset[str]] = field(default_factory=dict)
    sinir_disi_dct_sayisi: int = 0
    ats_yolu_sayisi: int = 0
    fra_var: bool = False
    fra_alani: object = None
    fra_alt_fl: float | None = None

    def kenar_ekle(self, a: str, b: str, yol: str, alt_fl=None, ust_fl=None, fra=False):
        self.komsular.setdefault(a, []).append(Kenar(b, yol, alt_fl, ust_fl, fra))

    def fra_acik_mi(self, zaman) -> bool:
        """zaman (UTC) FRA uygulama saatlerinde mi; saat tanımlı değilse her zaman açık."""
        return self.fra_penceresinde_mi(zaman)

    def fra_penceresinde_mi(self, giris, cikis=None) -> bool:
        """giris (UTC) bir FRA penceresinde ve cikis aynı pencere kapanmadan önce mi."""
        if not self.fra_saatleri or giris is None:
            return True
        sure_dk = 0.0 if cikis is None else (cikis - giris).total_seconds() / 60.0
        dakika = giris.hour * 60 + giris.minute + giris.second / 60.0
        for bas, bit in self.fra_saatleri:
            uzunluk = (bit - bas) % 1440 or 1440
            gecen = (dakika - bas) % 1440
            if uzunluk == 1440 or (gecen < uzunluk and sure_dk <= uzunluk - gecen):
                return True
        return False

    def fra_saatleri_metni(self) -> str:
        return ", ".join(f"{b // 60:02d}:{b % 60:02d}-{s // 60:02d}:{s % 60:02d} UTC" for b, s in self.fra_saatleri)

    def fra_alaninda_mi(self, enlem, boylam) -> bool | None:
        if self.fra_alani is None:
            return None
        import shapely

        return bool(shapely.contains_xy(self.fra_alani, boylam, enlem))

    def uc_baglantisi(self, enlem, boylam, ic_rol, dis_rol) -> list[tuple[str, float]]:
        """ToC (D/E) ya da ToD (A/X) bağlantıları. FRA alanı biliniyorsa dışarıdaki
        uç yalnız dis_rol (E/X) noktalarına; içerideki önce ic_rol (D/A), menzilde
        yoksa ic_rol/dis_rol (ENR 1.3 §5.2.2-5.2.3; bkz. rol_uyarilari). AIP'te
        A/D rolleri meydana özgüdür; meydan bilinmediği için genel sayılır."""
        icinde = self.fra_alaninda_mi(enlem, boylam)
        if icinde is False:
            return uc_baglantilari(self, enlem, boylam, roller=frozenset(dis_rol))
        baglar = uc_baglantilari(self, enlem, boylam, roller=frozenset(ic_rol)) if icinde else []
        return baglar or uc_baglantilari(self, enlem, boylam, roller=frozenset((ic_rol, dis_rol)))

    def rol_uyarilari(self, dugumler, bas, bit) -> list[str]:
        """FRA alanı içindeki ToC/ToD, kalkış (D)/varış (A) bağlantı noktası
        yerine yatay giriş/çıkış (E/X) noktasına bağlandıysa açık uyarı."""
        uyarilar = []
        for uc, nokta, rol, ad in ((bas, dugumler[1], "D", "kalkış"), (bit, dugumler[-2], "A", "varış")):
            if self.fra_alaninda_mi(*uc) and nokta in self.fra_rolleri and rol not in self.fra_rolleri[nokta]:
                uyarilar.append(
                    f"{nokta} FRA {ad} bağlantı noktası ({rol}) değil, yatay giriş/çıkış noktası "
                    f"({''.join(sorted(self.fra_rolleri[nokta]))}): {config.ATS_AGI_BAGLANTI_KM:.0f} km içinde "
                    f"{rol} rollü nokta yok. ENR 1.3 §5.2.3'e tam uymaz."
                )
        return uyarilar

    def etiket(self) -> str:
        """Ağda gerçekte ne olduğu: ör. 'FRA serbest rota (FL305+, 20:00-02:00 UTC)'."""
        parcalar = [f"{self.ats_yolu_sayisi} ATS yolu"] if self.ats_yolu_sayisi else []
        if self.fra_var:
            ayrinti = [f"FL{self.fra_alt_fl:.0f}+"] if self.fra_alt_fl is not None else []
            ayrinti += [self.fra_saatleri_metni()] if self.fra_saatleri else []
            parcalar.append("FRA serbest rota" + (f" ({', '.join(ayrinti)})" if ayrinti else ""))
        return " + ".join(parcalar)


def mesafe_km(enlem1, boylam1, enlem2, boylam2) -> float:
    p1, p2 = math.radians(enlem1), math.radians(enlem2)
    dp, dl = p2 - p1, math.radians(boylam2 - boylam1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, a)))


def _ara_nokta(e1, b1, e2, b2, oran):
    p1, l1, p2, l2 = map(math.radians, (e1, b1, e2, b2))
    d = 2 * math.asin(
        math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2)
    )
    if d == 0:
        return e1, b1
    a, b = math.sin((1 - oran) * d) / math.sin(d), math.sin(oran * d) / math.sin(d)
    x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
    y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
    z = a * math.sin(p1) + b * math.sin(p2)
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def _fl(deger, alan, konum):
    if deger is None:
        return None
    if isinstance(deger, bool) or not isinstance(deger, int | float) or not 0 <= deger <= 700:
        raise AtsAgiHatasi(f"{konum}: '{alan}' 0-700 arası uçuş seviyesi (FL) ya da null olmalı")
    return float(deger)


def _saat_dakika(deger, konum) -> int:
    try:
        saat, dakika = (int(p) for p in str(deger).split(":"))
    except (TypeError, ValueError):
        raise AtsAgiHatasi(f"{konum}: saat 'SS:DD' biçiminde olmalı") from None
    if not (0 <= saat <= 24 and 0 <= dakika < 60) or saat * 60 + dakika > 1440:
        raise AtsAgiHatasi(f"{konum}: geçersiz saat {deger!r}")
    return saat * 60 + dakika


def fra_siniri_geometrisi(firler):
    """FIR'ların birleşimi (lon/lat). Birleşimdeki 1 km²'den küçük boşluklar
    (yaklaşık çizimin dikiş artığı) doldurulur."""
    import shapely
    from shapely.geometry import Polygon

    from turbulans_radar.veri.fir_sinirlari import fir_geometrisi

    parcalar = {kod: fir_geometrisi(kod) for kod in firler}
    eksik = [kod for kod, g in parcalar.items() if g is None]
    if eksik:
        raise AtsAgiHatasi(
            f"fra.firler: FIR sınırı yok ({', '.join(eksik)}; {config.FIR_SINIRLARI_DOSYASI}); "
            "turbulans-statik ile indirin"
        )
    birlesik = shapely.union_all(list(parcalar.values()))
    return shapely.union_all(
        [
            Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area >= _FIR_BOSLUK_DERECE2])
            for p in getattr(birlesik, "geoms", [birlesik])
        ]
    )


def _cizgi_km(cizgi) -> float:
    import shapely

    xy = shapely.get_coordinates(cizgi).tolist()
    return sum(mesafe_km(y1, x1, y2, x2) for (x1, y1), (x2, y2) in itertools.pairwise(xy))


def sinir_icindeki_dct_maskesi(sinir, tampon_nm, ciftler, noktalar) -> list[bool]:
    """Her (a, b) büyük daire kenarı (_DCT_ORNEK_KM aralıkla örneklenmiş)
    sinir'in tampon_nm içeri daraltılmış iç bölgesinde mi. Sınır bandındaki
    yayımlanmış bir uç noktadan (E/X noktaları sınırın üstündedir) çıkan kenarın
    o uca bitişik dış parçası muaftır, ama (1) uzunluğu ucun iç bölgeye en kısa
    uzaklığının _UC_MUAFIYET_KATI katını geçemez (sınırdan ≥30° açıyla
    uzaklaşma; AIP'te sayı yok, bizim varsayımımız) ve (2) sinir dışına ancak
    uç noktanın kendisi sinir dışındaysa (yaklaşık çizim) o uçta çıkabilir.
    Uca bitişik olmayan her dış parça (sınır boyunca uçma, FIR dışına çıkıp
    dönme) kenarı geçersiz kılar."""
    import shapely

    from turbulans_radar.rota.risk_katmanlari import km_tamponla

    if not ciftler:
        return []
    ic = km_tamponla(sinir, -tampon_nm * _NM_KM)
    koordinatlar, sira = [], []
    for k, (a, b) in enumerate(ciftler):
        (e1, b1), (e2, b2) = noktalar[a], noktalar[b]
        parca = max(1, math.ceil(mesafe_km(e1, b1, e2, b2) / _DCT_ORNEK_KM))
        koordinatlar += [_ara_nokta(e1, b1, e2, b2, i / parca)[::-1] for i in range(parca + 1)]
        sira += [k] * (parca + 1)
    cizgiler = shapely.linestrings(koordinatlar, indices=sira)
    shapely.prepare(ic)
    shapely.prepare(sinir)
    sonuc = shapely.contains(ic, cizgiler).tolist()
    uc_bilgisi: dict[str, tuple] = {}

    def uc(ad):
        if ad not in uc_bilgisi:
            nokta = shapely.Point(noktalar[ad][1], noktalar[ad][0])
            pay = 0.0
            if not shapely.contains(ic, nokta):
                yakin = shapely.get_coordinates(shapely.shortest_line(nokta, ic))[-1]
                pay = _UC_MUAFIYET_KATI * mesafe_km(noktalar[ad][0], noktalar[ad][1], yakin[1], yakin[0])
            uc_bilgisi[ad] = (nokta, pay, not shapely.contains(sinir, nokta))
        return uc_bilgisi[ad]

    def parcalar(geometri):
        return [p for p in shapely.get_parts(geometri) if not p.is_empty]

    for k, icinde in enumerate(sonuc):
        if icinde:
            continue
        uclar = [uc(ad) for ad in ciftler[k]]
        sonuc[k] = all(
            any(pay > 0 and parca.distance(nokta) < 1e-9 and _cizgi_km(parca) <= pay for nokta, pay, _ in uclar)
            for parca in parcalar(shapely.difference(cizgiler[k], ic))
        ) and all(
            any(disarida and parca.distance(nokta) < 1e-9 for nokta, _, disarida in uclar)
            for parca in parcalar(shapely.difference(cizgiler[k], sinir))
        )
    return sonuc


def agi_kur(veri: dict, ara_nokta_km: float | None = None, fra_siniri=None) -> HavaYoluAgi:
    """JSON sözlüğünden ağ; hatalı veride nerede olduğunu söyleyen AtsAgiHatasi.
    fra_siniri (lon/lat poligon) verilirse fra.firler yerine o kullanılır."""
    ara_nokta_km = config.ATS_AGI_ARA_NOKTA_KM if ara_nokta_km is None else ara_nokta_km
    if not isinstance(veri, dict) or not isinstance(veri.get("noktalar"), list) or not veri["noktalar"]:
        raise AtsAgiHatasi("'noktalar' boş olmayan bir liste olmalı")
    noktalar = {}
    roller = {}
    for sira, nokta in enumerate(veri["noktalar"]):
        try:
            ad, enlem, boylam = str(nokta["ad"]).strip().upper(), float(nokta["enlem"]), float(nokta["boylam"])
        except (KeyError, TypeError, ValueError):
            raise AtsAgiHatasi(f"noktalar[{sira}]: 'ad', 'enlem', 'boylam' gerekli") from None
        if not ad or not (-90 <= enlem <= 90 and -180 <= boylam <= 180):
            raise AtsAgiHatasi(f"noktalar[{sira}]: geçersiz ad ya da koordinat")
        if ad in noktalar:
            raise AtsAgiHatasi(f"noktalar[{sira}]: '{ad}' iki kez tanımlı")
        noktalar[ad] = (enlem, boylam)
        if nokta.get("fra_rolleri") is not None:
            rol = frozenset(str(r).strip().upper() for r in nokta["fra_rolleri"])
            if not rol <= _ROLLER:
                raise AtsAgiHatasi(f"noktalar[{sira}]: 'fra_rolleri' yalnız {', '.join(sorted(_ROLLER))} içerebilir")
            roller[ad] = rol
    ag = HavaYoluAgi(kaynak=str(veri.get("kaynak") or "belirtilmedi"), noktalar=dict(noktalar), fra_rolleri=roller)

    def segment_ekle(a, b, yol, alt_fl, ust_fl, yonler, fra=False):
        (e1, b1), (e2, b2) = noktalar[a], noktalar[b]
        parca = max(1, math.ceil(mesafe_km(e1, b1, e2, b2) / ara_nokta_km)) if ara_nokta_km > 0 else 1
        zincir = [a]
        for i in range(1, parca):
            ara = f"{a}>{b}#{i}"
            ag.noktalar[ara] = _ara_nokta(e1, b1, e2, b2, i / parca)
            zincir.append(ara)
        zincir.append(b)
        for x, y in itertools.pairwise(zincir):
            if "ileri" in yonler:
                ag.kenar_ekle(x, y, yol, alt_fl, ust_fl, fra)
            if "geri" in yonler:
                ag.kenar_ekle(y, x, yol, alt_fl, ust_fl, fra)

    for sira, yol in enumerate(veri.get("yollar") or []):
        konum = f"yollar[{sira}]"
        if not isinstance(yol, dict) or not isinstance(yol.get("noktalar"), list) or len(yol["noktalar"]) < 2:
            raise AtsAgiHatasi(f"{konum}: 'noktalar' en az 2 nokta adı içermeli")
        ad = str(yol.get("ad") or f"YOL{sira}")
        yon = str(yol.get("yon") or "cift")
        if yon not in _YONLER:
            raise AtsAgiHatasi(f"{konum}: 'yon' şunlardan biri olmalı: {', '.join(_YONLER)}")
        alt_fl, ust_fl = _fl(yol.get("alt_fl"), "alt_fl", konum), _fl(yol.get("ust_fl"), "ust_fl", konum)
        if alt_fl is not None and ust_fl is not None and alt_fl > ust_fl:
            raise AtsAgiHatasi(f"{konum}: alt_fl ust_fl'den büyük olamaz")
        sirali = [str(n).strip().upper() for n in yol["noktalar"]]
        bilinmeyen = [n for n in sirali if n not in noktalar]
        if bilinmeyen:
            raise AtsAgiHatasi(f"{konum} ({ad}): tanımsız nokta(lar): {', '.join(bilinmeyen)}")
        yonler = {"cift": ("ileri", "geri"), "ileri": ("ileri",), "geri": ("geri",)}[yon]
        for a, b in itertools.pairwise(sirali):
            segment_ekle(a, b, ad, alt_fl, ust_fl, yonler)
        ag.ats_yolu_sayisi += 1

    fra = veri.get("fra")
    if fra:
        fra_noktalari = [str(n).strip().upper() for n in fra.get("noktalar") or []]
        bilinmeyen = [n for n in fra_noktalari if n not in noktalar]
        if bilinmeyen:
            raise AtsAgiHatasi(f"fra: tanımsız nokta(lar): {', '.join(bilinmeyen)}")
        dct_km = float(fra.get("dct_maks_km") or 0)
        alt_fl, ust_fl = _fl(fra.get("alt_fl"), "alt_fl", "fra"), _fl(fra.get("ust_fl"), "ust_fl", "fra")
        ag.fra_var, ag.fra_alt_fl = True, alt_fl
        saatler = fra.get("saatler_utc") or []
        if not isinstance(saatler, list):
            raise AtsAgiHatasi("fra: 'saatler_utc' {baslangic, bitis} listesi olmalı")
        for sira, aralik in enumerate(saatler):
            konum = f"fra.saatler_utc[{sira}]"
            if not isinstance(aralik, dict):
                raise AtsAgiHatasi(f"{konum}: {{baslangic, bitis}} olmalı")
            bas, bit = _saat_dakika(aralik.get("baslangic"), konum), _saat_dakika(aralik.get("bitis"), konum)
            if bas == bit:
                raise AtsAgiHatasi(f"{konum}: baslangic ve bitis aynı olamaz")
            ag.fra_saatleri.append((bas, bit % 1440))
        firler = [str(k).strip().upper() for k in fra.get("firler") or []]
        if fra_siniri is None and firler:
            fra_siniri = fra_siniri_geometrisi(firler)
        ciftler = [
            (a, b)
            for i, a in enumerate(fra_noktalari)
            for b in fra_noktalari[i + 1 :]
            if mesafe_km(*noktalar[a], *noktalar[b]) <= dct_km
        ]
        ag.fra_alani = fra_siniri
        if fra_siniri is not None:
            icinde = sinir_icindeki_dct_maskesi(fra_siniri, float(fra.get("sinir_tamponu_nm") or 0), ciftler, noktalar)
            ag.sinir_disi_dct_sayisi = icinde.count(False)
            ciftler = [c for c, ic in zip(ciftler, icinde, strict=True) if ic]
        for a, b in ciftler:
            segment_ekle(a, b, "DCT", alt_fl, ust_fl, ("ileri", "geri"), fra=True)
    if not ag.komsular:
        raise AtsAgiHatasi("Ağda hiç segment yok ('yollar' ya da 'fra' gerekli)")
    return ag


_onbellek: dict[str, tuple[tuple, HavaYoluAgi]] = {}


def agi_yukle(yol: str | None = None) -> HavaYoluAgi | None:
    """Dosya yoksa None (ATS modu kullanılamaz); hatalıysa AtsAgiHatasi. Kurulan
    ağ dosyanın değişme zamanı/boyutuyla önbelleğe alınır (FIR kontrolü pahalı)."""
    yol = Path(yol or config.ATS_AGI_DOSYASI)
    if not yol.is_file():
        return None
    durum = yol.stat()
    imza = (durum.st_mtime_ns, durum.st_size, config.FIR_SINIRLARI_DOSYASI)
    kayit = _onbellek.get(str(yol))
    if kayit and kayit[0] == imza:
        return kayit[1]
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as hata:
        raise AtsAgiHatasi(f"{yol} okunamadı: {hata}") from None
    ag = agi_kur(veri)
    _onbellek[str(yol)] = (imza, ag)
    return ag


def _seviyede_mi(kenar: Kenar, fl: float) -> bool:
    return (kenar.alt_fl is None or kenar.alt_fl <= fl) and (kenar.ust_fl is None or fl <= kenar.ust_fl)


BASLANGIC, BITIS = "<ToC>", "<ToD>"


def uc_baglantilari(ag: HavaYoluAgi, enlem, boylam, maks_km=None, sayi=None, roller=None) -> list[tuple[str, float]]:
    """(nokta, km) -- ToC/ToD'ye en yakın gerçek ağ noktaları (ara noktalar hariç).
    roller verilirse FRA rolü bilinen noktalardan yalnız bu rollerden birini taşıyanlar."""
    maks_km = config.ATS_AGI_BAGLANTI_KM if maks_km is None else maks_km
    sayi = config.ATS_AGI_BAGLANTI_SAYISI if sayi is None else sayi
    adaylar = sorted(
        (mesafe_km(enlem, boylam, e, b), ad)
        for ad, (e, b) in ag.noktalar.items()
        if "#" not in ad
        and ad in ag.komsular
        and (roller is None or ad not in ag.fra_rolleri or ag.fra_rolleri[ad] & roller)
    )
    return [(ad, km) for km, ad in adaylar if km <= maks_km][:sayi]


def arama_grafi(ag: HavaYoluAgi, bas, bit, irtifa_ft, zaman=None, dugum_zamanlari=None) -> tuple[dict, dict, list]:
    """A* için (konumlar, komsular, kenarlar): seviyeye uymayan segmentler ve
    FRA penceresi dışındaki FRA DCT kenarları çıkarılmış, ToC/ToD bağlantıları
    (FRA rollerine göre) eklenmiş graf. dugum_zamanlari {düğüm: (nominal, en geç)}
    verilirse her FRA kenarı a->b için giriş nominal(a), çıkış en_gec(b) pencereye
    bakılır; verilmezse yalnız `zaman` (kalkış) anına."""
    fl = irtifa_ft / 100.0
    fra_acik = ag.fra_acik_mi(zaman)

    def fra_uygun(a, b):
        if dugum_zamanlari is None:
            return fra_acik
        return ag.fra_penceresinde_mi(dugum_zamanlari[a][0], dugum_zamanlari[b][1])

    konumlar = dict(ag.noktalar)
    konumlar[BASLANGIC], konumlar[BITIS] = bas, bit
    komsular = {
        a: [(k.hedef, k.yol) for k in kenarlar if _seviyede_mi(k, fl) and (not k.fra or fra_uygun(a, k.hedef))]
        for a, kenarlar in ag.komsular.items()
    }
    komsular[BASLANGIC] = [(ad, "DCT") for ad, _ in ag.uc_baglantisi(*bas, "D", "E")]
    for ad, _ in ag.uc_baglantisi(*bit, "A", "X"):
        komsular.setdefault(ad, []).append((BITIS, "DCT"))
    kenarlar = [(a, b) for a, hedefler in komsular.items() for b, _ in hedefler]
    return konumlar, komsular, kenarlar


def a_yildiz(komsular: dict, bas: str, bit: str, kenar_maliyeti, sezgisel, yasak_dugumler=(), yasak_kenarlar=()):
    """Genel A*: kenar_maliyeti(a, b) ve sezgisel(d) saniye. Dönüş: düğüm
    yolu ve yol üzerindeki kenarların adları; yol yoksa None."""
    if bas in yasak_dugumler or bit in yasak_dugumler:
        return None
    acik = [(sezgisel(bas), 0.0, bas)]
    maliyet = {bas: 0.0}
    ebeveyn: dict[str, tuple[str, str]] = {}
    kapali = set()
    while acik:
        _, g, dugum = heapq.heappop(acik)
        if dugum in kapali:
            continue
        kapali.add(dugum)
        if dugum == bit:
            break
        for komsu, yol in komsular.get(dugum, []):
            if komsu in yasak_dugumler or (dugum, komsu) in yasak_kenarlar or komsu in kapali:
                continue
            yeni = g + kenar_maliyeti(dugum, komsu)
            if yeni < maliyet.get(komsu, math.inf):
                maliyet[komsu] = yeni
                ebeveyn[komsu] = (dugum, yol)
                heapq.heappush(acik, (yeni + sezgisel(komsu), yeni, komsu))
    if bit not in ebeveyn and bit != bas:
        return None
    dugumler, yollar = [bit], []
    while dugumler[-1] != bas:
        onceki, yol = ebeveyn[dugumler[-1]]
        yollar.append(yol)
        dugumler.append(onceki)
    return dugumler[::-1], yollar[::-1]


def rota_ozeti(dugumler: list[str], yollar: list[str]) -> list[dict]:
    """Uçuş planı biçimine yakın özet: ara noktalar atılır, aynı yoldaki ardışık
    segmentler birleştirilir. [{"nokta": "ABCDE", "yol": "UL123" | "DCT" | None}]"""
    ozet = []
    for i, dugum in enumerate(dugumler):
        if "#" in dugum:
            continue
        gelen = yollar[i - 1] if i > 0 else None
        if ozet and gelen not in (None, "DCT") and gelen == ozet[-1]["yol"] and i < len(dugumler) - 1:
            ozet[-1]["nokta"] = dugum
            continue
        ozet.append({"nokta": dugum, "yol": gelen})
    return ozet
