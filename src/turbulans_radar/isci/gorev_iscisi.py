"""
gorev_iscisi.py
------------------
analiz_gorevleri kuyruğunun (bkz. depo/gorev_deposu.py) İŞÇİSİ. Uzun işler
API sürecinin içinde değil burada çalışır:
  - Eşzamanlılık sınırı: config.GOREV_ISCI_SAYISI iş parçacığı -- aynı anda en
    fazla bu kadar ağır iş (ör. 5 GB'lık bir toplu işte bile API yanıt verir).
  - Kalıcılık: görev kuyrukta beklerken API/işçi yeniden başlasa kaybolmaz;
    çalışırken işçi ölürse kalp atışı kesilir, görev yeniden kuyruğa girer.
  - Ölçekleme: birden fazla işçi süreci aynı kuyruğu güvenle paylaşır (SKIP LOCKED).
Varsayılan olarak API kendi içinde gömülü bir işçi başlatır
(config.GOREV_GOMULU_ISCI); docker-compose'da ayrı `worker` servisi çalışır:
    turbulans-isci          (ya da python -m turbulans_radar.isci.gorev_iscisi)

Canlı uyarılar: riskli nokta bulunan analizler PostgreSQL NOTIFY ile
BILDIRIM_KANALI'na yayınlanır; API bu kanalı dinleyip WebSocket istemcilerine
iletir -- işçi hangi süreçte çalışırsa çalışsın uyarılar kaybolmaz.
"""

import json
import os
import signal
import socket
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from functools import partial

import pandas as pd
from sqlalchemy import text

from turbulans_radar import config, loglama
from turbulans_radar.analiz.toplu_analiz import toplu_analiz_calistir
from turbulans_radar.analiz.ucus_analizi import calistir, rota_df_ile_calistir
from turbulans_radar.depo.dagitik_kilit import KilitZamanAsimiHatasi, dagitik_kilit
from turbulans_radar.depo.gorev_deposu import (
    bayat_gorevleri_kurtar,
    gorev_getir_senkron,
    gorev_olustur_senkron,
    gorevi_bitir,
    kalp_atisi_gonder,
    siradaki_gorevi_al,
)
from turbulans_radar.depo.kup_katalogu import kup_meta_verisi
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.dogrulama.rota_backtest import toplu_backtest
from turbulans_radar.hata_yardimcisi import dostane_hata_mesaji
from turbulans_radar.veri.veri_saglayicilari import Kutu, canli_kup_hazirla
from turbulans_radar.veri.veri_yukleme import veri_kupu_adi
from turbulans_radar.webhook import webhook_gonder

_logger = loglama.logger_al(__name__)

BILDIRIM_KANALI = "turbulans_uyarilari"
CANLI_VERI_HATA_MESAJI = "Canlı hava verisi sağlayıcısından geçerli veri alınamadı."

# harita_uret=False: sunucuda kimsenin açmayacağı bir Folium HTML'i
# ciktilar/'a yazmak yerine sonuç PostgreSQL'den (GET /ucuslar/{..} + csv/
# geojson) okunur -- disk sınırsız büyümesin diye (bkz. ucus_analizi.py).
tek_ucus_analiz_et = partial(calistir, kayit_zorunlu=True, harita_uret=False)
rota_analiz_et = partial(rota_df_ile_calistir, kayit_zorunlu=True, harita_uret=False)


def bildirim_yayinla(mesaj: dict, motor=None) -> None:
    motor = motor or motor_al()
    with motor.begin() as baglanti:
        baglanti.execute(text("SELECT pg_notify(:kanal, :yuk)"), {"kanal": BILDIRIM_KANALI, "yuk": json.dumps(mesaj)})


def riskli_noktalari_bildir(eslesmis_df, ucus_numarasi, tarih) -> None:
    if eslesmis_df is None or eslesmis_df.empty or "ti1_indeksi" not in eslesmis_df.columns:
        return
    riskli = eslesmis_df[eslesmis_df["ti1_indeksi"] >= config.TI1_ESIK_ORTA_SIDDETLI]
    if riskli.empty:
        return
    try:
        bildirim_yayinla(
            {
                "tip": "turbulans_uyarisi",
                "ucus_numarasi": ucus_numarasi,
                "tarih": tarih,
                "orta_siddetli_nokta_sayisi": int(len(riskli)),
                "maks_ti1": float(riskli["ti1_indeksi"].max()),
            }
        )
    except Exception as hata:
        _logger.warning("Canlı uyarı yayınlanamadı (%s): %s", ucus_numarasi, dostane_hata_mesaji(hata))


def _analiz_sonucu(sonuc, ucus_numarasi, tarih) -> dict:
    riskli_noktalari_bildir(sonuc, ucus_numarasi, tarih)
    return {"durum": "tamamlandi" if sonuc is not None else "basarisiz"}


def _ucus_gorevi(gorev):
    return _analiz_sonucu(
        tek_ucus_analiz_et(gorev["ucus_numarasi"], gorev["tarih"]), gorev["ucus_numarasi"], gorev["tarih"]
    )


