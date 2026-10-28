if (!window.maplibregl) {
  document.body.insertAdjacentHTML("afterbegin", '<div style="padding:16px;color:#e74c3c">MapLibre yüklenemedi: web/vendor eksik (turbulans-statik ile indirin).</div>');
  throw new Error("MapLibre yok");
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

async function apiIste(yol, yontem) {
  const anahtar = anahtarAl();
  const yanit = await fetch(API_TABANI + yol, { method: yontem || "GET", headers: { "X-API-Key": anahtar } });
  if (!yanit.ok) {
    let detay = yanit.statusText;
    // FastAPI'nin 422 yanıtlarında 'detail' bir metin değil, Pydantic
    // doğrulama hatalarının LİSTESİ olur -- düz metne çevrilmezse
    // "[object Object]" gibi anlamsız bir hata gösterilir.
    try {
      const govde = await yanit.json();
      if (Array.isArray(govde.detail)) detay = govde.detail.map(d => d.msg || JSON.stringify(d)).join("; ");
      else if (govde.detail) detay = govde.detail;
    } catch (e) {}
    const hata = new Error(detay);
    hata.durumKodu = yanit.status;
    throw hata;
  }
  // DELETE 204 No Content döner -- gövde parse edilemez, boş nesne yeterli.
  if (yanit.status === 204) return {};
  return yanit.json();
}

function turbulansRengi(ti1, esikler) {
  if (ti1 === null || ti1 === undefined) return "#95a5a6";
  if (ti1 < esikler.ti1_esik_hafif) return "#2ecc71";
  if (ti1 < esikler.ti1_esik_orta_siddetli) return "#e67e22";
  return "#e74c3c";
}

let harita, esikler = { ti1_esik_hafif: 4e-7, ti1_esik_orta_siddetli: 7e-7 };
let tumNoktalar = [];

function haritayiHazirla() {
  harita = new maplibregl.Map({
    container: "harita",
    style: {
      version: 8,
      // Altlık: sunucudan gelen sade ülke sınırları (Natural Earth, kamu
      // malı) -- İNTERNETSİZ de görünür; Esri karoları (ALTLIK_KATMANI=esri)
      // yüklenince üste eklenir, bağlantı yoksa gelmezler ama harita boş kalmaz.
      sources: {
        "ulke-sinirlari": { type: "geojson", data: new URL("veri/ulke_sinirlari.geojson", location.href).href },
      },
      layers: [
        { id: "arka-plan", type: "background", paint: { "background-color": "#16222e" } },
        { id: "ulke-sinirlari", type: "line", source: "ulke-sinirlari", paint: { "line-color": "#7f95a8", "line-width": 0.8 } },
      ],
    },
    center: [30, 40],
    zoom: 4,
    pitch: 30,
    projection: { type: "globe" },
  });
  // GERÇEK TARAYICI TESTİYLE BULUNAN HATA: setProjection()'ı constructor'dan
  // SONRA çağırmak "Style is not done loading" hatası veriyordu (stil henüz
  // asenkron yüklenmemişken projeksiyon değiştirilemiyor) -- bu yüzden
  // "globe" doğrudan yukarıdaki constructor seçeneğine taşındı. Yine de
  // CDN'den beklenmedik bir sürüm gelirse sayfa çökmesin diye harita "load"
  // olayında bir savunmacı deneme daha yapılıyor.
  harita.once("load", () => {
    try { harita.setProjection({ type: "globe" }); } catch (e) { console.warn("globe projeksiyonu kullanılamadı", e); }
    esriKatmaniniEkle();
  });
  harita.addControl(new maplibregl.NavigationControl());
}

async function esriKatmaniniEkle() {
  let ayarlar = {};
  try {
    const yanit = await fetch("/harita-ayarlari");
    if (yanit.ok) ayarlar = await yanit.json();
  } catch (e) {}
  if (ayarlar.altlik_katmani !== "esri") return;
  harita.addSource("esri-yol", {
    type: "raster",
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}"],
    tileSize: 256,
    attribution: "Tiles &copy; Esri",
  });
  const katmanlar = harita.getStyle().layers;
  const sonraki = katmanlar[katmanlar.findIndex(k => k.id === "ulke-sinirlari") + 1];
  harita.addLayer({ id: "esri-yol", type: "raster", source: "esri-yol" }, sonraki && sonraki.id);
}

