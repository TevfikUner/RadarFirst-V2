"""
rota_backtest.py
-------------------
A* rota optimizasyonunun GERÇEK uçuşlar üzerinde otomatik doğrulaması
(backtest). Veritabanındaki analiz edilmiş bir uçuşun gerçek izinin, hava
küpünün kapsadığı seyir bölümü için üç rota AYNI ölçütle karşılaştırılır:

  gercek      : uçağın OpenSky'da kaydedilmiş gerçek izi (gerçek irtifasıyla)
  buyuk_daire : aynı giriş/çıkış noktaları arası büyük daire
  optimize    : rota_optimizasyonu.py'nin önerdiği rota (SIGMET > TI1 > yakıt)

Adil karşılaştırma için gerçek iz, büyük daire/optimize rotalarla AYNI nokta
sayısına (config.ROTA_SIMULASYONU_NOKTA_SAYISI) kümülatif mesafe boyunca
yeniden örneklenir ve TI1 aynı hava küpüyle, aynı kodla
(risk_katmanlari.rota_ti1_degerleri) hesaplanır. Metrikler: mesafe, süre,
riskli (TI1 >= eşik) nokta oranı ve aktif SIGMET ihlali. Sonuç uçuş başına
`rota_backtestleri` tablosuna yazılır (en son çalıştırma).

Seyir irtifası, gerçek izin kapsam içi noktalarının medyan irtifasının en
yakın 1000 ft'e yuvarlanmasıdır (uçuş seviyesi).

Çalıştırma:
    turbulans-backtest THY322 2019-01-15
    turbulans-backtest --hepsi
"""

import argparse

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo.models import RotaBacktesti, Ucus
from turbulans_radar.depo.veritabani import motor_al, ucus_olcumlerini_dataframe_olarak_getir
from turbulans_radar.fizik.birim_donusumleri import irtifa_metre_to_basinc_hpa
from turbulans_radar.rota.risk_katmanlari import SigmetKisitKatmani, rota_ti1_degerleri
from turbulans_radar.rota.rota_optimizasyonu import buyuk_daire_mesafesi_km, rota_simulasyonu_olustur
from turbulans_radar.veri.sigmet_saglayici import gecerli_sigmetleri_getir
from turbulans_radar.veri.veri_saglayicilari import veri_kupu_kaynagi, veri_kupunu_sec

_ROTALAR = ("gercek", "buyuk_daire", "optimize")
_EN_AZ_SEYIR_NOKTASI = 10
_SEYIR_BOSLUGU = pd.Timedelta(minutes=15)
_YETERSIZ_SEYIR_MESAJI = (
    "Hava küpünün kapsadığı kesintisiz seyir bölümünde yeterli nokta yok ({nokta} < 10) -- uçuş küp dışında "
    "olabilir ya da ölçümlerde irtifa kayıtlı değil (irtifa_m sütunundan önce analiz edilmiş uçuşları yeniden "
    "analiz et)."
)


class BacktestYapilamadiHatasi(ValueError):
    """Uçuş yok, irtifası kayıtlı değil ya da hava küpü seyir bölümünü kapsamıyor."""


def _kumulatif_km(enlemler, boylamlar):
    adimlar = [
        buyuk_daire_mesafesi_km(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1])
        for i in range(len(enlemler) - 1)
    ]
    return np.concatenate([[0.0], np.cumsum(adimlar)])


def _yeniden_ornekle(seyir_df, nokta_sayisi):
    """Gerçek izi kümülatif mesafe boyunca eşit aralıklı noktalara indirger."""
    kumulatif = _kumulatif_km(seyir_df["enlem"].to_numpy(), seyir_df["boylam"].to_numpy())
    hedef = np.linspace(0.0, kumulatif[-1], nokta_sayisi)
    zaman_sn = (pd.to_datetime(seyir_df["zaman"], utc=True) - pd.Timestamp(0, tz="UTC")).dt.total_seconds()
    return {
        "enlem": np.interp(hedef, kumulatif, seyir_df["enlem"].to_numpy()),
        "boylam": np.interp(hedef, kumulatif, seyir_df["boylam"].to_numpy()),
        "irtifa_m": np.interp(hedef, kumulatif, seyir_df["irtifa_m"].to_numpy()),
        "zaman": pd.to_datetime(np.interp(hedef, kumulatif, zaman_sn.to_numpy()), unit="s", utc=True),
        "mesafe_km": float(kumulatif[-1]),
    }


