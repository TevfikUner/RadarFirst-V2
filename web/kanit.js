"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";

function el(etiket, ozellikler, ...cocuklar) {
  const dugum = document.createElement(etiket);
  for (const [ad, deger] of Object.entries(ozellikler || {})) {
    if (ad === "sinif") dugum.className = deger;
    else dugum.setAttribute(ad, deger);
  }
  for (const cocuk of cocuklar.flat()) {
    if (cocuk === null || cocuk === undefined) continue;
    dugum.append(cocuk instanceof Node ? cocuk : String(cocuk));
  }
  return dugum;
}

function svgEl(etiket, ozellikler, ...cocuklar) {
  const dugum = document.createElementNS(SVG_NS, etiket);
  for (const [ad, deger] of Object.entries(ozellikler || {})) dugum.setAttribute(ad, deger);
  for (const cocuk of cocuklar.flat()) {
    if (cocuk === null || cocuk === undefined) continue;
    dugum.append(cocuk instanceof Node ? cocuk : String(cocuk));
  }
  return dugum;
}

function sayi(deger, hane = 3) {
  if (deger === null || deger === undefined || Number.isNaN(deger)) return "—";
  return Number(deger).toLocaleString("tr-TR", { minimumFractionDigits: hane, maximumFractionDigits: hane });
}

function isaretli(deger, hane = 3) {
  if (deger === null || deger === undefined) return "—";
  return (deger > 0 ? "+" : deger < 0 ? "−" : "") + sayi(Math.abs(deger), hane);
}

function gaMetni(ga, hane = 3, fonk = sayi) {
  return ga && ga.length === 2 ? `%95 GA [${fonk(ga[0], hane)}; ${fonk(ga[1], hane)}]` : "GA kaynakta yok";
}

function yuzde(deger, hane = 1) {
  return deger === null || deger === undefined ? "—" : "%" + sayi(deger * 100, hane);
}

