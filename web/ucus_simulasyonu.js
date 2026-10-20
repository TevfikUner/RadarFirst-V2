if (!window.Cesium) {
  document.body.insertAdjacentHTML("afterbegin", '<div style="padding:16px;color:#e74c3c">CesiumJS yüklenemedi: web/vendor eksik (turbulans-statik ile indirin).</div>');
  throw new Error("CesiumJS yok");
}
const API_TABANI = "";  // aynı origin -- göreli yollar yeterli

function anahtarAl() {
  return document.getElementById("giris-anahtar").value || sessionStorage.getItem("tr_api_anahtari") || "";
}

function durumGoster(mesaj, tur) {
  const el = document.getElementById("durum");
  el.textContent = mesaj;
  el.className = tur || "";
}

async function apiIste(yol, secenekler) {
  const anahtar = anahtarAl();
  const yanit = await fetch(API_TABANI + yol, {
    ...secenekler,
    headers: { "X-API-Key": anahtar, "Content-Type": "application/json", ...(secenekler && secenekler.headers) },
  });
  if (!yanit.ok) {
    let detay = yanit.statusText;
    try { detay = (await yanit.json()).detail || detay; } catch (e) {}
    const hata = new Error(typeof detay === "string" ? detay : JSON.stringify(detay));
    hata.durumKodu = yanit.status;
    throw hata;
  }
  return yanit.json();
}

// --- Cesium: anahtarsız kurulum (bkz. dosya başındaki not) ---
const viewer = new Cesium.Viewer("cesiumContainer", {
  baseLayerPicker: false,
  geocoder: false,
  homeButton: true,
  sceneModePicker: true,
  navigationHelpButton: false,
  animation: true,
  timeline: true,
  fullscreenButton: false,
  infoBox: false,
  selectionIndicator: false,
  shouldAnimate: true,
  // NOT: CesiumJS 1.104+'ta Viewer'ın 'imageryProvider' seçeneği artık
  // sessizce HİÇBİR KATMAN EKLEMİYOR (deprecated) -- doğru yol 'baseLayer'a
  // bir Cesium.ImageryLayer örneği vermek (bkz. Cesium kaynak kodundaki
  // Viewer.js: sadece options.baseLayer, scene.imageryLayers.add() ile
  // eklenir). Bu proje Playwright ile gerçek bir tarayıcıda test edilirken
  // bulundu -- 'imageryProvider' kullanan eski örnekler artık çalışmıyor.
  // Altlık: Cesium paketiyle gelen NaturalEarthII dokusu -- sunucudan gelir,
  // İNTERNETSİZ de görünür. Esri sokak haritası (ALTLIK_KATMANI=esri) üstte
  // ek katmandır; bağlantı yoksa karoları gelmez ama harita boş kalmaz.
  baseLayer: Cesium.ImageryLayer.fromProviderAsync(
    Cesium.TileMapServiceImageryProvider.fromUrl(Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII"))
  ),
  terrainProvider: new Cesium.EllipsoidTerrainProvider(),
});
fetch("/harita-ayarlari")
  .then((yanit) => (yanit.ok ? yanit.json() : {}))
  .then((ayarlar) => {
    if (ayarlar.altlik_katmani !== "esri") return;
    viewer.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        credit: "Tiles © Esri",
      })
    );
  })
  .catch(() => {});
viewer.scene.globe.enableLighting = true;

let mevcutDataSource = null;
let sonEkranSonucu = null;

async function ucakProfilleriniYukle() {
  const secim = document.getElementById("ucak-modeli");
  try {
    const profiller = await apiIste("/api/v1/simulasyon/ucak-profilleri");
    secim.innerHTML = "";
    for (const p of profiller) {
      const opt = document.createElement("option");
      opt.value = p.kod;
      opt.textContent = p.etiket;
      secim.appendChild(opt);
    }
  } catch (e) {
    secim.innerHTML = '<option value="">(API anahtarı geçersiz/eksik)</option>';
  }
}

function saniyeyiDkSaatOlarakYaz(dk) {
  const toplam = Math.round(dk);
  return `${Math.floor(toplam / 60)}:${String(toplam % 60).padStart(2, "0")}`;
}

const NM_KM = 1.852;
const nmMetni = (km) => `${(km / NM_KM).toFixed(0)} NM (${km.toFixed(0)} km)`;
const flMetni = (rota) => `FL${String(rota.fl ?? Math.round(rota.irtifa_ft / 100)).padStart(3, "0")}`;
const sapmaMetni = (nm, yon) => yon
  ? `${nm.toFixed(0)} NM ${yon} of track, rotanın ${yon === "R" ? "sağı" : "solu"}`
  : `rotadan en çok ${nm.toFixed(0)} NM`;
