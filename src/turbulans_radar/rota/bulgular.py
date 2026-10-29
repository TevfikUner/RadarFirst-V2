"""Rota sonucundaki dispeç bulguları (rota_optimizasyonu'ndan ayrıldı)."""

from __future__ import annotations

from turbulans_radar import config
from turbulans_radar.ariza_taklidi import etkin_taklit
from turbulans_radar.fizik.ti1_esigi import etkin_ti1_esigi
from turbulans_radar.rota.brifing import riskli_bolumler
from turbulans_radar.rota.geometri import NM_KM
from turbulans_radar.veri.veri_saglayicilari import veri_kupu_kaynagi


def _temel_strateji(strateji: str) -> str:
    """Pareto adayları ("yanal_ceza_60", "ats_ceza_0") temel stratejiye indirgenir."""
    if "_ceza_" not in strateji:
        return strateji
    return "yanal" if strateji.startswith("yanal") else "ats_alternatif"


_SEVIYE_MALIYET_NOTU = (
    " Yakıt farkı yalnızca geçici seviyeye gidip planlanan seviyeye dönmenin yaklaşık bedelidir; seviyeye bağlı "
    "seyir yakıt akışı modellenmez."
)


_SEVIYE_MALIYET_NOTU_OPENAP = (
    " Yakıt OpenAP ile seviyeye ve kütleye bağlı hesaplanır (geçiş ±1500 ft/dk; seyir başı kütlesi varsayımdır)."
)


def _seviye_maliyet_notu(aday):
    if not aday["strateji"].startswith("irtifa"):
        return ""
    return _SEVIYE_MALIYET_NOTU_OPENAP if aday.get("yakit_modeli") == "openap" else _SEVIYE_MALIYET_NOTU


def _bulgu(kod, seviye, metin, **parametreler):
    """Yanıttaki makine-okunur bulgu (kod + seviye + parametreler) ve onun
    Türkçe cümlesi TEK yerde üretilir: 'aciklama' metni bulgulardan türetilir,
    ikisi birbirinden kopamaz. Seviye: bilgi | uyari | kritik."""
    return {"kod": kod, "seviye": seviye, "parametreler": parametreler, "metin": metin}


def _seviye_bulgulari(seviye):
    if not seviye or not seviye["duzeltildi"]:
        return []
    yon = "doğu (000-179°): tek" if seviye["yon"] == "dogu" else "batı (180-359°): çift"
    if seviye["tavan_asildi"]:
        neden = f"uçak tipinin azami seviyesinin (FL{seviye['azami_fl']}) üstünde"
    else:
        neden = f"yarım daire kuralına aykırı (manyetik iz {seviye['manyetik_iz']:03.0f}°, {yon} FL)"
    return [
        _bulgu(
            "ucus_seviyesi_duzeltildi",
            "uyari",
            f"İstenen FL{seviye['istenen_fl']:.0f} {neden}; hesap en yakın yasal seviye FL{seviye['fl']} ile "
            f"yapıldı. Manyetik sapma sabit {config.MANYETIK_SAPMA_DERECE:+.0f}° varsayıldı.",
            istenen_fl=seviye["istenen_fl"],
            fl=seviye["fl"],
            manyetik_iz=seviye["manyetik_iz"],
            yon=seviye["yon"],
            tavan_asildi=seviye["tavan_asildi"],
        )
    ]