def _rota_gorevi(gorev):
    rota_df = pd.DataFrame(gorev["parametreler"]["noktalar"]).rename(columns={"irtifa_m": "geo_irtifa_m"})
    rota_df["zaman"] = pd.to_datetime(rota_df["zaman"], utc=True)
    rota_df["geo_irtifa_m"] = rota_df["geo_irtifa_m"].astype(float)
    rota_df = rota_df.sort_values("zaman").reset_index(drop=True)
    rota_df["ucus_numarasi"] = gorev["ucus_numarasi"]
    return _analiz_sonucu(
        rota_analiz_et(rota_df, gorev["ucus_numarasi"], gorev["tarih"]), gorev["ucus_numarasi"], gorev["tarih"]
    )


def _toplu_gorevi(gorev):
    ozet_df = toplu_analiz_calistir(
        pd.DataFrame(gorev["parametreler"]["ucuslar"]),
        kayit_zorunlu=True,
        ucus_tamamlandi=lambda ucus_numarasi, tarih, eslesmis_df: riskli_noktalari_bildir(
            eslesmis_df, ucus_numarasi, tarih
        ),
        harita_uret=False,
    )
    return {
        "durum": "tamamlandi",
        "ozet": ozet_df.astype(object).where(ozet_df.notna(), None).to_dict(orient="records"),
    }


def _backtest_gorevi(gorev):
    return {"durum": "tamamlandi", "ozet": toplu_backtest(gorev["parametreler"]["limit"])}


def _canli_veri_gorevi(gorev):
    p = gorev["parametreler"]
    baslangic = pd.Timestamp(p["baslangic"])
    try:
        kup = canli_kup_hazirla(Kutu(*p["kutu"]), baslangic, baslangic + pd.Timedelta(hours=p["saat_sayisi"]))
    except Exception as hata:
        _logger.error("Canlı GFS küpü hazırlanamadı", exc_info=hata)
        return {"durum": "hata", "aciklama": CANLI_VERI_HATA_MESAJI}
    ozet = {
        "kaynak": kup.attrs.get("kaynak", "era5"),
        "model_calisma_zamani": kup.attrs.get("model_calisma_zamani"),
        "dosya_adi": veri_kupu_adi(kup),
        **kup_meta_verisi(kup),
    }
    return {"durum": "tamamlandi", "ozet": [json.loads(json.dumps(ozet, default=str))]}


def _openaip_gorevi(gorev):
    from turbulans_radar.veri.openaip_saglayici import openaip_ice_aktar

    return {"durum": "tamamlandi", "ozet": [openaip_ice_aktar((gorev["parametreler"] or {}).get("ulkeler"))]}


ML_ATLANDI_MESAJI = "Aynı türde bir ML işi başka bir işçide sürüyor; bu tetikleme atlandı."


def _ml_veri_gorevi(gorev):
    from turbulans_radar.ml.ml_veri_hatti import ml_veri_hatti_calistir

    p = gorev["parametreler"] or {}
    try:
        with dagitik_kilit("ml_veri_hatti", zaman_asimi_saniye=0):
            ozet = ml_veri_hatti_calistir(
                iem_guncelle=p.get("iem_guncelle", True), maks_cds_istek=p.get("maks_cds_istek")
            )
    except KilitZamanAsimiHatasi:
        return {"durum": "tamamlandi", "aciklama": ML_ATLANDI_MESAJI}
    if p.get("ardindan_egitim", True):
        ozet["egitim_gorev_id"] = gorev_olustur_senkron("ml_egitim", parametreler={})
    return {"durum": "tamamlandi", "ozet": [ozet]}


def _ml_egitim_gorevi(gorev):
    from turbulans_radar.ml.ml_otomatik_egitim import otomatik_egitim_calistir

    try:
        with dagitik_kilit("ml_egitim", zaman_asimi_saniye=0):
            ozet = otomatik_egitim_calistir()
    except KilitZamanAsimiHatasi:
        return {"durum": "tamamlandi", "aciklama": ML_ATLANDI_MESAJI}
    return {"durum": "tamamlandi", "aciklama": ozet["gerekce"], "ozet": [ozet]}


ISLEYICILER = {
    "ucus": _ucus_gorevi,
    "rota": _rota_gorevi,
    "toplu": _toplu_gorevi,
    "backtest": _backtest_gorevi,
    "canli_veri": _canli_veri_gorevi,
    "openaip": _openaip_gorevi,
    "ml_veri": _ml_veri_gorevi,
    "ml_egitim": _ml_egitim_gorevi,
}


def gorevi_yurut(gorev: dict) -> dict:
    """Görevi türüne göre çalıştırır; dönüş gorevi_bitir alanları. Hata
    sızdırmaz: istisna 'hata' durumuna ve dostane bir mesaja çevrilir."""
    isleyici = ISLEYICILER.get(gorev["tur"])
    if isleyici is None:
        return {"durum": "hata", "aciklama": f"Bilinmeyen görev türü: {gorev['tur']}"}
    try:
        return isleyici(gorev)
    except Exception as hata:
        _logger.error("Görev başarısız (%s / %s)", gorev["tur"], gorev["id"], exc_info=hata)
        return {"durum": "hata", "aciklama": dostane_hata_mesaji(hata)}