const ruzgarMetni = (kt) => kt == null ? "–" : `${kt >= 0 ? "P" : "M"}${Math.abs(kt).toFixed(0).padStart(2, "0")} kt`;
const utcSaat = (iso) => iso.slice(11, 16) + "Z";

// "Hesaplanmadı" 0 risk değildir: kapsam dışı / veri yoksa sayı gösterilmez.
function riskMetni(rota) {
  if (rota.riskli_nokta_sayisi == null) return "hesaplanmadı";
  if (!rota.riskli_bolumler || rota.riskli_bolumler.length === 0) return "yok";
  return `~${rota.riskli_mesafe_nm.toFixed(0)} NM / ~${rota.riskli_sure_dk.toFixed(0)} dk`;
}

function riskliBolumleriGoster(rota) {
  const kutu = document.getElementById("riskli-bolumler-kutusu");
  const tablo = document.getElementById("riskli-bolumler-tablosu");
  while (tablo.rows.length > 1) tablo.deleteRow(1);
  const bolumler = rota.riskli_bolumler || [];
  kutu.style.display = bolumler.length ? "block" : "none";
  for (const b of bolumler) {
    const satir = tablo.insertRow();
    for (const metin of [
      `${utcSaat(b.baslangic_utc)}–${utcSaat(b.bitis_utc)}`,
      `FL${String(b.fl).padStart(3, "0")}`,
      b.uzunluk_nm.toFixed(0),
      b.sure_dk.toFixed(0),
      b.beklenen_siddet || "–",
    ]) satir.insertCell().textContent = metin;
  }
}

