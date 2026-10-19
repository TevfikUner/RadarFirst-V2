"""AIRAC döngüsü bitince ATS ağını ve ENR 5.1 sahalarını DHMİ'den yeniler (komite O-3).

    python -m turbulans_radar.cli.airac_yenile            (döngü bitmediyse hiçbir şey yapmaz)
    python -m turbulans_radar.cli.airac_yenile --zorla

Döngü başına DHMİ'ye 4 istek (ENR 1.3, 4.1, 4.4, 5.1), günde en fazla bir deneme. FRA saat ve
seviyeleri ENR 1.3 §5.1.1 cümlesinden okunur; cümle bulunamazsa eski ağ korunur. ENR 5.1
veritabanına yalnız günün yedeği varsa aktarılır.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import UTC, date, datetime
from pathlib import Path

DHMI = "https://www.dhmi.gov.tr/AIPDocuments/"
BELGELER = ("LT_ENR_1_3_en.pdf", "LT_ENR_4_4_en.pdf", "LT_ENR_4_1_en.pdf", "LT_ENR_5_1_en.pdf")
ISTEKLER_ARASI_SANIYE = 5.0
YAYIM_BEKLEME_GUN = 2
_FRA_CUMLESI = re.compile(
    r"FRATURK is available in .{0,80}? from FL\s*(\d{3}) to FL\s*(\d{3})"
    r"(?: within the time period (\d{2}:\d{2}\s*-\s*\d{2}:\d{2}) UTC)?",
    re.DOTALL,
)


class AiracYenilemeHatasi(RuntimeError):
    pass


def _bitis(yol: Path) -> date | None:
    if not yol.is_file():
        return None
    deger = json.loads(yol.read_text(encoding="utf-8")).get("airac_bitis")
    return date.fromisoformat(deger) if deger else None


def yenileme_gerekli_mi(klasor: Path, bugun: date) -> bool:
    bitisler = [_bitis(klasor / "ats_agi.json"), _bitis(klasor / "aip_enr51.geojson")]
    return any(b is None or b <= bugun for b in bitisler)


def fra_parametreleri(enr13_metni: str) -> dict:
    eslesme = _FRA_CUMLESI.search(" ".join(enr13_metni.split()))
    if not eslesme:
        raise AiracYenilemeHatasi("ENR 1.3 §5.1.1 FRA cümlesi bulunamadı; FRA kuralları elle kontrol edilmeli.")
    alt, ust, saatler = eslesme.groups()
    return {"alt_fl": alt, "ust_fl": ust, "fra_saatleri": (saatler or "").replace(" ", "")}


def _sha(yol: Path) -> str | None:
    return hashlib.sha256(yol.read_bytes()).hexdigest() if yol.is_file() else None


def _durumu_oku(yol: Path) -> dict:
    return json.loads(yol.read_text(encoding="utf-8")) if yol.is_file() else {}


def _varsayilan_indirici(hedef: Path, url: str) -> None:
    from turbulans_radar.cli.aip_ats_agi import indir

    indir(str(hedef), url)


def _varsayilan_aktarici(kok: Path) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "turbulans_radar.veri.kisitli_saha_saglayici",
            "ice-aktar",
            "/app/ats_verisi/aip_enr51.geojson",
            "--kaynak",
            "aip_enr51",
            "--eskileri-kaldir",
        ],
        cwd=kok,
        check=True,
    )


def _saha_sayisi(yol: Path) -> int:
    return len(json.loads(yol.read_text(encoding="utf-8"))["features"]) if yol.is_file() else 0


def _indir_ve_ayristir(klasor: Path, yeni: Path, bugun: date, indirici, bekle) -> dict:
    from turbulans_radar.cli import aip_ats_agi, aip_enr51

    for sira, belge in enumerate(BELGELER):
        if sira:
            bekle(ISTEKLER_ARASI_SANIYE)
        indirici(yeni / belge, DHMI + belge)
    eski_bitis = _bitis(klasor / "aip_enr51.geojson")
    if (
        eski_bitis
        and (bugun - eski_bitis).days < YAYIM_BEKLEME_GUN
        and all(_sha(klasor / "kaynak" / b) == _sha(yeni / b) for b in BELGELER)
    ):
        raise AiracYenilemeHatasi(
            "Dört belge de değişmedi; DHMİ yeni döngüyü henüz yayımlamamış olabilir, yarın denenecek."
        )
    fra = fra_parametreleri(aip_ats_agi.pdf_metni(str(yeni / BELGELER[0])))
    aip_ats_agi.ana(
        [
            "--enr44", str(yeni / "LT_ENR_4_4_en.pdf"),
            "--enr41", str(yeni / "LT_ENR_4_1_en.pdf"),
            "--cikti", str(yeni / "ats_agi.json"),
            "--alt-fl", fra["alt_fl"],
            "--ust-fl", fra["ust_fl"],
            "--fra-saatleri", fra["fra_saatleri"],
        ]
    )  # fmt: skip
    aip_enr51.ana(["--enr51", str(yeni / "LT_ENR_5_1_en.pdf"), "--cikti", str(yeni / "aip_enr51.geojson")])
    eski_saha, yeni_saha = _saha_sayisi(klasor / "aip_enr51.geojson"), _saha_sayisi(yeni / "aip_enr51.geojson")
    if yeni_saha < 0.8 * eski_saha:
        raise AiracYenilemeHatasi(f"ENR 5.1 saha sayısı {eski_saha} → {yeni_saha}; eski veri korundu.")
    if yenileme_gerekli_mi(yeni, bugun):
        raise AiracYenilemeHatasi("Yeni dosyaların AIRAC bitişi bugünden sonra değil; eski veri korundu.")
    return fra


def _yerine_koy(klasor: Path, yeni: Path, bugun: date) -> list[str]:
    kaynak = klasor / "kaynak"
    onceki = klasor / "onceki" / f"{bugun:%Y%m%d}"
    onceki.mkdir(parents=True, exist_ok=True)
    kaynak.mkdir(exist_ok=True)
    degismeyen = [b for b in BELGELER if _sha(kaynak / b) == _sha(yeni / b)]
    for ad, eski_klasor in [*((b, kaynak) for b in BELGELER), ("ats_agi.json", klasor), ("aip_enr51.geojson", klasor)]:
        if (eski_klasor / ad).is_file():
            shutil.copy2(eski_klasor / ad, onceki / ad)
        (yeni / ad).replace(eski_klasor / ad)
    return degismeyen


def yenile(
    kok: Path,
    bugun: date,
    zorla: bool = False,
    indirici=_varsayilan_indirici,
    aktarici=_varsayilan_aktarici,
    bekle=time.sleep,
) -> dict:
    klasor = kok / "ats_verisi"
    durum_yolu = klasor / ".airac_durum.json"
    durum = _durumu_oku(durum_yolu)
    gerekli = yenileme_gerekli_mi(klasor, bugun) or zorla
    if not gerekli and durum.get("db_aktarildi", True):
        return {"sonuc": "guncel"}
    if gerekli and durum.get("son_deneme") == bugun.isoformat() and not zorla:
        return {"sonuc": "bugun_denendi"}

    if gerekli:
        durum = {"son_deneme": bugun.isoformat(), "db_aktarildi": False}
        durum_yolu.write_text(json.dumps(durum), encoding="utf-8")
        yeni = klasor / f"yeni_{bugun:%Y%m%d}"
        yeni.mkdir(parents=True, exist_ok=True)
        try:
            fra = _indir_ve_ayristir(klasor, yeni, bugun, indirici, bekle)
            degismeyen = _yerine_koy(klasor, yeni, bugun)
        finally:
            shutil.rmtree(yeni, ignore_errors=True)
        durum.update(fra=fra, degismeyen_belgeler=degismeyen, airac_bitis=str(_bitis(klasor / "ats_agi.json")))

    if (kok / "db_yedekleri" / f"turbulans_{bugun:%Y%m%d}.dump").is_file():
        aktarici(kok)
        durum["db_aktarildi"] = True
    durum_yolu.write_text(json.dumps(durum, ensure_ascii=False), encoding="utf-8")
    return {"sonuc": "yenilendi" if gerekli else "db_aktarimi", **durum}


def ana(argv=None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--kok", default=".", help="Depo kökü (ats_verisi/ ve db_yedekleri/ burada).")
    ayristirici.add_argument("--zorla", action="store_true", help="Döngü bitmemiş olsa da yenile.")
    a = ayristirici.parse_args(argv)
    zaman = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        sonuc = yenile(Path(a.kok).resolve(), datetime.now(UTC).date(), a.zorla)
    except Exception as hata:
        print(f"{zaman} AIRAC yenileme BAŞARISIZ: {hata}")
        return 1
    print(f"{zaman} AIRAC: {json.dumps(sonuc, ensure_ascii=False)}")
    if sonuc["sonuc"] == "yenilendi" and not sonuc.get("db_aktarildi"):
        print(f"{zaman} UYARI: günün yedeği yok, ENR 5.1 veritabanına aktarılmadı; yedekten sonra yeniden çalışır.")
    return 0


if __name__ == "__main__":
    raise SystemExit(ana())