function rotaKatmaniniGuncelle(noktalar) {
  const cizgi = {
    type: "Feature", geometry: { type: "LineString", coordinates: noktalar.map(n => [n.boylam, n.enlem]) },
  };
  const noktaKoleksiyonu = {
    type: "FeatureCollection",
    features: noktalar.map(n => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [n.boylam, n.enlem] },
      properties: { renk: turbulansRengi(n.ti1_indeksi, esikler), zaman: n.zaman, ti1: n.ti1_indeksi },
    })),
  };

  if (harita.getSource("rota-cizgi")) {
    harita.getSource("rota-cizgi").setData(cizgi);
    harita.getSource("rota-noktalari").setData(noktaKoleksiyonu);
  } else {
    harita.addSource("rota-cizgi", { type: "geojson", data: cizgi });
    harita.addLayer({ id: "rota-cizgi", type: "line", source: "rota-cizgi",
      paint: { "line-color": "#3388ff", "line-width": 2, "line-opacity": 0.6 } });

    harita.addSource("rota-noktalari", { type: "geojson", data: noktaKoleksiyonu });
    harita.addLayer({ id: "rota-noktalari", type: "circle", source: "rota-noktalari",
      paint: {
        "circle-radius": 6, "circle-color": ["get", "renk"],
        "circle-stroke-width": 1, "circle-stroke-color": "#000",
      } });

    harita.on("click", "rota-noktalari", (e) => {
      const p = e.features[0].properties;
      const ti1Metni = p.ti1 !== null ? Number(p.ti1).toExponential(2) + " s^-2" : "veri yok";
      new maplibregl.Popup().setLngLat(e.lngLat)
        .setHTML(`<b>Saat:</b> ${new Date(p.zaman).toISOString().slice(11,16)}<br><b>TI1:</b> ${ti1Metni}`)
        .addTo(harita);
    });
  }

  if (noktalar.length) {
    const enlemler = noktalar.map(n => n.enlem), boylamlar = noktalar.map(n => n.boylam);
    harita.fitBounds([[Math.min(...boylamlar), Math.min(...enlemler)], [Math.max(...boylamlar), Math.max(...enlemler)]],
      { padding: 60, maxZoom: 8 });
  }
}

function sigmetKatmaniniGuncelle(sigmetler) {
  const koleksiyon = {
    type: "FeatureCollection",
    features: sigmetler.map(s => ({
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [s.poligon.map(([lat, lon]) => [lon, lat]).concat([[s.poligon[0][1], s.poligon[0][0]]])] },
      properties: { etiket: s.etiket },
    })),
  };
  if (harita.getSource("sigmetler")) {
    harita.getSource("sigmetler").setData(koleksiyon);
  } else {
    harita.addSource("sigmetler", { type: "geojson", data: koleksiyon });
    harita.addLayer({ id: "sigmetler-dolgu", type: "fill", source: "sigmetler",
      paint: { "fill-color": "#ffcc00", "fill-opacity": 0.25 } });
    harita.addLayer({ id: "sigmetler-cizgi", type: "line", source: "sigmetler",
      paint: { "line-color": "#ffcc00", "line-width": 2 } });
  }
}

// Seviye bandı (FL) filtresi: irtifası bilinmeyen noktalar yalnızca bant
// varsayılandayken (FL0-600) gösterilir. Oynatma, noktaların gerçek zaman
// damgalarıyla ilerler (100 ms'de hız x 0,1 sn uçuş süresi).
let oynatmaZamanlayicisi = null;

function seviyeFiltresi() {
  const seyir = document.getElementById("yalniz-seyir").checked;
  const flMin = seyir ? 280 : Number(document.getElementById("fl-min").value || 0);
  const flMax = seyir ? 420 : Number(document.getElementById("fl-max").value || 600);
  const varsayilan = flMin <= 0 && flMax >= 600;
  return (n) => {
    if (n.irtifa_m === null || n.irtifa_m === undefined) return varsayilan;
    const fl = n.irtifa_m / 0.3048 / 100;
    return fl >= flMin && fl <= flMax;
  };
}

function filtreyiUygula() {
  oynatmayiDurdur();
  zamanKaydiricisiniHazirla(tumNoktalar.filter(seviyeFiltresi()));
}

