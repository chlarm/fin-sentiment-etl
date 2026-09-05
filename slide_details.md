# Slide Detail: การพัฒนาระบบท่อส่งข้อมูลอัตโนมัติและคลังข้อมูลเพื่อวิเคราะห์ความสัมพันธ์ระหว่างข่าวเศรษฐกิจและราคาหลักทรัพย์
**เวลาพรีเซนต์:** 20 นาที | **จำนวนสไลด์:** 30 สไลด์

> ## ⚠️ ปรับปรุง 5 ก.ย. 2026 — อ่านก่อนใช้
>
> ไฟล์นี้เขียนเมื่อ ก.ค. 2026 เนื้อหาบางส่วนไม่ตรงกับระบบและผลการวิจัยปัจจุบัน
>
> | ประเด็น | เดิม | ปัจจุบัน |
> |---|---|---|
> | URL เว็บบน Cloud Run | ใช้งานได้ | **ตอบ HTTP 500** — แคปหน้าจอจาก `http://localhost:8000` แทน |
> | จำนวนสินทรัพย์ | 7 | **30** |
> | หน้าต่างข่าว | 168 ชม. (7 วัน) | **2,160 ชม. (90 วัน)** |
> | แท็บ Dashboard | 5 (มี Heatmap) | **7** (ถอด Heatmap เพิ่ม Signal, Fundamentals) |
> | ผล Correlation | "รอข้อมูลสะสมแล้วจะสรุปได้" | **ข้อมูลพอแล้ว — ผลเป็นลบ** |
>
> ข้อสรุปปัจจุบัน: ทั้ง sentiment และงบการเงิน **ไม่แสดงความสัมพันธ์กับผลตอบแทน**
> ที่รอดการตรวจสอบ 3 ชั้น (ค่าผิดปกติ / นอกกลุ่มตัวอย่าง / ขนาดตัวอย่างจริง)
> รายละเอียดใน `thesis_methodology_revised.md`

---


---

## สไลด์ 1 — ปกวิทยานิพนธ์
**เวลา:** ~0:30 นาที

**หัวข้อหลัก (Title):**
การพัฒนาระบบท่อส่งข้อมูลอัตโนมัติและคลังข้อมูลเพื่อวิเคราะห์ความสัมพันธ์ระหว่างข่าวเศรษฐกิจและราคาหลักทรัพย์
*(Development of Automated Data Pipeline and Data Warehouse for Financial Market and News Sentiment Analysis)*

**ข้อมูลบนสไลด์:**
- ผู้จัดทำ: นายเอเชีย อ่อนพรม รหัสนักศึกษา 66070324
- อาจารย์ที่ปรึกษา: ผศ.ดร.กนกวรรณ อัจฉริยะชาญวณิช
- สาขาวิชา: วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ
- คณะเทคโนโลยีสารสนเทศ สจล.
- ภาคเรียนที่ 2 ปีการศึกษา 2568

**Tips ออกแบบ:** ใส่ logo KMITL, สีหลักของ IT Faculty, ฟอนต์สวยงามเป็นทางการ

---

## สไลด์ 2 — Agenda / สารบัญ
**เวลา:** ~0:30 นาที

**หัวข้อหลัก:** Overview of Presentation

**เนื้อหา:**
| # | บท | หัวข้อ |
|---|-----|--------|
| 01 | บทที่ 1 | บทนำ — ที่มา วัตถุประสงค์ ขอบเขต |
| 02 | บทที่ 2 | ทบทวนวรรณกรรม — FinBERT, ETL, Star Schema, GCP |
| 03 | บทที่ 3 | วิธีดำเนินการวิจัย — สถาปัตยกรรม, Pipeline, Database, Dashboard |
| 04 | บทที่ 4 | ผลการทดลอง — GCP results, Sentiment, Correlation |
| 05 | บทที่ 5 | บทสรุป — Findings, Limitations, Future Work |

**Tips:** ทำ numbered icon ให้ดูสะอาดตา ไฮไลต์บทปัจจุบันเมื่อพรีเซนต์แต่ละส่วน

---

## สไลด์ 3 — ที่มาและความสำคัญ
**เวลา:** ~0:45 นาที | **บทที่ 1**

**หัวข้อหลัก:** ทำไมถึงทำโปรเจกต์นี้?

**Key Messages (3 ประเด็น):**

1. **ตลาดทุนกำลังเติบโต**
   - นักลงทุนรายย่อยมีสัดส่วนมูลค่าซื้อขาย **28.98%** ของตลาดหลักทรัพย์ไทย (ธ.ค. 2568)
   - ดัชนีความเชื่อมั่นนักลงทุน FETCO อยู่ที่ **102.67** (ธ.ค. 2568)

2. **ข่าวสารทางการเงินเป็นปัญหา**
   - ข่าวมีปริมาณมหาศาล อัปเดตรวดเร็ว กระจายหลายแหล่ง
   - Reuters Digital News Report 2025: ผู้ตอบแบบสอบถาม **40%** หลีกเลี่ยงข่าวเพราะข้อมูลล้น
   - ผู้คนเผชิญ **Information Overload** → ตัดสินใจลงทุนด้วย bias

3. **Human Limitation**
   - มนุษย์ไม่สามารถติดตามข่าวหลายแหล่งพร้อมกันและวิเคราะห์ได้ทันเวลา
   - เกิด **Information Lag** → พลาดโอกาสการลงทุน

**Visual แนะนำ:** infographic 3 column หรือ problem–gap–solution diagram

---

## สไลด์ 4 — วัตถุประสงค์ของโครงงาน
**เวลา:** ~0:45 นาที | **บทที่ 1**

**หัวข้อหลัก:** 5 วัตถุประสงค์

**เนื้อหา:**

| # | วัตถุประสงค์ | คีย์เวิร์ด |
|---|-------------|-----------|
| 1 | พัฒนาระบบ **Automated ETL Pipeline** ดึงราคาสินทรัพย์ + ข่าวรายวัน | Extract, Schedule, Automate |
| 2 | ประยุกต์ใช้โมเดล Deep Learning **FinBERT** วิเคราะห์ Sentiment ข่าวการเงิน (Positive / Negative / Neutral) | NLP, Classification |
| 3 | ออกแบบ **Data Warehouse แบบ Star Schema** บน PostgreSQL รองรับ OLAP | Data Modeling |
| 4 | Deploy ระบบบน **GCP แบบ Serverless** (Cloud Run + Cloud SQL + Cloud Scheduler) รองรับ Scalability | Cloud, Infra |
| 5 | พัฒนา **Web Dashboard** สำหรับ Data Visualization เพื่อสนับสนุนการตัดสินใจ | Dashboard, Decision Support |

**Tips:** แสดงเป็น 5 card หรือ numbered list พร้อม icon ประกอบแต่ละข้อ

---

## สไลด์ 5 — ขอบเขตของโครงงาน
**เวลา:** ~0:45 นาที | **บทที่ 1**

**หัวข้อหลัก:** ระบบครอบคลุมอะไรบ้าง?

**4 ขอบเขตหลัก:**

**1. สินทรัพย์เป้าหมาย (Multi-Asset Class — 30 รายการ)**
- US Equity (21): AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, NFLX, AMD, ORCL, INTC, JPM, V, JNJ, XOM, PG, KO, WMT, HD, DIS, BA
- Index (3): S&P 500 (^GSPC), Dow Jones (^DJI), Nasdaq (^IXIC)
- Cryptocurrency (2): Bitcoin (BTC-USD), Ethereum (ETH-USD)
- Forex (2): EUR/USD, THB/USD
- Commodity (2): Gold Futures (GC=F), WTI Crude (CL=F)

