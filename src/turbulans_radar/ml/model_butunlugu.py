"""
model_butunlugu.py
--------------------
joblib dosyaları pickle'dır: yüklemek, dosyayı yazan kişinin kodunu çalıştırmak
demektir. Bu yüzden her model dosyasının sha256 özeti eğitim anında model
bilgisine (`model_sha256`) yazılır ve yüklemeden ÖNCE doğrulanır; uyuşmayan dosya
yüklenmez (sistem "model yok" yoluna düşer, uydurma tahmin üretmez).

Sınır: özet, model bilgisi JSON'ıyla aynı klasörde durur. Model klasörüne yazabilen
biri ikisini birden değiştirebilir; bu önlem bozulmayı, yarım yazımı ve yalnızca
.joblib'in değiştirildiği saldırıyı yakalar, yazma izni korumasının yerine geçmez.
Özeti olmayan eski modeller `MODEL_BUTUNLUK_ZORUNLU` kapalıyken uyarıyla yüklenir;
`turbulans-ml --muhurle` mevcut modellere özet ekler.
"""

import hashlib
import json
import os

from turbulans_radar import config, loglama

_logger = loglama.logger_al(__name__)


class ModelButunlukHatasi(RuntimeError):
    pass


def dosya_ozeti(yol: str) -> str:
    ozet = hashlib.sha256()
    with open(yol, "rb") as dosya:
        for parca in iter(lambda: dosya.read(1 << 20), b""):
            ozet.update(parca)
    return ozet.hexdigest()


def dogrula(yol: str, beklenen: str | None) -> None:
    if beklenen is None:
        if config.MODEL_BUTUNLUK_ZORUNLU:
            raise ModelButunlukHatasi(f"{os.path.basename(yol)} için model_sha256 kaydı yok (MODEL_BUTUNLUK_ZORUNLU).")
        _logger.warning(
            "%s için sha256 kaydı yok; doğrulanmadan yükleniyor (turbulans-ml --muhurle ile mühürleyin).",
            os.path.basename(yol),
        )
        return
    gercek = dosya_ozeti(yol)
    if gercek != beklenen:
        raise ModelButunlukHatasi(
            f"{os.path.basename(yol)} sha256 uyuşmuyor (beklenen {beklenen[:12]}…, bulunan {gercek[:12]}…)."
        )


def guvenle_yukle(yol: str, bilgi: dict | None):
    import joblib

    dogrula(yol, (bilgi or {}).get("model_sha256"))
    return joblib.load(yol)


def _atomik_json(yol: str, veri) -> None:
    gecici = f"{yol}.{os.getpid()}.gecici"
    with open(gecici, "w", encoding="utf-8") as dosya:
        json.dump(veri, dosya, ensure_ascii=False, indent=2)
    os.replace(gecici, yol)


def muhurle() -> dict:
    """Aktif modele ve manifest'teki sürümlere, özeti olmayanlar için sha256 ekler.
    Özeti olup uyuşmayan dosyaya dokunmaz, hata olarak raporlar."""
    from turbulans_radar.ml import turbulans_ml_modeli as tm

    sonuc = {"aktif": None, "surumler_muhurlendi": 0, "hatalar": []}
    bilgi = tm.model_bilgisini_yukle()
    if bilgi is not None and os.path.isfile(tm.MODEL_DOSYA_YOLU):
        gercek = dosya_ozeti(tm.MODEL_DOSYA_YOLU)
        if "model_sha256" not in bilgi:
            _atomik_json(tm.MODEL_BILGI_DOSYA_YOLU, {**bilgi, "model_sha256": gercek})
            sonuc["aktif"] = "muhurlendi"
        elif bilgi["model_sha256"] == gercek:
            sonuc["aktif"] = "zaten_muhurlu"
        else:
            sonuc["aktif"] = "uyusmuyor"
            sonuc["hatalar"].append("aktif model")
    surumler = tm._versiyonlari_oku()
    degisti = False
    for surum in surumler:
        dosya = tm._versiyon_dosyasi(surum)
        if not os.path.isfile(dosya):
            continue
        gercek = dosya_ozeti(dosya)
        if "model_sha256" not in surum:
            surum["model_sha256"] = gercek
            sonuc["surumler_muhurlendi"] += 1
            degisti = True
        elif surum["model_sha256"] != gercek:
            sonuc["hatalar"].append(surum["versiyon_id"])
    if degisti:
        _atomik_json(tm.MODEL_VERSIYONLARI_MANIFEST_YOLU, surumler)
    return sonuc
