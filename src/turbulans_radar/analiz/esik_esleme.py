import argparse
import json
import os
import tempfile
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
from turbulans_radar.loglama import logger_al

_logger = logger_al(__name__)

VARSAYILAN_KUTU = (30.0, 50.0, 10.0, 50.0)
VARSAYILAN_FL = (300, 320, 340, 360, 380)
_FT_M = 0.3048
_INDIRME_PAYI_DERECE = 1.0


def izgara_noktalari(kutu, adim_derece, zamanlar, fl_listesi) -> pd.DataFrame:
    enlemler = np.round(np.arange(kutu[0], kutu[1] + 1e-9, adim_derece), 4)
    boylamlar = np.round(np.arange(kutu[2], kutu[3] + 1e-9, adim_derece), 4)
    zaman_idx = pd.DatetimeIndex([pd.Timestamp(z).tz_convert("UTC") for z in zamanlar])
    z, fl, e, b = np.meshgrid(np.arange(len(zaman_idx)), np.asarray(fl_listesi), enlemler, boylamlar, indexing="ij")
    return pd.DataFrame(
        {
            "zaman": zaman_idx[z.ravel()],
            "enlem": e.ravel(),
            "boylam": b.ravel(),
            "baro_irtifa_m": fl.ravel() * 100.0 * _FT_M,
            "fl": fl.ravel(),
        }
    )


def ti1_orneklemi(veri_kupu, noktalar: pd.DataFrame) -> np.ndarray:
    girdi = noktalar[["zaman", "enlem", "boylam", "baro_irtifa_m"]].reset_index(drop=True)
    return rotayi_hava_durumuyla_eslestir(girdi, veri_kupu)["ti1_indeksi"].to_numpy(dtype=float)


def _spearman(a, b) -> float | None:
    if len(a) < 3:
        return None
    return float(np.corrcoef(pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy())[0, 1])


def yuzdelik_esleme(era5_ti1, gfs_ti1, esik) -> dict:
    era5_ti1 = np.asarray(era5_ti1, dtype=float)
    gfs_ti1 = np.asarray(gfs_ti1, dtype=float)
    gecerli = np.isfinite(era5_ti1) & np.isfinite(gfs_ti1)
    a, g = era5_ti1[gecerli], gfs_ti1[gecerli]
    if len(a) == 0:
        return {"n": 0, "yuzdelik": None, "gfs_esdeger_esik": None}
    yuzdelik = float(np.mean(a < esik))
    return {
        "n": int(len(a)),
        "era5_esik": float(esik),
        "yuzdelik": yuzdelik,
        "gfs_esdeger_esik": float(np.quantile(g, yuzdelik)),
        "era5_riskli_orani": float(np.mean(a >= esik)),
        "gfs_riskli_orani_ayni_esikte": float(np.mean(g >= esik)),
        "era5_medyan": float(np.median(a)),
        "gfs_medyan": float(np.median(g)),
        "spearman": _spearman(a, g),
    }


def zaman_bootstrap(era5_ti1, gfs_ti1, zaman_etiketleri, esik, tekrar=1000, tohum=0) -> list[float] | None:
    era5_ti1 = np.asarray(era5_ti1, dtype=float)
    gfs_ti1 = np.asarray(gfs_ti1, dtype=float)
    etiketler = np.asarray(zaman_etiketleri)
    benzersiz = np.unique(etiketler)
    if len(benzersiz) < 2:
        return None
    gruplar = [np.flatnonzero(etiketler == z) for z in benzersiz]
    uretec = np.random.default_rng(tohum)
    degerler = []
    for _ in range(tekrar):
        secim = np.concatenate([gruplar[i] for i in uretec.integers(0, len(gruplar), len(gruplar))])
        deger = yuzdelik_esleme(era5_ti1[secim], gfs_ti1[secim], esik)["gfs_esdeger_esik"]
        if deger is not None:
            degerler.append(deger)
    return [float(x) for x in np.percentile(degerler, [2.5, 97.5])] if degerler else None


def esleme_raporu(noktalar: pd.DataFrame, era5_ti1, gfs_ti1, esik, tekrar=1000) -> dict:
    zaman_etiketi = noktalar["zaman"].astype(str).to_numpy()
    genel = yuzdelik_esleme(era5_ti1, gfs_ti1, esik)
    genel["gfs_esdeger_esik_ga95"] = zaman_bootstrap(era5_ti1, gfs_ti1, zaman_etiketi, esik, tekrar=tekrar)
    seviyeler = {}
    for fl in sorted(noktalar["fl"].unique()):
        maske = (noktalar["fl"] == fl).to_numpy()
        seviyeler[f"FL{int(fl)}"] = yuzdelik_esleme(np.asarray(era5_ti1)[maske], np.asarray(gfs_ti1)[maske], esik)
    return {
        "genel": genel,
        "seviyeler": seviyeler,
        "zaman_sayisi": int(len(np.unique(zaman_etiketi))),
        "zamanlar": sorted(np.unique(zaman_etiketi).tolist()),
    }


