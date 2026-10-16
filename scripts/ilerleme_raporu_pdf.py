import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "docs" / "rapor" / "ILERLEME_RAPORU.md"
TAM_PDF = KOK / "docs" / "rapor" / "ILERLEME_RAPORU.pdf"
SON_HAFTA_PDF = KOK / "docs" / "rapor" / "ILERLEME_RAPORU_SON_HAFTA.pdf"

TARAYICI_ADAYLARI = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge",
    "google-chrome",
    "chromium",
]

STIL = """
@page { size: A4; margin: 12mm 16mm 12mm 16mm;
  @bottom-center { content: counter(page) " / " counter(pages); font: 9pt 'Segoe UI', sans-serif; color: #7a8696; } }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', 'Calibri', sans-serif; font-size: 9.8pt; line-height: 1.36; color: #1f2933; margin: 0; }
.kapak { border-bottom: 3px solid #1d4e89; padding-bottom: 10px; margin-bottom: 14px; }
.ust-baslik { font-size: 9pt; letter-spacing: .12em; text-transform: uppercase; color: #1d4e89; font-weight: 600; }
h1 { font-size: 21pt; margin: 2px 0 8px; color: #10243e; }
.kunye { display: grid; grid-template-columns: auto 1fr; gap: 2px 12px; font-size: 10pt; }
.kunye b { color: #52606d; font-weight: 600; }
.ozet { background: #f1f5fa; border-left: 4px solid #1d4e89; padding: 8px 12px; margin: 10px 0; border-radius: 0 4px 4px 0; }
.not { font-size: 9pt; color: #616e7c; font-style: italic; margin: 6px 0 4px; }
.hafta { margin-top: 14px; }
.hafta + .hafta { break-before: auto; }
h2 { display: flex; align-items: baseline; gap: 10px; background: #1d4e89; color: #fff; font-size: 12.5pt;
  padding: 7px 12px; border-radius: 4px; margin: 0 0 8px; break-after: avoid; }
h2 .tarih { font-weight: 400; font-size: 10.5pt; opacity: .9; }
h3 { font-size: 11pt; color: #1d4e89; margin: 10px 0 3px; padding-bottom: 2px; border-bottom: 1px solid #d9e2ec; break-after: avoid; }
ul { margin: 4px 0 6px; padding-left: 20px; }
ul ul { margin: 2px 0; }
li { margin: 1px 0; break-inside: avoid; }
p { margin: 6px 0; }
"""


def satir_ici(metin):
    metin = html.escape(metin, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", metin)


def liste_html(ogeler):
    cikti, derinlik = [], -1
    for seviye, metin in ogeler:
        if seviye > derinlik:
            cikti.append("<ul>" * (seviye - derinlik))
        elif seviye < derinlik:
            cikti.append("</li>" + "</ul></li>" * (derinlik - seviye))
        else:
            cikti.append("</li>")
        cikti.append(f"<li>{satir_ici(metin)}")
        derinlik = seviye
    cikti.append("</li>" + "</ul></li>" * derinlik + "</ul>")
    return "".join(cikti)


def govde_html(satirlar):
    parcalar, ogeler, paragraf = [], [], []

    def bosalt():
        if ogeler:
            parcalar.append(liste_html(ogeler))
            ogeler.clear()
        if paragraf:
            parcalar.append(f"<p>{satir_ici(' '.join(paragraf))}</p>")
            paragraf.clear()

    for satir in satirlar:
        duz = satir.strip()
        madde = re.match(r"^(\s*)- (.*)$", satir)
        if not duz:
            bosalt()
        elif madde:
            if paragraf:
                bosalt()
            ogeler.append((len(madde.group(1)) // 2, madde.group(2)))
        elif ogeler and satir.startswith(" "):
            seviye, metin = ogeler[-1]
            ogeler[-1] = (seviye, f"{metin} {duz}")
        elif re.fullmatch(r"\*\*[^*]+\*\*", duz):
            bosalt()
            parcalar.append(f"<h3>{html.escape(duz.strip('*'))}</h3>")
        else:
            paragraf.append(duz)
    bosalt()
    return "".join(parcalar)


def kapak_html(blok):
    satirlar = blok.splitlines()
    baslik = next(s[2:] for s in satirlar if s.startswith("# "))
    kunye, ozet, notlar = [], [], []
    for satir in satirlar:
        k = re.match(r"^\*\*(.+?):\*\*\s*(.*?)\s*$", satir)
        if k:
            kunye.append(f"<b>{html.escape(k.group(1))}</b><span>{satir_ici(k.group(2))}</span>")
        elif satir.startswith(">"):
            notlar.append(satir.lstrip("> ").strip())
        elif satir.startswith("**Proje kısaca.**"):
            ozet.append(satir.replace("**Proje kısaca.**", "").strip())
        elif ozet and satir.strip() and not satir.startswith("#"):
            ozet.append(satir.strip())
    proje, _, alt = baslik.partition("—")
    return (
        f'<div class="kapak"><div class="ust-baslik">{html.escape(proje.strip())}</div>'
        f"<h1>{html.escape(alt.strip() or proje.strip())}</h1>"
        f'<div class="kunye">{"".join(kunye)}</div></div>'
        f'<div class="ozet"><b>Proje kısaca.</b> {satir_ici(" ".join(ozet))}</div>'
        + (f'<p class="not">{satir_ici(" ".join(notlar))}</p>' if notlar else "")
    )


def hafta_html(blok):
    satirlar = blok.strip().splitlines()
    baslik = satirlar[0][3:]
    ad, _, tarih = baslik.partition("—")
    return (
        f'<section class="hafta"><h2>{html.escape(ad.strip())}'
        f'<span class="tarih">{html.escape(tarih.strip())}</span></h2>'
        f"{govde_html(satirlar[1:])}</section>"
    )


def belge_html(kapak, haftalar, baslik):
    return (
        '<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        f"<title>{html.escape(baslik)}</title><style>{STIL}</style></head><body>"
        f"{kapak}{''.join(haftalar)}</body></html>"
    )


def tarayici_bul():
    for aday in TARAYICI_ADAYLARI:
        if Path(aday).exists() or shutil.which(aday):
            return aday
    sys.exit("Edge/Chrome bulunamadı.")


def pdf_yaz(tarayici, html_metni, hedef, gecici):
    kaynak = Path(gecici) / f"{hedef.stem}.html"
    kaynak.write_text(html_metni, encoding="utf-8")
    subprocess.run(
        [
            tarayici,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={Path(gecici) / 'profil'}",
            f"--print-to-pdf={hedef}",
            kaynak.as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    print(hedef)


def main():
    bloklar = re.split(r"\n---\n", KAYNAK.read_text(encoding="utf-8"))
    kapak = kapak_html(bloklar[0])
    haftalar = [hafta_html(b) for b in bloklar[1:] if b.strip().startswith("## ")]
    tarayici = tarayici_bul()
    with tempfile.TemporaryDirectory() as gecici:
        pdf_yaz(tarayici, belge_html(kapak, haftalar, "Proje İlerleme Raporu"), TAM_PDF, gecici)
        pdf_yaz(tarayici, belge_html(kapak, haftalar[-1:], "Proje İlerleme Raporu — Son Hafta"), SON_HAFTA_PDF, gecici)


if __name__ == "__main__":
    main()