function sonucPanelDoldur(sonuc) {
  document.getElementById("sonuc-paneli").style.display = "block";
  document.body.classList.add("sonuc-acik");

  const ufuk = sonuc.planlama_ufku;
  const kullanim = !ufuk ? "" : ufuk.kullanim === "gecmis_analiz"
    ? "geçmiş tarihli analiz"
    : `uçuş öncesi planlama, kalkışa ${ufuk.kalkisa_kalan_saat.toFixed(1)} sa`;
  document.getElementById("kapsam-satiri").textContent =
    `Kapsam: yalnız seyir safhası (ToC–ToD); ${sonuc.ats ? `rota ağı: ${sonuc.ats.etiket}` : "ATS yolları dikkate alınmaz"}; ` +
    `trafik ayırması dikkate alınmaz${kullanim ? " · " + kullanim : ""}.`;

  const kaynakEl = document.getElementById("kaynak-etiketi");
  if (sonuc.ruzgar_verisi_kaynagi === "era5_gercek") {
    kaynakEl.textContent = "✓ Gerçek ERA5 rüzgar verisi";
    kaynakEl.className = "gercek";
  } else if (sonuc.ruzgar_verisi_kaynagi === "gfs_tahmin") {
    kaynakEl.textContent = "✓ Canlı NOAA GFS tahmin verisi";
    kaynakEl.className = "gercek";
  } else if (sonuc.ruzgar_verisi_kaynagi === "canli_veri_hazirlaniyor") {
    kaynakEl.textContent = "⏳ Canlı veri hazırlanıyor (rüzgarsız ön sonuç, otomatik yenilenecek)";
    kaynakEl.className = "kapsam-disi";
  } else if (sonuc.ruzgar_verisi_kaynagi === "canli_veri_alinamadi") {
    kaynakEl.textContent = "⚠ Canlı veri alınamadı (rüzgarsız tahmin)";
    kaynakEl.className = "kapsam-disi";
  } else {
    kaynakEl.textContent = "⚠ Kapsam dışı (rüzgarsız tahmin)";
    kaynakEl.className = "kapsam-disi";
  }
  document.getElementById("aciklama").textContent = sonuc.aciklama;

  document.getElementById("s-normal-sure").textContent = saniyeyiDkSaatOlarakYaz(sonuc.normal_rota.toplam_sure_dk);
  document.getElementById("s-optimize-sure").textContent = saniyeyiDkSaatOlarakYaz(sonuc.optimize_rota.toplam_sure_dk);
  document.getElementById("s-normal-mesafe").textContent = nmMetni(sonuc.normal_rota.mesafe_km);
  document.getElementById("s-optimize-mesafe").textContent = nmMetni(sonuc.optimize_rota.mesafe_km);
  document.getElementById("s-normal-ruzgar").textContent = ruzgarMetni(sonuc.normal_rota.ortalama_ruzgar_bileseni_kt);
  document.getElementById("s-optimize-ruzgar").textContent = ruzgarMetni(sonuc.optimize_rota.ortalama_ruzgar_bileseni_kt);
  document.getElementById("s-normal-yakit").textContent = sonuc.normal_rota.tahmini_yakit_kg.toFixed(0) + " kg";
  document.getElementById("s-optimize-yakit").textContent = sonuc.optimize_rota.tahmini_yakit_kg.toFixed(0) + " kg";
  document.getElementById("s-normal-co2").textContent = sonuc.normal_rota.tahmini_co2_kg.toFixed(0) + " kg";
  document.getElementById("s-optimize-co2").textContent = sonuc.optimize_rota.tahmini_co2_kg.toFixed(0) + " kg";
  const noxVar = sonuc.normal_rota.tahmini_nox_kg != null;
  document.getElementById("nox-satiri").style.display = noxVar ? "" : "none";
  if (noxVar) {
    document.getElementById("s-normal-nox").textContent = sonuc.normal_rota.tahmini_nox_kg.toFixed(1) + " kg";
    document.getElementById("s-optimize-nox").textContent = sonuc.optimize_rota.tahmini_nox_kg.toFixed(1) + " kg";
  }
  document.getElementById("s-normal-turbulans").textContent = riskMetni(sonuc.normal_rota);
  document.getElementById("s-optimize-turbulans").textContent = riskMetni(sonuc.optimize_rota);
  document.getElementById("s-normal-irtifa").textContent = flMetni(sonuc.normal_rota);
  document.getElementById("s-optimize-irtifa").textContent = flMetni(sonuc.optimize_rota);
  riskliBolumleriGoster(sonuc.optimize_rota);
  for (const [id, rota] of [["s-normal-iz", sonuc.normal_rota], ["s-optimize-iz", sonuc.optimize_rota]]) {
    document.getElementById(id).textContent =
      rota.iz_bulutu_nokta_sayisi == null ? "nem verisi yok" : `${rota.iz_bulutu_nokta_sayisi} nokta`;
  }
  for (const [id, rota] of [["s-normal-kisit", sonuc.normal_rota], ["s-optimize-kisit", sonuc.optimize_rota]]) {
    document.getElementById(id).textContent = `${rota.sigmet_ihlali_sayisi} / ${rota.kisitli_saha_ihlali_sayisi}`;
  }

  const stratejiEtiketleri = {
    yanal: "Strateji: yanal sapma (A*)",
    irtifa_yukari: "Strateji: tırmanma (irtifa artırıldı)",
    irtifa_asagi: "Strateji: alçalma (irtifa azaltıldı)",
    ats_alternatif: "Strateji: ATS ağında alternatif rota",
    yok: "",
  };
  const atsMetni = (noktalar) => noktalar
    .map((n) => (n.yol ? `${n.yol === "BAGLANTI" ? "(bağlantı rotası)" : n.yol} ` : "") +
      n.nokta.replace("<ToC>", "ToC").replace("<ToD>", "ToD"))
    .join(" ");
  const sapmaNm = (sonuc.optimize_rota.maks_yanal_sapma_km || 0) / NM_KM;
  document.getElementById("strateji-satiri").textContent =
    (stratejiEtiketleri[sonuc.kacinma_stratejisi] || "") +
    (sonuc.kacinma_stratejisi === "yanal" ? ` (${sapmaMetni(sapmaNm, sonuc.optimize_rota.maks_yanal_sapma_yonu)})` : "") +
    (sonuc.ats ? ` · FRA: ${atsMetni(sonuc.ats.optimize_rota)} (${sonuc.ats.kaynak})` : "") +
    (sonuc.ats?.uyarilar?.length ? ` · ⚠ ${sonuc.ats.uyarilar.join(" ")}` : "");

  // Önce GÜVENLİK durumu, sonra yakıt etkisi ayrı ayrı gösterilir -- ikisini
  // tek bir "iyi/kötü" yargısına karıştırmıyoruz (bkz. rota_optimizasyonu.py
  // dosya başlığındaki öncelik sırası notu).
  const tasarrufEl = document.getElementById("tasarruf-satiri");
  const co2Eki = Math.abs(sonuc.co2_farki_kg) > 0.5
    ? (sonuc.co2_farki_kg > 0 ? ` (${sonuc.co2_farki_kg.toFixed(0)} kg CO2 azaldı 🌱)` : ` (${Math.abs(sonuc.co2_farki_kg).toFixed(0)} kg CO2 arttı)`)
    : "";
  const yakitCumlesi = sonuc.yakit_tasarrufu_yuzde > 0.01
    ? `yakıt tasarrufu: %${sonuc.yakit_tasarrufu_yuzde.toFixed(2)}${co2Eki}`
    : sonuc.yakit_tasarrufu_yuzde < -0.01
      ? `ekstra yakıt: %${Math.abs(sonuc.yakit_tasarrufu_yuzde).toFixed(2)} (güvenlik için sapmanın bedeli)${co2Eki}`
      : `yakıt farkı yok`;

  const n = sonuc.normal_rota, o = sonuc.optimize_rota;
  const kisittanKacinildi = sonuc.sigmetten_kacinildi_mi || sonuc.kisitli_sahadan_kacinildi_mi;
  if (sonuc.guvenli_rota_bulundu_mu === false) {
    tasarrufEl.innerHTML = `<span class="tasarruf-yok">⚠ SIGMET ve kısıtlı sahalara girmeyen güvenli bir rota bulunamadı -- öneri yok.</span>`;
  } else if (kisittanKacinildi && !n.riskli_nokta_sayisi) {
    tasarrufEl.innerHTML = `<span class="tasarruf-iyi">✓ Sert kısıttan kaçınıldı</span> (SIGMET / kısıtlı saha ihlali ${n.sigmet_ihlali_sayisi} / ${n.kisitli_saha_ihlali_sayisi} → ${o.sigmet_ihlali_sayisi} / ${o.kisitli_saha_ihlali_sayisi}), ${yakitCumlesi}.` +
      (n.riskli_nokta_sayisi == null ? " Türbülans riski hesaplanmadı (rota veri kapsamı dışında)." : "");
  } else if (n.riskli_nokta_sayisi == null) {
    tasarrufEl.innerHTML = `<span class="tasarruf-yok">Türbülans riski hesaplanmadı (rota veri kapsamı dışında); bu, risk olmadığı anlamına gelmez.</span>`;
  } else if (n.riskli_nokta_sayisi === 0) {
    tasarrufEl.innerHTML = `<span class="tasarruf-yok">Rotada riskli türbülans tespit edilmedi -- iki rota aynı, ${yakitCumlesi}.</span>`;
  } else if (sonuc.optimize_rota.riskli_nokta_sayisi === 0) {
    tasarrufEl.innerHTML = `<span class="tasarruf-iyi">✓ Türbülanstan TAMAMEN kaçınıldı</span> (${riskMetni(n)} riskli bölüm atlatıldı), ${yakitCumlesi}.`;
  } else if (sonuc.turbulanstan_kacinildi_mi) {
    tasarrufEl.innerHTML = `<span class="tasarruf-yok">Kısmi kaçınma: ${riskMetni(n)} → ${riskMetni(o)} (tamamen atlatılamadı)</span>, ${yakitCumlesi}.`;
  } else {
    tasarrufEl.innerHTML = `<span class="tasarruf-yok">Türbülans verisi/rüzgar değerlendirilemedi.</span>`;
  }
  const refKars = sonuc.referans_karsilastirmasi;
  if (refKars && (refKars.ruzgar_kazanci || refKars.kacinma_bedeli)) {
    const isaretli = (deger, basamak) => (deger > 0 ? "+" : "") + deger.toFixed(basamak);
    const parcalar = [];
    if (refKars.ruzgar_kazanci) parcalar.push(`yalnız rüzgâr kazancı (büyük daireye göre): ${isaretli(refKars.ruzgar_kazanci.sure_dk, 1)} dk, %${isaretli(refKars.ruzgar_kazanci.yakit_yuzde, 2)} yakıt`);
    if (refKars.kacinma_bedeli) parcalar.push(`kaçınma bedeli (rüzgâr-optimum rotaya göre): ${isaretli(refKars.kacinma_bedeli.ek_sure_dk, 1)} dk, %${isaretli(refKars.kacinma_bedeli.ek_yakit_yuzde, 2)} yakıt`);
    tasarrufEl.innerHTML += `<br><small>${parcalar.join(" · ")}</small>`;
  }

  const secenekKutusu = document.getElementById("secenekler-kutusu");
  const secenekTablosu = document.getElementById("secenekler-tablosu");
  while (secenekTablosu.rows.length > 1) secenekTablosu.deleteRow(1);
  const secenekler = sonuc.secenekler || [];
  secenekKutusu.style.display = secenekler.length > 1 ? "block" : "none";
  for (const s of secenekler) {
    const satir = secenekTablosu.insertRow();
    const ad = ((s.strateji === "yok" && "Normal rota") || (s.strateji.startsWith("irtifa_yukari") && "Tırmanma") ||
      (s.strateji.startsWith("irtifa_asagi") && "Alçalma") || (s.strateji.startsWith("ats") && "ATS alternatif") ||
      "Yanal sapma") + ` (FL${Math.round(s.irtifa_ft / 100)})` + (s.onerilen ? " ✓" : "");
    const isaretli = (deger, basamak) => (deger > 0 ? "+" : "") + deger.toFixed(basamak);
    for (const metin of [ad, `${isaretli(s.ek_sure_dk, 1)} dk`, `%${isaretli(s.ek_yakit_yuzde, 1)}`, s.riskli_nokta_sayisi == null ? "hesaplanmadı" : String(s.riskli_nokta_sayisi)]) {
      satir.insertCell().textContent = metin;
    }
  }

  // Madde 6 (bkz. konuşma geçmişi): TI1'in tek başına doğrulanmadığı notu
  // sunucudan (turbulans_indeksleri.TI1_GUVENILIRLIK_NOTU) geldiği gibi
  // gösterilir -- metin değişirse arayüz otomatik güncellenir.
  document.getElementById("ti1-guvenilirlik-notu").textContent = sonuc.ti1_guvenilirlik_notu
    ? `⚠ ${sonuc.ti1_guvenilirlik_notu}`
    : "";

  kabinBildirimiGoster(sonuc);
  brifingKartiniGoster(sonuc);
}