**2. แหล่งข้อมูล**
- ราคา: Yahoo Finance (Primary) → Stooq (Failover)
- ข่าว: Google News RSS Feed (feedparser library)

**3. Cloud Infrastructure (GCP Serverless)**
- Artifact Registry → Cloud Run Job (ETL) → Cloud Run Service (Dashboard)
- Cloud SQL (PostgreSQL) + Cloud Scheduler (Cron)

**4. Monitoring**
- Daily Operation Report ทางอีเมล ผ่าน Gmail SMTP (SSL port 465)

**Tips:** ใช้ grid layout หรือ 4 quadrant ให้ดูครบในหน้าเดียว

---

## สไลด์ 6 — ประโยชน์ที่คาดว่าจะได้รับ
**เวลา:** ~0:45 นาที | **บทที่ 1**

**หัวข้อหลัก:** ใครได้ประโยชน์ และได้อะไร?

**ประโยชน์ 4 ด้าน:**

1. **Market Insight ที่รวดเร็ว**
   → ผู้ใช้เข้าถึง Sentiment Analysis รายสินทรัพย์ผ่าน Dashboard โดยไม่ต้องอ่านข่าวทุกชิ้น

2. **Zero-Touch Automation**
   → ระบบรันเองทุกวันโดยอัตโนมัติ ไม่ต้องอาศัยคน ลด Human Error

3. **ลด Bias ในการตีความข้อมูล**
   → ใช้โมเดล AI แทนการตัดสินใจเชิงอารมณ์ของมนุษย์

4. **ทักษะสำหรับสายงาน Data Engineering & AI**
   → โครงงานครอบคลุมตั้งแต่ Data Ingestion → Model Deployment → Cloud Infra Management

**ใส่ Quote สั้นๆ จาก abstract:**
> "ระบบช่วยลดภาระในการติดตามข่าวจำนวนมาก ช่วยสรุปสาระสำคัญ และลดช่องว่างระหว่างข้อมูลกับการตัดสินใจที่มีหลักฐานรองรับ"

---

## สไลด์ 7 — Sentiment Analysis ในตลาดการเงิน
**เวลา:** ~0:40 นาที | **บทที่ 2**

**หัวข้อหลัก:** Sentiment Analysis คืออะไร และสำคัญอย่างไรในการลงทุน?

**นิยาม:**
- Sentiment Analysis = Opinion Mining — ใช้ AI ระบุและวัด "ทัศนคติ/อารมณ์" ที่ซ่อนอยู่ในข้อความ
- ไม่ใช่แค่ Binary (บวก/ลบ) แต่วัด Confidence Score ได้ด้วย

**งานวิจัยที่อ้างอิง:**
- **Tetlock (2007)** — คำเชิงลบใน Wall Street Journal มีความสัมพันธ์กับการลดลงของ Dow Jones
- **Bollen et al. (2011)** — Twitter mood พยากรณ์ทิศทาง DJIA ได้แม่นยำ 87.6%
- **Loughran & McDonald (2011)** — พัฒนา finance-specific sentiment dictionary แทน general dictionary

**ทฤษฎีเบื้องหลัง:**
- Efficient Market Hypothesis (EMH) — ราคาสะท้อนข้อมูลสาธารณะทันที (Semi-strong Form)
- แต่ในความเป็นจริง: ข่าวไม่ได้ส่งผลทุกข่าว ต้องแยก signal จาก noise

**Tips:** ใส่ timeline diagram หรือ quote box จากงานวิจัย

---

## สไลด์ 8 — FinBERT: โมเดลเฉพาะทางการเงิน
**เวลา:** ~0:40 นาที | **บทที่ 2**

**หัวข้อหลัก:** ทำไมถึงเลือก FinBERT?

**Background: BERT Architecture**
- พัฒนาโดย Google (Vaswani et al., 2017 "Attention is All You Need")
- ใช้ Self-Attention Mechanism — โมเดลเห็นความสัมพันธ์ทุกคู่คำในประโยคพร้อมกัน
- Pre-trained บน BooksCorpus (800M คำ) + Wikipedia (2,500M คำ)

**FinBERT คืออะไร?**
- Fine-tuned จาก BERT-Base (12 Encoder Layers, 110M Parameters)
- Dataset เฉพาะการเงิน:
  - Financial PhraseBank — 4,840 ประโยค ติดป้ายโดยผู้เชี่ยวชาญ 16 คน
  - Reuters/Bloomberg Financial News Corpus
- **Accuracy: >88%** บน Financial PhraseBank (Araci, 2019)
- เรียกใช้จาก HuggingFace Hub: `ProsusAI/finbert`

**Output:** Positive / Negative / Neutral + Confidence Score (0–1)

**เหตุผลที่เลือก FinBERT แทน BERT ทั่วไป:**
> ภาษาการเงินมีความเฉพาะตัวสูง เช่น "liability" มีความหมายต่างจากภาษาทั่วไป — BERT ทั่วไปอ่านไม่ออก

---

## สไลด์ 9 — วิศวกรรมข้อมูลและกระบวนการ ETL
**เวลา:** ~0:40 นาที | **บทที่ 2**

**หัวข้อหลัก:** Data Engineering และ ETL Pipeline คืออะไร?

**วิศวกรรมข้อมูล (Data Engineering)**
วิศวกรรมข้อมูลเป็นศาสตร์ที่มุ่งออกแบบ สร้าง และบำรุงรักษาโครงสร้างพื้นฐานที่ช่วยให้ข้อมูลไหลจากต้นทางไปยังปลายทางได้อย่างน่าเชื่อถือและมีเสถียรภาพ

**ETL = Design Pattern มาตรฐานในอุตสาหกรรม**

| ขั้นตอน | แนวคิดทางทฤษฎี | ความท้าทายเชิงระบบ |
|---------|---------------|-------------------|
| **Extract** | ดึงข้อมูลดิบจาก Heterogeneous Data Sources | Rate Limiting, Schema Drift, Source Reliability |
| **Transform** | แปลงข้อมูลดิบให้อยู่ในรูปแบบมาตรฐานและพร้อมวิเคราะห์ | Data Quality, Encoding, Business Logic |
| **Load** | บันทึกข้อมูลลงระบบปลายทางอย่างมีประสิทธิภาพ | Idempotency, Deduplication, Consistency |

**คุณสมบัติสำคัญของ ETL ที่ดี (ตามหลักวิชาการ):**
- **Idempotency** — รันซ้ำกี่ครั้งก็ได้ผลลัพธ์เดิม ไม่เกิดข้อมูลซ้ำ (Upsert pattern)
- **Fault Tolerance** — ระบบยังทำงานต่อได้แม้แหล่งข้อมูลบางส่วนขัดข้อง
- **Automation** — ลด Human Error และรับประกัน Data Continuity ตามรอบเวลา

**RSS Feed: แหล่งข้อมูลข่าวกึ่งโครงสร้าง (Semi-structured Data)**
RSS (Really Simple Syndication) เป็น XML-based protocol มาตรฐานสำหรับเผยแพร่ข่าวสารบนอินเทอร์เน็ต มีโครงสร้าง element ที่ชัดเจน แต่เนื้อหาข้อความยังอยู่ในรูปแบบ unstructured — จึงต้องผ่านกระบวนการ parsing และ filtering ก่อนนำไปใช้งาน

---

## สไลด์ 10 — การออกแบบคลังข้อมูลด้วย Star Schema
**เวลา:** ~0:40 นาที | **บทที่ 2**

**หัวข้อหลัก:** Data Warehouse และ Dimensional Modeling คืออะไร?