function tarih(iso) {
  if (!iso) return "bilinmiyor";
  const t = new Date(iso);
  return Number.isNaN(t.getTime()) ? iso : t.toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

function karo(etiket, deger, ga) {
  return el("div", { sinif: "karo" }, el("div", { sinif: "etiket" }, etiket), el("div", { sinif: "deger" }, deger), ga ? el("div", { sinif: "ga" }, ga) : null);
}

function kaynakSatiri(kart) {
  const satirlar = [
    el("div", {}, "Betik: ", el("code", {}, kart.betik)),
    el("div", {}, "Kaynak dosya: ", el("code", {}, kart.kaynak), kart.depoda ? null : el("span", { sinif: "rozet" }, "depo dışı çıktı")),
  ];
  if (kart.veri) satirlar.push(el("div", {}, "Veri: " + kart.veri));
  if (kart.durum === "tamam") {
    satirlar.push(
      el("div", {}, `Üretim: ${tarih(kart.uretim_zamani)}${kart.uretim_zamani_kaynagi ? " (" + kart.uretim_zamani_kaynagi + ")" : ""} · Commit: `,
        el("code", {}, kart.commit || "kaynakta yok"))
    );
  }
  return el("div", { sinif: "kaynak" }, satirlar);
}

function kartKabugu(baslik, soru, kart, icerikFonk) {
  const govde = el("section", { sinif: "kart" }, el("h2", {}, baslik), el("p", { sinif: "soru" }, soru));
  if (!kart) {
    govde.append(el("p", { sinif: "hata" }, "Kaynak bulunamadı: kanit.json bu kartı içermiyor."));
    return govde;
  }
  if (kart.durum === "kaynak_bulunamadi") {
    govde.append(el("p", { sinif: "hata" }, `Kaynak bulunamadı: ${kart.kaynak} yok; sayı gösterilmiyor.`));
  } else if (kart.durum !== "tamam") {
    govde.append(el("p", { sinif: "hata" }, `Kaynak okunamadı (${kart.kaynak}): ${kart.hata || kart.durum}`));
  } else {
    try {
      govde.append(icerikFonk(kart));
    } catch (hata) {
      console.error(hata);
      govde.append(el("p", { sinif: "hata" }, `Kart çizilemedi: ${hata.message}`));
    }
  }
  govde.append(kaynakSatiri(kart));
  return govde;
}

function rocCiz(kart) {
  const G = 340, Y = 300, sol = 44, alt = 36, ust = 10, sag = 12;
  const gx = (v) => sol + v * (G - sol - sag);
  const gy = (v) => ust + (1 - v) * (Y - ust - alt);
  const svg = svgEl("svg", { viewBox: `0 0 ${G} ${Y}`, width: G, height: Y, role: "img", "aria-label": "TI1 ROC eğrisi" });
  for (const v of [0, 0.25, 0.5, 0.75, 1]) {
    svg.append(svgEl("line", { x1: gx(0), x2: gx(1), y1: gy(v), y2: gy(v), stroke: "var(--izgara)", "stroke-width": 1 }));
    svg.append(svgEl("text", { x: sol - 6, y: gy(v) + 4, "text-anchor": "end" }, sayi(v, 2)));
    svg.append(svgEl("text", { x: gx(v), y: Y - alt + 16, "text-anchor": "middle" }, sayi(v, 2)));
  }
  svg.append(svgEl("text", { x: gx(0.5), y: Y - 4, "text-anchor": "middle" }, "POFD (yanlış alarm oranı)"));
  svg.append(svgEl("text", { x: 12, y: gy(0.5), "text-anchor": "middle", transform: `rotate(-90 12 ${gy(0.5)})` }, "POD (yakalama)"));
  svg.append(svgEl("line", { x1: gx(0), y1: gy(0), x2: gx(1), y2: gy(1), stroke: "var(--referans)", "stroke-dasharray": "4 4", "stroke-width": 1 }));
  const noktalar = [[0, 0], ...kart.roc_noktalari, [1, 1]];
  svg.append(svgEl("polyline", { points: noktalar.map(([x, y]) => `${gx(x)},${gy(y)}`).join(" "), fill: "none", stroke: "var(--seri)", "stroke-width": 2, "stroke-linejoin": "round" }));
  for (const [x, y] of kart.roc_noktalari) {
    const g = svgEl("g", {}, svgEl("title", {}, `POFD ${sayi(x)} · POD ${sayi(y)}`));
    g.append(svgEl("circle", { cx: gx(x), cy: gy(y), r: 8, fill: "transparent" }));
    g.append(svgEl("circle", { cx: gx(x), cy: gy(y), r: 3, fill: "var(--seri)", stroke: "var(--kart)", "stroke-width": 2 }));
    svg.append(g);
  }
  const e = kart.esik;
  const ge = svgEl("g", {}, svgEl("title", {}, `${e.ad} = ${e.deger}: POD ${sayi(e.pod)} · POFD ${sayi(e.pofd)}`));
  ge.append(svgEl("circle", { cx: gx(e.pofd), cy: gy(e.pod), r: 6, fill: "none", stroke: "var(--metin)", "stroke-width": 2 }));
  ge.append(svgEl("text", { x: gx(e.pofd) + 9, y: gy(e.pod) + 14, fill: "var(--metin)" }, `rota eşiği ${e.deger}`));
  svg.append(ge);
  return svg;
}

function pirepIcerik(k) {
  const ti1 = k.skorlar.find((s) => s.ad === "TI1");
  const model = k.skorlar.find((s) => s.ad === "Model");
  const tablo = el("table", {},
    el("tr", {}, el("th", {}, "Skor"), el("th", { sinif: "sayi" }, "ROC-AUC"), el("th", { sinif: "sayi" }, "%95 GA (gün bloklu)")),
    k.skorlar.map((s) => el("tr", {}, el("td", {}, s.ad), el("td", { sinif: "sayi" }, sayi(s.roc_auc)), el("td", { sinif: "sayi" }, `[${sayi(s.roc_auc_ga[0])}; ${sayi(s.roc_auc_ga[1])}]`)))
  );
  return el("div", {},
    el("div", { sinif: "karolar" },
      ti1 ? karo("TI1 ROC-AUC (rotada kullanılan)", sayi(ti1.roc_auc), gaMetni(ti1.roc_auc_ga)) : null,
      model ? karo("ML modeli ROC-AUC (rotaya girmez)", sayi(model.roc_auc), gaMetni(model.roc_auc_ga)) : null,
      karo(`Rota eşiğinde yakalama (POD)`, sayi(k.esik.pod), `TI1 ≥ ${k.esik.deger}`),
      karo(`Rota eşiğinde yanlış alarm (POFD)`, sayi(k.esik.pofd), `FAR ${sayi(k.esik.far)}`),
      karo("Test raporu / gün", `${k.test.rapor.toLocaleString("tr-TR")} / ${k.test.gun}`, `${k.test.orta_ustu.toLocaleString("tr-TR")} orta ve üstü`)
    ),
    el("div", { sinif: "iki-sutun" },
      el("div", {}, rocCiz(k), el("div", { sinif: "ga" , style: "font-size:11px;color:var(--ikincil)" }, k.roc_aciklamasi + "; daire = rota eşiği.")),
      el("div", {}, tablo,
        el("p", { sinif: "okuma" },
          `Test: ${k.test_yontemi}, ${k.test.rapor.toLocaleString("tr-TR")} PIREP, ${k.test.gun} gün (eğitimde kullanılmadı). `
          + `Tüm veri ${k.tum_veri.rapor.toLocaleString("tr-TR")} PIREP, ${k.tum_veri.gun} gün. AUC 0,5 = şans, 1 = kusursuz.`))
    )
  );
}

function aralikCiz(satirlar, { min, max, referans, eksenAdi, adGenisligi = 200, bicim = sayi, isaretler = null }) {
  const G = 560, satirY = 30, ust = 8, alt = 34;
  const Y = ust + satirlar.length * satirY + alt;
  const sol = adGenisligi, sag = 16;
  const gx = (v) => sol + ((Math.min(Math.max(v, min), max) - min) / (max - min)) * (G - sol - sag);
  const svg = svgEl("svg", { viewBox: `0 0 ${G} ${Y}`, width: G, height: Y, role: "img", "aria-label": eksenAdi });
  for (const v of isaretler || [0, 1, 2, 3, 4].map((i) => min + (i * (max - min)) / 4)) {
    svg.append(svgEl("line", { x1: gx(v), x2: gx(v), y1: ust, y2: Y - alt, stroke: "var(--izgara)", "stroke-width": 1 }));
    svg.append(svgEl("text", { x: gx(v), y: Y - alt + 14, "text-anchor": "middle" }, bicim(v, 2)));
  }
  svg.append(svgEl("line", { x1: gx(referans), x2: gx(referans), y1: ust, y2: Y - alt, stroke: "var(--referans)", "stroke-dasharray": "4 4", "stroke-width": 1.5 }));
  svg.append(svgEl("text", { x: gx((min + max) / 2), y: Y - 4, "text-anchor": "middle" }, eksenAdi));
  satirlar.forEach((s, i) => {
    const y = ust + i * satirY + satirY / 2;
    svg.append(svgEl("text", { x: sol - 10, y: y + 4, "text-anchor": "end", fill: s.vurgu ? "var(--metin)" : "var(--ikincil)" }, s.ad));
    if (s.deger === null || s.deger === undefined) {
      svg.append(svgEl("text", { x: sol + 4, y: y + 4 }, s.not || "değer yok"));
      return;
    }
    const g = svgEl("g", {}, svgEl("title", {}, `${s.ad}: ${bicim(s.deger)}${s.ga ? " " + gaMetni(s.ga, 3, bicim) : ""}`));
    g.append(svgEl("rect", { x: sol, y: y - satirY / 2, width: G - sol - sag, height: satirY, fill: "transparent" }));
    if (s.ga) g.append(svgEl("line", { x1: gx(s.ga[0]), x2: gx(s.ga[1]), y1: y, y2: y, stroke: "var(--seri)", "stroke-width": 2, "stroke-linecap": "round" }));
    g.append(svgEl("circle", { cx: gx(s.deger), cy: y, r: s.vurgu ? 6 : 4.5, fill: "var(--seri)", stroke: "var(--kart)", "stroke-width": 2 }));
    svg.append(g);
  });
  return svg;
}

function backtestIcerik(k) {
  const sutun = (s) => el("div", { sinif: "karo", style: "min-width:0" },
    el("div", { style: "font-weight:600;margin-bottom:8px" }, s.ad),
    el("table", {},
      el("tr", {}, el("th", {}, ""), el("th", { sinif: "sayi" }, "Büyük daire"), el("th", { sinif: "sayi" }, "Önerilen (A*)")),
      el("tr", {}, el("td", {}, "Tüpteki rapor (orta+ / hafif-yok)"), el("td", { sinif: "sayi" }, `${s.bd_tupu[0]} / ${s.bd_tupu[1]}`), el("td", { sinif: "sayi" }, `${s.astar_tupu[0]} / ${s.astar_tupu[1]}`)),
      el("tr", {}, el("td", {}, "Türbülanslı (orta+) pay"), el("td", { sinif: "sayi" }, yuzde(s.bd_payi)), el("td", { sinif: "sayi" }, yuzde(s.astar_payi)))
    ),
    el("div", { sinif: "karolar", style: "margin:10px 0 0" },
      karo("Pay oranı (A* / büyük daire)", sayi(s.pay_orani, 2), "iki paydan bölüm · GA kaynakta yok"),
      karo("Göreli odds oranı (GMO)", sayi(s.gmo, 2), gaMetni(s.gmo_ga, 2))
    ),
    el("div", { style: "font-size:11.5px;color:var(--ikincil)" }, `${s.rota.toLocaleString("tr-TR")} sapmalı rota · ${s.gun} gün`)
  );
  const [birincil, tum] = k.surumler;
  return el("div", {},
    el("div", { sinif: "iki-sutun" }, k.surumler.map(sutun)),
    el("div", { style: "margin-top:12px" },
      aralikCiz(k.surumler.map((s, i) => ({ ad: s.ad.split(" (")[0], deger: s.gmo, ga: s.gmo_ga, vurgu: i === 0 })),
        { min: 0.4, max: 1.4, referans: 1, isaretler: [0.4, 0.6, 0.8, 1.0, 1.2, 1.4], eksenAdi: "GMO (1 = fark yok; < 1 önerilen rota daha az türbülanslı)", adGenisligi: 170 })
    ),
    el("p", { sinif: "okuma" },
      `Tüp: rota noktasına ${sayi(k.tup.yaricap_km, 0)} km, ±${sayi(k.tup.irtifa_ft, 0)} ft, ±${sayi(k.tup.zaman_saat, 0)} sa içindeki IEM PIREP'leri; `
      + `PIREP'ler rota kararına girmez. ${k.esik_gunu_sayisi} eşik günü TI1 eşiğinin seçildiği PIREP'leri içerdiği için birincil sonuçtan çıkarıldı. `
      + `Birincil: önerilen rotanın türbülanslı payı %${sayi(birincil.astar_payi * 100, 1)}, büyük dairenin %${sayi(birincil.bd_payi * 100, 1)} `
      + `(pay oranı ${sayi(birincil.pay_orani, 2)}); GMO ${sayi(birincil.gmo, 2)} ${gaMetni(birincil.gmo_ga, 2)}. `
      + `Eşik günleri dahil edilince GA 1'i kapsıyor (${gaMetni(tum.gmo_ga, 2)}). Raporlama yanlılığı giderilmez; tek bölge (NE-ABD).`)
  );
}

function sigmetIcerik(k) {
  const satirlar = k.kayitlar.map((r) => ({ ad: `${r.ad} · ${tarih(r.baslangic).slice(0, 10)}`, deger: r.fark, not: "bant dışı, değerlendirilmedi" }));
  satirlar.push({ ad: `Ortalama (${k.sigmet} SIGMET)`, deger: k.ortalama_fark, ga: k.ga, vurgu: true });
  const tablo = el("table", {},
    el("tr", {}, el("th", {}, "SIGMET"), el("th", { sinif: "sayi" }, "İçeride riskli"), el("th", { sinif: "sayi" }, "Halkada riskli"), el("th", { sinif: "sayi" }, "Fark")),
    k.kayitlar.map((r) => el("tr", {}, el("td", {}, r.ad), el("td", { sinif: "sayi" }, yuzde(r.iceride)), el("td", { sinif: "sayi" }, yuzde(r.halka)), el("td", { sinif: "sayi" }, r.fark === null ? "bant dışı" : isaretli(r.fark))))
  );
  return el("div", {},
    el("div", { sinif: "karolar" },
      karo("İçeride − halka (riskli oran farkı)", isaretli(k.ortalama_fark), gaMetni(k.ga, 3, isaretli)),
      karo("Fark pozitif SIGMET", `${k.pozitif_sigmet} / ${k.sigmet}`, null),
      karo("Okuma (ön kayıtlı kural)", k.okuma || "—", null)
    ),
    el("div", { sinif: "iki-sutun" },
      aralikCiz(satirlar, { min: -0.1, max: 0.1, referans: 0, eksenAdi: "TI1 riskli oran farkı (içeride − 300 km halka)", adGenisligi: 190, bicim: isaretli }),
      tablo
    ),
    el("p", { sinif: "okuma" }, "Türk TURB SIGMET'lerinin içinde TI1 riskli oranı çevresindeki halkadan yüksek mi? Keşifsel; SIGMET sayısı az olduğu için istatistiksel güç düşük. GA sıfırı kapsıyor: fark gösterilemedi.")
  );
}

function sanalPirepIcerik(k) {
  const oran = (o) => `${o.isabet} / ${o.degerlendirilebilir}`;
  return el("div", {},
    el("div", { sinif: "karolar" },
      karo("Sanal PIREP yakalama (POD)", oran(k.pod), gaMetni(k.pod.guven_araligi_95, 2)),
      karo("Sanal PIREP yanlış alarm (POFD)", oran(k.pofd), gaMetni(k.pofd.guven_araligi_95, 2))
    ),
    el("p", { sinif: "okuma" }, "ADS-B izinden türbülans olayı çıkarma (sanal PIREP) gerçek PIREP'lerle sınandı. Örneklem çok küçük; sonuç ön bulgudur ve rota kararına girmez.")
  );
}

async function yukle() {
  const ustNot = document.getElementById("ust-not");
  const kutu = document.getElementById("kartlar");
  let veri;
  try {
    const yanit = await fetch(new URL("veri/kanit.json", location.href).href, { cache: "no-cache" });
    if (!yanit.ok) throw new Error(`HTTP ${yanit.status}`);
    veri = await yanit.json();
  } catch (hata) {
    ustNot.textContent = "";
    ustNot.append(el("span", { sinif: "hata" }, `veri/kanit.json yüklenemedi (${hata.message}). Üretmek için: turbulans-kanit-paneli`));
    console.error("kanit.json yüklenemedi", hata);
    return;
  }
  const k = veri.kartlar || {};
  ustNot.textContent = `Sayılar mevcut sonuç dosyalarından derlendi (turbulans-kanit-paneli · ${tarih(veri.olusturma_zamani)} · commit ${veri.derleme_commit || "bilinmiyor"}). Elle yazılmış sayı yok; yeni hesap yapılmadı.`;
  kutu.append(
    kartKabugu("1 · PIREP doğrulaması", "Sistemin türbülans göstergesi, eğitimde görmediği günlerde pilot raporlarını ne kadar ayırt ediyor?", k.pirep_dogrulamasi, pirepIcerik),
    kartKabugu("2 · Rota testi (bağımsız kanıt)", "Önerilen rota, düz (büyük daire) rotaya göre pilotların türbülans bildirdiği yerlerden daha az mı geçiyor?", k.rota_backtest, backtestIcerik),
    kartKabugu("3 · Türkiye SIGMET alan deneyi", "Türk meteoroloji uyarılarının (TURB SIGMET) içinde sistem daha çok risk görüyor mu?", k.sigmet_alan, sigmetIcerik),
    kartKabugu("4 · Sanal PIREP (ADS-B) ön sınaması", "Uçak izlerinden türbülans olayı çıkarılabilir mi?", k.sanal_pirep, sanalPirepIcerik)
  );
  if (veri.uyari) document.getElementById("altbilgi").textContent = veri.uyari;
}

yukle();
