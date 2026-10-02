"""
iwxxm.py
-----------
M7: saklanan SIGMET'i ICAO/WMO IWXXM (2025-2) XML'ine yeniden kodlar. Yapı
WMO'nun resmi örneğini (wmo-im/iwxxm, IWXXM/examples/sigmet-A6-1a-TS.xml)
izler; olgu kodları WMO 49-2 SigWxPhenomena kod listesindendir.

Dürüstlük kuralları:
  - Mesaj permissibleUsage="NON-OPERATIONAL" (TEST) işaretlidir: AWC'den
    alınmış SIGMET'in Türbülans Radar tarafından yeniden kodlanmasıdır, yetkili
    MWO'nun yayımladığı IWXXM değildir.
  - Kaynak veride MWO kodu tutulmadığı için MWO ve ATS birimi tanıtıcısı olarak
    FIR kodu kullanılır; bu, permissibleUsageSupplementary'de yazılıdır.
  - WMO koduna kesin eşlenemeyen olgular (ör. ABD'ye özgü CONVECTIVE ya da
    niteleyicisi bilinmeyen TS) dışa aktarılmaz (IwxxmEslemeHatasi).
  - Gözlem/tahmin ayrımı ham metinde 'OBS'/'FCST' olarak aranır; yoksa
    FORECAST varsayılır ve bu da açıklamaya yazılır.
"""

import re
import uuid
from xml.sax.saxutils import escape

import pandas as pd

IWXXM_SURUMU = "2025-2"
_OLGU_KOK = "http://codes.wmo.int/49-2/SigWxPhenomena/"
_TS_NITELEYICILERI = {"OBSC", "EMBD", "FRQ", "SQL"}
_SABIT_OLGULAR = {
    "TURB": "SEV_TURB",
    "ICE": "SEV_ICE",
    "MTW": "SEV_MTW",
    "VA": "VA_CLD",
    "TC": "TC",
    "DS": "HVY_DS",
    "SS": "HVY_SS",
    "RDOACT": "RDOACT_CLD",
}


class IwxxmEslemeHatasi(ValueError):
    pass


def olgu_kodu(tehlike: str, niteleyici: str | None) -> str:
    tehlike = (tehlike or "").upper()
    niteleyici = (niteleyici or "").upper()
    if tehlike in _SABIT_OLGULAR:
        return _SABIT_OLGULAR[tehlike]
    if tehlike == "TS" and niteleyici in _TS_NITELEYICILERI:
        return f"{niteleyici}_TS"
    raise IwxxmEslemeHatasi(
        f"'{tehlike}'{f' ({niteleyici})' if niteleyici else ''} WMO SigWxPhenomena koduna kesin eşlenemiyor."
    )


def _kimlik(sigmet_id, ad: str) -> str:
    return f"uuid.{uuid.uuid5(uuid.NAMESPACE_URL, f'turbulans-radar/sigmet/{sigmet_id}/{ad}')}"


def _zaman(deger) -> str:
    z = pd.Timestamp(deger)
    z = z.tz_localize("UTC") if z.tzinfo is None else z.tz_convert("UTC")
    return z.strftime("%Y-%m-%dT%H:%M:%SZ")


def _pos_list(poligon) -> str:
    noktalar = [(float(enlem), (float(boylam) + 180.0) % 360.0 - 180.0) for boylam, enlem in poligon]
    if noktalar[0] != noktalar[-1]:
        noktalar.append(noktalar[0])
    return " ".join(f"{e:.4f} {b:.4f}" for e, b in noktalar)


def _birim(sigmet_id, etiket, tur, tanitici) -> str:
    return f"""        <aixm:Unit gml:id="{_kimlik(sigmet_id, etiket)}">
            <aixm:timeSlice>
                <aixm:UnitTimeSlice gml:id="{_kimlik(sigmet_id, etiket + "-ts")}">
                    <gml:validTime/>
                    <aixm:interpretation>SNAPSHOT</aixm:interpretation>
                    <aixm:name>{escape(tanitici)} {tur}</aixm:name>
                    <aixm:type>{tur}</aixm:type>
                    <aixm:designator>{escape(tanitici)}</aixm:designator>
                </aixm:UnitTimeSlice>
            </aixm:timeSlice>
        </aixm:Unit>"""


