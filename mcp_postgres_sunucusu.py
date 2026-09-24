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

Elle çalıştırmak/test etmek için:
    python mcp_postgres_sunucusu.py
"""

import re

from mcp.server.mcpserver import MCPServer
from sqlalchemy import text

from veritabani import motor_al, ucus_detayini_getir, ucuslari_listele

sunucu = MCPServer("turbulans-postgres")

_SATIR_LIMITI_TAVANI = 1000

# Tek bir SELECT ifadesine izin verir; noktalı virgülle ikinci bir ifade
# eklenmesini veya yazma amaçlı anahtar kelimeleri reddeder.
_YAZMA_ANAHTAR_KELIMELERI = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|MERGE)\b",
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
    return temiz


@sunucu.tool()
def tablolari_listele() -> list[str]:
    """Veritabanındaki (public şema) tablo adlarını döndürür."""
    motor = motor_al()
    with motor.connect() as baglanti:
        sonuc = baglanti.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        )
        return [satir[0] for satir in sonuc]


@sunucu.tool()
def ucuslar_listesi(limit: int = 100) -> list[dict]:
    """Veritabanına kaydedilmiş uçuşları (en yeni önce) listeler."""
    return ucuslari_listele(limit=min(limit, _SATIR_LIMITI_TAVANI))


@sunucu.tool()
def ucus_detayi(ucus_numarasi: str, tarih: str) -> dict:
    """Belirli bir uçuş/tarih için uçuş bilgisini ve tüm EDR/TI1 ölçüm noktalarını döndürür.

    tarih: 'YYYY-MM-DD' formatında.
    """
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

    motor = motor_al()
    with motor.connect() as baglanti:
        baglanti = baglanti.execution_options(postgresql_readonly=True)
        sonuc = baglanti.execute(text(f"SELECT * FROM ({temiz_sql}) AS alt_sorgu LIMIT {limit}"))
        return [dict(satir._mapping) for satir in sonuc]


if __name__ == "__main__":
    sunucu.run()