function oynatmayiDurdur() {
  if (oynatmaZamanlayicisi) clearInterval(oynatmaZamanlayicisi);
  oynatmaZamanlayicisi = null;
  document.getElementById("oynat-buton").textContent = "▶";
}

function zamanKaydiricisiniHazirla(noktalar) {
  const kontrolDiv = document.getElementById("zaman-kontrolu");
  const kaydirici = document.getElementById("zaman-kaydirici");
  const etiket = document.getElementById("zaman-etiketi");
  if (!noktalar.length) {
    kontrolDiv.style.display = "none";
    rotaKatmaniniGuncelle([]);
    return;
  }

  kontrolDiv.style.display = "flex";
  kaydirici.min = 0; kaydirici.max = noktalar.length - 1; kaydirici.value = noktalar.length - 1;

  const guncelle = () => {
    const i = Number(kaydirici.value);
    etiket.textContent = new Date(noktalar[i].zaman).toISOString().slice(11, 16);
    rotaKatmaniniGuncelle(noktalar.slice(0, i + 1));
  };
  kaydirici.oninput = () => { oynatmayiDurdur(); guncelle(); };
  document.getElementById("oynat-buton").onclick = () => {
    if (oynatmaZamanlayicisi) { oynatmayiDurdur(); return; }
    if (Number(kaydirici.value) >= noktalar.length - 1) kaydirici.value = 0;
    let anlik = new Date(noktalar[Number(kaydirici.value)].zaman).getTime();
    document.getElementById("oynat-buton").textContent = "⏸";
    oynatmaZamanlayicisi = setInterval(() => {
      anlik += Number(document.getElementById("oynatma-hizi").value) * 100;
      let i = Number(kaydirici.value);
      while (i < noktalar.length - 1 && new Date(noktalar[i + 1].zaman).getTime() <= anlik) i++;
      kaydirici.value = i;
      guncelle();
      if (i >= noktalar.length - 1) oynatmayiDurdur();
    }, 100);
  };
  guncelle();
}

async function ucusuYukle() {
  const ucus = document.getElementById("giris-ucus").value.trim();
  const tarih = document.getElementById("giris-tarih").value.trim();
  const anahtar = anahtarAl();
  if (!ucus || !tarih || !anahtar) {
    durumGoster("Uçuş numarası, tarih ve API anahtarı gerekli.", "hata");
    return;
  }
  sessionStorage.setItem("tr_api_anahtari", anahtar);

  durumGoster("Yükleniyor...", "bilgi");
  try {
    esikler = await apiIste("/api/v1/esikler");
    if (esikler.ti1_guvenilirlik_notu) {
      document.getElementById("ti1-guvenilirlik-notu").textContent = `⚠ ${esikler.ti1_guvenilirlik_notu}`;
    }
    const detay = await apiIste(`/api/v1/ucuslar/${encodeURIComponent(ucus)}/${tarih}?olcum_limit=5000`);
    tumNoktalar = detay.olcumler;
    rotaKatmaniniGuncelle(tumNoktalar.filter(seviyeFiltresi()));
    filtreyiUygula();
    durumGoster(`${detay.toplam_olcum_sayisi} nokta yüklendi.`, "bilgi");
    kayitliUcuslariListele();
    modelBilgisiniGetirVeGoster();

    try {
      const sigmet = await apiIste(`/api/v1/ucuslar/${encodeURIComponent(ucus)}/${tarih}/sigmet-dogrulama`);
      sigmetKatmaniniGuncelle(sigmet.sigmetler);
      if (sigmet.toplam_turbulans_sigmeti === 0) {
        durumGoster(durumEl().textContent + "\nSIGMET: bu bölge/tarih için ABD arşivinde kayıt yok (beklenen bir durum, bkz. sigmet_dogrulama.py).", "bilgi");
      } else {
        durumGoster(durumEl().textContent + `\nSIGMET: ${sigmet.toplam_turbulans_sigmeti} türbülans uyarısı, ${sigmet.sigmetle_ortusen_nokta_sayisi}/${sigmet.orta_siddetli_nokta_sayisi} nokta örtüşüyor.`, "bilgi");
      }
    } catch (e) {
      console.warn("SIGMET doğrulaması alınamadı", e);
    }
  } catch (e) {
    if (e.durumKodu === 401) durumGoster("API anahtarı geçersiz.", "hata");
    else if (e.durumKodu === 404) durumGoster("Uçuş bulunamadı. Önce POST /api/v1/analiz/ucus ile analiz tetikle.", "hata");
    else durumGoster("Hata: " + e.message, "hata");
  }
}