def webhooku_bildir(webhook_url, govde) -> None:
    if not webhook_url:
        return
    try:
        gonderildi = webhook_gonder(webhook_url, json.loads(json.dumps(govde, default=str)))
    except Exception as hata:
        _logger.warning("Webhook bildirimi gönderilemedi (%s): %s", webhook_url, dostane_hata_mesaji(hata))
        return
    if not gonderildi:
        _logger.warning(
            "Webhook gönderilmedi: %s iç ağ/çözümlenemeyen bir adrese işaret ediyor (SSRF koruması).", webhook_url
        )


class GorevIscisi:
    """isci_sayisi iş parçacığıyla kuyruğu işler; bir bakım iş parçacığı
    çalışan görevlerin kalp atışını gönderir ve ölmüş işçilerin görevlerini kurtarır."""

    def __init__(self, isci_sayisi=None, bekleme_saniye=None, ad=None, turler=None):
        self.isci_sayisi = isci_sayisi or config.GOREV_ISCI_SAYISI
        self.turler = tuple(turler) if turler else config.GOREV_ISCI_TURLERI or None
        self.bekleme_saniye = config.GOREV_KUYRUK_BEKLEME_SANIYE if bekleme_saniye is None else bekleme_saniye
        self.ad = ad or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self._dur = threading.Event()
        self._kilit = threading.Lock()
        self._calisanlar: set[str] = set()
        self._is_parcaciklari: list[threading.Thread] = []

    def baslat(self):
        for i in range(self.isci_sayisi):
            self._is_parcaciklari.append(threading.Thread(target=self._dongu, name=f"gorev-iscisi-{i}", daemon=True))
        self._is_parcaciklari.append(threading.Thread(target=self._bakim_dongusu, name="gorev-bakim", daemon=True))
        for is_parcacigi in self._is_parcaciklari:
            is_parcacigi.start()
        _logger.info("Görev işçisi başladı: %s (%d iş parçacığı)", self.ad, self.isci_sayisi)
        return self

    def durdur(self, zaman_asimi=10.0):
        """Yeni görev almayı keser; çalışan görevin bitmesini zaman_asimi kadar
        bekler (bitmeyen görev kalp atışı kesilince başka işçiye geçer)."""
        self._dur.set()
        son_an = time.monotonic() + zaman_asimi
        for is_parcacigi in self._is_parcaciklari:
            is_parcacigi.join(max(0.0, son_an - time.monotonic()))

    def _dongu(self):
        while not self._dur.is_set():
            try:
                gorev = siradaki_gorevi_al(self.ad, self.turler)
            except Exception as hata:
                _logger.warning("Görev kuyruğuna erişilemedi: %s", dostane_hata_mesaji(hata))
                self._dur.wait(max(self.bekleme_saniye, 1.0) * 5)
                continue
            if gorev is None:
                self._dur.wait(self.bekleme_saniye)
                continue
            self.calistir(gorev)

    def calistir(self, gorev: dict) -> None:
        with self._kilit:
            self._calisanlar.add(gorev["id"])
        try:
            alanlar = gorevi_yurut(gorev)
        finally:
            with self._kilit:
                self._calisanlar.discard(gorev["id"])
        try:
            if gorevi_bitir(gorev["id"], self.ad, **alanlar):
                webhooku_bildir(
                    gorev["bildirim_webhook_url"], {"gorev_id": gorev["id"], **gorev_getir_senkron(gorev["id"])}
                )
        except Exception as hata:
            _logger.error("Görev sonucu kaydedilemedi (%s)", gorev["id"], exc_info=hata)

    def _bakim_dongusu(self):
        bayat_sure = timedelta(seconds=config.GOREV_BAYAT_SANIYE)
        while not self._dur.wait(config.GOREV_KALP_ATISI_SANIYE):
            with self._kilit:
                calisanlar = list(self._calisanlar)
            try:
                if calisanlar:
                    kalp_atisi_gonder(calisanlar, self.ad)
                kurtarilan = bayat_gorevleri_kurtar(bayat_sure, config.GOREV_MAKS_DENEME)
                if any(kurtarilan.values()):
                    _logger.warning("Ölmüş işçilerin görevleri kurtarıldı: %s", kurtarilan)
            except Exception as hata:
                _logger.warning("Görev bakımı yapılamadı: %s", dostane_hata_mesaji(hata))


def ana():
    from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

    konsolu_utf8_yap()
    loglama.ayarla()
    isci = GorevIscisi().baslat()
    dur = threading.Event()
    for sinyal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sinyal, lambda *_: dur.set())
    while not dur.wait(1.0):
        pass
    _logger.info("İşçi durduruluyor (%s), çalışan görev bekleniyor...", datetime.now(UTC).isoformat())
    isci.durdur(zaman_asimi=60.0)


if __name__ == "__main__":
    ana()