**Data Warehouse vs Database ทั่วไป:**
- Database ทั่วไป (OLTP) → ออกแบบมาเพื่อ **บันทึกธุรกรรม** ให้เร็วและถูกต้อง
- Data Warehouse (OLAP) → ออกแบบมาเพื่อ **วิเคราะห์ข้อมูลย้อนหลัง** ในปริมาณมาก
- งานวิจัยนี้ต้องการ OLAP เพราะ Dashboard อ่านข้อมูลตลอดเวลา แต่เขียนแค่วันละครั้ง (Read-heavy workload)

**Dimensional Modeling: Fact Table & Dimension Table**
แนวคิดของ Kimball & Ross (2013) — "The Data Warehouse Toolkit":
- **Fact Table** — เก็บ "เหตุการณ์" ที่เกิดขึ้นซ้ำๆ (Row-heavy) เช่น ราคาสินทรัพย์รายวัน, ข่าวแต่ละชิ้น มีตัวเลขวัดค่าได้ (Measures) เช่น close price, sentiment_score
- **Dimension Table** — เก็บ "บริบทอธิบาย" ที่ไม่ค่อยเปลี่ยน (Column-rich) เช่น ชื่อสินทรัพย์, ชื่อแหล่งข่าว, ปฏิทินวันที่

**Star Schema vs ทางเลือกอื่น:**

| เกณฑ์ | 3NF (Normalized) | Star Schema ✓ | Snowflake Schema |
|-------|-----------------|--------------|-----------------|
| วัตถุประสงค์หลัก | OLTP (Transaction) | **OLAP (Analytics)** | OLAP |
| จำนวน JOIN | มาก (5–10 ตาราง) | **น้อย (1–2 ตาราง)** | ปานกลาง (3–5) |
| Query Speed | ช้าสำหรับ analytics | **เร็วที่สุด** | ปานกลาง |
| Data Redundancy | ต่ำ | ปานกลาง | ต่ำ |
| ความซับซ้อนของโครงสร้าง | สูง | **ต่ำ (เข้าใจง่าย)** | ปานกลาง |
| เหมาะกับ Dashboard | ต่ำ | **สูงมาก** | สูง |

**เหตุผลเชิงทฤษฎีที่เลือก Star Schema:**
Star Schema ถูกเลือกเพราะสถาปัตยกรรม "ดาว" ที่มี Fact Table อยู่ตรงกลางล้อมรอบด้วย Dimension Tables ช่วยให้ Query OLAP ลดจำนวน JOIN ได้อย่างมาก ซึ่งสอดคล้องกับพฤติกรรมการใช้งาน Dashboard ที่ต้องการดึงข้อมูลเร็วทุกครั้งที่ผู้ใช้โหลดหน้าเว็บ — การแลกรับ Data Redundancy เล็กน้อยเพื่อได้ Query Performance สูงถือเป็นการตัดสินใจทางสถาปัตยกรรมที่เหมาะสม

---

## สไลด์ 11 — โครงสร้างพื้นฐานคลาวด์และ Containerization
**เวลา:** ~0:35 นาที | **บทที่ 2**

**หัวข้อหลัก:** Serverless Computing และ Docker คืออะไร?

**Cloud Computing และ Serverless Architecture:**
- Cloud Computing เปลี่ยนรูปแบบต้นทุน: จาก **CAPEX** (ซื้อ server) → **OPEX** (จ่ายตามใช้งานจริง)
- **Serverless Computing** — ผู้ใช้งานไม่ต้องจัดการ server, OS, หรือ scaling เอง ผู้ให้บริการ cloud ดูแลทั้งหมด

**GCP Services ที่เกี่ยวข้อง (ทฤษฎี):**

| บริการ | ประเภท | บทบาท |
|-------|--------|-------|
| **Cloud Run** | Serverless container runtime | รัน containerized app โดยไม่ต้องดูแล server |
| **Cloud Run Job** | Batch execution | รัน task ที่มีจุดเริ่มและจบชัดเจน เช่น ETL |
| **Cloud SQL** | Managed relational DB | PostgreSQL บน cloud ที่มี automatic backup + scaling |
| **Cloud Scheduler** | Managed cron service | Trigger งานตามเวลาที่กำหนด (Enterprise-grade cron) |
| **Artifact Registry** | Container image registry | เก็บ Docker Images ก่อน deploy |

**Docker และ Containerization:**
Docker คือแพลตฟอร์ม Open-source สำหรับ Containerization — การบรรจุโปรแกรม, dependencies, และ runtime environment ทั้งหมดไว้ใน "Container Image" เดียว เพื่อให้สามารถรันได้เหมือนกันบนทุก environment โดยไม่มีปัญหา *"It works on my machine"*

**ความสำคัญต่องาน Machine Learning:**
- โมเดลอย่าง FinBERT มี dependency ซับซ้อน (PyTorch, transformers, CUDA)
- Docker รับประกันว่า environment บนเครื่องนักพัฒนา = environment บน Cloud Server ทุกประการ
- แยก Image ได้ตามน้ำหนัก: Image สำหรับ Web (lightweight) ≠ Image สำหรับ ML inference (heavyweight)

---

## สไลด์ 12 — สถาปัตยกรรมระบบภาพรวม
**เวลา:** ~0:45 นาที | **บทที่ 3**

**หัวข้อหลัก:** ระบบทั้งหมดทำงานอย่างไร?

**Architecture Diagram (อธิบายจากซ้ายไปขวา):**
```
[Google News RSS] ─┐
                   ├→ [Cloud Run Job: ETL Pipeline]
[Yahoo Finance]  ──┘         │
                         (FinBERT)
                             ↓
                   [Cloud SQL: PostgreSQL]
                    (Star Schema fin_dw)
                             ↓
                   [Cloud Run Service: Dashboard]
                             ↓
                        [Web Browser]
                        
[Cloud Scheduler] ──→ trigger ทุก 08:00 น.
[SMTP Email]      ←── Daily Operation Report
```

**3 หลักการออกแบบ:**
1. **Separation of Concerns** — ETL แยกจาก Dashboard อย่างชัดเจน
2. **Fault Tolerance** — ถ้าแหล่งข้อมูลหนึ่งล้ม ระบบยังทำงานต่อได้
3. **Serverless-First** — ไม่ต้องดูแล server เอง, scale อัตโนมัติ

**Tips:** ใช้ architecture diagram สวยๆ มี color coding แต่ละ layer

---

## สไลด์ 13 — ETL Pipeline ภาพรวม
**เวลา:** ~0:45 นาที | **บทที่ 3**

**หัวข้อหลัก:** ขั้นตอน ETL ทั้งหมดมีอะไรบ้าง?

**Flow Diagram (6 ขั้นตอน):**

```
① Extract Price  ──→  ② Extract News  
         ↓                    ↓
③ Transform & Clean    ④ FinBERT Sentiment
         ↓                    ↓
    ⑤ Daily Aggregate (fact_sentiment_daily)
              ↓
         ⑥ Load → PostgreSQL
              ↓
         ⑦ DQ Check (Data Quality)
              ↓
         ⑧ SMTP Email Alert
```

**Output ของแต่ละขั้น:**
- ① ราคา OHLCV + pct_change ของ 30 สินทรัพย์
- ② พาดหัวข่าวจาก RSS พร้อม source, timestamp
- ③ ข้อมูลสะอาด ไม่มี null, timestamp มาตรฐาน UTC
- ④ sentiment_label + sentiment_score ต่อข่าว 1 ชิ้น
- ⑤ sentiment_index รายวันต่อสินทรัพย์ (aggregate)
- ⑥ เก็บใน 3 fact tables + 3 dimension tables
- ⑦ ตรวจสอบความครบถ้วน, ไม่มี null ผิดปกติ
- ⑧ รายงานสถานะทางอีเมล

---

## สไลด์ 14 — Price Extraction Module
**เวลา:** ~0:40 นาที | **บทที่ 3**

