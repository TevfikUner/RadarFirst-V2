"""
mcp_postgres_sunucusu.py
--------------------------
Bu projenin PostgreSQL veritabanına (Turbulence-db -- ucuslar, edr_olcumleri
tabloları) Claude Code/Claude Desktop üzerinden MCP protokolüyle SALT OKUNUR
erişim sağlayan yerel bir stdio sunucusu.

GÜVENLİK: Bağlantı bilgileri kimlik_dogrulama.py/veritabani.py ile AYNI
prensiple '.env' dosyasından okunur, bu dosyaya asla düz metin yazılmaz.
salt_okunur_sorgu_calistir() aracı, yalnızca tek bir SELECT ifadesine izin
verir -- INSERT/UPDATE/DELETE/DROP/ALTER gibi yazma ifadeleri kod
seviyesinde reddedilir; bu sunucu üzerinden veritabanı asla değiştirilemez.

Claude Code'a bağlamak için proje kökündeki .mcp.json zaten bu dosyayı
işaret ediyor -- ayrıca bir şey yapmana gerek yok, ilk bağlantıda Claude
Code onay isteyecek.

Bağlantı: '.env'de MCP_POSTGRES_USER/PASSWORD zorunludur (HOST/PORT
isteğe bağlı) ve POSTGRES_* yerine bunlar kullanılır. Eksikse, uygulama
kullanıcısıyla aynıysa ya da rol süper kullanıcıysa sunucu çalışmaz. Windows'ta yerel bir PostgreSQL 5432'yi tutuyorsa
Docker veritabanı 127.0.0.1:5433'ten okunur (MCP_POSTGRES_PORT=5433); salt
okunur rol (MCP_POSTGRES_USER) yazmayı veritabanı düzeyinde de engeller
(docs/KILAVUZ.md "Claude Code'dan veritabanına MCP ile bağlanmak").

Elle çalıştırmak/test etmek için:
    turbulans-mcp
"""

import os
import re
import sys

from mcp.server.mcpserver import MCPServer
from sqlalchemy import text

from turbulans_radar.depo.veritabani import motor_al, ucus_detayini_getir, ucuslari_listele

sunucu = MCPServer("turbulans-postgres")

_SATIR_LIMITI_TAVANI = 1000
_SORGU_ZAMAN_ASIMI_MS = 10_000

# Tek bir SELECT ifadesine izin verir; noktalı virgülle ikinci bir ifade
# eklenmesini veya yazma amaçlı anahtar kelimeleri reddeder.
_YAZMA_ANAHTAR_KELIMELERI = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|MERGE)\b",
    re.IGNORECASE,
)

_YASAK_FONKSIYONLAR = re.compile(
    r"\b(pg_\w+|lo_\w+|dblink\w*|set_config|current_setting|query_to_xml\w*|table_to_xml\w*|"
    r"cursor_to_xml\w*|database_to_xml\w*|schema_to_xml\w*)\s*\(",
    re.IGNORECASE,
)


def _salt_okunur_sorgu_dogrula(sql: str):
    temiz = sql.strip().rstrip(";").strip()
    if not temiz.lower().startswith("select"):
        raise ValueError("Sadece SELECT ile başlayan sorgulara izin verilir.")
    if ";" in temiz:
        raise ValueError("Tek bir SELECT ifadesi dışında (noktalı virgülle ayrılmış) ek ifadeye izin verilmez.")
    if _YAZMA_ANAHTAR_KELIMELERI.search(temiz):
        raise ValueError("Sorguda yazma amaçlı bir anahtar kelime tespit edildi, reddedildi.")
    if _YASAK_FONKSIYONLAR.search(temiz):
        raise ValueError("Sorguda sistem/yönetim fonksiyonu tespit edildi, reddedildi.")
    return temiz


_rol_dogrulandi = False


