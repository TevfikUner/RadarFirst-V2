"""
api_servisi.py
-----------------
Hava durumu eşleştirme sonuçlarını (Ellrod TI1, Richardson, EDR proxy) JSON
olarak dışarıya sunan FastAPI servis katmanı -- REST API İSKELETİdir.

Okuma uç noktaları (/ucuslar/*) PostgreSQL'deki (veritabani.py) kayıtları
döndürür. Tetikleme uç noktaları (/analiz/*) main.py/toplu_analiz.py ile
AYNI mantığı arka planda (BackgroundTasks) çalıştırır -- n8n gibi bir
otomasyon aracı, bir Cron/Schedule Trigger'dan bu uç noktaları HTTP Request
node'uyla periyodik olarak çağırıp sonucu /analiz/durum/{gorev_id} ve
/ucuslar/* ile takip edebilir.

BİLİNÇLİ OLARAK EKLENMEDİ: veri_indirme.py'nin GERÇEK ERA5 indirmesini
tetikleyen bir uç nokta. O modül, OpenSky/Copernicus'u rate-limit/ban
riskine sokmamak için kasıtlı olarak sadece elle, açık onayla
(--gercekten-indir) çalışacak şekilde tasarlandı -- bunu periyodik/otomatik
hale getirmek o güvenlik kararını bozar.

Çalıştırma:
    uvicorn api_servisi:app --reload --port 8000
"""

import uuid

import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from main import calistir as tek_ucus_analiz_et
from toplu_analiz import toplu_analiz_calistir
from veritabani import ucuslari_listele, ucus_detayini_getir, VeritabaniAyarlariEksikHatasi
from hata_yardimcisi import dostane_hata_mesaji

app = FastAPI(
    title="Türbülans Radar API",
    description="Ellrod TI1 + Richardson tabanlı türbülans eşleştirme sonuçlarını JSON olarak sunar.",
    version="1.0.0",
)

# Basit bellek-içi görev durumu takibi -- iskelet amaçlı. Süreç yeniden
# başlarsa (örn. deploy) sıfırlanır; kalıcı bir görev kuyruğu (Celery/RQ)
# gerekiyorsa ileride buraya eklenebilir.
_gorevler = {}


class UcusAnalizIstegi(BaseModel):
    ucus_numarasi: str
    tarih: str  # YYYY-MM-DD


class TopluAnalizIstegi(BaseModel):
    ucuslar: list[UcusAnalizIstegi]


@app.get("/saglik")
def saglik_kontrolu():
    return {"durum": "ayakta"}


@app.get("/ucuslar")
def ucuslar_listesi(limit: int = 100):
    try:
        return ucuslari_listele(limit=limit)
    except VeritabaniAyarlariEksikHatasi as hata:
        raise HTTPException(status_code=503, detail=str(hata))


@app.get("/ucuslar/{ucus_numarasi}/{tarih}")
def ucus_detayi(ucus_numarasi: str, tarih: str):
    try:
        detay = ucus_detayini_getir(ucus_numarasi, tarih)
    except VeritabaniAyarlariEksikHatasi as hata:
        raise HTTPException(status_code=503, detail=str(hata))
    if detay is None:
        raise HTTPException(
            status_code=404,
            detail="Uçuş bulunamadı. Önce POST /analiz/ucus ile analiz tetikle.",
        )
    return detay


def _tek_ucus_arkaplan_gorevi(gorev_id, ucus_numarasi, tarih):
    _gorevler[gorev_id] = {"durum": "calisiyor", "ucus_numarasi": ucus_numarasi, "tarih": tarih}
    try:
        sonuc = tek_ucus_analiz_et(ucus_numarasi, tarih)
        _gorevler[gorev_id]["durum"] = "tamamlandi" if sonuc is not None else "basarisiz"
    except Exception as hata:
        _gorevler[gorev_id]["durum"] = "hata"
        _gorevler[gorev_id]["aciklama"] = dostane_hata_mesaji(hata)


@app.post("/analiz/ucus", status_code=202)
def ucus_analizi_baslat(istek: UcusAnalizIstegi, arkaplan_gorevleri: BackgroundTasks):
    gorev_id = str(uuid.uuid4())
    arkaplan_gorevleri.add_task(_tek_ucus_arkaplan_gorevi, gorev_id, istek.ucus_numarasi, istek.tarih)
    return {"gorev_id": gorev_id, "durum": "baslatildi"}


def _toplu_arkaplan_gorevi(gorev_id, ucus_listesi_df):
    _gorevler[gorev_id] = {"durum": "calisiyor"}
    try:
        ozet_df = toplu_analiz_calistir(ucus_listesi_df)
        _gorevler[gorev_id]["durum"] = "tamamlandi"
        _gorevler[gorev_id]["ozet"] = ozet_df.to_dict(orient="records")
    except Exception as hata:
        _gorevler[gorev_id]["durum"] = "hata"
        _gorevler[gorev_id]["aciklama"] = dostane_hata_mesaji(hata)


@app.post("/analiz/toplu", status_code=202)
def toplu_analiz_baslat(istek: TopluAnalizIstegi, arkaplan_gorevleri: BackgroundTasks):
    if not istek.ucuslar:
        raise HTTPException(status_code=400, detail="'ucuslar' listesi boş olamaz.")
    ucus_listesi_df = pd.DataFrame([u.model_dump() for u in istek.ucuslar])
    gorev_id = str(uuid.uuid4())
    arkaplan_gorevleri.add_task(_toplu_arkaplan_gorevi, gorev_id, ucus_listesi_df)
    return {"gorev_id": gorev_id, "durum": "baslatildi"}


@app.get("/analiz/durum/{gorev_id}")
def analiz_durumu(gorev_id: str):
    gorev = _gorevler.get(gorev_id)
    if gorev is None:
        raise HTTPException(status_code=404, detail="Bilinmeyen gorev_id.")
    return gorev