def _bulgulari_olustur(
    ruzgarli_mi,
    veri_kupu,
    kup_adi,
    normal,
    en_iyi,
    irtifa_m,
    sigmet_kontrolu,
    guvenli_rota_bulundu_mu,
    kisitli_saha_kontrolu=None,
    canli_hata=None,
    seviye=None,
):
    bulgular = _seviye_bulgulari(seviye)
    if (taklit := etkin_taklit()) is not None:
        bulgular.insert(
            0,
            _bulgu(
                "ariza_taklidi",
                "uyari",
                f"SENTETİK ARIZA TATBİKATI ({taklit}): aşağıdaki veri kaynağı durumu demo için yalnız bu istekte "
                "taklit edildi; gerçek sunucu durumu değildir (bkz. GET /saglik?derin=true).",
                taklit=taklit,
            ),
        )
    if ruzgarli_mi and veri_kupu_kaynagi(veri_kupu) == "gfs":
        calisma = veri_kupu.attrs.get("model_calisma_zamani")
        bulgular.append(
            _bulgu(
                "veri_gfs_tahmin",
                "bilgi",
                f"Canlı NOAA GFS tahmin verisiyle hesaplandı (model çalıştırması "
                f"{f'{calisma} UTC' if calisma else 'bilinmiyor'}).",
                model_calisma_zamani=str(calisma) if calisma else None,
            )
        )
    elif ruzgarli_mi:
        bulgular.append(_bulgu("veri_era5", "bilgi", f"Gerçek ERA5 verisiyle hesaplandı ('{kup_adi}').", kup=kup_adi))
    if ruzgarli_mi:
        normal_bolumler = riskli_bolumler(normal)
        if normal_bolumler is None:
            bulgular.append(
                _bulgu(
                    "ti1_hesaplanmadi",
                    "uyari",
                    "Normal rota için TI1 hesaplanamadı (rota veri küpünün kapsamı dışında); bu, risk OLMADIĞI "
                    "anlamına gelmez.",
                )
            )
        elif normal["riskli_sayisi"] == 0:
            bulgular.append(
                _bulgu(
                    "ti1_risk_yok",
                    "bilgi",
                    f"Normal rota üzerinde riskli türbülans (TI1 >= {etkin_ti1_esigi():.1e} s^-2) TESPİT EDİLMEDİ.",
                    esik=etkin_ti1_esigi(),
                )
            )
        else:
            bulgular.append(
                _bulgu(
                    "ti1_risk_var",
                    "uyari",
                    f"Normal rota üzerinde {normal['riskli_sayisi']} noktada (~"
                    f"{sum(b['uzunluk_nm'] for b in normal_bolumler):.0f} NM, ~"
                    f"{sum(b['sure_dk'] for b in normal_bolumler):.0f} dk) riskli türbülans tespit edildi.",
                    riskli_nokta_sayisi=normal["riskli_sayisi"],
                    esik=etkin_ti1_esigi(),
                )
            )
    elif canli_hata:
        bulgular.append(
            _bulgu(
                "ruzgar_hesaba_katilamadi",
                "uyari",
                f"UYARI: {canli_hata} Rüzgar ve türbülans (TI1) hesaba katılamadı, rotalar sadece uçağın hava "
                "hızıyla (TAS) zamanlandı (bkz. GET /saglik?derin=true); SIGMET ve kısıtlı saha kısıtları yine "
                "uygulandı.",
                neden="canli_veri",
            )
        )
    else:
        bulgular.append(
            _bulgu(
                "ruzgar_hesaba_katilamadi",
                "uyari",
                "Seçilen bölge/tarih/irtifa için ne sunucudaki ERA5 arşiv küpleri ne de canlı GFS "
                f"verisi (şimdi -{config.CANLI_GECMIS_SAAT} sa / +{config.CANLI_TAHMIN_UFKU_SAAT} sa aralığı için) "
                "rotanın TAMAMINI kapsıyor -- rüzgar ve türbülans (TI1) hesaba katılamadı, rotalar sadece uçağın "
                "hava hızıyla (TAS) zamanlandı; gerçek bir yakıt tasarrufu/türbülans kaçınması iddia edilmiyor.",
                neden="kapsam_disi",
            )
        )

    durum = sigmet_kontrolu["durum"]
    if durum == "erisilemedi":
        bulgular.append(
            _bulgu(
                "sigmet_erisilemedi",
                "kritik",
                "UYARI: SIGMET veritabanına erişilemedi -- aktif SIGMET kontrolü YAPILAMADI.",
            )
        )
    elif durum == "uygulandi":
        ihlal = normal["sigmet_ihlali"]
        bulgular.append(
            _bulgu(
                "sigmet_uygulandi",
                "bilgi",
                f"{sigmet_kontrolu['aktif_sigmet_sayisi']} aktif SIGMET sert kısıt olarak uygulandı; normal rota "
                + (f"{ihlal} nokta/bacakta bunlara giriyor." if ihlal else "bunlara girmiyor."),
                aktif_sigmet_sayisi=sigmet_kontrolu["aktif_sigmet_sayisi"],
                normal_rota_ihlali=ihlal,
            )
        )
    ufuk_disi = sigmet_kontrolu.get("yayin_ufku_disi", "yok")
    if durum != "erisilemedi" and ufuk_disi != "yok":
        bulgular.append(
            _bulgu(
                "sigmet_ufuk_disi",
                "uyari",
                ("Uçuşun tamamı" if ufuk_disi == "tam" else "Uçuşun bir kısmı")
                + f" şu andan {config.SIGMET_YAYIN_UFKU_SAAT:g} saatten daha sonra; o zaman dilimi için SIGMET henüz "
                "yayımlanmamış olabilir. SIGMET kontrolü bu kısım için güvence vermez -- kalkıştan önceki son "
                "saatlerde yeniden hesaplayın.",
                kisim=ufuk_disi,
                yayin_ufku_saat=config.SIGMET_YAYIN_UFKU_SAAT,
            )
        )
    if sigmet_kontrolu.get("bayat_mi"):
        sorunlu = sigmet_kontrolu.get("sorunlu_kaynaklar") or []
        bulgular.append(
            _bulgu(
                "sigmet_bayat",
                "kritik",
                f"UYARI: son başarılı SIGMET güncellemesi {config.SIGMET_BAYATLIK_DAKIKA} dakikadan eski ya da hiç "
                "yapılmamış (bkz. POST /api/v1/sigmet/guncelle)"
                + (f"; hata veren kaynak: {', '.join(sorunlu)}" if sorunlu else "")
                + " -- aktif uyarılar eksik olabilir.",
                bayatlik_esigi_dakika=config.SIGMET_BAYATLIK_DAKIKA,
                sorunlu_kaynaklar=list(sorunlu),
            )
        )

    bulgular += _kisitli_saha_bulgulari(kisitli_saha_kontrolu or {}, normal)

    if not guvenli_rota_bulundu_mu:
        bulgular.append(
            _bulgu(
                "guvenli_rota_yok",
                "kritik",
                "ÖNERİ YOK: aktif SIGMET'lere ve kısıtlı hava sahalarına girmeyen geçerli bir rota bulunamadı "
                "(başlangıç/bitiş SIGMET içinde olabilir ya da alan arama ızgarasından geniş) -- gösterilen rota "
                "normal rotadır ve ÖNERİLMEZ.",
            )
        )
    elif en_iyi["strateji"] == "yok":
        bulgular.append(
            _bulgu(
                "sapma_gereksiz",
                "bilgi",
                "Kaçınılacak bir risk olmadığı için optimize rota normal rotayla birebir aynıdır "
                "(uydurma bir sapma gösterilmiyor).",
            )
        )
    else:
        strateji = _temel_strateji(en_iyi["strateji"])
        irtifa_farki_ft = (en_iyi["irtifa_m"] - irtifa_m) / 0.3048
        strateji_aciklamasi = {
            "yanal": (
                f"A* araması ile yanal sapma (en fazla {en_iyi['yanal_sapma_km'] / NM_KM:.0f} NM, "
                f"{en_iyi['yanal_sapma_km']:.0f} km)"
            ),
            "ats_alternatif": "ATS ağı üzerinde alternatif rota (A*)",
            "irtifa_yukari": f"irtifayı {irtifa_farki_ft:.0f} ft artırarak (tırmanma)",
            "irtifa_asagi": f"irtifayı {-irtifa_farki_ft:.0f} ft azaltarak (alçalma)",
        }[strateji]
        kacinma = {"strateji": strateji, "yanal_sapma_km": en_iyi["yanal_sapma_km"], "irtifa_farki_ft": irtifa_farki_ft}
        if not ruzgarli_mi:
            bulgular.append(
                _bulgu(
                    "kacinma_sert_kisit",
                    "bilgi",
                    f"Aktif SIGMET'lere ve kısıtlı sahalara girmeyen en kısa rota olarak {strateji_aciklamasi} "
                    "bulundu.",
                    **kacinma,
                )
            )
        elif en_iyi["riskli_sayisi"] == 0:
            bulgular.append(
                _bulgu(
                    "kacinma_tam_guvenli",
                    "bilgi",
                    "ÇOK FAKTÖRLÜ karşılaştırmada (yanal A* araması vs aynı yönün bir üst/alt yasal FL'sine geçiş, her "
                    "biri yaklaşık yakıt/süre maliyetiyle) riskli TI1 noktası içermeyen en ucuz seçenek olarak "
                    f"{strateji_aciklamasi} bulundu." + _seviye_maliyet_notu(en_iyi),
                    **kacinma,
                )
            )
        else:
            bulgular.append(
                _bulgu(
                    "ti1_riski_kismen_kaldi",
                    "uyari",
                    "Denenen adaylar TI1 riskini TAMAMEN ortadan kaldıramadı (türbülans alanı geniş olabilir) -- "
                    f"sert kısıtlara uyan seçenekler arasından {strateji_aciklamasi} seçildi "
                    f"({en_iyi['riskli_sayisi']} riskli nokta, normal rotadaki {normal['riskli_sayisi']}'e karşı)."
                    + _seviye_maliyet_notu(en_iyi),
                    riskli_nokta_sayisi=en_iyi["riskli_sayisi"],
                    normal_riskli_nokta_sayisi=normal["riskli_sayisi"],
                    **kacinma,
                )
            )
    return bulgular


