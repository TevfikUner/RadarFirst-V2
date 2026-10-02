"""IWXXM dışa aktarımı. SIGMET'ler SENTETİKTİR. Resmi XSD doğrulaması (xmlschema,
şemalar schemas.wmo.int'ten) 2 Ekim 2026'da elle yapıldı; burada ağsız yapı kontrolü."""

import xml.etree.ElementTree as ET

import pytest

from turbulans_radar.veri import iwxxm

NS = {
    "iwxxm": "http://icao.int/iwxxm/2025-2",
    "aixm": "http://www.aixm.aero/schema/5.1.1",
    "gml": "http://www.opengis.net/gml/3.2",
    "xlink": "http://www.w3.org/1999/xlink",
}
SIGMET = {
    "id": 42,
    "fir_kodu": "LTAA",
    "seri_no": "A3",
    "tehlike": "TURB",
    "niteleyici": "SEV",
    "gecerlilik_baslangic": "2026-10-02T12:00Z",
    "gecerlilik_bitis": "2026-10-02T16:00Z",
    "taban_ft": 30000,
    "tavan_ft": 38000,
    "poligon": [[30, 40], [34, 40], [34, 38], [30, 38]],
    "hareket_yonu_derece": 90,
    "hareket_hizi_kt": 20,
}


def test_sigmet_iwxxm_yapisi_ve_durustluk_isaretleri():
    kok = ET.fromstring(iwxxm.sigmet_iwxxm(SIGMET, "LTAA SIGMET A3 SEV TURB FCST").encode())
    assert kok.tag == "{http://icao.int/iwxxm/2025-2}SIGMET"
    assert kok.get("permissibleUsage") == "NON-OPERATIONAL" and "yetkili MWO" in kok.get(
        "permissibleUsageSupplementary"
    )
    olgu = kok.find("iwxxm:phenomenon", NS).get(f"{{{NS['xlink']}}}href")
    assert olgu == "http://codes.wmo.int/49-2/SigWxPhenomena/SEV_TURB"
    assert kok.find("iwxxm:sequenceNumber", NS).text == "A3"
    hacim = kok.find(".//aixm:AirspaceVolume", NS)
    assert hacim.find("aixm:upperLimit", NS).text == "380" and hacim.find("aixm:lowerLimit", NS).text == "300"
    konumlar = kok.find(".//gml:posList", NS).text.split()
    assert konumlar[:2] == ["40.0000", "30.0000"] and konumlar[:2] == konumlar[-2:]
    assert kok.find(".//iwxxm:SIGMETEvolvingConditionCollection", NS).get("timeIndicator") == "FORECAST"
    assert kok.find(".//iwxxm:speedOfMotion", NS).text == "20"
    assert iwxxm.sigmet_iwxxm(SIGMET) == iwxxm.sigmet_iwxxm(SIGMET)


def test_eksik_bilgi_aciklamaya_yazilir_ve_istege_bagli_alanlar_atlanir():
    eksik = {**SIGMET, "seri_no": None, "taban_ft": None, "tavan_ft": None, "hareket_yonu_derece": None}
    kok = ET.fromstring(iwxxm.sigmet_iwxxm(eksik, "OBS AT 1200Z").encode())
    assert "Seri numarası kaynakta yok" in kok.get("permissibleUsageSupplementary")
    assert kok.find(".//aixm:upperLimit", NS) is None and kok.find(".//iwxxm:speedOfMotion", NS) is None
    assert kok.find(".//iwxxm:SIGMETEvolvingConditionCollection", NS).get("timeIndicator") == "OBSERVATION"


@pytest.mark.parametrize(
    "tehlike, niteleyici, kod",
    [("TS", "EMBD", "EMBD_TS"), ("ICE", None, "SEV_ICE"), ("MTW", "SEV", "SEV_MTW"), ("VA", None, "VA_CLD")],
)
def test_olgu_kodlari(tehlike, niteleyici, kod):
    assert iwxxm.olgu_kodu(tehlike, niteleyici) == kod


@pytest.mark.parametrize(
    "degisiklik", [{"tehlike": "CONVECTIVE"}, {"tehlike": "TS", "niteleyici": None}, {"fir_kodu": "KZ"}]
)
def test_eslenemeyen_sigmet_disa_aktarilmaz(degisiklik):
    with pytest.raises(iwxxm.IwxxmEslemeHatasi):
        iwxxm.sigmet_iwxxm({**SIGMET, **degisiklik})