// Brifing kartı: sunucunun ürettiği 3 satırlık özet (rota_optimizasyonu.brifing_karti).
function brifingKartiniGoster(sonuc) {
  const kutu = document.getElementById("brifing-karti");
  const satirlar = document.getElementById("brifing-satirlari");
  satirlar.replaceChildren(...(sonuc.brifing_karti || []).map((metin) => {
    const el = document.createElement("div");
    el.textContent = metin;
    return el;
  }));
  const fpl = sonuc.fpl_madde15;
  document.getElementById("fpl-dizgisi").textContent = fpl ? fpl.madde15 : "";
  document.getElementById("fpl-satiri").style.display = fpl ? "block" : "none";
  document.getElementById("fpl-satiri").title = fpl ? fpl.aciklama : "";
  const pencere = sonuc.kalkis_penceresi;
  const tablo = document.getElementById("kalkis-penceresi-tablosu");
  tablo.replaceChildren();
  if (pencere) {
    const baslik = tablo.insertRow();
    for (const metin of ["Kalkış", "Riskli (normal)", "Riskli (önerilen)", "Süre"]) baslik.insertCell().textContent = metin;
    const dk = (deger) => (deger == null ? "hesaplanmadı" : `${deger.toFixed(0)} dk`);
    for (const s of pencere.satirlar) {
      const satir = tablo.insertRow();
      const isaret = s.fark_saat === 0 ? "istenen" : `${s.fark_saat > 0 ? "+" : ""}${s.fark_saat} sa`;
      for (const metin of [`${s.kalkis_utc.slice(11, 16)}Z (${isaret})`, dk(s.normal_riskli_sure_dk), dk(s.optimize_riskli_sure_dk), dk(s.optimize_sure_dk)]) {
        satir.insertCell().textContent = metin;
      }
    }
  }
  document.getElementById("kalkis-penceresi-kutusu").style.display = pencere ? "block" : "none";
  document.getElementById("kalkis-penceresi-kutusu").title = pencere ? pencere.bilgi_notu : "";
  dikeyKesitiCiz(sonuc);
  kutu.style.display = satirlar.childElementCount ? "block" : "none";
}