**หัวข้อหลัก:** ดึงข้อมูลราคาอย่างไร?

**สินทรัพย์เป้าหมาย 30 รายการ:**
| ประเภท | จำนวน | Ticker |
|-------|-------|--------|
| US Equity | 21 | AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, NFLX, AMD, ORCL, INTC, JPM, V, JNJ, XOM, PG, KO, WMT, HD, DIS, BA |
| Index | 3 | ^GSPC, ^DJI, ^IXIC |
| Cryptocurrency | 2 | BTC-USD, ETH-USD |
| Forex | 2 | EURUSD=X, THBUSD=X |
| Commodity | 2 | GC=F (ทองคำ), CL=F (น้ำมันดิบ WTI) |

*แหล่งข้อมูล: Yahoo Finance (primary) → Stooq (failover)*
*ราคาย้อนหลังถึง 2006-09-11 รวม 145,918 แถว*

**Fallback Mechanism:**
- Yahoo Finance ล้ม → สลับไป **Stooq** อัตโนมัติ
- ระบบยังทำงานต่อแม้แหล่งข้อมูลหลักมีปัญหา

**Data Cleansing Steps:**
1. ปรับชื่อคอลัมน์ให้เป็นมาตรฐาน (lowercase)
2. ลบ null values ที่ไม่สมเหตุสมผล
3. คำนวณ `return_1d` = (close - prev_close) / prev_close
4. คำนวณ `pct_change` = return_1d × 100

**Fields ที่เก็บ:** open, high, low, close, adj_close, volume, return_1d, pct_change

---

## สไลด์ 15 — News Extraction Module
**เวลา:** ~0:40 นาที | **บทที่ 3**

**หัวข้อหลัก:** ดึงข่าวอย่างไร และกรองอย่างไร?

**แหล่งข้อมูล:** Google News RSS Feed
- ค้นหาตาม Ticker Symbol ผ่าน URL Query Parameters
- ฟรี ไม่ต้อง API Key

**Custom Filtering Pipeline (4 ขั้น):**

1. **Age Filter** — ตัดข่าวเก่ากว่า 2,160 ชั่วโมง (90 วัน) ออก *(เดิม 168 ชม. ซึ่งทิ้งข่าวที่ดึงมาได้แล้ว 67-91%)*
   - ข่าวเก่า = ตลาดรับรู้ไปแล้ว → เพิ่ม noise

2. **Source Credibility Filter** — เก็บเฉพาะแหล่งน่าเชื่อถือ:
   > Bloomberg, Reuters, CNBC, Yahoo Finance, Seeking Alpha, MarketWatch

3. **Timestamp Normalization** — แปลงทุก format (RFC 2822, ISO 8601) → UTC

4. **Deduplication** — ป้องกันข่าวซ้ำผ่าน UNIQUE constraint บน DB
   - ตรวจสอบ URL + Title + Date ก่อน insert

**ผลลัพธ์:** พาดหัวข่าวที่ผ่านการกรองคุณภาพ พร้อม source metadata สำหรับ FinBERT

---

## สไลด์ 16 — FinBERT Sentiment Pipeline
**เวลา:** ~0:45 นาที | **บทที่ 3**

**หัวข้อหลัก:** FinBERT วิเคราะห์ข่าวอย่างไร?

**Step-by-Step Process:**

```
INPUT: "Apple Reports Record Q1 Earnings, Beating Estimates"
       ↓
① Tokenization (WordPiece Tokenizer)
   → แปลงข้อความเป็น Token IDs
       ↓
② Encoding (Transformer Layers)
   → FinBERT Encoder เรียนรู้บริบทรอบข้าง
       ↓
③ Compute Logits
   → คะแนนดิบ 3 คลาส: positive, negative, neutral
       ↓
④ Softmax → Probability
   → positive: 0.92 | negative: 0.04 | neutral: 0.04
       ↓
OUTPUT: sentiment_label = "positive", sentiment_score = +0.92
```

**Daily Aggregation:**
- รวม sentiment_score ของข่าวทุกชิ้นของสินทรัพย์ในวันนั้น → **sentiment_index รายวัน**
- เก็บใน `fact_sentiment_daily`
- ลดผลกระทบจากข่าวชิ้นเดียวที่ extreme เกินไป

**ข้อดีของการ aggregate รายวัน:**
- จับคู่กับราคาปิดรายวันได้ธรรมชาติ
- เหมาะกับ Correlation Analysis ทางสถิติ

---

## สไลด์ 17 — โมดูลโหลดข้อมูล (Load Module)
**เวลา:** ~0:35 นาที | **บทที่ 3**

**หัวข้อหลัก:** ข้อมูลที่ผ่านการวิเคราะห์แล้วถูกเขียนลงฐานข้อมูลอย่างไร?

**เครื่องมือที่ใช้:**
- **SQLAlchemy ORM** — ทำหน้าที่เป็นตัวกลางระหว่าง Python กับ PostgreSQL ช่วยให้โค้ดมีความยืดหยุ่น อ่านง่าย และสลับ database engine ได้โดยไม่ต้องแก้ logic หลัก
- **PostgreSQL** บน Cloud SQL — ฐานข้อมูลปลายทาง (Star Schema: `fin_dw`)

**กระบวนการ Load (3 ขั้นตอน):**

```
① ตรวจสอบก่อน insert
   → ค้นหา record ที่ตรงกัน (ด้วย Ticker + Date หรือ URL)
   
② UPSERT (Insert or Update)
   → ถ้ายังไม่มี → INSERT ปกติ
   → ถ้ามีอยู่แล้ว → UPDATE ค่าใหม่ทับ (ไม่ duplicate)
   
③ Commit / Rollback
   → ถ้าสำเร็จทั้ง batch → COMMIT
   → ถ้าเกิด Exception → ROLLBACK ทั้ง batch ทันที
```

**หลักการสำคัญ: Idempotency**
> ระบบสามารถรัน ETL ซ้ำกี่รอบก็ได้ — ผลลัพธ์ในฐานข้อมูลยังคงเหมือนเดิม ไม่มีข้อมูลซ้ำซ้อน
> คุณสมบัตินี้จำเป็นอย่างยิ่งสำหรับระบบ Production เพราะ ETL อาจต้อง rerun หลังเกิด error

**3 Fact Tables ที่ถูก Load:**

| ตาราง | ข้อมูลที่ load | Grain (1 row = ?) |
|-------|--------------|------------------|
| `fact_price_daily` | ราคา OHLCV + return_1d, pct_change | 1 สินทรัพย์ × 1 วัน |
| `fact_news` | พาดหัวข่าว + sentiment_label + score | 1 ข่าว × 1 สินทรัพย์ |
| `fact_sentiment_daily` | avg_sentiment_index รายวัน | 1 สินทรัพย์ × 1 วัน |

---

## สไลด์ 18 — ระบบตรวจสอบคุณภาพข้อมูล (Data Quality Checks)
**เวลา:** ~0:35 นาที | **บทที่ 3**

**หัวข้อหลัก:** ระบบมั่นใจได้อย่างไรว่าข้อมูลที่ load เข้าไปมีคุณภาพเพียงพอ?

**ทำไม Data Quality Check ถึงสำคัญ?**
ระบบ Dashboard และ Correlation Analysis จะเชื่อถือได้ก็ต่อเมื่อข้อมูลที่อยู่ในฐานข้อมูล **ถูกต้อง ครบถ้วน และอยู่ในช่วงค่าที่สมเหตุสมผล** หากข้อมูลคุณภาพต่ำหลุดเข้าไป ค่า Sentiment Index และ Correlation จะคลาดเคลื่อนทันที

