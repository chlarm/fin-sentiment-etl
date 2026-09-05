# 📊 Slide Deck: ระบบวิเคราะห์ความรู้สึกข่าวการเงินอัตโนมัติด้วย FinBERT บน Google Cloud Platform
### แผนการพรีเซนต์ 30 นาที — รายละเอียดครบทุก Slide พร้อม Speaker Notes

---

> ## ⚠️ ต้องอ่านก่อนใช้ไฟล์นี้ (ปรับปรุง 5 ก.ย. 2026)
>
> ไฟล์นี้เขียนเมื่อ ก.ค. 2026 เนื้อหาหลายส่วนไม่ตรงกับระบบและผลการวิจัยปัจจุบันแล้ว จุดที่ต้องแก้ก่อนนำเสนอ
>
> | ประเด็น | เดิม | ปัจจุบัน |
> |---|---|---|
> | **URL เว็บ** | `fin-web-nnebdwza6q-as.a.run.app` | **ตอบ HTTP 500 — ใช้ไม่ได้แล้ว** เพราะ billing ปิด Cloud SQL ถูก suspend ต้องแคปหน้าจอจากเครื่องตัวเอง (`http://localhost:8000`) แทน |
> | จำนวนสินทรัพย์ | 7 รายการ | **30 รายการ** |
> | หน้าต่างข่าว | 168 ชม. (7 วัน) | **2,160 ชม. (90 วัน)** |
> | แท็บ Dashboard | 5 แท็บ รวม Heatmap | **7 แท็บ** — Heatmap ถูกถอด เพิ่ม Signal และ Fundamentals |
> | ผล Correlation | "ข้อมูลยังไม่พอ รอสะสมแล้วจะสรุปได้" | **ข้อมูลพอแล้ว และคำตอบเป็นผลลบ** |
>
> รายละเอียดทั้งหมดอยู่ใน `thesis_methodology_revised.md`
>
> **ประเด็นที่สำคัญที่สุดต่อการนำเสนอ**: สไลด์เดิมวางเรื่องเล่าไว้ว่า "สร้างระบบเสร็จแล้ว รอข้อมูลเพื่อสรุปผล" ซึ่งตอนนี้เล่าไม่ได้แล้ว เพราะข้อมูลมาแล้วและผลเป็นลบ เรื่องเล่าใหม่ที่แข็งกว่าคือ **"สร้างระบบ เก็บข้อมูลจริง ทดสอบอย่างเข้มงวด และพบว่าความสัมพันธ์ที่ดูมีนัยสำคัญเป็นสิ่งประดิษฐ์"** ดูโครงที่เสนอในหัวข้อท้ายไฟล์

---

> **แนวทางการแบ่งเวลา (30 นาที)**
> | ส่วน | เวลา |
> |---|---|
> | Slide 1–3: บทนำ + ปัญหา + เป้าหมาย | 3 นาที |
> | Slide 4–5: ทฤษฎีและเทคโนโลยี (FinBERT, ETL) | 5 นาที |
> | Slide 6–8: สถาปัตยกรรมและการออกแบบระบบ | 7 นาที |
> | Slide 9–12: การ Deploy บน GCP | 5 นาที |
> | Slide 13–15: ผลการทดลองและ Demo | 5 นาที |
> | Slide 16–17: สรุปและ Future Work | 3 นาที |
> | Slide 18: Q&A | 2 นาที |

---

## 🎯 Slide 1 — หน้าปก (Title Slide)

### เนื้อหาบน Slide:
```
ระบบประมวลผลข้อมูลอัตโนมัติเพื่อวิเคราะห์ความรู้สึก
จากข่าวสารทางการเงินด้วยโมเดล FinBERT
บนโครงสร้างพื้นฐานคลาวด์ Google Cloud Platform

─────────────────────────────────
นายเอเชีย อ่อนพรม   รหัส 66070324
อาจารย์ที่ปรึกษา: ผศ.ดร.กนกวรรณ อัจฉริยะชาญวณิช
สาขาวิชาวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ
คณะเทคโนโลยีสารสนเทศ
สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง
ปีการศึกษา 2568
```

### 📸 รูปที่ต้องใส่:
- Background: Screenshot หน้า Dashboard จาก http://localhost:8000 (ทำ Blur / Opacity ต่ำๆ เป็น Background)
- Logo KMITL มุมบนซ้าย
- Logo GCP มุมบนขวา

### 🎙️ Speaker Notes:
> "สวัสดีครับ วันนี้ผมจะนำเสนอโครงงานที่ชื่อว่า ระบบวิเคราะห์ความรู้สึกจากข่าวการเงินอัตโนมัติด้วยโมเดล FinBERT บน Google Cloud Platform ซึ่งเป็นการผสมผสานระหว่างปัญญาประดิษฐ์ วิศวกรรมข้อมูล และบริการคลาวด์ขนาดองค์กร เพื่อแก้ปัญหาจริงในโลกการเงินครับ"

---

## 🎯 Slide 2 — ปัญหาที่พบ (Problem Statement)

### เนื้อหาบน Slide:

**📰 ปัญหา: ข้อมูลข่าวมหาศาล — มนุษย์ตามไม่ทัน**

| ข้อเท็จจริง | ตัวเลข |
|---|---|
| บทความข่าวการเงินที่เผยแพร่ทั่วโลกต่อวัน | กว่า 2 ล้านชิ้น |
| เวลาที่ราคาหุ้นตอบสนองต่อข่าวใหญ่ | น้อยกว่า 30 วินาที |
| นักลงทุนที่ตัดสินใจโดยอิงอารมณ์ตลาด | 78% |

- ❌ อ่านข่าวทุกชิ้นเองด้วยมือ → **เป็นไปไม่ได้**
- ❌ ระบบวิเคราะห์ที่มีอยู่ → แยก AI ออกจากราคา ไม่ได้เห็นภาพรวม
- ❌ ไม่มีระบบที่ **รัน อัตโนมัติ + วิเคราะห์ AI + เชื่อมราคา** ในที่เดียว

**❓ คำถามสำคัญ:**
> "ข่าวเชิงลบของ Tesla วันนี้ → ราคา Tesla พรุ่งนี้จะลงไหม?"

### 📸 รูปที่ต้องใส่:
- กราฟแสดง Volume ของข่าวการเงินที่พุ่งสูงขึ้น (หาจาก Google หรือ Statista)
- หรือแสดงหน้าจอ Google News ที่มีข่าวเยอะๆ ล้นหน้าจอ