def _riskli_oran(ti1_degerleri):
    gecerli = ti1_degerleri[~np.isnan(ti1_degerleri)]
    return float(np.mean(gecerli >= config.TI1_ESIK_ORTA_SIDDETLI)) if len(gecerli) else None


def _seyir_bolumu(olcum_df):
    """Hava küpünün kapsadığı (TI1'i ve irtifası olan) noktalardan oluşan EN
    UZUN kesintisiz blok. Aradaki boşluk _SEYIR_BOSLUGU'ndan uzunsa blok
    bölünür -- OpenSky'ın gürültülü geo irtifalarıyla kapsam içine düşen tekil
    noktalar (örn. kalkıştan 1 dk sonra 9.9 km) seyir sayılmasın diye."""
    kapsam_ici = olcum_df[olcum_df["ti1_indeksi"].notna() & olcum_df["irtifa_m"].notna()].reset_index(drop=True)
    if kapsam_ici.empty:
        raise BacktestYapilamadiHatasi(_YETERSIZ_SEYIR_MESAJI.format(nokta=0))
    zaman = pd.to_datetime(kapsam_ici["zaman"], utc=True)
    blok = (zaman.diff() > _SEYIR_BOSLUGU).cumsum()
    sureler = zaman.groupby(blok).agg(lambda z: z.max() - z.min())
    seyir = kapsam_ici[blok == sureler.idxmax()].reset_index(drop=True)
    if len(seyir) < _EN_AZ_SEYIR_NOKTASI:
        raise BacktestYapilamadiHatasi(_YETERSIZ_SEYIR_MESAJI.format(nokta=len(seyir)))
    return seyir