def _rol_dogrula(baglanti):
    global _rol_dogrulandi
    if _rol_dogrulandi:
        return
    yetkili = baglanti.execute(
        text("SELECT rolsuper OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if yetkili is not False:
        raise PermissionError("MCP rolü yetkili (süper kullanıcı/rol ya da DB oluşturabilir); sorgu reddedildi.")
    _rol_dogrulandi = True


def _denetimli_motor():
    motor = motor_al()
    if not _rol_dogrulandi:
        with motor.connect() as baglanti:
            _rol_dogrula(baglanti)
    return motor


@sunucu.tool()
def tablolari_listele() -> list[str]:
    """Veritabanındaki (public şema) tablo adlarını döndürür."""
    motor = _denetimli_motor()
    with motor.connect() as baglanti:
        sonuc = baglanti.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        )
        return [satir[0] for satir in sonuc]


@sunucu.tool()
def ucuslar_listesi(limit: int = 100) -> list[dict]:
    """Veritabanına kaydedilmiş uçuşları (en yeni önce) listeler."""
    _denetimli_motor()
    return ucuslari_listele(limit=min(limit, _SATIR_LIMITI_TAVANI))


@sunucu.tool()
def ucus_detayi(ucus_numarasi: str, tarih: str) -> dict:
    """Belirli bir uçuş/tarih için uçuş bilgisini ve tüm EDR/TI1 ölçüm noktalarını döndürür.

    tarih: 'YYYY-MM-DD' formatında.
    """
    _denetimli_motor()
    detay = ucus_detayini_getir(ucus_numarasi, tarih)
    if detay is None:
        return {"hata": f"'{ucus_numarasi}' / {tarih} için kayıt bulunamadı."}
    return detay


@sunucu.tool()
def salt_okunur_sorgu_calistir(sql: str, limit: int = 200) -> list[dict]:
    """Veritabanında SADECE bir SELECT sorgusu çalıştırır (yazma işlemleri reddedilir).

    limit, döndürülecek en fazla satır sayısıdır (en fazla 1000).
    """
    temiz_sql = _salt_okunur_sorgu_dogrula(sql)
    limit = max(1, min(limit, _SATIR_LIMITI_TAVANI))

    motor = _denetimli_motor()
    with motor.connect() as baglanti:
        baglanti = baglanti.execution_options(postgresql_readonly=True)
        baglanti.execute(text(f"SET LOCAL statement_timeout = {_SORGU_ZAMAN_ASIMI_MS}"))
        sonuc = baglanti.execute(text(f"SELECT * FROM ({temiz_sql}) AS alt_sorgu LIMIT {limit}"))
        return [dict(satir._mapping) for satir in sonuc]


_MCP_ORTAM_ESLEMESI = {
    "MCP_POSTGRES_HOST": "POSTGRES_HOST",
    "MCP_POSTGRES_PORT": "POSTGRES_PORT",
    "MCP_POSTGRES_USER": "POSTGRES_USER",
    "MCP_POSTGRES_PASSWORD": "POSTGRES_PASSWORD",
}


_ZORUNLU_MCP_AYARLARI = ("MCP_POSTGRES_USER", "MCP_POSTGRES_PASSWORD")


def mcp_baglanti_ayarlarini_uygula(ortam=None) -> list[str]:
    """Dolu MCP_POSTGRES_* değerlerini POSTGRES_* üzerine yazar; uygulananları döner.

    MCP kullanıcısı/şifresi boşsa ya da kullanıcı uygulamanınkiyle aynıysa ValueError.
    """
    ortam = os.environ if ortam is None else ortam
    eksik = [ad for ad in _ZORUNLU_MCP_AYARLARI if not ortam.get(ad)]
    if eksik:
        raise ValueError(f"{', '.join(eksik)} tanımlı değil; MCP sunucusu salt okunur rol olmadan başlamaz.")
    if ortam["MCP_POSTGRES_USER"] in {ortam.get("POSTGRES_USER"), ortam.get("UYGULAMA_POSTGRES_USER"), "postgres"}:
        raise ValueError("MCP_POSTGRES_USER uygulama/süper kullanıcıyla aynı olamaz; salt okunur rol kullanın.")
    uygulanan = []
    for kaynak, hedef in _MCP_ORTAM_ESLEMESI.items():
        if ortam.get(kaynak):
            ortam[hedef] = ortam[kaynak]
            uygulanan.append(hedef)
    return uygulanan


def ana():
    try:
        mcp_baglanti_ayarlarini_uygula()
    except ValueError as hata:
        sys.exit(f"turbulans-mcp başlatılmadı: {hata} (docs/KILAVUZ.md: MCP ile bağlanmak)")
    sunucu.run()


if __name__ == "__main__":
    ana()
