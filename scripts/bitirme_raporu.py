import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
RAPOR = KOK / "docs" / "rapor"
HEDEF_MD = RAPOR / "BITIRME_RAPORU.md"
HEDEF_PDF = RAPOR / "BITIRME_RAPORU.pdf"

BASLIK = "Türbülans Radar: Gerçek Uçuş İzleri ve Reanaliz Verisiyle Seyir Türbülansı Riski ve Kaçınma Rotası"
KUNYE = "Tevfik Uner · Danışman: Arş. Gör. Dr. Fatih Titrek · Bilgisayar Mühendisliği, Konya Teknik Üniversitesi · 2026"
BOLUMLER = [
    ("GIRIS.md", "Giriş"),
    ("ILGILI_CALISMALAR.md", "İlgili Çalışmalar"),
    ("YONTEM.md", "Yöntem"),
    ("SONUCLAR.md", "Sonuçlar"),
    ("KATKILAR.md", "Katkılar"),
    ("SINIRLAMALAR_VE_DERSLER.md", "Sınırlamalar ve Öğrenilen Dersler"),
    ("GELECEK_CALISMA.md", "Sonuç ve Gelecek Çalışma"),
]
KALDIRILACAK = ("Bu bölüm bitirme raporuna doğrudan aktarılabilir. ",)

TARAYICI_ADAYLARI = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge",
    "google-chrome",
    "chromium",
]


def _oku(ad):
    return (RAPOR / ad).read_text(encoding="utf-8")


def bolum_ayir(metin, baslik):
    """'## baslik' bölümünü ve geri kalanı döndürür."""
    eslesme = re.search(rf"^## {re.escape(baslik)}\n(.*?)(?=^## |\Z)", metin, flags=re.M | re.S)
    if not eslesme:
        return "", metin
    return eslesme.group(1).strip(), metin[: eslesme.start()] + metin[eslesme.end() :]


def _kod_disi_satirlar(metin):
    kod = False
    for satir in metin.split("\n"):
        if satir.startswith("```"):
            kod = not kod
        yield satir, kod


def bolumu_numarala(metin, no, baslik):
    satirlar = []
    for satir, kod in _kod_disi_satirlar(metin):
        if not kod and satir.startswith("# "):
            satir = f"# {no}. {baslik}"
        elif not kod and (m := re.match(r"^(#{2,4}) (\d+(?:\.\d+)*)\.? (.*)$", satir)):
            satir = f"{m.group(1)} {no}.{m.group(2)} {m.group(3)}"
        satirlar.append(satir)
    metin = "\n".join(satirlar)
    for parca in KALDIRILACAK:
        metin = metin.replace(parca, "")
    return metin.strip()


def raporu_olustur() -> str:
    kaynakca, ilgili = bolum_ayir(_oku("ILGILI_CALISMALAR.md"), "Kaynakça")
    beyan, _ = bolum_ayir(_oku("ARAC_KULLANIMI_BEYANI.md"), "Paragraf")
    ozet = _oku("OZET.md").split("\n", 1)[1].strip()
    parcalar = [
        f"# {BASLIK}",
        KUNYE,
        "> Bu dosya `python scripts/bitirme_raporu.py` ile `docs/rapor/` altındaki bölüm dosyalarından üretilir; "
        "düzeltme bölüm dosyasında yapılır, sonra betik yeniden çalıştırılır.",
        "## Özet",
        ozet,
    ]
    for no, (ad, baslik) in enumerate(BOLUMLER, start=1):
        metin = ilgili if ad == "ILGILI_CALISMALAR.md" else _oku(ad)
        metin = bolumu_numarala(metin, no, baslik)
        if ad == "YONTEM.md":
            son = max(int(n) for n in re.findall(rf"^## {no}\.(\d+) ", metin, flags=re.M))
            metin += f"\n\n## {no}.{son + 1} Araç kullanımı beyanı\n\n{beyan}"
        parcalar.append(metin)
    parcalar += ["# Kaynakça", kaynakca]
    return "\n\n".join(parcalar) + "\n"


def _satir_ici(metin):
    parcalar = re.split(r"(\[[^\]]+\]\([^)\s]+\)|`[^`]+`)", metin)
    cikti = []
    for parca in parcalar:
        if parca.startswith("`") and parca.endswith("`") and len(parca) > 1:
            cikti.append(f"<code>{html.escape(parca[1:-1], quote=False)}</code>")
            continue
        if m := re.fullmatch(r"\[([^\]]+)\]\(([^)\s]+)\)", parca):
            cikti.append(f'<a href="{html.escape(m.group(2))}">{_satir_ici(m.group(1))}</a>')
            continue
        parca = html.escape(parca, quote=False)
        parca = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", parca)
        parca = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<i>\1</i>", parca)
        cikti.append(parca)
    return "".join(cikti)


def _tablo_hucreleri(satir):
    return [h.strip() for h in re.split(r"(?<!\\)\|", satir.strip().strip("|"))]