**Module:** `src/dq/checks.py` — รันอัตโนมัติหลัง Load Module เสร็จทุกรอบ

**DQ Checks ที่ระบบทำ:**

| เกณฑ์ตรวจสอบ | รายละเอียด | ถ้าไม่ผ่าน |
|-------------|-----------|-----------|
| **Completeness** | ราคาครบ 30 สินทรัพย์หรือไม่? | Flag + แจ้ง alert |
| **Non-zero News** | มีข่าวถูกดึงเข้ารอบนี้หรือเปล่า? | Flag + แจ้ง alert |
| **Null Check** | ไม่มีค่า null ในคอลัมน์สำคัญ (close, sentiment_score) | Reject แถวนั้น |
| **Range Validation** | pct_change อยู่ในช่วงที่สมเหตุสมผลไหม? (เช่น ไม่เกิน ±50%) | Flag เป็น outlier |
| **Deduplication** | ไม่มีข่าวซ้ำหลุด (ควบคุมด้วย UNIQUE constraint) | DB reject อัตโนมัติ |

**Flow การทำงาน:**
```
Load Module เสร็จ
       ↓
DQ Checks (src/dq/checks.py)
       ↓
  ผ่านทุกเกณฑ์?
   ✅ YES → บันทึก status = PASSED → ส่ง Email "SUCCESS"
   ❌ NO  → บันทึก error detail  → ส่ง Email "WARNING/FAILED"
```

**ผลการทดสอบจริง:** DQ Check ผ่านทุกเกณฑ์ในรอบแรก — ไม่พบข้อมูลซ้ำ ไม่มี null ผิดปกติ

---

## สไลด์ 19 — Star Schema Database Design
**เวลา:** ~0:45 นาที | **บทที่ 3**

**หัวข้อหลัก:** ออกแบบ Data Warehouse อย่างไร?

**ER Diagram (Star Schema: fin_dw)**

```
                    [dim_asset]
                    - asset_id (PK)
                    - ticker
                    - asset_class
                    - currency
                         │
[dim_source] ────[fact_news]────[dim_date]
- source_id (PK)  - news_id (PK)  - d (PK)
- source_name     - asset_id (FK) - year, month
- credibility     - source_id(FK) - day, dow
  _score          - d (FK)        - is_weekend
                  - headline
                  - sentiment
                  - score
                         │
              [fact_price_daily]        [fact_sentiment_daily]
              - asset_id, d (PK)        - asset_id, d (PK)
              - open, high, low         - avg_sentiment_score
              - close, volume           - pos_count, neg_count
              - return_1d, pct_change   - neutral_count
```

**Analytical View:**
- `vw_daily_asset_metrics` — JOIN ทุก fact table + dim ไว้แล้ว → Dashboard ใช้ได้ทันที

**3 Fact Tables:** fact_price_daily, fact_news, fact_sentiment_daily
**3 Dimension Tables:** dim_asset, dim_source, dim_date

---

## สไลด์ 20 — Web Dashboard: 3 แท็บ
**เวลา:** ~0:45 นาที | **บทที่ 3**

**หัวข้อหลัก:** Dashboard มีฟีเจอร์อะไรบ้าง?

**Tech Stack:**
- Backend: **FastAPI** (Python, async, type-safe)
- ORM: **SQLAlchemy** (เชื่อมต่อ Cloud SQL)
- Template: **Jinja2** (server-side rendering)
- Chart: **Chart.js** (กราฟบน browser)

**3 แท็บหลัก:**

**Tab 1 — News Feed**
- แสดงพาดหัวข่าวพร้อม Badge สี (🟢 Positive / 🔴 Negative / ⚪ Neutral)
- Pagination 15 ข่าวต่อหน้า
- คลิก link อ่านต้นฉบับได้ทันที

**Tab 2 — Daily Summary**
- สรุปสัดส่วนข่าว Positive/Negative/Neutral รายวันต่อสินทรัพย์
- แสดง avg sentiment_index ของวัน
- **ฟีเจอร์พิเศษ:** แปลพาดหัวข่าวเป็นภาษาไทย on-demand

**Tab 3 — Metrics**
- กราฟ Market Dynamics: Dual-axis chart ราคาสินทรัพย์ + Sentiment Index ในกราฟเดียว
- Sparklines แสดงแนวโน้มย่อ
- Tab Correlation: Pearson Correlation + Lag Analysis

---

## สไลด์ 21 — GCP Deployment Architecture
**เวลา:** ~0:30 นาที | **บทที่ 3**

**หัวข้อหลัก:** Deploy ขึ้น Cloud อย่างไร?

**5 ขั้นตอน Deployment:**

1. **Build Docker Images** (build --platform linux/amd64)
   - `Dockerfile.web` → Dashboard container (lightweight)
   - `Dockerfile.etl` → ETL container + FinBERT (heavyweight)

2. **Push to Artifact Registry**
   - เก็บ Docker Images บน GCP

3. **Provision Cloud SQL (PostgreSQL)**
   - สร้างฐานข้อมูล `fin_dw` + Star Schema tables + views

4. **Deploy Dashboard → Cloud Run Service**
   - รอรับ HTTP request จากผู้ใช้
   - Scale อัตโนมัติตาม traffic

5. **Deploy ETL → Cloud Run Job**
   - รันเป็น batch ตามที่ถูก trigger
   - สิ้นสุดการทำงานหลัง ETL เสร็จ

6. **Cloud Scheduler → Cron `0 8 * * *`**
   - Trigger ETL Job ทุกวัน 08:00 น. อัตโนมัติ

**Key Design:** เปลี่ยน environment ด้วย env variables เท่านั้น ไม่ต้องแก้ logic

---

## สไลด์ 22 — ระบบแจ้งเตือนทางอีเมล (SMTP Alert System)
**เวลา:** ~0:35 นาที | **บทที่ 3**

**หัวข้อหลัก:** ระบบรายงานผลการทำงานอัตโนมัติผ่านอีเมล

---

**วัตถุประสงค์**
เพื่อให้ผู้ดูแลระบบสามารถติดตามสถานะการทำงานของ ETL Pipeline ได้ทันทีหลังรันแต่ละรอบ โดยไม่ต้องเข้าไปตรวจสอบ Cloud Run Logs ด้วยตนเอง

---

**การทำงานของระบบ**

ระบบแจ้งเตือนถูกพัฒนาในโมดูล `src/alerting.py` โดยใช้ไลบรารี `smtplib` มาตรฐานของ Python ส่งอีเมลผ่าน Gmail SMTP Server บนพอร์ต 465 ซึ่งเป็นการเชื่อมต่อแบบ SSL เพื่อความปลอดภัย

สำหรับการยืนยันตัวตน ระบบใช้ **Google App Password** แทน password บัญชีปกติ และเก็บ credential ไว้ใน Cloud Run Environment Variables เพื่อไม่ให้ข้อมูลสำคัญปรากฏในโค้ด

---

**เนื้อหาใน Daily Operation Report**

อีเมลจะถูกส่งอัตโนมัติทุกครั้งที่ ETL รันเสร็จ ประกอบด้วยข้อมูลดังนี้

| รายการ | ตัวอย่างข้อมูล |
|--------|--------------|
| วันที่และเวลาที่รัน | 2025-12-01 08:01:14 |
| สถานะการทำงาน | SUCCESS / FAILED |
| จำนวนแถวราคาที่บันทึก | 258+ rows (7 assets) |
| จำนวนข่าวที่ดึงได้ | 93 articles |
| จำนวน Sentiment Index ที่สร้าง | 7 daily records |
| ผล Data Quality Check | PASSED / WARNING |
| ข้อความ error (กรณีล้มเหลว) | รายละเอียด exception |

---

