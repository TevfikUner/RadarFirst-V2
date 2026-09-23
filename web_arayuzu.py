"""
web_arayuzu.py
-----------------
main.py'nin işlevini terminalden değil, tarayıcıdan kullanılabilir hale
getiren basit bir web sayfası (Streamlit ile). Uçuş numarası ve tarihi bir
kutuya yazıp "Analiz Et" butonuna basman yeterli; sonuç tablosu ve zaman
kaydırıcılı harita direkt sayfada görünür.

Çalıştırma:
    pip install -r requirements.txt
    streamlit run web_arayuzu.py

Bu sayfa main.py'deki calistir() fonksiyonunu ÇAĞIRIR -- yani arkada hâlâ
gerçek OpenSky/Trino sorgusu ve gerçek hava durumu eşleştirmesi yapılıyor;
bu sadece görsel bir ön yüz, hesaplama mantığı aynı.
"""

import contextlib
import io

import streamlit as st
import streamlit.components.v1 as components

from hata_yardimcisi import dostane_hata_mesaji
from konsol_kurulumu import konsolu_utf8_yap
from main import calistir

konsolu_utf8_yap()

st.set_page_config(page_title="Türbülans Radar", page_icon="✈️", layout="wide")

st.title("✈️ Türbülans Radar")
st.caption(
    "Gerçek bir uçuşun rotasını, hava durumu verisiyle eşleştirerek türbülans şiddeti tahmini (Ellrod TI1) "
    "ve dinamik kararsızlık göstergesi (Richardson sayısı) hesaplar. Sertifikalı EDR değeri DEĞİLDİR -- "
    "araştırma/görselleştirme amaçlıdır."
)

with st.form("analiz_formu"):
    sutun1, sutun2 = st.columns(2)
    with sutun1:
        ucus_numarasi = st.text_input("Uçuş numarası (callsign)", value="THY1234", help="Örn. THY1234")
    with sutun2:
        tarih = st.text_input("Tarih (YYYY-MM-DD)", value="2019-01-01")
    gonder = st.form_submit_button("Analiz Et", type="primary")

if gonder:
    if not ucus_numarasi.strip() or not tarih.strip():
        st.warning("Lütfen hem uçuş numarası hem de tarih gir.")
    else:
        gunluk = io.StringIO()
        eslesmis_df = None
        hata = None

        with st.spinner("Analiz ediliyor -- OpenSky'a bağlanılıyor ve hava durumuyla eşleştiriliyor, biraz sürebilir..."):
            try:
                with contextlib.redirect_stdout(gunluk):
                    eslesmis_df = calistir(ucus_numarasi.strip(), tarih.strip())
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

            harita_dosyasi = f"turbulans_haritasi_{ucus_numarasi.strip()}_{tarih.strip()}.html"
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
