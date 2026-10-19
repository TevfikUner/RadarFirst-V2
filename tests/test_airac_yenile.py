import json
from datetime import date

import pytest

from turbulans_radar.cli import aip_ats_agi, aip_enr51
from turbulans_radar.cli.airac_yenile import BELGELER, AiracYenilemeHatasi, fra_parametreleri, yenile

BUGUN = date(2026, 10, 29)
ENR13 = "5.1.1 FRATURK is available in Ankara FIR and Istanbul FIR from FL305 to FL660 within the time period 20:00-02:00 UTC."


def _yaz(yol, bitis, saha=85, isaret="eski"):
    yol.write_text(
        json.dumps({"airac_bitis": bitis, "isaret": isaret, "features": [{}] * saha}),
        encoding="utf-8",
    )


@pytest.fixture
def depo(tmp_path, monkeypatch):
    klasor = tmp_path / "ats_verisi"
    (klasor / "kaynak").mkdir(parents=True)
    _yaz(klasor / "ats_agi.json", "2026-10-29")
    _yaz(klasor / "aip_enr51.geojson", "2026-10-29")
    for belge in BELGELER:
        (klasor / "kaynak" / belge).write_bytes(b"%PDF eski " + belge.encode())
    ayar = {"saha": 86, "bitis": "2026-11-26", "enr13": ENR13, "argumanlar": []}

    def ats(argv):
        ayar["argumanlar"] = argv
        _yaz(tmp_path / argv[argv.index("--cikti") + 1], ayar["bitis"], isaret="yeni")

    def enr51(argv):
        _yaz(tmp_path / argv[argv.index("--cikti") + 1], ayar["bitis"], ayar["saha"], isaret="yeni")

    monkeypatch.setattr(aip_ats_agi, "ana", ats)
    monkeypatch.setattr(aip_enr51, "ana", enr51)
    monkeypatch.setattr(aip_ats_agi, "pdf_metni", lambda yol: ayar["enr13"])
    return tmp_path, ayar


class Sayac:
    def __init__(self):
        self.indirilen, self.aktarim, self.bekleme = [], 0, 0

    def indir(self, hedef, url):
        self.indirilen.append(url)
        hedef.write_bytes(b"%PDF yeni " + hedef.name.encode())

    def aktar(self, kok):
        self.aktarim += 1

    def bekle(self, saniye):
        self.bekleme += 1


def _calistir(kok, sayac, bugun=BUGUN, zorla=False):
    return yenile(kok, bugun, zorla, indirici=sayac.indir, aktarici=sayac.aktar, bekle=sayac.bekle)


def _isaret(yol):
    return json.loads(yol.read_text(encoding="utf-8"))["isaret"]


def test_fra_cumlesi_ayristirilir_ve_yoksa_hata_verir():
    assert fra_parametreleri(ENR13) == {"alt_fl": "305", "ust_fl": "660", "fra_saatleri": "20:00-02:00"}
    h24 = "FRATURK is available in Ankara FIR and Istanbul FIR from FL305 to FL660."
    assert fra_parametreleri(h24)["fra_saatleri"] == ""
    with pytest.raises(AiracYenilemeHatasi):
        fra_parametreleri("FRATURK is available H24.")


def test_dongu_bitmediyse_hicbir_istek_atilmaz(depo):
    kok, _ = depo
    sayac = Sayac()
    assert _calistir(kok, sayac, bugun=date(2026, 10, 28))["sonuc"] == "guncel"
    assert sayac.indirilen == []


def test_dongu_bitince_yenilenir_eskisi_saklanir_ve_db_yedek_varsa_aktarilir(depo):
    kok, ayar = depo
    (kok / "db_yedekleri").mkdir()
    (kok / "db_yedekleri" / "turbulans_20261029.dump").write_bytes(b"")
    sayac = Sayac()
    sonuc = _calistir(kok, sayac)
    klasor = kok / "ats_verisi"
    assert sonuc["sonuc"] == "yenilendi" and sonuc["db_aktarildi"] and sonuc["airac_bitis"] == "2026-11-26"
    assert len(sayac.indirilen) == 4 and sayac.bekleme == 3 and sayac.aktarim == 1
    assert ayar["argumanlar"][-6:] == ["--alt-fl", "305", "--ust-fl", "660", "--fra-saatleri", "20:00-02:00"]
    assert _isaret(klasor / "ats_agi.json") == "yeni" and _isaret(klasor / "aip_enr51.geojson") == "yeni"
    assert _isaret(klasor / "onceki/20261029/ats_agi.json") == "eski"
    assert (klasor / "kaynak/LT_ENR_1_3_en.pdf").read_bytes().startswith(b"%PDF yeni")
    assert (klasor / "onceki/20261029/LT_ENR_1_3_en.pdf").read_bytes().startswith(b"%PDF eski")
    assert not (klasor / "yeni_20261029").exists()
    assert _calistir(kok, sayac)["sonuc"] == "guncel" and len(sayac.indirilen) == 4


def test_saha_sayisi_dusunce_eski_veri_korunur_ve_ayni_gun_tekrar_denenmez(depo):
    kok, ayar = depo
    ayar["saha"] = 10
    sayac = Sayac()
    with pytest.raises(AiracYenilemeHatasi):
        _calistir(kok, sayac)
    klasor = kok / "ats_verisi"
    assert _isaret(klasor / "aip_enr51.geojson") == "eski" and _isaret(klasor / "ats_agi.json") == "eski"
    assert not (klasor / "yeni_20261029").exists()
    assert _calistir(kok, sayac)["sonuc"] == "bugun_denendi" and len(sayac.indirilen) == 4


def test_belgeler_degismediyse_iki_gun_beklenir_sonra_kabul_edilir(depo):
    kok, _ = depo

    class AyniBelge(Sayac):
        def indir(self, hedef, url):
            self.indirilen.append(url)
            hedef.write_bytes((kok / "ats_verisi/kaynak" / hedef.name).read_bytes())

    sayac = AyniBelge()
    with pytest.raises(AiracYenilemeHatasi, match="değişmedi"):
        _calistir(kok, sayac)
    assert _isaret(kok / "ats_verisi/ats_agi.json") == "eski"
    sonuc = _calistir(kok, sayac, bugun=date(2026, 10, 31))
    assert sonuc["sonuc"] == "yenilendi" and len(sonuc["degismeyen_belgeler"]) == 4


def test_fra_cumlesi_yoksa_ag_degismez(depo):
    kok, ayar = depo
    ayar["enr13"] = "FRA H24"
    with pytest.raises(AiracYenilemeHatasi):
        _calistir(kok, Sayac())
    assert _isaret(kok / "ats_verisi/ats_agi.json") == "eski"


def test_yedek_yoksa_db_aktarimi_ertelenir_ve_sonra_indirmeden_yapilir(depo):
    kok, _ = depo
    sayac = Sayac()
    sonuc = _calistir(kok, sayac)
    assert sonuc["sonuc"] == "yenilendi" and not sonuc["db_aktarildi"] and sayac.aktarim == 0
    (kok / "db_yedekleri").mkdir()
    (kok / "db_yedekleri" / "turbulans_20261030.dump").write_bytes(b"")
    sonuc = _calistir(kok, sayac, bugun=date(2026, 10, 30))
    assert sonuc["sonuc"] == "db_aktarimi" and sonuc["db_aktarildi"] and sayac.aktarim == 1
    assert len(sayac.indirilen) == 4