**ประโยชน์ที่ได้รับ**
ระบบนี้เปลี่ยน ETL จาก "รันแล้วไม่รู้ว่าสำเร็จหรือเปล่า" ให้กลายเป็นระบบที่มี **Operational Visibility** ช่วยลดระยะเวลาในการรับรู้ปัญหา และเป็นองค์ประกอบสำคัญที่ยกระดับระบบต้นแบบให้ใกล้เคียงกับมาตรฐาน Production จริง

---

## สไลด์ 23 — ผล ETL Pipeline บน GCP
**เวลา:** ~0:45 นาที | **บทที่ 4**

**หัวข้อหลัก:** ETL รันบน Cloud สำเร็จหรือไม่?

**ผลการทดสอบ Cloud Run Job (ครั้งแรก):**

| รายการ | ผลลัพธ์ |
|-------|---------|
| Status | ✅ Succeeded |
| Run Time | 1 นาที 14 วินาที |
| Log สุดท้าย | `=== ETL DONE ===` |
| Exceptions | ไม่มี (ครบทั้ง pipeline) |

**การตีความ:**
- **Succeeded** = ผ่านทุก stage ตั้งแต่ Extract → DQ Check
- เวลา 1:14 นาที เหมาะสมกับงาน batch รายวัน (ดึงข้อมูลผ่าน internet + FinBERT inference + เขียน DB)
- ก่อนทำงานได้: แก้ปัญหา Docker architecture (ARM64 → linux/amd64) + IAM permission

**ใส่ Screenshot:** Cloud Run Jobs Executions หน้าจอ + Cloud Run Job Logs แสดง "=== ETL DONE ==="

---

## สไลด์ 24 — ผล Web Dashboard
**เวลา:** ~0:45 นาที | **บทที่ 4**

**หัวข้อหลัก:** Dashboard ทำงานได้ตามที่ออกแบบหรือไม่?

**ผลการทดสอบ:**

| รายการ | ผลลัพธ์ |
|-------|---------|
| URL | http://localhost:8000 |
| HTTP Status | 200 OK |
| Load Time | < 3 วินาที |
| ข่าวทั้งหมด | **93 ข่าว** |
| Pagination | 15 ข่าวต่อหน้า |
| Chart ราคา | แสดงครบ 30 สินทรัพย์ |
| Sentiment Badge | แสดงสีถูกต้อง |
| แปลภาษาไทย | ทำงาน on-demand |

**ใส่ Screenshot:** หน้าหลัก Dashboard + กราฟ Market Dynamics + Sparklines

**Key Insight:**
- ข่าว 93 รายการถูก paginate 15 ต่อหน้า → UX ดี ไม่โหลดหนัก
- Backend-Database-Frontend เชื่อมต่อกันถูกต้องครบ

---

## สไลด์ 25 — FinBERT: ตัวอย่างผลการวิเคราะห์
**เวลา:** ~0:45 นาที | **บทที่ 4**

**หัวข้อหลัก:** FinBERT จำแนก sentiment ได้แม่นยำแค่ไหน?

**ตัวอย่างผลลัพธ์จากระบบ:**

| พาดหัวข่าว | Label | Score |
|-----------|-------|-------|
| "Apple Reports Record Q1 Earnings, Beating Estimates" | ✅ Positive | +0.92 |
| "Tesla Reports Worst Quarter in Two Years, Layoffs Loom" | ❌ Negative | -0.87 |
| "Microsoft Announces Partnership with OpenAI for New Products" | ✅ Positive | +0.78 |
| "Bitcoin Stabilizes After Recent Volatility" | ⚪ Neutral | +0.05 |
| "Gold Futures Rise Amid Global Uncertainty" | ✅ Positive | +0.61 |

**การตีความของ FinBERT:**
- คำว่า "Record earnings" + "beating estimates" → Positive อย่างชัดเจน
- คำว่า "Worst quarter" + "layoffs" → Negative ชัดเจน
- "Stabilizes" → Neutral เพราะไม่มีทิศทางชัด

**ข้อสังเกต:** FinBERT อ่านภาษาการเงินได้แม่นยำกว่า BERT ทั่วไป เพราะเข้าใจ domain-specific vocabulary

---

## สไลด์ 26 — Sentiment Distribution
**เวลา:** ~0:40 นาที | **บทที่ 4**

**หัวข้อหลัก:** ข่าวในระบบกระจายตัวอย่างไร?

**แสดง 2 ระดับ:**

**ระดับที่ 1 — ภาพรวม (Pie Chart / Bar Chart)**
- กราฟสัดส่วน Positive / Negative / Neutral ของข่าวทั้งหมด 93 ชิ้น
- ผู้ใช้เห็นภาพรวม "บรรยากาศข่าว" ของตลาดวันนั้นทันที

**ระดับที่ 2 — รายข่าว (News Table)**
- ตาราง News Feed พร้อม Badge สีประจำ sentiment
  - 🟢 Positive badge
  - 🔴 Negative badge
  - ⚪ Neutral badge
- ผู้ใช้สามารถ scroll ดูว่าข่าวไหนถูกจัดเป็น label อะไร

**ใส่ Screenshot:** Tab Daily Summary + กราฟ Pie/Bar + ตาราง News พร้อม Badge

**Insight:** ช่วยแยก "ข่าวที่เป็นสัญญาณ" ออกจาก "ข่าวที่เป็น noise"

---

## สไลด์ 27 — Correlation Analysis: ข่าวส่งผลต่อราคาจริงไหม?
**เวลา:** ~0:40 นาที | **บทที่ 4**

**คำถามหลักของสไลด์นี้:**
> ถ้าวันนี้ข่าวเป็น Positive — ราคาจะขึ้นพรุ่งนี้จริงไหม?

**วิธีที่ใช้วัด:**

| ขั้นตอน | รายละเอียด |
|--------|-----------|
| 1. นำ sentiment_index แต่ละวัน | ค่าเฉลี่ยของ positive/negative/neutral จากข่าวทั้งหมดวันนั้น |
| 2. จับคู่กับ pct_change ของราคา | ทั้งแบบ same-day และแบบ Lag +1 วัน (ข่าววันนี้ → ราคาพรุ่งนี้) |
| 3. คำนวณ Pearson Correlation | ค่าตั้งแต่ -1 ถึง +1 บอกว่าสองตัวแปรเดินไปด้วยกันแค่ไหน |

**ผลที่ได้:**

⚠️ **ยังสรุปไม่ได้ชัดเจน** — ไม่ใช่เพราะระบบผิด แต่เพราะ **ข้อมูลยังน้อยเกินไป**
ต้องมีอย่างน้อยหลักร้อยจุดข้อมูลจึงจะ "ลด noise" ได้และเห็นสัญญาณจริง

**สิ่งที่ทำสำเร็จแล้ว (สำคัญ!):**

✅ โครงสร้างทุกอย่างพร้อมแล้ว — ตาราง, view, และ chart ทำงานได้จริง
✅ เมื่อข้อมูลสะสมมากพอ **ไม่ต้องแก้ระบบเลย** แค่รอให้ pipeline รันต่อไปทุกวัน

**ใส่ Screenshot:** Tab Correlation + Dual-axis Chart (sentiment vs price ในกราฟเดียวกัน)

---

## สไลด์ 28 — Cloud Scheduler & Email Alert
**เวลา:** ~0:30 นาที | **บทที่ 4**

**หัวข้อหลัก:** ระบบทำงานอัตโนมัติได้จริงหรือไม่?

**Cloud Scheduler:**
- Cron Expression: `0 8 * * *` → ทุกวัน 08:00 น.
- ส่ง HTTP Trigger → Cloud Run Job (ETL)
- ผลทดสอบ: **Triggered และ Executed สำเร็จ**