def ucus_backtest_et(ucus_numarasi, tarih_str, ucak_modeli=None, motor=None) -> dict:
    """Bir uçuşun backtest'ini çalıştırıp `rota_backtestleri`'ne yazar; sonucu döner."""
    ucak_modeli = ucak_modeli or config.BACKTEST_UCAK_MODELI
    motor = motor or motor_al()
    olcum_df = ucus_olcumlerini_dataframe_olarak_getir(ucus_numarasi, tarih_str, motor=motor)
    if olcum_df is None:
        raise BacktestYapilamadiHatasi(f"'{ucus_numarasi}' / {tarih_str} için kayıtlı uçuş yok.")
    seyir = _seyir_bolumu(olcum_df)
    irtifa_ft = float(round(seyir["irtifa_m"].median() / 0.3048 / 1000.0) * 1000.0)
    ilk, son = seyir.iloc[0], seyir.iloc[-1]
    baslangic_zamani = pd.Timestamp(ilk["zaman"]).tz_convert("UTC")
    bitis_zamani = pd.Timestamp(son["zaman"]).tz_convert("UTC")

    sigmetler = gecerli_sigmetleri_getir(
        baslangic_zamani.to_pydatetime(),
        bitis_zamani.to_pydatetime(),
        float(seyir["enlem"].min()) - 5.0,
        float(seyir["enlem"].max()) + 5.0,
        float(seyir["boylam"].min()) - 5.0,
        float(seyir["boylam"].max()) + 5.0,
        tehlikeler=config.SIGMET_KACINILACAK_TEHLIKELER,
        motor=motor,
    )
    simulasyon = rota_simulasyonu_olustur(
        float(ilk["enlem"]),
        float(ilk["boylam"]),
        float(son["enlem"]),
        float(son["boylam"]),
        irtifa_ft,
        baslangic_zamani.tz_localize(None).isoformat(),
        ucak_modeli,
        sigmetler=sigmetler,
    )

    gercek = _yeniden_ornekle(seyir, config.ROTA_SIMULASYONU_NOKTA_SAYISI)
    veri_kupu = veri_kupunu_sec(
        gercek["enlem"], gercek["boylam"], list(gercek["zaman"]), irtifa_metre_to_basinc_hpa(gercek["irtifa_m"])
    )
    if veri_kupu is None:
        raise BacktestYapilamadiHatasi("Gerçek izin seyir bölümünü kapsayan hava küpü bulunamadı.")
    gercek_ti1 = rota_ti1_degerleri(gercek["enlem"], gercek["boylam"], gercek["irtifa_m"], gercek["zaman"], veri_kupu)
    sigmet_katmani = SigmetKisitKatmani(sigmetler)
    nokta_sayisi = config.ROTA_SIMULASYONU_NOKTA_SAYISI

    satir = {
        "ucak_modeli": ucak_modeli,
        "seyir_irtifasi_ft": irtifa_ft,
        "veri_kaynagi": veri_kupu_kaynagi(veri_kupu),
        "kacinma_stratejisi": simulasyon["kacinma_stratejisi"],
        "guvenli_rota_bulundu_mu": simulasyon["guvenli_rota_bulundu_mu"],
        "gercek_mesafe_km": float(_kumulatif_km(seyir["enlem"].to_numpy(), seyir["boylam"].to_numpy())[-1]),
        "gercek_sure_dk": (bitis_zamani - baslangic_zamani).total_seconds() / 60.0,
        "gercek_riskli_oran": _riskli_oran(gercek_ti1),
        "gercek_sigmet_ihlali": sigmet_katmani.rota_ihlal_sayisi(
            gercek["enlem"], gercek["boylam"], list(gercek["zaman"]), irtifa_ft * 0.3048
        ),
    }
    for rota, anahtar in (("buyuk_daire", "normal_rota"), ("optimize", "optimize_rota")):
        ozet = simulasyon[anahtar]
        satir.update(
            {
                f"{rota}_mesafe_km": ozet["mesafe_km"],
                f"{rota}_sure_dk": ozet["toplam_sure_dk"],
                f"{rota}_riskli_oran": ozet["riskli_nokta_sayisi"] / nokta_sayisi
                if ozet["maks_ti1"] is not None
                else None,
                f"{rota}_sigmet_ihlali": ozet["sigmet_ihlali_sayisi"],
            }
        )

    satir = {k: (v.item() if isinstance(v, np.generic) else v) for k, v in satir.items()}
    with Session(motor) as oturum:
        ucus_id = oturum.execute(
            select(Ucus.id).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == pd.Timestamp(tarih_str).date())
        ).scalar_one()
        ifade = insert(RotaBacktesti).values(ucus_id=ucus_id, **satir)
        oturum.execute(
            ifade.on_conflict_do_update(
                index_elements=["ucus_id"],
                set_={**{k: ifade.excluded[k] for k in satir}, "olusturulma_zamani": func.now()},
            )
        )
        oturum.commit()
    return {"ucus_numarasi": ucus_numarasi, "tarih": str(tarih_str), **satir}


def backtest_edilmemis_ucuslar(limit=20, motor=None) -> list[tuple[str, str]]:
    motor = motor or motor_al()
    with Session(motor) as oturum:
        satirlar = oturum.execute(
            select(Ucus.ucus_numarasi, Ucus.tarih)
            .outerjoin(RotaBacktesti, RotaBacktesti.ucus_id == Ucus.id)
            .where(RotaBacktesti.id.is_(None))
            .order_by(Ucus.olusturulma_zamani.desc())
            .limit(limit)
        ).all()
    return [(u, t.isoformat()) for u, t in satirlar]


