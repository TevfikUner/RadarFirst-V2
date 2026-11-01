import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "docs" / "sunum" / "kaynak" / "komite_sunumu.html"
TARAYICI_ADAYLARI = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge",
    "google-chrome",
    "chromium",
]


def tarayici_bul():
    for aday in TARAYICI_ADAYLARI:
        if Path(aday).exists() or shutil.which(aday):
            return aday
    sys.exit("Edge/Chrome bulunamadı.")


def pdf_yaz(kaynak: Path, hedef: Path):
    with tempfile.TemporaryDirectory() as gecici:
        subprocess.run(
            [
                tarayici_bul(),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--user-data-dir={Path(gecici) / 'profil'}",
                f"--print-to-pdf={hedef.resolve()}",
                kaynak.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )


def main(argv=None):
    ayrac = argparse.ArgumentParser(description="Komite sunumunu HTML kaynağından PDF'e basar (Edge/Chrome).")
    ayrac.add_argument("--kaynak", type=Path, default=KAYNAK)
    ayrac.add_argument("--cikti", type=Path, default=KOK / "docs" / "sunum" / f"KOMITE_SUNUMU_{date.today()}.pdf")
    arg = ayrac.parse_args(argv)
    pdf_yaz(arg.kaynak, arg.cikti)
    print(arg.cikti)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
