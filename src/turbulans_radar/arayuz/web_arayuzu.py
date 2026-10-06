"""
web_arayuzu.py
-----------------
turbulans-analiz'in (analiz/ucus_analizi.py) işlevini terminalden değil, tarayıcıdan kullanılabilir hale
getiren basit bir web sayfası (Streamlit ile). Uçuş numarası ve tarihi bir
kutuya yazıp "Analiz Et" butonuna basman yeterli; sonuç tablosu ve zaman
kaydırıcılı harita direkt sayfada görünür.

Çalıştırma:
    pip install -e .
    streamlit run src/turbulans_radar/arayuz/web_arayuzu.py

Bu sayfa ucus_analizi.py'deki calistir() fonksiyonunu ÇAĞIRIR -- yani arkada hâlâ
gerçek OpenSky/Trino sorgusu ve gerçek hava durumu eşleştirmesi yapılıyor;
bu sadece görsel bir ön yüz, hesaplama mantığı aynı.
"""

import contextlib
import io
import os
import re

import streamlit as st
import streamlit.components.v1 as components

from turbulans_radar import config
from turbulans_radar.analiz.ucus_analizi import calistir
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.hata_yardimcisi import dostane_hata_mesaji
from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap
from turbulans_radar.ml.turbulans_ml_modeli import model_bilgisini_yukle, model_kullanilabilir_mi

konsolu_utf8_yap()

st.set_page_config(page_title="Türbülans Radar", page_icon="✈️", layout="wide")

st.title("✈️ Türbülans Radar")
st.caption(
    "Gerçek bir uçuşun rotasını, hava durumu verisiyle eşleştirerek türbülans şiddeti tahmini (Ellrod TI1) "
    "ve dinamik kararsızlık göstergesi (Richardson sayısı) hesaplar. Sertifikalı EDR değeri DEĞİLDİR -- "
    "araştırma/görselleştirme amaçlıdır."
)

with st.sidebar:
    st.subheader("📋 Kayıtlı uçuşlar")
    arama = st.text_input("Uçuş no ara", key="kayitli_arama", placeholder="THY322")
    try:
        kayitli = vt.ucuslari_listele(limit=20, ucus_numarasi_arama=arama or None)
    except Exception as e:
        kayitli = []
        st.caption(f"Veritabanına erişilemedi: {dostane_hata_mesaji(e)}")

    if kayitli:
        for u in kayitli:
            satir1, satir2 = st.columns([3, 1])
            satir1.caption(f"**{u['ucus_numarasi']}** / {u['tarih']}")
            with satir2.popover("Sil"):
                st.caption(f"{u['ucus_numarasi']} / {u['tarih']} ölçümleriyle silinsin mi?")
                if st.button("Evet, sil", key=f"sil_{u['id']}"):
                    vt.ucus_sil(u["ucus_numarasi"], str(u["tarih"]))
                    st.rerun()
    elif arama:
        st.caption("Eşleşen kayıtlı uçuş yok.")
    else:
        st.caption("Henüz kayıtlı uçuş yok -- aşağıdan bir analiz çalıştır.")

    st.divider()
    st.subheader("🤖 ML Türbülans Modeli")
    model_bilgisi = model_bilgisini_yukle()
    model_kullanimda, model_uyarisi = model_kullanilabilir_mi(model_bilgisi)
    if model_bilgisi is None:
        st.caption("Model henüz eğitilmedi (bkz. GET /api/v1/ml/durum).")
    elif not model_kullanimda:
        st.caption(f"⚠ {model_uyarisi}")
    else:
        st.caption(f"Seçilen model: **{model_bilgisi['secilen_model']}**")
        m = model_bilgisi["metrikler"]
        # Sidebar dar olduğu için st.metric() yerine tek satırlık metin --
        # üç st.metric() yan yana rakamları kesiyordu.
        st.caption(f"Recall **{m['recall']:.3f}** · F1 **{m['f1']:.3f}** · ROC-AUC **{m['roc_auc']:.3f}**")

with st.form("analiz_formu"):
    sutun1, sutun2 = st.columns(2)
    with sutun1:
        ucus_numarasi = st.text_input(
            "Uçuş numarası (callsign)", value="THY322", help="Örn. THY322 (depodaki demo uçuşu, OpenSky gerektirmez)"
        )
    with sutun2:
        tarih = st.text_input("Tarih (YYYY-MM-DD)", value="2019-01-15")
    gonder = st.form_submit_button("Analiz Et", type="primary")

if gonder:
    ucus_numarasi, tarih = ucus_numarasi.strip(), tarih.strip()
    if not ucus_numarasi or not tarih:
        st.warning("Lütfen hem uçuş numarası hem de tarih gir.")
    elif not re.fullmatch(r"[A-Za-z0-9]{1,8}", ucus_numarasi):
        # Uçuş no ve tarih aşağıda harita dosya adına da giriyor (ciktilar/...):
        # API'deki desenle aynı doğrulama '../' gibi yol parçalarını da dışlar.
        st.warning("Uçuş numarası en fazla 8 harf/rakam olmalı (örn. THY1234).")
    elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", tarih):
        st.warning("Tarih YYYY-MM-DD biçiminde olmalı.")
    else:
        gunluk = io.StringIO()
        eslesmis_df = None
        hata = None

        with st.spinner(
            "Analiz ediliyor -- OpenSky'a bağlanılıyor ve hava durumuyla eşleştiriliyor, biraz sürebilir..."
        ):
            try:
                with contextlib.redirect_stdout(gunluk):
                    eslesmis_df = calistir(ucus_numarasi, tarih)
            except Exception as e:
                hata = e

        if hata is not None:
            st.error(dostane_hata_mesaji(hata))
        elif eslesmis_df is None:
            gunluk_metni = gunluk.getvalue().strip()
            son_mesaj = gunluk_metni.splitlines()[-1] if gunluk_metni else "Bilinmeyen sebep."
            st.warning(f"Analiz tamamlanamadı: {son_mesaj}")
        else:
            gecerli_sayisi = eslesmis_df["ti1_indeksi"].notna().sum()
            st.success(f"Analiz tamamlandı: {len(eslesmis_df)} nokta işlendi, {gecerli_sayisi} tanesi eşleşti.")

            sutun1, sutun2, sutun3 = st.columns(3)
            ti1_gecerli = eslesmis_df["ti1_indeksi"].dropna()
            if len(ti1_gecerli) > 0:
                sutun1.metric("Ortalama TI1", f"{ti1_gecerli.mean():.2e} s^-2")
                sutun2.metric("Maksimum TI1", f"{ti1_gecerli.max():.2e} s^-2")
                if "dinamik_kararsizlik" in eslesmis_df.columns:
                    kararsiz_sayisi = int(eslesmis_df["dinamik_kararsizlik"].fillna(False).astype(bool).sum())
                    sutun3.metric("Dinamik kararsız nokta", kararsiz_sayisi)

            harita_dosyasi = os.path.join(config.CIKTI_KLASORU, f"turbulans_haritasi_{ucus_numarasi}_{tarih}.html")
            try:
                with open(harita_dosyasi, encoding="utf-8") as f:
                    st.subheader("Türbülans Haritası")
                    components.html(f.read(), height=600, scrolling=True)
            except FileNotFoundError:
                st.info("Harita dosyası bulunamadı.")

            with st.expander("Sonuç tablosu (ilk 200 satır)"):
                st.dataframe(eslesmis_df.head(200))

        with st.expander("İşlem günlüğü (teknik detaylar)"):
            st.text(gunluk.getvalue() or "(günlük boş)")