// Dikey kesit: sunucunun hesapladığı seviye x mesafe TI1 ızgarası (rota_optimizasyonu.dikey_kesit).
function dikeyKesitiCiz(sonuc) {
  const kesit = sonuc.dikey_kesit;
  const kutu = document.getElementById("dikey-kesit-kutusu");
  if (!kesit) { kutu.style.display = "none"; return; }
  const tuval = document.getElementById("dikey-kesit");
  const ctx = tuval.getContext("2d");
  const sol = 34, satirSayisi = kesit.fl.length, sutunSayisi = kesit.mesafe_nm.length;
  const h = tuval.height / satirSayisi, g = (tuval.width - sol) / sutunSayisi;
  ctx.clearRect(0, 0, tuval.width, tuval.height);
  ctx.font = "9px sans-serif";
  kesit.fl.forEach((fl, i) => {
    const y = (satirSayisi - 1 - i) * h;
    ctx.fillStyle = "#9fb3c8";
    ctx.fillText(`FL${fl}`, 1, y + h - 2);
    const satir = kesit.ti1[i];
    for (let j = 0; j < sutunSayisi; j++) {
      const deger = satir ? satir[j] : null;
      ctx.fillStyle = deger == null ? "#444" : deger >= kesit.esik ? "#e74c3c" : deger >= kesit.esik / 2 ? "#e67e22" : "#2ecc71";
      ctx.fillRect(sol + j * g, y, Math.ceil(g), h - 1);
    }
    if (sonuc.optimize_rota && fl === sonuc.optimize_rota.fl) {
      ctx.strokeStyle = "#fff";
      ctx.strokeRect(sol, y + 0.5, tuval.width - sol - 1, h - 2);
    }
  });
  document.getElementById("dikey-kesit-notu").textContent =
    `0–${kesit.mesafe_nm[kesit.mesafe_nm.length - 1].toFixed(0)} NM; beyaz çerçeve önerilen seviye. ${kesit.aciklama}`;
  kutu.style.display = "block";
}