def md_html(metin) -> str:
    cikti, paragraf, liste = [], [], []
    satirlar = metin.split("\n")

    def paragrafi_bosalt():
        if paragraf:
            cikti.append(f"<p>{_satir_ici(' '.join(paragraf))}</p>")
            paragraf.clear()

    def listeyi_bosalt():
        if not liste:
            return
        derinlik = -1
        for seviye, sirali, oge in liste:
            etiket = "ol" if sirali else "ul"
            if seviye > derinlik:
                cikti.append(f"<{etiket}>" * (seviye - derinlik))
            elif seviye < derinlik:
                cikti.append("</li>" + f"</{etiket}></li>" * (derinlik - seviye))
            else:
                cikti.append("</li>")
            derinlik = seviye
            cikti.append(f"<li>{_satir_ici(oge)}")
        cikti.append("</li>" + "</ul>" * (derinlik + 1))
        liste.clear()

    i = 0
    while i < len(satirlar):
        satir = satirlar[i]
        if satir.startswith("```"):
            paragrafi_bosalt()
            listeyi_bosalt()
            j = i + 1
            while j < len(satirlar) and not satirlar[j].startswith("```"):
                j += 1
            cikti.append(f"<pre>{html.escape(chr(10).join(satirlar[i + 1 : j]), quote=False)}</pre>")
            i = j + 1
            continue
        if m := re.match(r"^(#{1,4}) (.*)$", satir):
            paragrafi_bosalt()
            listeyi_bosalt()
            seviye = len(m.group(1))
            cikti.append(f"<h{seviye}>{_satir_ici(m.group(2))}</h{seviye}>")
        elif satir.startswith("|") and i + 1 < len(satirlar) and re.match(r"^\|[\s:|-]+\|$", satirlar[i + 1]):
            paragrafi_bosalt()
            listeyi_bosalt()
            basliklar = _tablo_hucreleri(satir)
            cikti.append(
                "<table><thead><tr>" + "".join(f"<th>{_satir_ici(h)}</th>" for h in basliklar) + "</tr></thead><tbody>"
            )
            i += 2
            while i < len(satirlar) and satirlar[i].startswith("|"):
                hucreler = _tablo_hucreleri(satirlar[i])
                cikti.append("<tr>" + "".join(f"<td>{_satir_ici(h)}</td>" for h in hucreler) + "</tr>")
                i += 1
            cikti.append("</tbody></table>")
            continue
        elif m := re.match(r"^(\s*)([-*]|\d+\.) (.*)$", satir):
            paragrafi_bosalt()
            liste.append([len(m.group(1)) // 2, m.group(2)[0].isdigit(), m.group(3)])
        elif satir.startswith("> "):
            paragrafi_bosalt()
            listeyi_bosalt()
            cikti.append(f'<p class="not">{_satir_ici(satir[2:])}</p>')
        elif not satir.strip():
            paragrafi_bosalt()
            listeyi_bosalt()
        elif liste and satir.startswith("  "):
            liste[-1][2] += " " + satir.strip()
        else:
            listeyi_bosalt()
            paragraf.append(satir.strip())
        i += 1
    paragrafi_bosalt()
    listeyi_bosalt()
    return "\n".join(cikti)


STIL = """
@page { size: A4; margin: 18mm 18mm 16mm 18mm; }
body { font-family: 'Segoe UI', 'Calibri', sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1f2933; }
h1 { font-size: 17pt; color: #10243e; border-bottom: 2px solid #1d4e89; padding-bottom: 4px; margin-top: 22px;
  break-before: page; }
h1:first-of-type { break-before: auto; font-size: 20pt; }
h2 { font-size: 13pt; color: #1d4e89; margin: 16px 0 6px; break-after: avoid; }
h3 { font-size: 11.5pt; color: #1d4e89; margin: 12px 0 4px; break-after: avoid; }
h4 { font-size: 10.5pt; margin: 10px 0 4px; break-after: avoid; }
p { margin: 6px 0; text-align: justify; }
.not { font-size: 9pt; color: #616e7c; font-style: italic; }
table { border-collapse: collapse; width: 100%; font-size: 8.8pt; margin: 8px 0; break-inside: auto; }
th, td { border: 1px solid #c8d2dc; padding: 3px 5px; vertical-align: top; }
th { background: #eef2f7; }
tr { break-inside: avoid; }
pre { background: #f5f7fa; border: 1px solid #d9e2ec; padding: 6px 8px; font-size: 8pt; white-space: pre-wrap; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f1f5fa; padding: 0 2px; }
ul, ol { margin: 4px 0 6px; padding-left: 22px; }
li { margin: 2px 0; }
a { color: #1d4e89; text-decoration: none; }
"""


def belge_html(md_metni) -> str:
    return (
        f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{html.escape(BASLIK)}</title>'
        f"<style>{STIL}</style></head><body>{md_html(md_metni)}</body></html>"
    )


def tarayici_bul():
    for aday in TARAYICI_ADAYLARI:
        if Path(aday).exists() or shutil.which(aday):
            return aday
    sys.exit("Edge/Chrome bulunamadı.")


def pdf_yaz(html_metni, hedef):
    with tempfile.TemporaryDirectory() as gecici:
        kaynak = Path(gecici) / "rapor.html"
        kaynak.write_text(html_metni, encoding="utf-8")
        subprocess.run(
            [
                tarayici_bul(),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--user-data-dir={Path(gecici) / 'profil'}",
                f"--print-to-pdf={hedef}",
                kaynak.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )


def main(argv=None):
    ayrac = argparse.ArgumentParser(description="Bölüm dosyalarından bütünleşik bitirme raporu.")
    ayrac.add_argument("--kontrol", action="store_true", help="BITIRME_RAPORU.md güncel değilse 1 ile çık")
    ayrac.add_argument("--pdf", action="store_true", help="Ayrıca BITIRME_RAPORU.pdf üret (Edge/Chrome)")
    arg = ayrac.parse_args(argv)
    metin = raporu_olustur()
    if arg.kontrol:
        guncel = HEDEF_MD.exists() and HEDEF_MD.read_text(encoding="utf-8") == metin
        print("güncel" if guncel else "BITIRME_RAPORU.md eski: python scripts/bitirme_raporu.py")
        return 0 if guncel else 1
    HEDEF_MD.write_text(metin, encoding="utf-8", newline="\n")
    print(HEDEF_MD)
    if arg.pdf:
        pdf_yaz(belge_html(metin), HEDEF_PDF)
        print(HEDEF_PDF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