function durumEl() { return document.getElementById("durum"); }

async function ucusuSil() {
  const ucus = document.getElementById("giris-ucus").value.trim();
  const tarih = document.getElementById("giris-tarih").value.trim();
  if (!ucus || !tarih) {
    durumGoster("Silmek için uçuş numarası ve tarih gerekli.", "hata");
    return;
  }
  if (!confirm(`'${ucus}' / ${tarih} kaydı (tüm ölçümleriyle) kalıcı olarak silinsin mi?`)) return;

  try {
    await apiIste(`/api/v1/ucuslar/${encodeURIComponent(ucus)}/${tarih}`, "DELETE");
    durumGoster(`'${ucus}' / ${tarih} silindi.`, "bilgi");
    if (harita.getSource("rota-cizgi")) {
      rotaKatmaniniGuncelle([]);
      document.getElementById("zaman-kontrolu").style.display = "none";
    }
    kayitliUcuslariListele();
  } catch (e) {
    if (e.durumKodu === 404) durumGoster("Silinecek uçuş bulunamadı.", "hata");
    else durumGoster("Silme hatası: " + e.message, "hata");
  }
}

async function kayitliUcuslariListele() {
  const liste = document.getElementById("kayitli-ucuslar-listesi");
  const arama = document.getElementById("ucuslar-arama").value.trim();
  if (!anahtarAl()) { liste.textContent = "Önce API anahtarını gir."; return; }

  liste.textContent = "Yükleniyor...";
  try {
    const parametreler = new URLSearchParams({ limit: "20" });
    if (arama) parametreler.set("ucus_numarasi_arama", arama);
    const { toplam_sayi, ucuslar } = await apiIste(`/api/v1/ucuslar?${parametreler}`);
    if (!ucuslar.length) { liste.textContent = "Kayıtlı uçuş yok."; return; }

    liste.innerHTML = toplam_sayi > ucuslar.length
      ? `<div style="color:#999; padding:2px 6px">${ucuslar.length}/${toplam_sayi} gösteriliyor</div>` : "";
    for (const u of ucuslar) {
      const satir = document.createElement("div");
      satir.append(metinSpan(u.ucus_numarasi), metinSpan(u.tarih, "color:#999"));
      satir.title = "Yüklemek için tıkla";
      satir.addEventListener("click", () => {
        document.getElementById("giris-ucus").value = u.ucus_numarasi;
        document.getElementById("giris-tarih").value = u.tarih;
        ucusuYukle();
      });
      liste.appendChild(satir);
    }
  } catch (e) {
    liste.textContent = "Hata: " + e.message;
  }
}

async function modelBilgisiniGetirVeGoster() {
  const govde = document.getElementById("model-bilgisi-govde");
  try {
    const bilgi = await apiIste("/api/v1/turbulans/model-bilgisi");
    if (!bilgi.egitildi_mi) {
      govde.innerHTML = `<span style="color:#999">Model henüz eğitilmedi (bkz. GET /api/v1/ml/durum).</span>`;
      return;
    }
    if (bilgi.kullanimda === false) {
      const not = document.createElement("span");
      not.style.color = "#e67e22";
      not.textContent = bilgi.uyari;
      govde.replaceChildren(not);
      return;
    }
    const m = bilgi.metrikler;
    const altin = bilgi.altin_gun_ozeti;
    const aralik = ([d, a, u], isaret = "") => `${isaret && d > 0 ? "+" : ""}${d.toFixed(3)} [${a.toFixed(3)}–${u.toFixed(3)}]`;
    const satirlar = [["Seçilen model", bilgi.secilen_model]];
    if (altin) {
      satirlar.push(
        [`ROC-AUC (${altin.gun} test günü)`, aralik(altin.model_roc_auc)],
        ["TI1 ROC-AUC (aynı günler)", aralik(altin.ti1_roc_auc)],
      );
      if (altin.model_eksi_ti1) satirlar.push(["TI1'e göre fark", aralik(altin.model_eksi_ti1, "±")]);
    } else {
      satirlar.push(["ROC-AUC (çapraz doğrulama)", m.roc_auc.toFixed(3)]);
    }
    satirlar.push(
      ["Eğitim örneklemi", bilgi.egitim_orneklem_sayisi],
      ["Not", "PIREP verilmiş noktalara göre; olasılık mutlak türbülans sıklığı değildir"],
    );
    // Konformal belirsizlik (ml/belirsizlik.py): holdout'ta ölçülen kapsama ve
    // "belirsiz" denen tahminlerin oranı.
    const konformal = bilgi.konformal && bilgi.konformal.holdout_dogrulamasi;
    if (konformal) {
      const yuzde = (x) => `%${(100 * x).toFixed(0)}`;
      satirlar.push(["Kapsama (hedef)", `${yuzde(konformal.kapsama)} (${yuzde(konformal.hedef_kapsama)})`]);
      satirlar.push(["Belirsiz oranı", yuzde(konformal.belirsiz_orani)]);
    }
    govde.replaceChildren(...satirlar.map(([etiket, deger]) => {
      const satir = document.createElement("div");
      satir.className = "satir";
      const etiketEl = metinSpan(etiket);
      etiketEl.className = "etiket";
      satir.append(etiketEl, metinSpan(deger));
      return satir;
    }));
  } catch (e) {
    govde.replaceChildren(metinSpan("Model bilgisi alınamadı: " + e.message, "color:#999"));
  }
}