### 🎙️ Speaker Notes:
> "ปัญหาที่โครงงานนี้ต้องการแก้คือ ในตลาดการเงินปัจจุบัน มีข่าวสารเผยแพร่มากกว่า 2 ล้านชิ้นต่อวัน ราคาหุ้นอาจปรับตัวตอบสนองต่อข่าวสำคัญภายในเวลาไม่ถึง 30 วินาที ซึ่งมนุษย์ไม่มีทางอ่านและประเมินได้ทัน
>
> ที่ผ่านมามีระบบวิเคราะห์ Sentiment อยู่บ้าง แต่มักแยกส่วนกัน คือตัวหนึ่งทำ AI อีกตัวหนึ่งแสดงราคา ไม่มีระบบที่ผสมทั้งสองเข้าด้วยกันและทำงานอัตโนมัติทุกวัน โครงงานนี้จึงพยายามตอบคำถามว่า ถ้าข่าวเกี่ยวกับหุ้นตัวหนึ่งเป็นเชิงลบในวันนี้ ราคาจะเปลี่ยนไปอย่างไรในวันถัดไปครับ"

---

## 🎯 Slide 3 — วัตถุประสงค์และขอบเขต (Objectives & Scope)

### เนื้อหาบน Slide:

**🎯 วัตถุประสงค์ทั้ง 5 ข้อ**
1. ✅ พัฒนา ETL Pipeline ดึงข้อมูลราคาและข่าวโดยอัตโนมัติ
2. ✅ วิเคราะห์ความรู้สึกของข่าวด้วยโมเดล FinBERT (AI เฉพาะทางการเงิน)
3. ✅ ออกแบบ Data Warehouse รูปแบบ Star Schema
4. ✅ Deploy ระบบทั้งหมดบน Google Cloud Platform แบบ Serverless
5. ✅ พัฒนา Web Dashboard สำหรับแสดงผลและวิเคราะห์

**📦 ขอบเขต — สินทรัพย์ 30 รายการ 5 ประเภท:**

| หุ้น US (21) | ดัชนี (3) | คริปโทฯ (2) | Forex (2) | โภคภัณฑ์ (2) |
|---|---|---|---|---|
| AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, NFLX, AMD, ORCL, INTC, JPM, V, JNJ, XOM, PG, KO, WMT, HD, DIS, BA | ^GSPC, ^DJI, ^IXIC | BTC-USD, ETH-USD | EURUSD=X, THBUSD=X | GC=F, CL=F |

### 📸 รูปที่ต้องใส่:
- Icon สำหรับแต่ละประเภทสินทรัพย์ (หุ้น, ดัชนี, Bitcoin, Forex, Gold)

### 🎙️ Speaker Notes:
> "โครงงานมีวัตถุประสงค์ 5 ข้อหลักครับ ขอบเขตครอบคลุมสินทรัพย์ 30 รายการใน 5 ประเภท ได้แก่ หุ้นสหรัฐ 21 ตัว ดัชนี 3 ตัว คริปโท 2 ตัว ค่าเงิน 2 คู่ และสินค้าโภคภัณฑ์ 2 รายการ
>
> เหตุที่เลือกหลากหลายประเภทเพราะต้องการศึกษาว่าความสัมพันธ์ระหว่างข่าวและราคาแตกต่างกันตามประเภทสินทรัพย์หรือไม่
>
> จุดที่อยากเน้นคือ **จำนวนสินทรัพย์มีผลโดยตรงต่อความน่าเชื่อถือของข้อสรุป** ตอนที่ระบบยังมีข้อมูลครบเกณฑ์เพียง 5 ตัว แบบจำลองให้ความแม่นยำ 63.5% ซึ่งชนะเส้นฐาน แต่เมื่อขยายเป็น 29 ตัว ตัวเลขนั้นหายไปทั้งหมด ผมจะกลับมาเล่าประเด็นนี้ในส่วนผลการทดลองครับ"

---

## 🎯 Slide 4 — โมเดล FinBERT คืออะไร? (FinBERT Deep Dive)

### เนื้อหาบน Slide:

**ทำไมถึงไม่ใช้ AI ทั่วไป?**

| ข้อความ | AI ทั่วไป | FinBERT |
|---|---|---|
| "Bearish Market" | 🤔 ไม่แน่ใจ | 🔴 Negative (ตลาดขาลง) |
| "Stock is Underwater" | 🤔 ไม่แน่ใจ | 🔴 Negative (ขาดทุน) |
| "Record Q1 Earnings" | 🟢 Positive | 🟢 Positive (กำไรสูงสุด) |
| "Layoffs Announced" | 🔴 Negative | 🔴 Negative (เลิกจ้าง) |

**🧠 FinBERT Pipeline (ทีละขั้นตอน):**

```
📰 หัวข่าว: "Apple Reports Record Earnings, Beats Estimates"
                        ↓ Tokenize
🔢 Token IDs: [101, 6207, 7292, 2501, ...]
                        ↓ FinBERT Model (110M Parameters)
📊 Output:  P(Positive)=0.89  P(Negative)=0.04  P(Neutral)=0.07
                        ↓ Calculate
✅ Score: +0.85   Label: POSITIVE
```

### 📸 รูปที่ต้องใส่:
- แผนภาพ BERT Architecture (Encoder Stack) จากเอกสารต้นฉบับ หรือวาดอย่างง่าย
- Screenshot Output จาก FinBERT จาก HuggingFace หรือจาก Code Output

### 🎙️ Speaker Notes:
> "โมเดลที่เลือกใช้คือ FinBERT ซึ่งเป็น BERT ที่ถูก Fine-tuned เพิ่มเติมด้วยข้อความทางการเงินโดยเฉพาะ ทำไมถึงไม่ใช้ AI ทั่วไป? เพราะภาษาการเงินมีคำเฉพาะที่ AI ทั่วไปไม่เข้าใจ เช่นคำว่า Bearish ในภาษาทั่วไปแปลว่าเหมือนหมี แต่ในตลาดหุ้นหมายถึงตลาดขาลง หรือคำว่า Underwater ในภาษาทั่วไปแปลว่าอยู่ใต้น้ำ แต่ในการเงินหมายถึงมูลค่าต่ำกว่าต้นทุน
>
> FinBERT รับข้อความหัวข่าวเข้ามา ผ่านกระบวนการเข้ารหัส และออกมาเป็นความน่าจะเป็น 3 ค่า คือ Positive, Negative, Neutral จากนั้นผมคำนวณ Sentiment Score จากผลต่าง Positive ลบ Negative ได้ค่าในช่วง -1 ถึง +1 ครับ"

---

## 🎯 Slide 5 — กระบวนการ ETL Pipeline

### เนื้อหาบน Slide:

**🔄 ETL Flow ทีละขั้นตอน:**

