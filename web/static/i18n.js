/* Client-side EN/TH toggle for static UI copy (not news content, which stays
   in its original language). Persists the choice in localStorage so it
   carries across page navigations on every page that includes this script. */
(function () {
  const DICT = {
    th: {
      "nav.home": "หน้าแรก",
      "nav.news": "ข่าว",
      "nav.daily_summary": "สรุปรายวัน",
      "nav.metrics": "เมทริก",
      "nav.correlations": "ความสัมพันธ์",
      "nav.headlines_tracked": "ข่าวที่ติดตาม",
      "nav.search_placeholder": "ค้นหาสัญลักษณ์ บริษัท หรือข่าว...",

      "home.latest_headlines": "ข่าวล่าสุด",
      "home.view_all_news": "ดูข่าวทั้งหมด →",
      "home.no_news": "ยังไม่มีข่าวในช่วงเวลานี้",
      "home.trending": "🔥 ติดเทรนด์",
      "home.headlines_today_suffix": "ข่าววันนี้",
      "home.top_gainers": "📈 บวกมากสุด",
      "home.top_losers": "📉 ลบมากสุด",

      "toolbar.prices": "ราคา:",
      "toolbar.news": "ข่าว:",
      "toolbar.senti": "เซนติเมนต์:",
      "toolbar.to": "ถึง",
      "toolbar.asset": "สินทรัพย์:",

      "news.date": "วันที่",
      "news.time": "เวลา",
      "news.ticker": "สัญลักษณ์",
      "news.impact": "ผลกระทบ",
      "news.detail": "รายละเอียด",
      "news.sentiment": "เซนติเมนต์",
      "news.source": "แหล่งข่าว:",
      "news.results_for": "ผลการค้นหาสำหรับ",

      "pagination.page": "หน้า",
      "pagination.of": "จาก",
      "pagination.previous": "« ก่อนหน้า",
      "pagination.next": "ถัดไป »",

      "metrics.date": "วันที่",
      "metrics.ticker": "สัญลักษณ์",
      "metrics.open": "เปิด",
      "metrics.close": "ปิด",
      "metrics.return_1d": "ผลตอบแทน 1 วัน",
      "metrics.sentiment_index": "ดัชนีเซนติเมนต์",
      "metrics.news_count": "จำนวนข่าว",

      "nav.predict": "สัญญาณ",
      "nav.watchlist": "รายการเฝ้าดู",

      "corr.title": "การวิเคราะห์สหสัมพันธ์",
      "corr.supporting_title": "หลักฐานประกอบ — ไม่ใช่ผลลัพธ์หลัก",
      "corr.supporting_desc": "ตัวเลขในหน้านี้เป็นสถิติเชิงพรรณนา ค่าสหสัมพันธ์บอกได้แค่ว่าข้อมูลสองชุดเคลื่อนไหวไปด้วยกันในช่วงเวลาหนึ่ง แต่ไม่ได้บอกว่าความสัมพันธ์นั้นเสถียรหรือใช้ตัดสินใจได้จริง หากต้องการดูว่าโมเดลทำนายอะไร ทำได้ดีแค่ไหนกับข้อมูลที่ไม่เคยเห็น และผลนั้นคงเส้นคงวาข้ามช่วงเวลาหรือไม่ ให้ดูที่แท็บ Signal หน้านี้เก็บไว้เพราะเป็นเอกสารประกอบความสัมพันธ์ที่งานสร้างโมเดลตั้งอยู่บนนั้น โดยระบุขนาดตัวอย่าง ช่วงความเชื่อมั่น และการปรับค่าจากการทดสอบหลายครั้งไว้อย่างเปิดเผย",

      "corr.ticker": "สัญลักษณ์",
      "corr.corr_t": "สหสัมพันธ์ T",
      "corr.lag1": "แล็ก 1",
      "corr.lag1_ci": "ช่วงเชื่อมั่น 95% (แล็ก 1)",
      "corr.q_lag1": "q-value (FDR)",
      "corr.lag2": "แล็ก 2",
      "corr.n": "N (T/L1/L2)",
      "corr.low_n": "(N น้อย)",
      "corr.pooled_title": "ค่าประมาณรวม (ทุกสัญลักษณ์, fixed effects)",
      "corr.pooled_n": "N",
      "corr.pooled_tickers": "สัญลักษณ์",
      "corr.pooled_insufficient": "ข้อมูลที่ทับซ้อนกันระหว่างสัญลักษณ์ยังไม่พอ",

      "daily.back": "กลับ Dashboard",
      "daily.title": "สรุปข่าวประจำวัน",

      "vol.title": "แนวโน้มความผันผวน",
      "vol.badge": "ชนะเส้นฐานของตัวเอง",
      "vol.desc": "คาดการณ์ว่าสินทรัพย์นี้จะเคลื่อนไหว \"แรงแค่ไหน\" ไม่ใช่ \"ไปทางไหน\" เพราะทิศทางทำนายไม่ได้ในข้อมูลชุดนี้ (ดูผลด้านล่าง) แต่ขนาดของการเคลื่อนไหวทำนายได้ วัดจาก 30 สินทรัพย์ตั้งแต่ปี 2006 พบว่าผลตอบแทนรายวันแทบไม่มีความต่อเนื่อง ขณะที่ความผันผวนมีสูงมาก",
      "vol.current": "ปัจจุบัน (20 วัน, ต่อปี)",
      "vol.next": "อีก",
      "vol.days": "วันทำการข้างหน้า",
      "vol.range": "ช่วงที่พบบ่อย",
      "vol.evidence": "ทำไมตัวเลขนี้ถึงเชื่อถือได้",
      "vol.evidence_desc": "เส้นฐานที่ใช้เทียบไม่ใช่ศูนย์ แต่เป็นการทำนายฟรีที่ว่า \"ช่วงหน้าเท่ากับตอนนี้\" ซึ่งไม่ต้องใช้โมเดลเลย ค่า skill มากกว่า 0 แปลว่าโมเดลชนะการทำนายฟรีนั้น วัดบนช่วงเวลาที่โมเดลไม่เคยเห็น",
      "vol.horizon": "ช่วงเวลา",
      "vol.model_r2": "R² โมเดล",
      "vol.persist_r2": "R² ทำนายฟรี",
      "vol.skill": "Skill",
      "vol.typ_err": "ค่าคลาดเคลื่อนทั่วไป",
      "vol.days_short": "วัน",
      "vol.caveat": "กันข้อมูลไว้ทดสอบตั้งแต่วันที่ระบุเป็นต้นไป ทุก fold ของ walk-forward ชนะการทำนายฟรีทั้งสองช่วงเวลา และ 29 จาก 30 สินทรัพย์ชนะเมื่อแยกดูรายตัว (ยกเว้น THB/USD) หน้าต่างอนาคตของวันติดกันซ้อนทับกัน ขนาดตัวอย่างที่แท้จริงจึงน้อยกว่าจำนวนแถว แต่กระทบทั้งโมเดลและเส้นฐานเท่ากัน การเปรียบเทียบจึงยังใช้ได้",

      "nav.fundamentals": "งบการเงิน",
      "fund.title": "งบการเงิน",
      "fund.desc": "ข้อมูลงบการเงินรายไตรมาส ดึงตรงจากการยื่นต่อ SEC EDGAR — ย้อนหลังได้ถึง 19 ปีต่อบริษัท ไม่ใช่แค่ 5-7 ไตรมาสแบบ API ราคาตลาดทั่วไป",
      "fund.insufficient": "ไม่มีข้อมูลงบการเงินจาก EDGAR สำหรับสินทรัพย์นี้ — อาจเป็นดัชนี ค่าเงิน สินค้าโภคภัณฑ์ หรือคริปโต ซึ่งไม่ได้ยื่นงบต่อ SEC",
      "fund.quarters_since": "ไตรมาส นับตั้งแต่",
      "fund.latest_revenue": "รายได้ไตรมาสล่าสุด",
      "fund.yoy": "เทียบปีก่อน",
      "fund.latest_net_income": "กำไรสุทธิ",
      "fund.net_margin": "มาร์จิ้นสุทธิ",
      "fund.latest_eps": "กำไรต่อหุ้น (Diluted)",
      "fund.latest_fcf": "กระแสเงินสดอิสระ",
      "fund.revenue_trend": "แนวโน้มรายได้รายไตรมาส (ล่าสุด",
      "fund.period_end": "สิ้นงวด",
      "fund.announced": "วันประกาศ",
      "fund.revenue": "รายได้",
      "fund.yoy_col": "เทียบปีก่อน",
      "fund.net_income_col": "กำไรสุทธิ",
      "fund.eps": "EPS",
      "fund.gross_margin": "มาร์จิ้นขั้นต้น",
      "fund.net_margin_col": "มาร์จิ้นสุทธิ",
      "fund.debt": "หนี้สินรวม",
      "fund.fcf": "กระแสเงินสดอิสระ",

      "nav.company": "ข้อมูลบริษัท",
      "co.title": "ข้อมูลบริษัท",
      "co.desc": "ทุกอย่างในแท็บนี้มาจากเอกสารที่บริษัทยื่นต่อ ก.ล.ต. สหรัฐฯ (SEC) โดยตรง คำอธิบายธุรกิจคือ Item 1 ของรายงานประจำปีฉบับล่าสุด (แบบ 10-K) ซึ่งเป็นคำอธิบายที่บริษัทเขียนเองและยื่นตามข้อบังคับทางกฎหมาย ไม่ใช่บทสรุปจากบุคคลที่สาม ทุกส่วนมีลิงก์ไปยังเอกสารต้นฉบับ",
      "co.no_registrant": "สินทรัพย์นี้ไม่ได้จดทะเบียนกับ SEC — ดัชนี ค่าเงิน สินค้าโภคภัณฑ์ และคริปโตไม่ได้ยื่นเอกสารต่อ SEC จึงไม่มีข้อมูลบริษัทให้แสดง นี่เป็นคุณสมบัติของสินทรัพย์ ไม่ใช่ข้อมูลขาดหาย",
      "co.sic_label": "การจัดประเภทอุตสาหกรรมโดย SEC",
      "co.former_names": "ชื่อเดิม",
      "co.fact_cik": "เลขทะเบียน CIK",
      "co.fact_exchanges": "จดทะเบียนซื้อขายที่",
      "co.fact_incorporated": "รัฐที่จดทะเบียนบริษัท",
      "co.fact_fye": "วันสิ้นปีบัญชี (เดือน-วัน)",
      "co.fact_filer": "ประเภทผู้ยื่น",
      "co.fact_hq": "สำนักงานใหญ่",
      "co.business_title": "บริษัททำอะไร — Item 1, Business",
      "co.source_10k": "ที่มา: แบบ 10-K ยื่นวันที่",
      "co.business_note": "คัดลอกตามต้นฉบับ เลขที่เอกสาร",
      "co.business_chars": "ตัวอักษร",
      "co.business_reflow": "จัดย่อหน้าใหม่เพื่อให้อ่านง่าย ไม่มีการแก้ถ้อยคำใด ๆ",
      "co.read_full": "อ่านฉบับเต็ม",
      "co.more_paragraphs": "ย่อหน้าที่เหลือ",
      "co.business_unavailable": "เอกสารฉบับนี้ไม่ได้ใช้หัวข้อ \"Item 1. Business\" ในเนื้อเอกสารในรูปแบบที่ค้นหาได้ ระบบจึงไม่ดึงข้อความออกมา แทนที่จะเสี่ยงแสดงหัวข้อผิด ตัวเอกสารมีลิงก์อยู่ด้านบนและมีคำอธิบายธุรกิจอยู่ครบ",
      "co.filings_title": "เอกสารที่ยื่นต่อ SEC ล่าสุด",
      "co.filings_desc": "แต่ละแถวลิงก์ไปยังเอกสารหลักบน sec.gov",
      "co.filings_all": "ดูเอกสารทั้งหมดบน EDGAR",
      "co.filing_form": "แบบฟอร์ม",
      "co.filing_filed": "วันที่ยื่น",
      "co.filing_accession": "เลขที่เอกสาร",
      "co.filing_doc": "เอกสาร",
      "co.filing_open": "เปิดบน sec.gov →",
      "co.fetched": "ดึงข้อมูลจาก SEC EDGAR เมื่อ",
    },
  };

  function applyLang(lang) {
    document.documentElement.setAttribute("lang", lang === "th" ? "th" : "en");
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!el.dataset.i18nOrig) el.dataset.i18nOrig = el.textContent;
      if (lang === "th" && DICT.th[key]) {
        el.textContent = DICT.th[key];
      } else {
        el.textContent = el.dataset.i18nOrig;
      }
    });
    document.querySelectorAll("[data-i18n-suffix]").forEach((el) => {
      const key = el.getAttribute("data-i18n-suffix");
      if (!el.dataset.i18nOrig) el.dataset.i18nOrig = el.textContent;
      if (lang === "th" && DICT.th[key]) {
        // Keep the leading dynamic number, swap only the trailing label text.
        const num = el.dataset.i18nNum || "";
        el.textContent = num + " " + DICT.th[key];
      } else {
        el.textContent = el.dataset.i18nOrig;
      }
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (!el.dataset.i18nOrigPlaceholder) el.dataset.i18nOrigPlaceholder = el.placeholder;
      el.placeholder = (lang === "th" && DICT.th[key]) ? DICT.th[key] : el.dataset.i18nOrigPlaceholder;
    });
    document.querySelectorAll(".lang-btn[data-lang]").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-lang") === lang);
    });
    try {
      localStorage.setItem("fs_lang", lang);
    } catch (e) {}
  }

  window.setLang = applyLang;

  document.addEventListener("DOMContentLoaded", function () {
    let saved = "en";
    try {
      saved = localStorage.getItem("fs_lang") || "en";
    } catch (e) {}
    applyLang(saved);
  });
})();