def _utc(zaman) -> pd.Timestamp:
    ts = pd.Timestamp(zaman)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def gfs_analizini_getir(zaman, kutu, klasor) -> xr.Dataset:
    from turbulans_radar.veri.veri_saglayicilari import GfsThreddsSaglayici, Kutu, gfs_kosu_url

    zaman = _utc(zaman)
    yol = os.path.join(klasor, f"gfs_f000_{zaman:%Y%m%d%H}.nc")
    if not os.path.exists(yol):
        indirme_kutusu = Kutu(*kutu).genislet(_INDIRME_PAYI_DERECE)
        GfsThreddsSaglayici(url=gfs_kosu_url(zaman)).kup_indir(indirme_kutusu, zaman, zaman, yol)
    return xr.load_dataset(yol)


def era5_gununu_getir(gun, saatler, kutu, klasor) -> xr.Dataset:
    from turbulans_radar.veri import era5_saglayici as e
    from turbulans_radar.veri.veri_saglayicilari import Kutu
    from turbulans_radar.veri.veri_yukleme import hdf5_kilidi

    gun = _utc(gun).normalize()
    yol = os.path.join(klasor, f"era5_{gun:%Y%m%d}_{'-'.join(f'{s:02d}' for s in saatler)}.nc")
    if not os.path.exists(yol):
        indirme_kutusu = Kutu(*kutu).genislet(_INDIRME_PAYI_DERECE)
        istek = e.cds_istekleri_olustur(
            indirme_kutusu, gun, gun + pd.Timedelta(hours=23), config.ERA5_BASINC_SEVIYELERI_HPA
        )[0]
        istek["time"] = [f"{s:02d}:00" for s in saatler]
        with tempfile.TemporaryDirectory(dir=klasor) as gecici:
            ham_yol = os.path.join(gecici, "ham.nc")
            e.cds_kotasini_tuket()
            e.cds_nezaket_beklemesi()
            e._cds_istemcisi().retrieve(e.CDS_VERI_SETI, istek, ham_yol)
            with hdf5_kilidi, xr.open_dataset(ham_yol) as ham:
                kup = e.era5_kupunu_normalize_et(ham, "cds").load()
        e._atomik_yaz(kup, yol)
    return xr.load_dataset(yol)


def eslemeyi_calistir(zamanlar, kutu, adim_derece, fl_listesi, klasor, esik=None, tekrar=1000) -> dict:
    esik = config.TI1_ESIK_ORTA_SIDDETLI if esik is None else esik
    os.makedirs(klasor, exist_ok=True)
    zamanlar = [_utc(z) for z in zamanlar]
    era5_parcalari, gfs_parcalari, nokta_parcalari = [], [], []
    for gun, gun_zamanlari in pd.Series(zamanlar).groupby(pd.Series(zamanlar).dt.normalize()):
        era5_kupu = era5_gununu_getir(gun, sorted({z.hour for z in gun_zamanlari}), kutu, klasor)
        for zaman in gun_zamanlari:
            noktalar = izgara_noktalari(kutu, adim_derece, [zaman], fl_listesi)
            gfs_kupu = gfs_analizini_getir(zaman, kutu, klasor)
            era5_parcalari.append(ti1_orneklemi(era5_kupu, noktalar))
            gfs_parcalari.append(ti1_orneklemi(gfs_kupu, noktalar))
            nokta_parcalari.append(noktalar)
            _logger.info("Eşleme %s: %d nokta", zaman.isoformat(), len(noktalar))
    noktalar = pd.concat(nokta_parcalari, ignore_index=True)
    rapor = esleme_raporu(noktalar, np.concatenate(era5_parcalari), np.concatenate(gfs_parcalari), esik, tekrar)
    rapor["ayarlar"] = {
        "kutu": list(kutu),
        "adim_derece": adim_derece,
        "fl": [int(f) for f in fl_listesi],
        "era5_seviyeleri_hpa": [float(s) for s in config.ERA5_BASINC_SEVIYELERI_HPA],
        "gfs_seviyeleri_hpa": [float(s) for s in config.CANLI_BASINC_SEVIYELERI_HPA],
        "gfs": "THREDDS koşu bazlı veri kümesi, analiz (f000)",
        "era5": "Copernicus CDS reanalysis-era5-pressure-levels",
        "uretim_zamani": datetime.now(UTC).isoformat(),
    }
    return rapor


def _yuzde(x):
    return "—" if x is None else f"%{100 * x:.1f}"


def _bilimsel(x):
    return "—" if x is None else f"{x:.2e}"