// Sunucudan/veritabanından gelen metin HTML olarak DEĞİL düz metin olarak
// eklenir (innerHTML'e gömmek XSS'e açık olurdu).
function metinSpan(metin, stil) {
  const el = document.createElement("span");
  el.textContent = String(metin);
  if (stil) el.style.cssText = stil;
  return el;
}

async function canliUyarilariDinle() {
  const anahtar = anahtarAl();
  if (!anahtar) return;
  // Anahtar URL'ye yazılmaz (loglanır): önce 60 sn'lik bilet alınır.
  let bilet;
  try {
    const yanit = await fetch(API_TABANI + "/api/v1/ws-bileti", { method: "POST", headers: { "X-API-Key": anahtar } });
    if (!yanit.ok) return;
    bilet = (await yanit.json()).bilet;
  } catch (e) {
    return;
  }
  const protokol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protokol}//${location.host}/ws/uyarilar?bilet=${encodeURIComponent(bilet)}`);
  ws.onmessage = (olay) => {
    const veri = JSON.parse(olay.data);
    const toast = document.getElementById("uyari-toast");
    if (veri.tip === "turbulans_uyarisi") {
      toast.textContent = `🚨 ${veri.ucus_numarasi} (${veri.tarih}): ${veri.orta_siddetli_nokta_sayisi} orta-şiddetli nokta, maks TI1 ${Number(veri.maks_ti1).toExponential(2)}`;
    } else if (veri.tip === "sanal_pirep") {
      toast.textContent = `✈ Sanal PIREP: ${veri.ucus_numarasi || veri.ucak}, FL${Math.round(veri.seviye_ft / 100)} ` +
        `${veri.enlem.toFixed(2)}, ${veri.boylam.toFixed(2)} — ${veri.sapma_ft} ft sapma, ${veri.ucak_sayisi} uçak doğruladı (ADS-B, EDR değil)`;
    } else {
      return;
    }
    toast.style.display = "block";
    setTimeout(() => { toast.style.display = "none"; }, 8000);
  };
  ws.onerror = () => console.warn("Canlı uyarı WebSocket bağlantısı kurulamadı.");
}

document.getElementById("giris-anahtar").value = sessionStorage.getItem("tr_api_anahtari") || "";
document.getElementById("yukle-buton").addEventListener("click", () => { ucusuYukle(); canliUyarilariDinle(); });
document.getElementById("sil-buton").addEventListener("click", ucusuSil);
document.getElementById("ucuslar-arama-buton").addEventListener("click", kayitliUcuslariListele);
document.getElementById("ucuslar-arama").addEventListener("keydown", (e) => { if (e.key === "Enter") kayitliUcuslariListele(); });
haritayiHazirla();
if (anahtarAl()) { kayitliUcuslariListele(); modelBilgisiniGetirVeGoster(); }
for (const id of ["fl-min", "fl-max", "yalniz-seyir"]) {
  document.getElementById(id).addEventListener("change", filtreyiUygula);
}