// Kabin önerisi yalnızca ÖNERİLEN rotada kalan risk varsa çıkar (metin sunucudan,
// rota_optimizasyonu.kabin_onerisi). Karar kaptanındır; sertifikalı EDR değildir.
function kabinBildirimiGoster(sonuc) {
  const el = document.getElementById("kabin-bildirimi");
  if (!sonuc.kabin_onerisi) { el.style.display = "none"; el.textContent = ""; return; }
  el.textContent = `🔔 ${sonuc.kabin_onerisi.metin} Karar destek amaçlıdır.`;
  el.style.display = "block";
}

let sonHedefEnlem = null, sonHedefBoylam = null, sonUcakModeli = null;

// Seviye bandı: tabanı-tavanı seçilen FL aralığıyla kesişmeyen SIGMET ve
// kısıtlı saha hacimleri gizlenir (yalnız görünüm; rota hesabını değiştirmez).
function hacimFiltresiniUygula() {
  if (!mevcutDataSource) return;
  const flMin = Number(document.getElementById("hacim-fl-min").value || 0);
  const flMax = Number(document.getElementById("hacim-fl-max").value || 600);
  const an = viewer.clock.currentTime;
  for (const varlik of mevcutDataSource.entities.values) {
    if (!varlik.polygon || !/^(sigmet|kisitli-saha)-/.test(varlik.id)) continue;
    const taban = (varlik.polygon.height ? varlik.polygon.height.getValue(an) : 0) / 0.3048 / 100;
    const tavan = (varlik.polygon.extrudedHeight ? varlik.polygon.extrudedHeight.getValue(an) : 1e9) / 0.3048 / 100;
    varlik.show = tavan >= flMin && taban <= flMax;
  }
}

let alternatifVarliklari = [];
function alternatifleriCiz(sonuc) {
  for (const v of alternatifVarliklari) viewer.entities.remove(v);
  alternatifVarliklari = [];
  if (!document.getElementById("secenekleri-ciz").checked) return;
  for (const s of sonuc.secenekler || []) {
    if (s.onerilen || s.strateji === "yok") continue;
    alternatifVarliklari.push(viewer.entities.add({
      name: `Alternatif: ${s.riskli_nokta_sayisi} riskli nokta, +${s.ek_sure_dk.toFixed(1)} dk`,
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArrayHeights(s.noktalar.flatMap((n) => [n.boylam, n.enlem, n.irtifa_m])),
        width: 2,
        material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.LIGHTGRAY.withAlpha(0.8) }),
      },
    }));
  }
}