def markdown_ozeti(rapor) -> str:
    g = rapor["genel"]
    ga = g.get("gfs_esdeger_esik_ga95")
    ga_metni = "—" if not ga else f"{ga[0]:.2e} – {ga[1]:.2e}"
    spearman = "—" if g.get("spearman") is None else f"{g['spearman']:.2f}"
    satirlar = [
        "# TI1 eşik eşlemesi: ERA5 → canlı GFS",
        "",
        f"Üretim: {rapor['ayarlar']['uretim_zamani']}. Kutu {rapor['ayarlar']['kutu']}, "
        f"{rapor['ayarlar']['adim_derece']}° adım, FL {rapor['ayarlar']['fl']}, {rapor['zaman_sayisi']} analiz saati.",
        "",
        "ERA5 seviyeleri "
        f"{rapor['ayarlar']['era5_seviyeleri_hpa']} hPa, canlı GFS seviyeleri {rapor['ayarlar']['gfs_seviyeleri_hpa']} hPa. "
        "TI1 her iki kaynakta da rota kodunun kullandığı eşleştirmeyle (`rotayi_hava_durumuyla_eslestir`) "
        "aynı noktalarda hesaplandı.",
        "",
        "| Ölçü | Değer |",
        "|---|---|",
        f"| Eşleşen nokta | {g['n']} |",
        f"| ERA5 eşiği | {_bilimsel(g.get('era5_esik'))} |",
        f"| ERA5'te eşiğin yüzdeliği | {_yuzde(g.get('yuzdelik'))} |",
        f"| GFS eşdeğer eşik | {_bilimsel(g.get('gfs_esdeger_esik'))} |",
        f"| GFS eşdeğer eşik %95 GA (zaman bootstrap) | {ga_metni} |",
        f"| ERA5 riskli oran | {_yuzde(g.get('era5_riskli_orani'))} |",
        f"| GFS riskli oran (aynı eşikte) | {_yuzde(g.get('gfs_riskli_orani_ayni_esikte'))} |",
        f"| Medyan TI1 ERA5 / GFS | {_bilimsel(g.get('era5_medyan'))} / {_bilimsel(g.get('gfs_medyan'))} |",
        f"| Spearman (nokta bazlı) | {spearman} |",
        "",
        "| Seviye | n | ERA5 riskli | GFS riskli (aynı eşik) | GFS eşdeğer eşik |",
        "|---|---|---|---|---|",
    ]
    for ad, s in rapor["seviyeler"].items():
        satirlar.append(
            f"| {ad} | {s['n']} | {_yuzde(s.get('era5_riskli_orani'))} | "
            f"{_yuzde(s.get('gfs_riskli_orani_ayni_esikte'))} | {_bilimsel(s.get('gfs_esdeger_esik'))} |"
        )
    satirlar += [
        "",
        "Bu eşleme iki kaynağın TI1 dağılımlarını tutarlı kılar; GFS'in türbülans becerisini kanıtlamaz "
        "(o, PIREP/MADIS'e karşı doğrulama karnesinin işidir). Örneklem tek bölge ve kısa bir dönemdir. "
        "`TI1_ESIK_ORTA_SIDDETLI_GFS` bu rapordan otomatik ayarlanmaz; değer onayla `.env`'e yazılır.",
    ]
    return "\n".join(satirlar) + "\n"


def _zamanlar(baslangic, bitis) -> list[pd.Timestamp]:
    return list(pd.date_range(_utc(baslangic), _utc(bitis), freq="6h"))


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="ERA5 TI1 eşiğinin canlı GFS'teki yüzdelik eşleniğini hesaplar.")
    ayrac.add_argument("--baslangic", required=True, help="İlk analiz saati (UTC, 00/06/12/18)")
    ayrac.add_argument("--bitis", required=True, help="Son analiz saati (UTC, 00/06/12/18)")
    ayrac.add_argument(
        "--kutu", default=",".join(str(x) for x in VARSAYILAN_KUTU), help="enlem_min,enlem_maks,boylam_min,boylam_maks"
    )
    ayrac.add_argument("--adim", type=float, default=0.5, help="Örnekleme adımı (derece)")
    ayrac.add_argument("--fl", default=",".join(str(f) for f in VARSAYILAN_FL))
    ayrac.add_argument("--veri-klasoru", default=os.path.join("ciktilar", "esik_esleme"))
    ayrac.add_argument("--cikti", required=True, help="Rapor klasörü (örn. docs/sonuclar/2026-10-16)")
    ayrac.add_argument("--tekrar", type=int, default=1000)
    arg = ayrac.parse_args(argv)
    kutu = tuple(float(x) for x in arg.kutu.split(","))
    fl_listesi = tuple(int(x) for x in arg.fl.split(","))
    rapor = eslemeyi_calistir(
        _zamanlar(arg.baslangic, arg.bitis), kutu, arg.adim, fl_listesi, arg.veri_klasoru, tekrar=arg.tekrar
    )
    os.makedirs(arg.cikti, exist_ok=True)
    with open(os.path.join(arg.cikti, "esik_esleme.json"), "w", encoding="utf-8") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2)
    with open(os.path.join(arg.cikti, "esik_esleme.md"), "w", encoding="utf-8") as dosya:
        dosya.write(markdown_ozeti(rapor))
    g = rapor["genel"]
    print(
        f"GFS eşdeğer eşik: {_bilimsel(g.get('gfs_esdeger_esik'))} (ERA5 {_bilimsel(g.get('era5_esik'))}, n={g['n']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