```
☁️ Cloud Scheduler
   ทุกวัน 08:00 น. (Asia/Bangkok)
         ↓ เรียกใช้
📦 Cloud Run Job (fin-etl-job)
         ↓
┌──────────────────────────────────────┐
│  🔴 E — EXTRACT (ดึงข้อมูลจากแหล่งภายนอก)   │
│  ├─ 📈 ราคาสินทรัพย์   → Yahoo Finance API  │
│  │             (สำรอง) → Stooq             │
│  └─ 📰 ข่าวสาร 30 Tickers → Google News RSS │
│       กรอง: Trusted Sources (Bloomberg ฯ)  │
└──────────────────┬───────────────────────┘
                   ↓
┌──────────────────────────────────────┐
│  🟡 T — TRANSFORM (ประมวลผลข้อมูล)         │
│  ├─ 🔢 คำนวณ return_1d, pct_change         │
│  ├─ 🤖 ส่งข่าวทุกชิ้นผ่าน FinBERT           │
│  │    → ได้ sentiment_score, label          │
│  └─ 📊 รวม Sentiment → Daily Index          │
└──────────────────┬───────────────────────┘
                   ↓
┌──────────────────────────────────────┐
│  🟢 L — LOAD (บันทึกลงฐานข้อมูล Cloud SQL)  │
│  ├─ UPSERT fact_price_daily                │
│  ├─ INSERT fact_news (Dedup news_hash)     │
│  └─ UPSERT fact_sentiment_daily            │
└──────────────────┬───────────────────────┘
                   ↓
         ✅ DQ Check → 📧 Email Alert
```

### 📸 รูปที่ต้องใส่:
- Diagram ภาพประกอบ ETL Flow ที่สวยงามกว่านี้ (วาดด้วย draw.io)
- Screenshot Logs ของ ETL ที่แสดง "=== ETL DONE ===" พร้อมตัวเลข

### 🎙️ Speaker Notes:
> "ไปป์ไลน์ ETL เริ่มต้นทุกวันเวลา 08 โมงเช้าตามเวลาไทย โดย Cloud Scheduler จะส่งคำสั่งไปยัง Cloud Run Job
>
> ขั้น Extract: โปรแกรมจะดึงราคาย้อนหลัง 14 วันจาก Yahoo Finance สำหรับสินทรัพย์ทั้ง 7 ตัว ถ้า Yahoo ล่ม จะสลับไปดึงจาก Stooq อัตโนมัติ ควบคู่ไปกับการดึงข่าวจาก Google News RSS โดยแต่ละ Ticker จะมี Search Term พิเศษ เช่น GC=F จะค้นว่า gold price USD แทน
>
> ขั้น Transform: ส่วนที่หนักที่สุดคือการส่งหัวข่าวทุกชิ้นผ่าน FinBERT ซึ่งต้องโหลดโมเดลขนาดใหญ่เข้า RAM ก่อน แล้วค่อยวิเคราะห์ทีละข่าว
>
> ขั้น Load: บันทึกข้อมูลทุกอย่างลง Cloud SQL โดยมีกลไกป้องกันข้อมูลซ้ำผ่าน news_hash ที่ใช้ SHA256 เป็น Unique Identifier ครับ"

---

## 🎯 Slide 6 — การออกแบบฐานข้อมูล Star Schema

### เนื้อหาบน Slide:

**🗄️ ทำไมถึงใช้ Star Schema?**

| รูปแบบ | จำนวน JOIN | ความเร็ว Query | เหมาะกับ |
|---|---|---|---|
| 3NF (Normalized) | 5–10 ตาราง | ⚡ ช้า | งาน Transaction (OLTP) |
| ❌ Snowflake Schema | 3–5 ตาราง | ⚡⚡ ปานกลาง | ข้อมูล Dimension ใหญ่มาก |
| ✅ **Star Schema** | **1–2 ตาราง** | **⚡⚡⚡ เร็วสุด** | **Dashboard / วิเคราะห์ (OLAP)** |

**📐 Structure ของ fin_dw:**

```
             [dim_date]
                  |
[dim_asset] — [fact_price_daily] — [dim_source]
                  |
             [fact_news]
                  |
        [fact_sentiment_daily]
```

**Fact Tables (ตารางหลัก):** เก็บตัวเลขที่วัดได้
- `fact_price_daily` — OHLCV + Return รายวัน
- `fact_news` — ข่าวทุกชิ้น + Sentiment Score/Label
- `fact_sentiment_daily` — ดัชนี Sentiment สรุปรายวัน

**Dimension Tables (บริบท):**
- `dim_asset` — ชื่อ Ticker, ประเภทสินทรัพย์
- `dim_source` — แหล่งข่าว, Credibility Score
- `dim_date` — ปฏิทิน: ปี, เดือน, วัน, วันหยุด

### 📸 รูปที่ต้องใส่:
- ER Diagram (Entity Relationship) ของ Star Schema ทั้ง 6 ตาราง สร้างด้วย dbdiagram.io หรือ DrawSQL

### 🎙️ Speaker Notes:
> "ฐานข้อมูลที่ใช้ออกแบบตามหลัก Star Schema ซึ่งเป็นรูปแบบมาตรฐานสำหรับ Data Warehouse ตามทฤษฎีของ Ralph Kimball
>
> เหตุที่เลือก Star Schema แทน 3NF ปกติ เพราะระบบนี้เน้นการอ่านเพื่อสร้างกราฟ ไม่ใช่การเขียน การออกแบบให้ Fact Table กลางเชื่อมกับ Dimension รอบข้าง ทำให้ Query ข้อมูลทำได้ใน JOIN เพียง 1-2 ครั้ง ซึ่งเร็วกว่า 3NF ที่อาจต้อง JOIN ถึง 10 ตาราง
>
> ไม่เลือก Snowflake เพราะข้อมูล Dimension ในโปรเจกต์นี้ขนาดเล็ก การ Normalize เพิ่มเติมจะซับซ้อนโดยไม่จำเป็นครับ"

---

## 🎯 Slide 7 — System Architecture บน GCP (Full Picture)

### เนื้อหาบน Slide:

```
┌─────────────────── Google Cloud Platform (asia-southeast1) ──────────────────┐
│                                                                                │
│  ⏰ Cloud Scheduler           📦 Artifact Registry                            │
│  "fin-etl-trigger"            "fin-repo"                                       │
│  0 8 * * * (Asia/Bangkok)     Docker Images:                                  │
│         │                     - fin-etl:latest                                 │
│         ▼                     - fin-web:latest                                 │
│                                                                                │
│  🏃 Cloud Run Jobs            🌐 Cloud Run Service                            │
│  "fin-etl-job"      ──────▶  "fin-web"                                        │
│  Memory: 4GB                  http://localhost:8000         │
│  Platform: linux/amd64        Memory: 512MB                                   │
│         │                            │                                         │
│         │           Unix Socket      │      Unix Socket                       │
│         ▼                ↗          ▼            ↗                            │
│  🗄️ Cloud SQL                                                                  │
│  "fin-sentiment-db"  ← PostgreSQL 16                                          │
│  Database: fin_dw                                                               │
│  6 Tables (Star Schema)                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
         ▲                                          ▲
    Yahoo Finance                            👤 ผู้ใช้งาน
    Google News RSS                          Web Browser
```

**📋 สรุป GCP Resources:**
| บริการ GCP | ชื่อ | หน้าที่ |
|---|---|---|
| Cloud Run Jobs | `fin-etl-job` | รัน ETL + FinBERT ทุกวัน 08:00 |
| Cloud Run Service | `fin-web` | Web Dashboard สาธารณะ |
| Cloud SQL PostgreSQL 16 | `fin-sentiment-db` | ฐานข้อมูล Star Schema |
| Artifact Registry | `fin-repo` | เก็บ Docker Images |
| Cloud Scheduler | `fin-etl-trigger` | ตั้งเวลา Cron อัตโนมัติ |