**ความสำคัญ:**
> ระบบก้าวจาก "รันได้เมื่อสั่ง" → "ปฏิบัติงานอัตโนมัติด้วยตนเอง"
> = คุณสมบัติสำคัญของระบบระดับ Production

**Email Alert:**
- Daily report ส่งหลัง ETL เสร็จทุกครั้ง
- ผู้ดูแลรับรู้ผลทันที ไม่ต้องเปิด Cloud Console เอง

**ใส่ Screenshot:** Cloud Scheduler dashboard + ตัวอย่างอีเมล alert

---

## สไลด์ 29 — สรุปผลการทดสอบทั้งหมด
**เวลา:** ~0:35 นาที | **บทที่ 4**

**หัวข้อหลัก:** ระบบผ่านเกณฑ์ทั้งหมดหรือไม่?

**ตารางสรุปผล (ครบทุก component):**

| เกณฑ์การประเมิน | เป้าหมาย | ผลจริง | สถานะ |
|----------------|---------|--------|-------|
| จำนวนข่าวต่อรอบ | ≥ 50 ข่าว | **93 ข่าว** | ✅ ผ่าน |
| Deduplication | ไม่มีข่าวซ้ำ | ไม่มีซ้ำ (UNIQUE constraint) | ✅ ผ่าน |
| Price rows loaded | 7 tickers × n วัน | **258+ แถว** | ✅ ผ่าน |
| ETL Run Time | < 5 นาที | **1 นาที 14 วินาที** | ✅ ผ่าน |
| Web Dashboard | HTTP 200 + แสดงข้อมูล | URL สาธารณะ, โหลด < 3 วิ | ✅ ผ่าน |
| Cloud Scheduler | Trigger ตรงเวลา | Execute สำเร็จ | ✅ ผ่าน |
| Email Alert | ส่งรายงานหลัง ETL | ส่งสำเร็จทุกรอบ | ✅ ผ่าน |
| DQ Check | ไม่มี null ผิดปกติ | ผ่าน | ✅ ผ่าน |

**สรุป: ผ่านเกณฑ์ครบทุกข้อในรอบทดสอบแรก**

---

## สไลด์ 30 — 5.1 สรุปผลการดำเนินงาน
**เวลา:** ~0:35 นาที | **บทที่ 5**

**หัวข้อหลัก:** โครงการบรรลุวัตถุประสงค์ทั้ง 5 ข้อครบถ้วน

**ผลการดำเนินงานตามวัตถุประสงค์ที่กำหนด:**

| # | วัตถุประสงค์ | ผลที่ได้ | สถานะ |
|---|------------|---------|-------|
| 1 | พัฒนา ETL Pipeline อัตโนมัติ | ดึงราคา 30 สินทรัพย์ + ข่าว RSS รายวัน พร้อมระบบ fallback (Stooq) และ deduplication | ✅ สำเร็จ |
| 2 | วิเคราะห์ sentiment ด้วย FinBERT | จำแนก positive/negative/neutral จากพาดหัวข่าวภาษาอังกฤษได้ถูกต้อง | ✅ สำเร็จ |
| 3 | ออกแบบ Data Warehouse รูปแบบ Star Schema | สร้าง fin_dw บน Cloud SQL (PostgreSQL) พร้อม analytical view `vw_daily_asset_metrics` | ✅ สำเร็จ |
| 4 | Deploy บน GCP แบบ Serverless | ระบบทำงานอัตโนมัติด้วย Cloud Run Job + Cloud Scheduler ทุกวันเวลา 18:00 น. | ✅ สำเร็จ |
| 5 | พัฒนา Web Dashboard | เข้าถึงได้สาธารณะผ่าน URL ของ Cloud Run แสดงข้อมูลราคาและ sentiment ครบถ้วน | ✅ สำเร็จ |

**ตัวเลขสำคัญจากการทดสอบ:**
- ข่าวที่ประมวลผลได้: **93 รายการ**
- แถวข้อมูลราคาใน fact table: **258+ แถว**
- เวลารัน pipeline ทั้งหมด: **1 นาที 14 วินาที**

---

## สไลด์ 31 — 5.2 การวิจารณ์ผลลัพธ์และข้อสังเกตสำคัญ
**เวลา:** ~0:40 นาที | **บทที่ 5**

**หัวข้อหลัก:** ผลลัพธ์บอกอะไร และมีข้อสังเกตอะไรที่สำคัญ?

**5.2.1 — ผลการวิเคราะห์ความสัมพันธ์ (Correlation)**

**ปรับปรุง ก.ย. 2026 — ข้อมูลสะสมเพียงพอแล้ว และผลเป็นลบ**

ข้อความเดิมระบุว่าข้อมูลยังไม่พอสรุปผล และคาดว่าเมื่อสะสมมากขึ้นจะวิเคราะห์ได้ ปัจจุบันมีสินทรัพย์ 29 จาก 30 รายการที่ข้อมูล sentiment ครบเกณฑ์ 30 วัน ครอบคลุม 9 เดือน ผลการวิเคราะห์คือ

| ประเด็น | ผล |
|---|---|
| ความแม่นยำ (5 → 29 สินทรัพย์) | 0.635 → **0.483** (เส้นฐาน 0.590) |
| ชนะเส้นฐาน (walk-forward) | 1/3 → **0/3 folds** |
| AUC เมื่อเพิ่ม sentiment | **ลดลงทุกขอบเขตเวลา** (−0.013 ถึง −0.019) |
| Pearson vs Spearman | ค่าที่ p<0.001 ส่วนใหญ่ **หายไปเมื่อวัดด้วยอันดับ** |

ความได้เปรียบที่วัดได้ตอนมี 5 สินทรัพย์เป็นความผันผวนจากกลุ่มตัวอย่างขนาดเล็ก ปัจจัยที่ครอบงำผลคือการเปลี่ยนสภาวะตลาดระหว่างชุดฝึกและชุดทดสอบ (สัดส่วนวันขึ้น 0.438 → 0.590) ซึ่งข้อมูล 9 เดือนไม่พอจะฝึกให้ครอบคลุม

โครงสร้างพื้นฐานด้านข้อมูลครบสมบูรณ์และใช้งานได้จริง — สิ่งที่เปลี่ยนคือคำตอบ ไม่ใช่ความพร้อมของระบบ

**5.2.2 — ปัญหาที่พบและวิธีแก้ไข (จากตาราง 5.1 ในรายงาน):**

| ปัญหาที่พบ | สาเหตุ | วิธีแก้ไข |
|-----------|--------|---------|
| Cloud Run Job ล้มเหลว (Error 403) | Service Account ขาด IAM Permission สำหรับ Cloud SQL | เพิ่ม `roles/cloudsql.client` ให้ Service Account |
| Web Dashboard แสดง Error 500 | ไม่มี View `vw_daily_asset_metrics` ใน Database | สร้าง View ผ่าน Python Script เชื่อมตรงไปยัง Cloud SQL |
| ระบบแจ้งเตือนอีเมลส่งไม่ได้ | ใช้ password ปกติแทน App Password | สร้าง Google App Password และอัปเดตใน Cloud Run Environment Variable |
| Docker Build สำเร็จแต่รันบน Cloud ไม่ได้ | Build บน ARM64 (Apple Silicon M1/M2) | เพิ่ม flag `--platform linux/amd64` ในคำสั่ง build |

**ข้อสังเกตสำคัญ:** ปัญหาทุกข้อเกิดจากความแตกต่างระหว่าง Local Development กับ Cloud Environment — ยืนยันว่า Cloud Architecture ต้องออกแบบและทดสอบบน environment จริงตั้งแต่ต้น

---