def sigmet_iwxxm(sigmet: dict, ham_metin: str | None = None) -> str:
    """sigmet: sigmet_saglayici._satiri_sozluge_cevir biçimi."""
    kod = olgu_kodu(sigmet.get("tehlike"), sigmet.get("niteleyici"))
    fir = (sigmet.get("fir_kodu") or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{4}", fir):
        raise IwxxmEslemeHatasi("FIR kodu (4 harf) yok; IWXXM'de yayınlayan birim zorunludur.")
    if not sigmet.get("poligon") or len(sigmet["poligon"]) < 3:
        raise IwxxmEslemeHatasi("SIGMET alanı (en az 3 köşe) yok.")
    sid = sigmet.get("id")
    metin = (ham_metin or "").upper()
    if re.search(r"\bOBS\b", metin):
        zaman_gostergesi, zaman_notu = "OBSERVATION", ""
    elif re.search(r"\bFCST\b", metin):
        zaman_gostergesi, zaman_notu = "FORECAST", ""
    else:
        zaman_gostergesi, zaman_notu = "FORECAST", " Gözlem/tahmin ayrımı kaynakta yok; FORECAST varsayıldı."
    seri = re.sub(r"[^A-Za-z0-9]", "", str(sigmet.get("seri_no") or ""))
    if not seri:
        seri, zaman_notu = "1", zaman_notu + " Seri numarası kaynakta yok; zorunlu alan olduğu için 1 yazıldı."
    dikey = []
    if sigmet.get("tavan_ft"):
        dikey += [
            f'<aixm:upperLimit uom="FL">{round(sigmet["tavan_ft"] / 100):03d}</aixm:upperLimit>',
            "<aixm:upperLimitReference>STD</aixm:upperLimitReference>",
        ]
    if sigmet.get("taban_ft"):
        dikey += [
            f'<aixm:lowerLimit uom="FL">{round(sigmet["taban_ft"] / 100):03d}</aixm:lowerLimit>',
            "<aixm:lowerLimitReference>STD</aixm:lowerLimitReference>",
        ]
    hareket = []
    if sigmet.get("hareket_yonu_derece") is not None and sigmet.get("hareket_hizi_kt"):
        hareket = [
            f'<iwxxm:directionOfMotion uom="deg">{round(sigmet["hareket_yonu_derece"]) % 360}</iwxxm:directionOfMotion>',
            f'<iwxxm:speedOfMotion uom="[kn_i]">{round(sigmet["hareket_hizi_kt"])}</iwxxm:speedOfMotion>',
        ]
    aciklama = (
        "Türbülans Radar tarafından AWC verisinden yeniden kodlandı; yetkili MWO yayını değildir. "
        "Kaynakta MWO kodu olmadığı için MWO ve ATS birimi olarak FIR kodu kullanıldı." + zaman_notu
    )
    girinti = "\n" + " " * 36
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<iwxxm:SIGMET
    xmlns:iwxxm="http://icao.int/iwxxm/{IWXXM_SURUMU}"
    xmlns:aixm="http://www.aixm.aero/schema/5.1.1"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://icao.int/iwxxm/{IWXXM_SURUMU} http://schemas.wmo.int/iwxxm/{IWXXM_SURUMU}/iwxxm.xsd"
    gml:id="{_kimlik(sid, "sigmet")}"
    reportStatus="NORMAL"
    permissibleUsage="NON-OPERATIONAL"
    permissibleUsageReason="TEST"
    permissibleUsageSupplementary="{escape(aciklama, {'"': "&quot;"})}">

    <iwxxm:issueTime>
        <gml:TimeInstant gml:id="{_kimlik(sid, "yayin")}">
            <gml:timePosition>{_zaman(sigmet["gecerlilik_baslangic"])}</gml:timePosition>
        </gml:TimeInstant>
    </iwxxm:issueTime>

    <iwxxm:issuingAirTrafficServicesUnit>
{_birim(sid, "ats", "FIC", fir)}
    </iwxxm:issuingAirTrafficServicesUnit>

    <iwxxm:originatingMeteorologicalWatchOffice>
{_birim(sid, "mwo", "MWO", fir)}
    </iwxxm:originatingMeteorologicalWatchOffice>

    <iwxxm:issuingAirTrafficServicesRegion>
        <aixm:Airspace gml:id="{_kimlik(sid, "fir")}">
            <aixm:timeSlice>
                <aixm:AirspaceTimeSlice gml:id="{_kimlik(sid, "fir-ts")}">
                    <gml:validTime/>
                    <aixm:interpretation>SNAPSHOT</aixm:interpretation>
                    <aixm:type>OTHER:FIR_UIR</aixm:type>
                    <aixm:designator>{fir}</aixm:designator>
                    <aixm:name>{fir} FIR</aixm:name>
                </aixm:AirspaceTimeSlice>
            </aixm:timeSlice>
        </aixm:Airspace>
    </iwxxm:issuingAirTrafficServicesRegion>

    <iwxxm:sequenceNumber>{seri}</iwxxm:sequenceNumber>

    <iwxxm:validPeriod>
        <gml:TimePeriod gml:id="{_kimlik(sid, "gecerlilik")}">
            <gml:beginPosition>{_zaman(sigmet["gecerlilik_baslangic"])}</gml:beginPosition>
            <gml:endPosition>{_zaman(sigmet["gecerlilik_bitis"])}</gml:endPosition>
        </gml:TimePeriod>
    </iwxxm:validPeriod>

    <iwxxm:phenomenon xlink:href="{_OLGU_KOK}{kod}"/>

    <iwxxm:analysisCollection>
        <iwxxm:analysisAndForecastPositionAnalysis gml:id="{_kimlik(sid, "analiz")}">
            <iwxxm:analysis>
                <iwxxm:SIGMETEvolvingConditionCollection gml:id="{_kimlik(sid, "kosullar")}" timeIndicator="{zaman_gostergesi}">
                    <iwxxm:phenomenonTime nilReason="http://codes.wmo.int/common/nil/missing"/>
                    <iwxxm:member>
                        <iwxxm:SIGMETEvolvingCondition gml:id="{_kimlik(sid, "kosul")}">
                            <iwxxm:geometry>
                                <aixm:AirspaceVolume gml:id="{_kimlik(sid, "hacim")}">{"".join(girinti + d for d in dikey)}
                                    <aixm:horizontalProjection>
                                        <aixm:Surface gml:id="{_kimlik(sid, "yuzey")}" srsDimension="2" axisLabels="Lat Long" srsName="http://www.opengis.net/def/crs/EPSG/0/4326">
                                            <gml:patches>
                                                <gml:PolygonPatch>
                                                    <gml:exterior>
                                                        <gml:LinearRing>
                                                            <gml:posList>{_pos_list(sigmet["poligon"])}</gml:posList>
                                                        </gml:LinearRing>
                                                    </gml:exterior>
                                                </gml:PolygonPatch>
                                            </gml:patches>
                                        </aixm:Surface>
                                    </aixm:horizontalProjection>
                                </aixm:AirspaceVolume>
                            </iwxxm:geometry>{"".join(chr(10) + " " * 28 + h for h in hareket)}
                        </iwxxm:SIGMETEvolvingCondition>
                    </iwxxm:member>
                </iwxxm:SIGMETEvolvingConditionCollection>
            </iwxxm:analysis>
        </iwxxm:analysisAndForecastPositionAnalysis>
    </iwxxm:analysisCollection>

</iwxxm:SIGMET>
"""