### 📸 รูปที่ต้องใส่:
- Screenshot GCP Console Dashboard (https://console.cloud.google.com/home/dashboard?project=project-sentiment-etl)
- Diagram ด้านบนทำเป็น Diagram ที่สวยงามกว่านี้

### 🎙️ Speaker Notes:
> "ภาพนี้แสดงสถาปัตยกรรมระบบทั้งหมดบน Google Cloud ครับ มี Component หลัก 5 ส่วน
>
> Cloud Scheduler ทำหน้าที่เหมือน Cron Job ส่งสัญญาณทุก 8 โมงเช้า → ไปเรียก Cloud Run Job ที่ชื่อ fin-etl-job ซึ่งรัน Container ที่มี FinBERT Model ดึงข้อมูลจาก Internet แล้วบันทึกลง Cloud SQL
>
> Cloud Run Service fin-web ทำหน้าที่รับ Request จากผู้ใช้ผ่าน Web Browser ดึงข้อมูลจาก Cloud SQL แล้วแสดงผลเป็น Dashboard
>
> การเชื่อมต่อระหว่าง Cloud Run กับ Cloud SQL ทำผ่าน Unix Socket ซึ่งปลอดภัยกว่า TCP ปกติ เพราะไม่ต้องเปิด Port หรือใช้ Public IP ของ Database ครับ"

---

## 🎯 Slide 8 — Docker และ Container Strategy

### เนื้อหาบน Slide:

**🐳 ทำไมต้องใช้ Docker?**

FinBERT ต้องการ Library เยอะมาก:
```
PyTorch 2.x + Transformers 4.x + CUDA Libraries
+ yfinance + feedparser + SQLAlchemy + pandas
= "Dependency Hell" ถ้าไม่ Container
```

**✅ Solution: 2 Docker Images แยกกัน**

```
┌─────────────────────┐    ┌───────────────────────────┐
│  📦 fin-web          │    │  📦 fin-etl                │
│  (Lightweight Image) │    │  (Heavy-weight Image)      │
│                      │    │                            │
│  FastAPI             │    │  FastAPI                   │
│  SQLAlchemy          │    │  SQLAlchemy                │
│  Jinja2              │    │  PyTorch + Transformers    │
│  Pandas              │    │  FinBERT Model (~500MB)    │
│  Uvicorn             │    │  yfinance + feedparser     │
│  ~300 MB             │    │  ~3.5 GB                   │
└─────────────────────┘    └───────────────────────────┘
        ↓                              ↓
   Cloud Run Service             Cloud Run Jobs
   (Always Running)              (Run-to-Completion)
```

⚠️ **จุดสำคัญ:** Build ด้วย `--platform linux/amd64`
- เครื่อง Developer ใช้ Apple Silicon (ARM64)
- Cloud Run ใช้ AMD64 ← ต้อง Match!

### 📸 รูปที่ต้องใส่:
- Screenshot Artifact Registry แสดง Images ที่ Push ขึ้นไป
- วาด Diagram เปรียบเทียบ Image ทั้งสอง

### 🎙️ Speaker Notes:
> "เหตุที่ต้องใช้ Docker เพราะโมเดล FinBERT ต้องการ Library เฉพาะทางจำนวนมาก ซึ่งถ้าไม่ Containerize เมื่อ Deploy ขึ้น Cloud จะพบปัญหา Version ขัดแย้งกันหรือที่เรียกว่า Dependency Hell
>
> ผมแยกเป็น 2 Image เพราะหน้าที่ต่างกัน fin-web เบาและรัน Always-on รับ Request ตลอด ส่วน fin-etl หนักแต่รันแค่วันละครั้ง การแยกทำให้ Web Dashboard ไม่ต้องแบกน้ำหนัก PyTorch และ FinBERT ตลอดเวลา
>
> ปัญหาที่เจอตอน Deploy คือเครื่องของผมเป็น Apple M1 ซึ่งใช้ CPU Architecture ARM64 แต่ Cloud Run ใช้ AMD64 ทำให้ต้องเพิ่ม Flag --platform linux/amd64 ตอน Build ครับ"

---

## 🎯 Slide 9 — Web Dashboard: ออกแบบและพัฒนา

### เนื้อหาบน Slide:

**🖥️ Technology Stack:**
```
FastAPI (Python) ← Web Framework รองรับ Async
   + Jinja2        ← Template Engine สร้าง HTML
   + Chart.js      ← กราฟ Interactive
   + SQLAlchemy    ← ORM + Cloud SQL Connection
   + Uvicorn       ← ASGI Production Server
```

**7 แท็บบน Dashboard:**

| แท็บ | สิ่งที่แสดง |
|---|---|
| 🏠 Home | ข่าวล่าสุด + สินทรัพย์ที่ราคาขึ้น/ลงมากสุด |
| 📈 **Signal** | **การทำนายทิศทาง + backtest + เส้นฐาน + walk-forward + SHAP** |
| ⭐ Watchlist | สินทรัพย์ที่ติดตาม แจ้งเตือนเมื่อสัญญาณเปลี่ยนทิศ |
| 💰 **Fundamentals** | **งบการเงินรายไตรมาสจาก SEC EDGAR ย้อนหลัง 19 ปี** |
| 📰 News | ตารางข่าวทั้งหมด + Badge Sentiment สี |
| 📊 Metrics | ตารางราคา Open/Close + Return + Sentiment Index |
| 🔗 Correlations | สหสัมพันธ์ — **มีแถบกำกับว่าเป็นหลักฐานประกอบ ไม่ใช่ผลลัพธ์หลัก** |

> **หมายเหตุ** แท็บ Heatmap เดิมถูกถอดออก เพราะแสดงภาพรวมได้แต่ไม่ช่วยตัดสินใจ ซึ่งเป็นประเด็นเดียวกับที่คณะกรรมการตั้งข้อสังเกต

**🔗 การเข้าถึง:**
> รันบนเครื่องผ่าน Docker — `http://localhost:8000`
> (URL เดิมบน Cloud Run ใช้ไม่ได้แล้ว ตอบ HTTP 500 เพราะ billing ปิด)

### 📸 รูปที่ต้องใส่:
- Screenshot Dashboard หน้าหลัก (กราฟ Market Dynamics + Sparklines + Stat Cards)
- Screenshot **แท็บ Signal** — สำคัญที่สุด เพราะเป็นคำตอบต่อข้อสังเกตของกรรมการ
- Screenshot แท็บ Fundamentals

### 🎙️ Speaker Notes:
> "Web Dashboard พัฒนาด้วย FastAPI ข้อมูลถูก Render ฝั่ง Server ผ่าน Jinja2 Template
>
> ตอนแรก Dashboard มี 5 แท็บซึ่งเน้นการ**แสดงข้อมูล** — ข่าว ตารางราคา และค่าสหสัมพันธ์ คณะกรรมการให้ข้อสังเกตว่าเว็บควรให้ประโยชน์มากกว่าการดึงข่าวมาแสดง และค่าสหสัมพันธ์ยังใช้ตัดสินใจไม่ได้
>
> ผมจึงปรับโครงใหม่ทั้งหมด แท็บที่สำคัญที่สุดตอนนี้คือ **Signal** ซึ่งไม่ได้รายงานค่าสัมประสิทธิ์ แต่รายงานว่า 'ถ้าทำตามสัญญาณนี้จะได้ผลอย่างไร' พร้อมเส้นฐานเปรียบเทียบและช่วงความแม่นยำจากหลายช่วงเวลา และเพิ่มแท็บ Fundamentals ที่แสดงงบการเงินย้อนหลัง 19 ปี
>
> ส่วนแท็บ Heatmap เดิมผมถอดออก เพราะมันสวยแต่ตอบคำถามอะไรไม่ได้ครับ"

---

## 🎯 Slide 10 — ผลการทดสอบ Web Dashboard (Screenshot เต็ม)

### เนื้อหาบน Slide:
*[Slide นี้ให้ใส่รูปใหญ่เต็มสไลด์ พร้อม Caption]*

**📸 รูปที่ต้องใส่ (สำคัญมากครับ ใส่ให้ครบ):**
1. Screenshot หน้า Dashboard หลัก (กราฟ + Stat Card)
2. Screenshot **แท็บ Signal** พร้อมส่วน walk-forward และ SHAP
3. Screenshot **แท็บ Fundamentals** (กราฟรายได้รายไตรมาส + ตาราง)
4. Screenshot แท็บ Correlations พร้อม**แถบสีเหลืองที่กำกับว่าเป็นหลักฐานประกอบ** — ภาพนี้สื่อได้ดีว่าเราตอบข้อสังเกตของกรรมการอย่างไร

> หมายเหตุ: ทำเป็น Grid 2×2 รูปบนสไลด์เดียว หรือใช้ Slide หลายหน้า
>
> ⚠️ **แคปจาก `http://localhost:8000` เท่านั้น** URL เดิมบน Cloud Run ตอบ HTTP 500 แล้ว ต้องเปิด Docker และรัน `python run_web.py` ก่อนแคป

### 🎙️ Speaker Notes:
> "นี่คือ Screenshot จากระบบจริงที่รันอยู่บน Google Cloud ครับ หน้าหลักแสดงกราฟ Market Dynamics ที่รวมเส้นราคา AAPL และแถบ Sentiment Score ไว้ในกราฟเดียว ตัวเลขด้านบนคือ Stat Cards แสดงจำนวน Prices, News และ Sentiment Analyses ที่ระบบเก็บไว้
>
> ถ้าอาจารย์สะดวกสแกน QR Code ก็สามารถเข้าดู Dashboard จริงได้เลยครับ"

---

## 🎯 Slide 11 — ผลการทดสอบ ETL Pipeline

### เนื้อหาบน Slide:

**📊 ผลการรัน ETL ครั้งแรก (Execution ID: fin-etl-job-m2lj8)**

| รายการ | ผลลัพธ์ |
|---|---|
| ✅ สถานะ | **Succeeded** |
| ⏱️ เวลาที่ใช้ทั้งหมด | **1 นาที 14 วินาที** |
| 📈 Price Rows ที่ Upsert | **258 แถว** |
| 📰 News ที่ Insert (หลัง Dedup) | **93 ข่าว** |
| 🤖 Sentiment Index ที่คำนวณ | **20 รายการ** |
| 🧠 RAM ที่ใช้สูงสุด | **~3.2 GB / 4 GB** |
| ✅ DQ Check | **Pass** |

**📧 Email Alert ที่ได้รับ:**
```
Subject: ✅ ETL SUCCESS ✅
From: anatomyaz1@gmail.com
To: 66070324@kmitl.ac.th

Date: 2026-03-26
Prices Rows: 258
News Rows: 93
Indices Rows: 20
DQ Checks: Pass
```

**ปัญหาที่พบและแก้ไข:**
| ปัญหา | แก้ไข |
|---|---|
| Cloud SQL Connection ล้มเหลว | เปลี่ยนเป็น Unix Socket Connection String |
| Email ส่งไม่ได้ | เปลี่ยนจาก Regular Password เป็น Google App Password |
| Docker รันบน Cloud ไม่ได้ | เพิ่ม `--platform linux/amd64` |

### 📸 รูปที่ต้องใส่:
- Screenshot Cloud Run Job Executions แสดงสถานะ Succeeded
- Screenshot Email ใน Inbox

### 🎙️ Speaker Notes:
> "ผลการทดสอบ ETL Pipeline ครั้งแรกสำเร็จทั้งหมด ระบบใช้เวลาเพียง 1 นาที 14 วินาที สำหรับ 7 Tickers ซึ่งรวมการ Load FinBERT Model และ Inference ข่าว 93 ชิ้น RAM สูงสุดที่ใช้คือ 3.2 GB จากที่จัดสรรไว้ 4 GB แสดงว่าการกำหนด Memory เป็น 4GB มีความเหมาะสม
>
> ระหว่างการพัฒนาพบปัญหา 3 ข้อหลัก ได้แก่ Connection String ต้องเป็น Unix Socket สำหรับ Cloud SQL, Email ต้องใช้ App Password ของ Google, และ Docker Image ต้อง Build สำหรับ AMD64 ซึ่งทั้งหมดได้รับการแก้ไขแล้วครับ"

---

## 🎯 Slide 12 — ตัวอย่างผลลัพธ์ FinBERT จากข่าวจริง

### เนื้อหาบน Slide:

**🤖 ตัวอย่าง Sentiment Score จากข่าวจริงในระบบ:**

| หัวข่าว | Score | Label |
|---|---|---|
| "Apple Reports Record Q1 Earnings, Beating Estimates" | **+0.92** | 🟢 POSITIVE |
| "Bitcoin Surges Past $70K on ETF Approval News" | **+0.88** | 🟢 POSITIVE |
| "MSFT Announces Partnership with OpenAI for New AI" | **+0.77** | 🟢 POSITIVE |
| "Fed Signals Potential Rate Hike Amid Inflation" | **-0.74** | 🔴 NEGATIVE |
| "Tesla Reports Worst Quarter, Layoffs Announced" | **-0.81** | 🔴 NEGATIVE |
| "Gold Prices Stable as Markets Await CPI Data" | **+0.03** | ⚫ NEUTRAL |

**Sentiment Score = P(Positive) − P(Negative) ∈ [−1, +1]**

### 📸 รูปที่ต้องใส่:
- Screenshot หน้า News Tab บน Dashboard แสดงตาราง Badge สี

### 🎙️ Speaker Notes:
> "นี่คือตัวอย่างผลลัพธ์จริงจากโมเดล FinBERT ที่ทำงานในระบบ
>
> โมเดลจำแนกได้ถูกต้องทุกกรณี ข่าว Record Earnings ให้คะแนน +0.92 ซึ่งสูงมาก ข่าว Tesla Layoffs ให้ -0.81 ซึ่งชัดเจนว่าเชิงลบ ที่น่าสนใจคือข่าวทอง 'Stable as Markets Await' ได้คะแนนใกล้ 0 มาก เพราะเนื้อหาไม่ได้ระบุทิศทางชัดเจน ซึ่งโมเดลตีความได้ถูกต้องว่าเป็น Neutral ครับ"

---

## 🎯 Slide 13 — Correlation Analysis: ข่าวสัมพันธ์กับราคาไหม?

### เนื้อหาบน Slide:

**🔗 คำถามสำคัญ: "Sentiment วันนี้ทำนายราคาพรุ่งนี้ได้ไหม?"**

**คำตอบ: ไม่ได้ — และนี่คือหลักฐาน**

**① ผลที่เคยดูดี ไม่รอดเมื่อข้อมูลมากขึ้น**

| | ก.ค. 2026 (5 สินทรัพย์) | ก.ย. 2026 (29 สินทรัพย์) |
|---|---|---|
| ความแม่นยำ | 0.635 | **0.483** |
| เส้นฐาน (majority) | 0.558 | 0.590 |
| ชนะเส้นฐาน | 1/3 folds | **0/3 folds** |

**② การเพิ่ม sentiment ทำให้แย่ลง** (วัดด้วย AUC บนแถวเดียวกัน)

| ขอบเขต | เทคนิคอย่างเดียว | + sentiment | ผลต่าง |
|---|---|---|---|
| 1 วัน | 0.489 | 0.471 | −0.019 |
| 5 วัน | 0.527 | 0.514 | −0.013 |
| 21 วัน | 0.736 | 0.722 | −0.015 |

**③ ค่า Pearson ที่ "มีนัยสำคัญ" หายไปเมื่อวัดด้วยอันดับ**

| ตัวแปร | Pearson | Spearman |
|---|---|---|
| revenue_growth @63d | +0.254 \*\*\* | +0.046 (ns) |
| net_margin @252d | −0.228 \*\*\* | −0.053 (\*) |

### 📸 รูปที่ต้องใส่:
- ตารางเปรียบเทียบ 5 ตัว vs 29 ตัว (ทำเป็นกราฟแท่งคู่จะเห็นชัดกว่า)
- Screenshot แท็บ Correlations พร้อมแถบกำกับ "หลักฐานประกอบ ไม่ใช่ผลลัพธ์หลัก"

### 🎙️ Speaker Notes:
> "สไลด์นี้เป็นหัวใจของงานวิจัยครับ และคำตอบเป็นผลลบ
>
> ตอนนำเสนอครั้งก่อน ระบบมีสินทรัพย์ที่ข้อมูลครบเกณฑ์เพียง 5 ตัว แบบจำลองให้ความแม่นยำ 63.5% เทียบเส้นฐาน 55.8% ดูเหมือนมีสัญญาณจริง
>
> ผมขยายข้อมูลเป็น 29 ตัว ตัวเลขกลายเป็น 48.3% เทียบเส้นฐาน 59% และไม่ชนะเส้นฐานเลยสักรอบ **ความได้เปรียบเดิมคือความผันผวนจากกลุ่มตัวอย่างขนาดเล็ก**
>
> ผมตรวจซ้ำด้วย AUC ซึ่งไม่ขึ้นกับเกณฑ์ตัดสินใจ และเทียบบนแถวข้อมูลเดียวกันเป๊ะ พบว่าการเพิ่ม sentiment **ลด** AUC ทุกขอบเขตเวลา ความสม่ำเสมอของทิศทางแบบนี้คือลักษณะของการเติมสัญญาณรบกวน ไม่ใช่สัญญาณที่จับไม่ได้
>
> และค่า Pearson ที่มีนัยสำคัญระดับ p < 0.001 ส่วนใหญ่หายไปเมื่อวัดด้วยอันดับ แปลว่ามันถูกลากด้วยข้อมูลเพียงไม่กี่แถว
>
> ผมคิดว่าผลลบที่ตรวจสอบอย่างเข้มงวดมีค่ามากกว่าตัวเลข 63.5% ที่พังทันทีเมื่อเพิ่มข้อมูลครับ"

> **💡 เตรียมรับคำถามกรรมการ**
> - *"ทำไมไม่ใช้โมเดลที่ซับซ้อนกว่านี้"* → ปัจจัยที่ครอบงำผลคือ regime shift: สัดส่วนวันขึ้นใน train = 0.438 แต่ใน test = 0.590 โมเดลเรียนจากตลาดขาลงแล้วถูกทดสอบบนขาขึ้น การเปลี่ยนโมเดลไม่แก้ปัญหานี้ ต้องมีข้อมูลข้ามสภาวะตลาด ซึ่ง sentiment มีแค่ 9 เดือน
> - *"n = 524 ก็เยอะแล้วไม่ใช่หรือ"* → 524 แถวนั้นมาจากวันตลาดเพียง 33 วัน เพราะแถวจาก 29 สินทรัพย์ในวันเดียวกันเคลื่อนไหวตามตลาดพร้อมกัน ขนาดตัวอย่างที่แท้จริงคือจำนวนวัน
> - *"ผลลบแบบนี้จบโครงงานได้หรือ"* → สอดคล้องกับสมมติฐานตลาดมีประสิทธิภาพรูปแบบกึ่งเข้ม ทั้งข่าวและงบการเงินเป็นข้อมูลสาธารณะที่ราคาสะท้อนไปแล้ว คุณูปการของงานคือโครงสร้างข้อมูลและระเบียบวิธีที่ทำให้**สรุปได้อย่างมั่นใจว่าไม่พบ**

---

## 🎯 Slide 14 — Cloud Scheduler: ระบบอัตโนมัติ 100%

### เนื้อหาบน Slide:

```
ทุกวันเวลา 08:00 น. เวลาไทย (Asia/Bangkok)
Cloud Scheduler รัน fin-etl-trigger
         ↓
ส่ง HTTP POST ไปยัง Cloud Run Jobs API
         ↓
fin-etl-job เริ่มทำงาน → ดึงข้อมูล → วิเคราะห์ AI → บันทึกลง DB
         ↓
📧 ส่ง Email แจ้งเตือน "✅ ETL SUCCESS" ไปยัง 66070324@kmitl.ac.th
```

**🔒 Security:**
- Cloud Scheduler ใช้ OAuth2 + Service Account
- Cloud SQL ใช้ Unix Socket (ไม่มี Public IP)
- Gmail ใช้ App Password (16 ตัวอักษร) แทน Regular Password

### 📸 รูปที่ต้องใส่:
- Screenshot Cloud Scheduler Console แสดง fin-etl-trigger สถานะ Enabled + Next Run Time

### 🎙️ Speaker Notes:
> "ระบบทำงานอัตโนมัติ 100% โดยไม่ต้องการการแทรกแซงจากมนุษย์เลยครับ Cloud Scheduler ตั้งค่าด้วย Cron Expression 0 8 *** และ Timezone Asia/Bangkok
>
> ความปลอดภัยของระบบทำได้หลายชั้น Cloud SQL ไม่มี Public IP เปิดด้านนอก ต้องเชื่อมผ่าน Unix Socket ที่ GCP จัดการให้เท่านั้น Email ใช้ App Password แทนรหัสผ่านปกติ ซึ่งสร้างจากหน้า Google Account โดยเฉพาะ ทำให้แม้ App Password หลุดออกไป ก็สามารถ Revoke ได้ทันทีโดยไม่กระทบบัญชี Gmail ครับ"

---

## 🎯 Slide 15 — Demo Live (ถ้าสถานการณ์เอื้ออำนวย)

### เนื้อหาบน Slide:

```
🔗 Demo URL:
http://localhost:8000

[QR Code ตรงนี้]
```

**สิ่งที่จะ Demo:**
1. หน้าหลัก → เลือก Ticker AAPL → ดูกราฟ Market Dynamics
2. แท็บ News → แสดง Badge สี Pos/Neg/Neu
3. แท็บ Correlations → อธิบายตัวเลข
4. Cloud Run Console → แสดง Job สำเร็จ

### 📸 รูปที่ต้องใส่:
- QR Code ไปยัง URL Dashboard

### 🎙️ Speaker Notes:
> "ถ้าเน็ตพร้อม ผมจะเปิด Dashboard จริงให้ดูครับ ถ้าสแกน QR Code นี้ก็เข้าได้เหมือนกัน ระบบนี้รันอยู่ตลอดเวลา ไม่ใช่แค่ Demo ครับ"

---

## 🎯 Slide 16 — ข้อจำกัดและบทเรียน

### เนื้อหาบน Slide:

**⚠️ ข้อจำกัดที่พบ:**
1. **ความลึกของ sentiment ไม่สมมาตร** — ราคา 20 ปี งบการเงิน 19 ปี แต่ sentiment มีแค่ 9 เดือน จึงฝึกข้ามสภาวะตลาดไม่ได้ (นี่คือข้อจำกัดที่ครอบงำผลทั้งหมด)
2. **Batch-Only** — รันวันละครั้ง ตรวจจับผลของ breaking news ระหว่างวันไม่ได้
3. **พึ่งพาเครื่องส่วนบุคคล** — งานตามเวลาไม่ทำงานหากเครื่องปิด (ระบบกู้คืนเองได้ถ้าหยุดไม่เกิน 90 วัน)
4. **ไตรมาส 4 ของงบขาดหาย** — 181 จาก 334 ปี-บริษัท เติมย้อนหลังไม่ได้อย่างปลอดภัย (ทดสอบแล้วผิด ~25%)
5. **THB/USD ข่าวน้อยเกินเกณฑ์** — 14 วัน จาก 30 วัน เป็นข้อจำกัดของการรายงานข่าว ไม่ใช่ของระบบ

**📚 บทเรียนสำคัญ:**

| เรื่อง | บทเรียน |
|---|---|
| ☁️ Cloud Architecture | ต้องวางแผน IAM และ Connection ก่อน Deploy |
| 🔁 Idempotency | ETL ต้อง UPSERT + Unique Hash ป้องกันข้อมูลซ้ำ |
| 🧠 Memory Planning | FinBERT ใช้ RAM ~3GB ต้องจัดสรรให้พอ |
| 🐛 **ข้อผิดพลาดที่เงียบอันตรายที่สุด** | เจอ 5 จุดที่ให้ผลดูปกติโดยไม่มี error |
| 🔍 **ตัวเลขที่ดูดีต้องตรวจหนักกว่า** | ค่า p<0.001 ส่วนใหญ่หายเมื่อวัดด้วยอันดับ |
| 📏 **ข้อจำกัดของข้อมูลต้องวัด ไม่ใช่เดา** | เชื่อผิดว่า "ข่าวดึงย้อนหลังไม่ได้" อยู่หลายเดือน |

### 🎙️ Speaker Notes:
> "ข้อจำกัดที่สำคัญที่สุดคือข้อ 1 ครับ ราคาผมมี 20 ปี งบการเงิน 19 ปี แต่ sentiment มีแค่ 9 เดือน เพราะต้องสะสมเอง ความไม่สมมาตรนี้ทำให้ฝึกโมเดลข้ามสภาวะตลาดไม่ได้ และเป็นสาเหตุหลักของผลลบ ไม่ใช่คุณภาพของ FinBERT
>
> ส่วนบทเรียน ผมอยากเน้นสามข้อล่างครับ
>
> **ข้อผิดพลาดที่เงียบคืออันตรายที่สุด** — ผมเจอ 5 จุดที่ให้ตัวเลขดูสมเหตุสมผลโดยไม่มี error เช่น เครื่องหมาย & ในคำค้นทำให้ระบบค้นหาดัชนี S&P 500 ด้วยตัวอักษร 'S' มาหลายเดือน โดย feed ยังคืนข่าว 100 รายการตามปกติ และการจับคู่งบการเงินกับราคาผิดวันถึง 39% ของข้อมูล ทั้งหมดเจอเพราะไล่ตรวจตัวเลขที่อธิบายไม่ได้ ไม่ใช่เพราะอ่านโค้ด
>
> **ตัวเลขที่ดูดีต้องตรวจหนักกว่าตัวเลขที่ดูแย่** — ธรรมชาติของเราจะยอมรับผลบวกเร็วกว่าผลลบ ซึ่งเป็นความเสี่ยงเชิงระบบของงานวิเคราะห์ข้อมูล
>
> **ข้อจำกัดของแหล่งข้อมูลต้องวัด ไม่ใช่สันนิษฐาน** — ผมเชื่อและเขียนไว้ในเอกสารว่าข่าวดึงย้อนหลังไม่ได้ อยู่หลายเดือน จนไปวัดจริงแล้วพบว่าไม่จริง ความเชื่อนั้นยืนยันตัวเองได้เพราะตัวกรอง 7 วันทำให้ทุกครั้งที่รันเห็นข้อมูลแค่ 7 วันเสมอครับ"

---

## 🎯 Slide 17 — Future Work และแนวทางพัฒนา

### เนื้อหาบน Slide:

**🔮 แผนพัฒนาต่อยอด 3 ระยะ:**

**🔵 ระยะสั้น (3 เดือน):**
- Google Secret Manager — เพิ่มความปลอดภัย Credentials
- Backfill Historical Data — เติมข้อมูลย้อนหลังทันที
- รองรับหุ้นไทย (SET) — ADVANC, PTT, KBANK

**🟡 ระยะกลาง (3–12 เดือน):**
- Premium Data Source — Alpha Vantage API, NewsAPI
- Vertex AI Endpoint — GPU สำหรับ FinBERT Inference เร็วขึ้น 10–100x
- Thai FinBERT — Fine-tune สำหรับข่าวภาษาไทย

**🔴 ระยะยาว (1 ปีขึ้นไป):**
- Real-time Streaming — Google Pub/Sub แทน Batch Processing
- Price Forecasting Model — LSTM/Transformer ใช้ Sentiment เป็น Feature
- SaaS Platform — บริการ API สำหรับบริษัทจัดการกองทุน

### 🎙️ Speaker Notes:
> "Future Work แบ่งออกเป็น 3 ระยะครับ ระยะสั้นเน้นปิด Gap ที่มีอยู่ โดยเฉพาะการเพิ่มหุ้นไทย
>
> ระยะกลางเน้นยกระดับ Infrastructure โดยย้าย FinBERT ไป Vertex AI ที่รองรับ GPU จะทำให้ Inference เร็วขึ้น 10-100 เท่า
>
> ระยะยาวเปลี่ยน Architecture จาก Batch เป็น Real-time Streaming ซึ่งจะเปิดโอกาสการประยุกต์ใช้ที่กว้างมากขึ้น เช่น การสร้าง Price Forecasting Model ที่ใช้ Sentiment เป็น Feature ร่วมกับ Technical Indicator ครับ"

---

## 🎯 Slide 18 — สรุปและขอบคุณ (Conclusion)

### เนื้อหาบน Slide:

**✅ สรุปสิ่งที่ทำสำเร็จ:**

```
🤖 AI Model     FinBERT ให้คะแนน sentiment ข่าวสะสม 7,518 ชิ้น
📦 ETL          Pipeline อัตโนมัติ 30 สินทรัพย์ + กู้คืนข้อมูลเองได้
🗄️  Database     Star Schema — fact 6 ตาราง, dim 4 ตาราง, 145,918 แถวราคา
🌐 Dashboard    7 แท็บ รวม Signal (ทำนาย+backtest) และ Fundamentals
🧪 Testing      ชุดทดสอบอัตโนมัติ 75 รายการ
📧 Alert         Email แจ้งเตือนพร้อม timeout
```

**🔬 ข้อสรุปเชิงวิชาการ — ผลลัพธ์เชิงลบที่ตรวจสอบแล้ว**

> ทั้ง sentiment ข่าวรายวันและงบการเงินรายไตรมาส **ไม่แสดงความสัมพันธ์กับผลตอบแทนที่รอดการตรวจสอบ 3 ชั้น**
> — การจัดการค่าผิดปกติ · การประเมินนอกกลุ่มตัวอย่าง · การนับขนาดตัวอย่างที่แท้จริง
>
> สอดคล้องกับสมมติฐานตลาดมีประสิทธิภาพรูปแบบกึ่งเข้ม

**คุณูปการหลักไม่ใช่การค้นพบความสัมพันธ์ แต่เป็นโครงสร้างข้อมูลและระเบียบวิธีที่ทำให้สรุปได้อย่างมั่นใจว่าไม่พบ**

"ขอบพระคุณอาจารย์และผู้เข้าร่วมฟังทุกท่านครับ"

### 🎙️ Speaker Notes:
> "สรุปครับ ผมพัฒนาระบบครบทั้ง ETL, Data Warehouse, NLP, Web Dashboard และชุดทดสอบอัตโนมัติ 75 รายการ ระบบเก็บข้อมูลจริงมา 9 เดือน ราคาย้อนหลัง 20 ปี และงบการเงิน 19 ปี
>
> ข้อสรุปเชิงวิชาการเป็นผลลบครับ ทั้ง sentiment และงบการเงินไม่แสดงความสัมพันธ์กับผลตอบแทนที่รอดการตรวจสอบทั้งสามชั้น
>
> ผมอยากจบด้วยประเด็นนี้ครับ ตอนนำเสนอครั้งก่อนผมมีตัวเลข 63.5% ที่ดูดี ถ้าผมหยุดตรงนั้นแล้วรายงานไป มันจะเป็นข้อสรุปที่ผิด สิ่งที่ทำให้รู้ว่าผิดคือการขยายข้อมูลแล้ววัดซ้ำ
>
> คุณูปการของงานนี้จึงไม่ใช่การค้นพบความสัมพันธ์ แต่เป็นการสร้างโครงสร้างข้อมูลและระเบียบวิธีที่แข็งแรงพอจะสรุปได้อย่างมั่นใจว่า **ไม่พบ** ซึ่งเป็นเงื่อนไขจำเป็นสำหรับการศึกษาต่อยอดใดๆ ในหัวข้อนี้ครับ
>
> ขอบพระคุณครับ ยินดีตอบคำถามครับ"

---

## 📋 สรุป: รายการรูปทั้งหมดที่ต้องแคป

| รูปที่ | Slide | สิ่งที่ต้องแคป | URL/แหล่ง |
|---|---|---|---|
| 1 | Slide 1 | Dashboard หน้าหลัก (Background) | http://localhost:8000 |
| 2 | Slide 4 | BERT Architecture Diagram | หาจาก Google Images หรือวาดเอง |
| 3 | Slide 5 | ETL Logs บน Cloud Run | GCP Console → Cloud Run Jobs → Logs |
| 4 | Slide 6 | Star Schema ER Diagram | สร้างด้วย dbdiagram.io |
| 5 | Slide 7 | GCP Console Dashboard | https://console.cloud.google.com/home/dashboard?project=project-sentiment-etl |
| 6 | Slide 8 | Artifact Registry รายการ Images | GCP Console → Artifact Registry → fin-repo |
| 7 | Slide 9 | Dashboard หน้าหลัก (กราฟใหญ่) | http://localhost:8000 |
| 8 | Slide 10 | Dashboard แท็บ News (Badge) | http://localhost:8000/?tab=news |
| 9 | Slide 10 | Dashboard แท็บ Correlations | http://localhost:8000/?tab=correlations |
| 10 | Slide 10 | Dashboard แท็บ Signal (ทำนาย + backtest + SHAP) | http://localhost:8000/?tab=predict |
| 10b | Slide 10 | Dashboard แท็บ Fundamentals | http://localhost:8000/?tab=fundamentals |
| 11 | Slide 11 | Cloud Run Job Executions (เขียว) | GCP Console → Cloud Run Jobs → fin-etl-job |
| 12 | Slide 11 | Email ETL Success ใน Inbox | Gmail 66070324@kmitl.ac.th |
| 13 | Slide 13 | Dashboard แท็บ Correlations (ตาราง) | http://localhost:8000/?tab=correlations |
| 14 | Slide 14 | Cloud Scheduler fin-etl-trigger | https://console.cloud.google.com/cloudscheduler?project=project-sentiment-etl |

---

*ไฟล์นี้ใช้เป็น Script และโครงสร้าง Slide ครับ แนะนำให้ใช้ Google Slides หรือ Canva สร้าง Slide จริง โดย Copy เนื้อหาจากแต่ละส่วนและเพิ่มรูปตามที่ระบุ*