## สไลด์ 32 — 5.3 ข้อจำกัดของระบบ
**เวลา:** ~0:30 นาที | **บทที่ 5**

**หัวข้อหลัก:** ระบบมีข้อจำกัดด้านใดบ้างในปัจจุบัน?

| # | ข้อจำกัด | รายละเอียด | ผลกระทบ |
|---|---------|-----------|---------|
| 1 | **แหล่งข้อมูลเป็น Free Tier** | Google News RSS และ Yahoo Finance มี rate limit และไม่มี SLA รับประกัน | ข้อมูลอาจขาดหายหรือล่าช้าได้ |
| 2 | **Batch Processing วันละ 1 ครั้ง** | ระบบดึงข้อมูลเพียงวันละครั้ง ไม่รองรับการวิเคราะห์ intraday | ไม่เหมาะกับการเทรดระยะสั้น |
| 3 | **ครอบคลุม 30 สินทรัพย์** | หุ้นสหรัฐ 21, ดัชนี 3, คริปโท 2, forex 2, โภคภัณฑ์ 2 — ยังไม่รวมหุ้นไทย (SET) | ขอบเขตการวิเคราะห์จำกัดเฉพาะตลาดสากล |
| 4 | **Secrets เก็บใน Environment Variables** | API keys และ credentials ยังไม่ได้ใช้ Secret Manager | ความปลอดภัยต่ำกว่ามาตรฐาน production |
| 5 | **ความลึกของ sentiment ไม่สมมาตร** | ราคา 20 ปี งบการเงิน 19 ปี แต่ sentiment มีเพียง 9 เดือน เพราะต้องสะสมเอง | ฝึกแบบจำลองข้ามสภาวะตลาดไม่ได้ — เป็นข้อจำกัดที่ครอบงำผลการวิจัย |

> ข้อจำกัดเหล่านี้เป็น **known trade-off** ที่ยอมรับได้ในระดับ academic project และสามารถแก้ไขได้ในการพัฒนาต่อยอด

---

## สไลด์ 33 — 5.4 ข้อเสนอแนะสำหรับการพัฒนาต่อยอด
**เวลา:** ~0:35 นาที | **บทที่ 5**

**หัวข้อหลัก:** แนวทางพัฒนาระบบในอนาคต แบ่งตามกรอบเวลา

**ระยะสั้น (< 3 เดือน) — เสริมความมั่นคงของระบบ:**
- ย้าย API keys และ credentials ไปเก็บใน **Google Secret Manager** เพื่อเพิ่มความปลอดภัย
- เพิ่มโหมด **Backfill Historical Data** สำหรับสะสมข้อมูลย้อนหลัง
- ขยายช่องทางแจ้งเตือนเพิ่ม **Line Notify / Slack** นอกจากอีเมล

**ระยะกลาง (3–12 เดือน) — ยกระดับคุณภาพข้อมูลและโมเดล:**
- เปลี่ยนแหล่งข้อมูลเป็น **NewsAPI / Alpha Vantage** (paid tier) ที่มี SLA และ rate limit สูงกว่า
- แยก FinBERT ออกเป็น **Microservice บน Vertex AI** เพื่อลด memory footprint ของ ETL Job
- ขยายขอบเขตสินทรัพย์ → **หุ้น SET ไทย** พร้อมแหล่งข่าวภาษาไทย

**ระยะยาว (> 1 ปี) — สู่ระบบ Real-time และ Predictive:**
- พัฒนา **Real-time Streaming Pipeline** ด้วย Google Cloud Pub/Sub (จาก batch รายวัน → near real-time)
- **Fine-tune FinBERT สำหรับภาษาไทย** โดยใช้ข้อมูลข่าวการเงินไทย
- สร้าง **Predictive Model** โดยใช้ sentiment_score ร่วมกับ technical indicators เป็น feature สำหรับพยากรณ์ราคา

---

## สไลด์ 34 — 5.5 บทเรียนที่ได้รับ
**เวลา:** ~0:25 นาที | **บทที่ 5**

**หัวข้อหลัก:** สิ่งที่เรียนรู้จากการสร้างระบบนี้จริง

**5 บทเรียนสำคัญ:**

1. 🏗 **Cloud Architecture ต้องออกแบบตั้งแต่ต้น**
   IAM permission, VPC connectivity, และ platform compatibility (ARM vs AMD64) ไม่ใช่รายละเอียดที่ค่อยแก้ทีหลังได้ — ต้องวางแผนก่อน deploy

2. 🔄 **Idempotency คือหัวใจของ ETL Pipeline ที่เชื่อถือได้**
   การออกแบบ UPSERT + UNIQUE constraint ทำให้ rerun ซ้ำกี่ครั้งก็ไม่ทำให้ข้อมูลเสียหาย — สำคัญมากในระบบที่ run อัตโนมัติ

3. 🧠 **งาน AI/ML ต้องวางแผนทรัพยากรอย่างรอบคอบ**
   FinBERT ใช้ memory และ compute สูง — การแยก Dockerfile.etl ออกจาก Dockerfile.web เป็นตัวอย่างของ resource isolation ที่ดี

4. 🔒 **Security ไม่ใช่เรื่องที่ค่อยมาเพิ่มทีหลัง**
   ปัญหา Gmail authentication และ secrets management ส่งผลโดยตรงต่อการทำงานของระบบ — ควรออกแบบตั้งแต่ phase แรก

5. 🔗 **ระบบ End-to-End ให้บทเรียนมากกว่าการทดลองแยกส่วน**
   การเชื่อมทุก layer ตั้งแต่ data ingestion → NLP inference → storage → visualization → scheduling → alerting ทำให้เข้าใจ production data system อย่างแท้จริง

---

## สไลด์ 35 — 5.6 สรุป + ขอบคุณ + Q&A
**เวลา:** ~0:20 นาที | **บทที่ 5**

**หัวข้อหลัก:** สรุปภาพรวมโครงการ

**สรุปโครงการ:**
งานวิจัยนี้พัฒนา **Automated Data Pipeline และ Data Warehouse** สำหรับการวิเคราะห์ตลาดการเงินและ Sentiment จากข่าว โดยบูรณาการ ETL Pipeline, FinBERT NLP Model, Star Schema Data Warehouse, และ GCP Serverless Infrastructure เข้าด้วยกันเป็นระบบครบวงจรที่ทำงานอัตโนมัติทุกวัน

**จุดเด่นของโครงการ:**
- ระบบ production-grade ที่ deploy และทำงานจริงบน Google Cloud Platform
- ครอบคลุมทุก layer ของ Data Engineering: Ingestion → Processing → Storage → Visualization → Orchestration
- ออกแบบโดยยึดหลัก Idempotency, Fault Tolerance, และ Serverless-First

**ข้อสรุป:** ข้อมูลสะสมเพียงพอแล้วและได้วิเคราะห์จริง ผลเป็นลบ — ทั้ง sentiment และงบการเงินไม่แสดงความสัมพันธ์กับผลตอบแทนที่รอดการตรวจสอบ 3 ชั้น สอดคล้องกับสมมติฐานตลาดมีประสิทธิภาพรูปแบบกึ่งเข้ม คุณูปการของงานคือโครงสร้างข้อมูลและระเบียบวิธีที่ทำให้สรุปได้อย่างมั่นใจว่าไม่พบ

---

**ขอบคุณ**
- ผศ.ดร.กนกวรรณ อัจฉริยะชาญวณิช — อาจารย์ที่ปรึกษา
- คณาจารย์คณะเทคโนโลยีสารสนเทศ สจล.
- ครอบครัวและเพื่อนๆ

---
**Q&A**

---
*จัดทำโดย: นายเอเชีย อ่อนพรม — สาขาวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ สจล. 2568*