async function sonucuSahneyeUygula(sonuc, kameraUcsunMu) {
  sonucPanelDoldur(sonuc);
  sonEkranSonucu = sonuc;

  if (mevcutDataSource) { viewer.dataSources.remove(mevcutDataSource, true); }
  const ds = await Cesium.CzmlDataSource.load(sonuc.czml);
  mevcutDataSource = ds;
  viewer.dataSources.add(ds);

  viewer.clock.startTime = ds.clock.startTime.clone();
  viewer.clock.stopTime = ds.clock.stopTime.clone();
  viewer.clock.currentTime = ds.clock.startTime.clone();
  viewer.clock.clockRange = Cesium.ClockRange.CLAMPED;
  viewer.clock.multiplier = ds.clock.multiplier;
  viewer.timeline.zoomTo(ds.clock.startTime, ds.clock.stopTime);
  viewer.clock.shouldAnimate = true;
  hacimFiltresiniUygula();
  alternatifleriCiz(sonuc);

  if (kameraUcsunMu) {
    // viewer.flyTo(ds) sadece varlığın O ANKİ (tek nokta) pozisyonuna göre
    // yakınlaşıyor -- rotanın tamamını değil, uçağın anlık konumunu
    // kapsıyor. Tüm rotayı (her iki hat) baştan gösterebilmek için, sunucudan
    // zaten aldığımız ham koordinatlardan bir dikdörtgen hesaplayıp ona uçuyoruz.
    const tumNoktalar = [...sonuc.normal_rota.noktalar, ...sonuc.optimize_rota.noktalar];
    const dikdortgen = Cesium.Rectangle.fromCartographicArray(
      tumNoktalar.map((n) => Cesium.Cartographic.fromDegrees(n.boylam, n.enlem))
    );
    await viewer.camera.flyTo({ destination: dikdortgen, duration: 2 });
  }

  document.getElementById("yeniden-hesapla-buton").style.display = "block";
}

let yenidenDenemeSayisi = 0;

function meydanlariEkle(govde, kalkisDahil) {
  if (govde.arama_uzayi !== "ats") return;
  for (const [alan, kimlik] of [["kalkis_meydani", "kalkis-meydani"], ["varis_meydani", "varis-meydani"]]) {
    const icao = document.getElementById(kimlik).value.trim().toUpperCase();
    if (icao && (kalkisDahil || alan === "varis_meydani")) govde[alan] = icao;
  }
}

async function simulasyonuCalistir() {
  const govde = {
    baslangic_enlem: Number(document.getElementById("baslangic-enlem").value),
    baslangic_boylam: Number(document.getElementById("baslangic-boylam").value),
    bitis_enlem: Number(document.getElementById("bitis-enlem").value),
    bitis_boylam: Number(document.getElementById("bitis-boylam").value),
    irtifa_ft: Number(document.getElementById("irtifa-ft").value),
    zaman: document.getElementById("zaman").value + ":00",
    ucak_modeli: document.getElementById("ucak-modeli").value,
    arama_uzayi: document.getElementById("arama-uzayi").value,
    kalkis_penceresi: document.getElementById("kalkis-penceresi").checked,
  };
  meydanlariEkle(govde, true);
  const anahtar = anahtarAl();
  if (!anahtar) { durumGoster("API anahtarı gerekli.", "hata"); return; }
  if (!govde.ucak_modeli) { durumGoster("Uçak modeli listesi yüklenemedi -- API anahtarını kontrol et.", "hata"); return; }
  sessionStorage.setItem("tr_api_anahtari", anahtar);

  const buton = document.getElementById("simule-et-buton");
  buton.disabled = true;
  durumGoster("Hesaplanıyor (gerçek ERA5 rüzgar verisi okunuyor)...", "bilgi");
  try {
    const sonuc = await apiIste("/api/v1/simulasyon/rota", { method: "POST", body: JSON.stringify(govde) });
    sonHedefEnlem = govde.bitis_enlem;
    sonHedefBoylam = govde.bitis_boylam;
    sonUcakModeli = govde.ucak_modeli;
    await sonucuSahneyeUygula(sonuc, true);
    durumGoster(`Yüklendi (${sonuc.ucak_etiketi}).`, "bilgi");
    // Canlı GFS henüz inmediyse sunucu rüzgarsız ön sonuç döner ve indirmeyi
    // arka planda sürdürür; veri hazır olunca hesap kendiliğinden tekrarlanır.
    if (sonuc.ruzgar_verisi_kaynagi === "canli_veri_hazirlaniyor" && (yenidenDenemeSayisi += 1) <= 12) {
      setTimeout(simulasyonuCalistir, 10000);
    } else if (sonuc.ruzgar_verisi_kaynagi !== "canli_veri_hazirlaniyor") {
      yenidenDenemeSayisi = 0;
    }
  } catch (e) {
    if (e.durumKodu === 401) durumGoster("API anahtarı geçersiz.", "hata");
    else if (e.durumKodu === 400 || e.durumKodu === 422) durumGoster("Geçersiz girdi: " + e.message, "hata");
    else durumGoster("Hata: " + e.message, "hata");
  } finally {
    buton.disabled = false;
  }
}