def toplu_backtest(limit=20, motor=None) -> list[dict]:
    """Henüz backtest'i olmayan uçuşları sırayla dener; yapılamayanlar
    ('durum': 'atlandi', gerekçesiyle) raporlanır, akışı durdurmaz."""
    sonuclar = []
    for ucus_numarasi, tarih in backtest_edilmemis_ucuslar(limit, motor):
        try:
            ucus_backtest_et(ucus_numarasi, tarih, motor=motor)
            sonuclar.append({"ucus_numarasi": ucus_numarasi, "tarih": tarih, "durum": "tamamlandi"})
        except BacktestYapilamadiHatasi as hata:
            sonuclar.append({"ucus_numarasi": ucus_numarasi, "tarih": tarih, "durum": "atlandi", "aciklama": str(hata)})
    return sonuclar


def backtestleri_listele(motor=None) -> dict:
    """Tüm backtest sonuçları + filo geneli özet (A*'ın gerçek uçuşlara göre
    ortalama riskli nokta oranı değişimi, ek mesafe/süre)."""
    motor = motor or motor_al()
    with Session(motor) as oturum:
        satirlar = oturum.execute(
            select(RotaBacktesti, Ucus.ucus_numarasi, Ucus.tarih)
            .join(Ucus, Ucus.id == RotaBacktesti.ucus_id)
            .order_by(RotaBacktesti.olusturulma_zamani.desc())
        ).all()
    sonuclar = [
        {
            "ucus_numarasi": ucus_numarasi,
            "tarih": tarih.isoformat(),
            **{c.name: getattr(b, c.name) for c in RotaBacktesti.__table__.columns if c.name not in ("id", "ucus_id")},
        }
        for b, ucus_numarasi, tarih in satirlar
    ]
    return {"ozet": _filo_ozeti(sonuclar), "sonuclar": sonuclar}


def _filo_ozeti(sonuclar):
    ozet = {"ucus_sayisi": len(sonuclar)}
    if not sonuclar:
        return ozet
    df = pd.DataFrame(sonuclar)
    for rota in _ROTALAR:
        oran = df[f"{rota}_riskli_oran"].dropna()
        ozet[f"{rota}_ort_riskli_oran"] = float(oran.mean()) if len(oran) else None
        ozet[f"{rota}_toplam_sigmet_ihlali"] = int(df[f"{rota}_sigmet_ihlali"].sum())
    karsilastirilabilir = df.dropna(subset=["gercek_riskli_oran", "optimize_riskli_oran"])
    ozet["riski_azaltilan_ucus_orani"] = (
        float((karsilastirilabilir["optimize_riskli_oran"] < karsilastirilabilir["gercek_riskli_oran"]).mean())
        if len(karsilastirilabilir)
        else None
    )
    ozet["ort_ek_mesafe_km_gercege_gore"] = float((df["optimize_mesafe_km"] - df["gercek_mesafe_km"]).mean())
    ozet["ort_ek_sure_dk_gercege_gore"] = float((df["optimize_sure_dk"] - df["gercek_sure_dk"]).mean())
    return ozet


def ana():
    from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

    konsolu_utf8_yap()
    ayristirici = argparse.ArgumentParser(description="A* rota optimizasyonunu gerçek uçuşlarla karşılaştırır.")
    ayristirici.add_argument("ucus_numarasi", nargs="?")
    ayristirici.add_argument("tarih", nargs="?", help="YYYY-MM-DD")
    ayristirici.add_argument("--hepsi", action="store_true", help="Backtest'i olmayan tüm uçuşlar")
    argumanlar = ayristirici.parse_args()
    if argumanlar.hepsi:
        for sonuc in toplu_backtest(limit=1000):
            print(sonuc)
    elif argumanlar.ucus_numarasi and argumanlar.tarih:
        print(ucus_backtest_et(argumanlar.ucus_numarasi, argumanlar.tarih))
    print(backtestleri_listele()["ozet"])


if __name__ == "__main__":
    ana()
