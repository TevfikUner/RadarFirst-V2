"""Komite Y-1: ARAC_KULLANIMI_BEYANI sayımlarını güncel git'ten üretir ve beyandakilerle karşılaştırır.

~/.venvs/turbulans/bin/python scripts/beyan_sayimlari.py           # sayımları yazdır
~/.venvs/turbulans/bin/python scripts/beyan_sayimlari.py --kontrol # beyandan farklıysa çıkış kodu 1
"""

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
BEYAN = KOK / "docs/rapor/ARAC_KULLANIMI_BEYANI.md"
ISARETSIZ_ILK_COMMITLER = ("8bbdaa5", "aa1e7d9")
IMZA = re.compile(r"Co-Authored-By: (Claude[^<]*?)\s*<", re.IGNORECASE)


def _git(*arguman: str) -> str:
    return subprocess.run(["git", *arguman], cwd=KOK, capture_output=True, text=True, check=True).stdout


def commit_sayimlari() -> dict:
    mesajlar = _git("log", "--no-merges", "--format=%H%x00%B%x1e").split("\x1e")
    mesajlar = [m for m in mesajlar if m.strip()]
    modeller = Counter()
    isaretli = 0
    for mesaj in mesajlar:
        bulunan = IMZA.findall(mesaj)
        if bulunan:
            isaretli += 1
            modeller[bulunan[0].strip()] += 1
    return {"commit": len(mesajlar), "isaretli": isaretli, "modeller": dict(modeller.most_common())}


def kalan_satirlar() -> tuple[int, int]:
    dosyalar = [d for d in _git("ls-files", "src", "tests").splitlines() if d.endswith(".py")]
    toplam = kalan = 0
    for dosya in dosyalar:
        for satir in _git("blame", "-w", "--line-porcelain", "--", dosya).splitlines():
            if re.match(r"^[0-9a-f]{40} ", satir):
                toplam += 1
                kalan += satir.startswith(ISARETSIZ_ILK_COMMITLER)
    return kalan, toplam


def test_sayisi() -> int:
    cikti = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=KOK,
        capture_output=True,
        text=True,
    ).stdout
    eslesme = re.search(r"(\d+)(?:/\d+)? tests? collected", cikti)
    return int(eslesme.group(1)) if eslesme else sum(1 for s in cikti.splitlines() if "::" in s)


def _binlik(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def sayimlar() -> dict:
    kalan, toplam = kalan_satirlar()
    return {**commit_sayimlari(), "kalan": kalan, "toplam_satir": toplam, "test": test_sayisi()}


def beyandaki_sayimlar(metin: str) -> dict:
    tek = " ".join(metin.split())
    commit = re.search(r"birleştirme dışı (\d+) commit'in (\d+)'", tek)
    satir = re.search(r"\(([\d.]+) satırın ([\d.]+)'", tek)
    test = re.search(r"\(\S+ ([\d.]+) test\)", tek)
    return {
        "commit": int(commit.group(1)) if commit else None,
        "isaretli": int(commit.group(2)) if commit else None,
        "toplam_satir": int(satir.group(1).replace(".", "")) if satir else None,
        "kalan": int(satir.group(2).replace(".", "")) if satir else None,
        "test": int(test.group(1).replace(".", "")) if test else None,
    }


def main(argv=None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--kontrol", action="store_true")
    a = ayristirici.parse_args(argv)
    s = sayimlar()
    print(f"Commit (birleştirme dışı): {s['commit']}, işaretli: {s['isaretli']}")
    print("Model dağılımı: " + ", ".join(f"{m} {n}" for m, n in s["modeller"].items()))
    oran = f"{100 * s['kalan'] / s['toplam_satir']:.1f}".replace(".", ",")
    print(f"Kalan satır: {_binlik(s['kalan'])} / {_binlik(s['toplam_satir'])} (%{oran})")
    print(f"Test: {_binlik(s['test'])}")
    if not a.kontrol:
        return 0
    beyan = beyandaki_sayimlar(BEYAN.read_text(encoding="utf-8"))
    farklar = [f"{k}: beyan {beyan[k]}, git {s[k]}" for k in beyan if beyan[k] != s[k]]
    print("\n".join(["Beyan güncel değil:", *farklar]) if farklar else "Beyan güncel.")
    return 1 if farklar else 0


if __name__ == "__main__":
    sys.exit(main())