// DİNAMİK ROTA GÜNCELLEME: simülasyon oynarken uçağın O ANKİ (interpolasyonla
// bulunan) konumunu YENİ başlangıç noktası olarak alıp, AYNI hedefe, AYNI
// gerçek backend'i (rota_optimizasyonu.py -- A* + irtifa karşılaştırması)
// yeniden çağırır. Uydurma bir "anlık meteorolojik değişiklik" simülasyonu
// DEĞİLDİR -- gerçek bir yeniden-planlama çağrısıdır; ERA5 veri küpü sabit
// olduğu için (statik bir dosya) sonuç çoğu zaman benzer çıkar, ama mekanizma
// GERÇEKTİR ve gerçek zamanlı hava durumu akışına bağlanmaya hazırdır.
async function ucusSirasindaYenidenHesapla() {
  if (!mevcutDataSource || sonHedefEnlem === null) return;
  const optimizeVarligi = mevcutDataSource.entities.getById("optimize-rota");
  if (!optimizeVarligi) return;

  const suAnkiZaman = viewer.clock.currentTime;
  const konum = optimizeVarligi.position.getValue(suAnkiZaman);
  if (!konum) { durumGoster("Şu anki uçak konumu okunamadı.", "hata"); return; }
  const cografi = Cesium.Cartographic.fromCartesian(konum);

  const govde = {
    baslangic_enlem: Cesium.Math.toDegrees(cografi.latitude),
    baslangic_boylam: Cesium.Math.toDegrees(cografi.longitude),
    bitis_enlem: sonHedefEnlem,
    bitis_boylam: sonHedefBoylam,
    irtifa_ft: cografi.height / 0.3048,
    zaman: Cesium.JulianDate.toIso8601(suAnkiZaman).slice(0, 19),
    ucak_modeli: sonUcakModeli,
    arama_uzayi: document.getElementById("arama-uzayi").value,
  };
  meydanlariEkle(govde, false);

  const buton = document.getElementById("yeniden-hesapla-buton");
  buton.disabled = true;
  durumGoster("Uçuş sırasında yeniden hesaplanıyor (o anki konumdan hedefe)...", "bilgi");
  try {
    const sonuc = await apiIste("/api/v1/simulasyon/rota", { method: "POST", body: JSON.stringify(govde) });
    await sonucuSahneyeUygula(sonuc, true);
    durumGoster("Rota, uçağın o anki konumundan itibaren yeniden hesaplandı.", "bilgi");
  } catch (e) {
    durumGoster("Yeniden hesaplama hatası: " + e.message, "hata");
  } finally {
    buton.disabled = false;
  }
}

let senaryolar = [];

async function senaryolariYukle() {
  try {
    const yanit = await fetch(new URL("veri/senaryolar.json", location.href).href);
    if (!yanit.ok) return;
    senaryolar = await yanit.json();
  } catch (e) {
    return;
  }
  const secim = document.getElementById("senaryo");
  for (const s of senaryolar) {
    const secenek = document.createElement("option");
    secenek.value = s.kimlik;
    secenek.textContent = s.ad;
    secim.appendChild(secenek);
  }
}

function senaryoyuUygula() {
  const s = senaryolar.find(x => x.kimlik === document.getElementById("senaryo").value);
  document.getElementById("senaryo-aciklamasi").textContent = s ? s.aciklama : "";
  if (!s) return;
  for (const [kimlik, deger] of Object.entries(s.alanlar)) document.getElementById(kimlik).value = deger;
}

document.getElementById("senaryo").addEventListener("change", senaryoyuUygula);
senaryolariYukle();
document.getElementById("giris-anahtar").value = sessionStorage.getItem("tr_api_anahtari") || "";
document.getElementById("giris-anahtar").addEventListener("change", ucakProfilleriniYukle);
document.getElementById("simule-et-buton").addEventListener("click", simulasyonuCalistir);
document.getElementById("yeniden-hesapla-buton").addEventListener("click", ucusSirasindaYenidenHesapla);
if (anahtarAl()) ucakProfilleriniYukle();
for (const id of ["hacim-fl-min", "hacim-fl-max"]) {
  document.getElementById(id).addEventListener("change", hacimFiltresiniUygula);
}
document.getElementById("secenekleri-ciz").addEventListener("change", () => sonEkranSonucu && alternatifleriCiz(sonEkranSonucu));