def _kisitli_saha_bulgulari(kontrol, normal):
    bulgular = []
    if kontrol.get("durum") == "erisilemedi":
        bulgular.append(
            _bulgu(
                "kisitli_saha_erisilemedi",
                "kritik",
                "UYARI: kısıtlı hava sahası veritabanına erişilemedi -- saha kontrolü YAPILAMADI.",
            )
        )
    elif kontrol.get("durum") == "uygulandi":
        ihlal = normal["kisitli_saha_ihlali"]
        bulgular.append(
            _bulgu(
                "kisitli_saha_uygulandi",
                "bilgi",
                f"{kontrol['uygulanan_saha_sayisi']} kısıtlı hava sahası sert kısıt olarak uygulandı; normal rota "
                + (f"{ihlal} nokta/bacakta bunlara giriyor." if ihlal else "bunlara girmiyor."),
                uygulanan_saha_sayisi=kontrol["uygulanan_saha_sayisi"],
                normal_rota_ihlali=ihlal,
            )
        )
    if kontrol.get("muaf_tutulanlar"):
        bulgular.append(
            _bulgu(
                "kisitli_saha_uc_koridoru",
                "bilgi",
                "Kalkış/varış noktasını içeren saha(lar)da sadece planlı rotanın "
                f"±{config.KISITLI_SAHA_UC_KORIDORU_KM:.0f} km koridoru serbest bırakıldı: "
                + ", ".join(kontrol["muaf_tutulanlar"])
                + ".",
                koridor_km=config.KISITLI_SAHA_UC_KORIDORU_KM,
                sahalar=list(kontrol["muaf_tutulanlar"]),
            )
        )
    if kontrol.get("ornek_veri_mi"):
        bulgular.append(
            _bulgu(
                "kisitli_saha_ornek_veri",
                "uyari",
                "NOT: kısıtlı sahaların bir kısmı paketle gelen ÖRNEK veridir (ülke sınırından türetilmiş) -- resmi "
                "AIP/CZIB/NOTAM verisi değildir.",
            )
        )
    return bulgular
