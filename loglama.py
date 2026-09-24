"""
loglama.py
------------
Proje genelinde tek bir logging yapılandırması.

print() yerine logging kullanmanın faydası: seviye filtreleme (LOG_SEVIYESI
ortam değişkeniyle), her mesajın hangi modülden geldiğinin görünmesi ve
gerekirse (LOG_DOSYASI ile) dosyaya da yazılabilmesi -- sürekli çalışan
api_servisi.py gibi bir süreç için (konsolu izlemek pratik değil) bu
özellikle değerlidir.

BİLİNÇLİ SINIR: main.py/toplu_analiz.py/web_arayuzu.py gibi CLI/UI
script'lerinin adım adım ilerleme mesajları ve özet tabloları BİLEREK
print() olarak kalıyor -- bunlar loglanacak bir "olay" değil, aracın
doğrudan ÜRETTİĞİ, insan için tasarlanmış çıktıdır (web_arayuzu.py bu
çıktıyı stdout'tan yakalayıp arayüzde gösteriyor). logging'e taşınan yer,
sürekli çalışan api_servisi.py sürecinin KENDİ tanı/hata mesajlarıdır.

Ayrıca: stream BİLEREK stderr'dir, stdout DEĞİL -- gelecekte bu modülü
kullanabilecek bir MCP stdio sunucusunda (bkz. mcp_postgres_sunucusu.py)
stdout, JSON-RPC protokolü için ayrılmıştır; oraya print/log karışması
protokolü bozar. stderr + gerçek program çıktısının stdout'ta kalması,
standart Unix pratiğiyle de uyumludur.
"""

import logging
import os
import sys


def ayarla():
    """Kök logger'ı bir kez yapılandırır (tekrar çağrılırsa no-op)."""
    if logging.getLogger().handlers:
        return

    seviye_adi = os.environ.get("LOG_SEVIYESI", "INFO").upper()
    seviye = getattr(logging, seviye_adi, logging.INFO)

    logging.basicConfig(
        level=seviye,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    dosya_yolu = os.environ.get("LOG_DOSYASI")
    if dosya_yolu:
        dosya_handler = logging.FileHandler(dosya_yolu, encoding="utf-8")
        dosya_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(dosya_handler)


def logger_al(isim):
    return logging.getLogger(isim)
