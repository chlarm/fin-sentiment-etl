# ระบบ ETL วิเคราะห์ความรู้สึกข่าวการเงินด้วยโมเดล FinBERT บน Google Cloud Platform

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


**สถาบัน:** สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง (KMITL)
**นักศึกษา:** [ชื่อ-นามสกุล] รหัส 66070324
**อาจารย์ที่ปรึกษา:** [ชื่ออาจารย์]
**ปีการศึกษา:** 2568

---

# บทที่ 1: บทนำ (Introduction)

## 1.1 ความเป็นมาและความสำคัญของโครงงาน

ในยุคปัจจุบันที่ข้อมูลข่าวสารทางการเงินมีปริมาณมหาศาลและเคลื่อนที่ด้วยความเร็วสูง นักลงทุนและนักวิเคราะห์ต่างเผชิญกับความท้าทายในการคัดกรองและประเมินผลกระทบของข่าวต่อราคาสินทรัพย์อย่างทันท่วงที ข้อมูลข่าวสารที่ไม่ได้รับการประมวลผลหรือวิเคราะห์อย่างเป็นระบบมักก่อให้เกิดความล่าช้าในการตัดสินใจ ซึ่งในตลาดการเงินความล่าช้าเพียงไม่กี่วินาทีอาจส่งผลต่อผลตอบแทนได้อย่างมีนัยสำคัญ

การวิเคราะห์ความรู้สึก (Sentiment Analysis) เป็นสาขาย่อยของการประมวลผลภาษาธรรมชาติ (Natural Language Processing: NLP) ที่มุ่งจำแนกอารมณ์หรือทัศนคติที่แฝงอยู่ในข้อความ ในบริบทการเงิน โมเดล FinBERT ซึ่งพัฒนาต่อยอดจากสถาปัตยกรรม BERT (Bidirectional Encoder Representations from Transformers) ที่ผ่านการเทรน (Fine-tuned) ด้วยคลังข้อความการเงินขนาดใหญ่ ถือเป็นโมเดลที่ทรงประสิทธิภาพสูงสุดสำหรับงานประเภทนี้

โครงงานนี้จึงมีแนวคิดในการพัฒนาระบบ ETL (Extract, Transform, Load) อัตโนมัติ ที่ดึงข่าวการเงินจากแหล่งข้อมูล RSS Feed ของ Google News วิเคราะห์ความรู้สึกด้วยโมเดล FinBERT และเก็บผลลัพธ์ลงฐานข้อมูลเชิงสัมพันธ์ (Relational Database) โดยทั้งหมดนี้ถูกปรับใช้บน Google Cloud Platform เพื่อให้บริการผ่าน Web Dashboard สาธารณะซึ่งผู้ใช้ทั่วไปสามารถเข้าถึงได้

---

> **[รูปที่ 1.1]** แสดงตัวอย่างหน้า Web Dashboard ที่ทำงานบน Google Cloud Run  
> 📸 แคปหน้าจอเว็บ http://localhost:8000 ทั้งหน้า รวมถึงส่วนกราฟและตาราง

---

## 1.2 วัตถุประสงค์ของโครงงาน

1. พัฒนาไปป์ไลน์ ETL อัตโนมัติสำหรับดึงข้อมูลราคาสินทรัพย์ทางการเงินและข่าวสารรายวัน
2. นำโมเดล FinBERT มาใช้จำแนกความรู้สึกของข่าว (Positive / Negative / Neutral) อย่างแม่นยำ
3. ออกแบบและสร้างฐานข้อมูลที่มีประสิทธิภาพสำหรับการจัดเก็บและสืบค้นข้อมูลในรูปแบบ Star Schema
4. นำระบบทั้งหมดขึ้นสู่ Google Cloud Platform (GCP) แบบ Serverless Architecture ที่ทนทานและขยายตัวได้
5. พัฒนา Web Dashboard สำหรับแสดงผลข้อมูลแบบกราฟิกเพื่อสนับสนุนการตัดสินใจลงทุน

## 1.3 ขอบเขตของโครงงาน

- **สินทรัพย์ที่ครอบคลุม:** หุ้น US ได้แก่ AAPL, TSLA, MSFT; สกุลเงินดิจิทัล BTC-USD; ตลาด Forex ได้แก่ EURUSD=X และ THBUSD=X; และทองคำ GC=F
- **แหล่งข้อมูลราคา:** Yahoo Finance API (yfinance) และ Stooq เป็นแหล่งสำรอง
- **แหล่งข้อมูลข่าว:** Google News RSS Feed
- **โมเดล AI:** FinBERT (ProsusAI/finbert) จาก HuggingFace
- **โครงสร้างพื้นฐาน Cloud:** Google Cloud Platform (Cloud Run, Cloud SQL, Artifact Registry, Cloud Scheduler)
- **การแจ้งเตือน:** ระบบ Email Alert ผ่าน SMTP ส่งรายงานผลการรัน ETL ทุกวัน

## 1.4 ประโยชน์ที่คาดว่าจะได้รับ

1. ผู้ใช้งานสามารถติดตามแนวโน้มความรู้สึกของตลาดต่อสินทรัพย์ต่างๆ ได้สะดวก
2. ระบบสามารถทำงานเป็นอัตโนมัติทุกวันโดยไม่ต้องการการดูแลจากมนุษย์
3. เป็นแบบอย่างของการนำหลักการ MLOps มาใช้จริงในระดับงานวิจัย

---

# บทที่ 2: ทบทวนวรรณกรรมและทฤษฎีที่เกี่ยวข้อง (Literature Review)

## 2.1 การวิเคราะห์ความรู้สึก (Sentiment Analysis)

การวิเคราะห์ความรู้สึกหรือการวิเคราะห์ความคิดเห็น (Opinion Mining) คือกระบวนการใช้คอมพิวเตอร์ระบุและประเมินทัศนคติที่แสดงออกในข้อความ ในบริบทการเงิน ข่าวสารและรายงานวิเคราะห์มีผลกระทบต่อราคาหลักทรัพย์อย่างมีนัยสำคัญ งานวิจัยของ Tetlock (2007) แสดงให้เห็นว่าคะแนน Negative Media Coverage มีความสัมพันธ์เชิงลบกับผลตอบแทนหุ้นในวันถัดไป ซึ่งยืนยันความสำคัญของการวิเคราะห์ความรู้สึกในการพยากรณ์ตลาด

## 2.2 โมเดล BERT และ FinBERT

**BERT (Bidirectional Encoder Representations from Transformers)** พัฒนาโดย Google ในปี 2018 เป็นโมเดลภาษาเชิงลึก (Deep Language Model) ที่ใช้กลไก Self-Attention ในการเรียนรู้ความสัมพันธ์ระหว่างคำในทั้งสองทิศทาง ส่งผลให้เข้าใจบริบทของภาษาได้แม่นยำกว่าโมเดลรุ่นก่อนอย่าง LSTM หรือ GRU มาก

**FinBERT** (Araci, 2019) เป็นโมเดล BERT ที่ถูก Fine-tuned ด้วยข้อความทางการเงินจาก Financial PhraseBank Dataset ซึ่งประกอบด้วยหัวข้อข่าวทางการเงินที่มีผู้เชี่ยวชาญติดป้ายกำกับ (Label) ว่าเป็น Positive, Negative หรือ Neutral ผลลัพธ์คือโมเดลที่เข้าใจศัพท์และนัยสำคัญเฉพาะทางการเงิน เช่น "Volatility Surges" = Negative หรือ "Record Earnings" = Positive ได้อย่างแม่นยำสูง

---

> **[รูปที่ 2.1]** แผนภาพสถาปัตยกรรม Transformer ของ BERT  
> 📸 ดาวน์โหลดรูปสถาปัตยกรรม BERT จากเอกสาร Attention is All You Need (Vaswani et al., 2017) หรือวาดแผนภาพง่ายๆ แสดง Encoder Stack ของ BERT

---

## 2.3 กระบวนการ ETL (Extract, Transform, Load)

ETL เป็นกระบวนการหลักของวิศวกรรมข้อมูล (Data Engineering) ประกอบด้วยสามขั้นตอน:
- **Extract:** ดึงข้อมูลดิบจากแหล่งต่างๆ เช่น API, RSS Feed, Database
- **Transform:** ทำความสะอาด แปลงรูปแบบ คำนวณ และเพิ่มมูลค่าให้ข้อมูล เช่น คำนวณ Return, วิเคราะห์ Sentiment
- **Load:** โหลดข้อมูลที่ผ่านการแปลงแล้วเข้าสู่คลังข้อมูลปลายทาง (Data Warehouse)

## 2.4 Star Schema Design

Star Schema เป็นรูปแบบการออกแบบฐานข้อมูล (Database Schema) สำหรับงาน OLAP (Online Analytical Processing) ประกอบด้วยตารางหลักกลาง (Fact Table) ที่เก็บค่าที่วัดได้และตาราง Dimension รอบข้าง ข้อดีของ Star Schema คือสืบค้นข้อมูลเชิงวิเคราะห์ได้รวดเร็ว เพราะลด JOIN ที่ซับซ้อน

---

> **[รูปที่ 2.2]** แผนภาพ Star Schema ของฐานข้อมูล fin_dw  
> 📸 วาดหรือสร้างด้วย DrawSQL / dbdiagram.io โดยแสดงตาราง: fact_price_daily, fact_news, fact_sentiment_daily, dim_asset, dim_date, dim_source

---

## 2.5 Docker และ Container Technology

Docker คือแพลตฟอร์มการสร้าง Container ที่ช่วยให้แอปพลิเคชันสามารถทำงานได้บนสภาพแวดล้อมใดก็ได้อย่างสอดคล้องกัน โดยบรรจุโค้ด, Dependencies, และ OS Library ไว้ในหน่วยที่เรียกว่า Container Image ซึ่งพกพาได้ ในโครงงานนี้ใช้ Docker สำหรับตัดสินแยก Web Dashboard (fin-web) และ ETL Pipeline (fin-etl)

## 2.6 Google Cloud Platform (GCP)

GCP คือบริการ Cloud Computing ของ Google ที่นำมาใช้ในโครงงานนี้ประกอบด้วย:
- **Cloud Run:** บริการรัน Container แบบ Serverless ที่ปรับขนาดตามโหลด
- **Cloud SQL:** บริการจัดการฐานข้อมูล PostgreSQL ที่ดูแลรักษาให้อัตโนมัติ
- **Artifact Registry:** คลังเก็บ Docker Image เอกชนบน GCP
- **Cloud Scheduler:** บริการตั้งเวลา (Cron) เพื่อรัน Job อัตโนมัติ

---

# บทที่ 3: การออกแบบและพัฒนาระบบ (System Design & Development)

## 3.1 ภาพรวมสถาปัตยกรรมระบบ

ระบบได้รับการออกแบบตามหลักการ Microservices โดยแยกส่วนประมวลผลและส่วนแสดงผลออกจากกันอย่างชัดเจน มีส่วนประกอบหลัก 4 ส่วน:

1. **Data Extraction Layer:** ดึงราคาหุ้นจาก Yahoo Finance / Stooq และข่าวจาก Google News RSS Feed
2. **AI Processing Layer:** ส่งบทสรุปข่าวผ่านโมเดล FinBERT บน PyTorch เพื่อรับค่าน้ำหนัก Sentiment
3. **Storage Layer:** เก็บข้อมูลทั้งหมดใน PostgreSQL (Cloud SQL) ในรูปแบบ Star Schema
4. **Presentation Layer:** Web Dashboard สร้างด้วย FastAPI + Jinja2 + Chart.js แสดงกราฟ Time-series และตาราง

---

> **[รูปที่ 3.1]** แผนภาพ Architecture Diagram ของระบบทั้งหมด  
> 📸 วาดแผนภาพ Flowchart หรือ Architecture Diagram แสดง: Cloud Scheduler → Cloud Run Job (ETL) → Yahoo Finance + Google News → FinBERT Model → Cloud SQL → Cloud Run (Web Dashboard) → ผู้ใช้งาน  
> *แนะนำใช้ draw.io, Lucidchart, หรือ Excalidraw*

---

## 3.2 โมดูล Extract: การดึงข้อมูล

### 3.2.1 ราคาสินทรัพย์ทางการเงิน

ระบบดึงราคาสินทรัพย์ผ่านไลบรารี `yfinance` เป็นแหล่งหลัก โดยกำหนดสินทรัพย์เป้าหมาย 7 รายการผ่าน Environment Variable `TICKERS` ได้แก่ `AAPL, TSLA, MSFT, BTC-USD, EURUSD=X, THBUSD=X, GC=F` ระบบดึงข้อมูลย้อนหลัง 14 วัน เพื่อรองรับกรณีที่ข้อมูลขาดหายในวันหยุด และมีกลไก Fallback ไปยัง Stooq ในกรณีที่ Yahoo Finance ไม่ตอบสนอง

```python
# src/extract/prices_yahoo.py
def fetch_daily_prices_yahoo(tickers, end_d, lookback_days=14):
    start_d = end_d - timedelta(days=lookback_days)
    df = yf.download(tickers=tickers, start=start_d, end=end_d+timedelta(1))
    ...
```

### 3.2.2 ข่าวสารการเงิน

ระบบดึงข่าวผ่าน Google News RSS Feed โดยสร้าง URL ค้นหาตาม Ticker Symbol พร้อมกำหนด `LOOKBACK_HOURS` เพื่อกรองเฉพาะข่าวใน 168 ชั่วโมง (7 วัน) ย้อนหลัง ระบบยังมีกลไกกรองแหล่งข่าวน่าเชื่อถือ (Trusted Sources) เช่น Bloomberg, Reuters, CNBC, Yahoo Finance, Seeking Alpha

```
URL Pattern: https://news.google.com/rss/search?q={search_term}%20market&hl=en-US&gl=US&ceid=US:en
```

รูปแบบการค้นหาใช้ `search_term` พิเศษสำหรับ Ticker ที่ชื่อยากค้นหา เช่น:
- `GC=F` → ค้นหา `gold` *(เดิม "gold price USD futures" — วัดแล้วได้ข่าว 4 ชิ้น เทียบกับ 39 ชิ้น)*
- `THBUSD=X` → ค้นหา `Thai baht` *(เดิม "Thai baht USD exchange rate" — 1 ชิ้น เทียบกับ 9 ชิ้น)*
- `^GSPC` → ค้นหา `S&P 500` *(ต้อง percent-encode เครื่องหมาย & มิฉะนั้น query จะถูกตัดเหลือ `q=S`)*

คำค้นทุกตัวถูกกำหนดจากการวัดกับ feed จริง ไม่ใช่การออกแบบตามสัญชาตญาณ รายละเอียดใน `thesis_methodology_revised.md` §3.3

---

> **[รูปที่ 3.2]** ตัวอย่างโค้ดส่วน Extract ของ news_rss.py  
> 📸 แคปหน้าจอโค้ดในส่วน `fetch_news_rss_for_ticker()` ใน VSCode / โปรแกรม Editor

---

## 3.3 โมดูล Transform: การแปลงและวิเคราะห์ข้อมูล

### 3.3.1 การคำนวณ Return ของราคา

ระบบคำนวณผลตอบแทนรายวัน (Daily Return) และ Percentage Change จากข้อมูลราคา Open/Close เพื่อใช้แสดงบน Dashboard

```
return_1d = (close_today - close_yesterday) / close_yesterday
pct_change = return_1d × 100
```

### 3.3.2 การวิเคราะห์ Sentiment ด้วย FinBERT

โมเดล FinBERT โหลดจาก HuggingFace Hub (`ProsusAI/finbert`) ผ่านไลบรารี Transformers และ PyTorch ทีมรับข้อความหัวข่าวเป็น Input และ Output เป็นน้ำหนักความน่าจะเป็นของ 3 Class:

| Class    | ความหมาย     |
|----------|--------------|
| Positive | ข่าวเชิงบวก  |
| Negative | ข่าวเชิงลบ   |
| Neutral  | ข่าวเป็นกลาง |

ค่าสุดท้ายที่เก็บใน Database คือ `sentiment_score` ซึ่งคำนวณจาก `P(Positive) - P(Negative)` มีค่าอยู่ใน `[-1, 1]`

### 3.3.3 การคำนวณ Sentiment Index รายวัน

ระบบรวมคะแนน Sentiment ของข่าวทั้งหมดในหนึ่งวันในแต่ละ Ticker เพื่อสร้าง `sentiment_index` (ค่าเฉลี่ยถ่วงน้ำหนัก) และจัดเก็บไว้ในตาราง `fact_sentiment_daily`

---

> **[รูปที่ 3.3]** กราฟเปรียบเทียบราคาหุ้น (เส้นสีฟ้า) กับ Sentiment Score (แถบสีในกราฟ)  
> 📸 แคปหน้าจอกราฟ "Market Dynamics" บนหน้า Dashboard ของ http://localhost:8000

---

## 3.4 โมดูล Load: การโหลดข้อมูลเข้าฐานข้อมูล

ระบบใช้ SQLAlchemy เป็นตัวกลางเชื่อมต่อฐานข้อมูล PostgreSQL โดยใช้กลยุทธ์ `UPSERT (INSERT … ON CONFLICT DO UPDATE)` เพื่อรองรับการรัน ETL ซ้ำโดยไม่ให้ข้อมูลซ้ำกัน (Idempotency) และใช้ `news_hash` (SHA256 ของ Ticker + Published_at + Title + URL) เพื่อตรวจสอบและกำจัดข่าวซ้ำ

## 3.5 การออกแบบฐานข้อมูล

ฐานข้อมูล `fin_dw` ออกแบบตามหลัก Star Schema มีตาราง Fact 3 ตาราง และ Dimension 3 ตาราง:

**Fact Tables:**
- `fact_price_daily` — ราคาสินทรัพย์รายวัน (Open, High, Low, Close, Volume, Return)
- `fact_news` — ข่าวแต่ละชิ้นพร้อม Sentiment Score และ Label
- `fact_sentiment_daily` — ดัชนีความรู้สึกสรุปรายวันต่อสินทรัพย์

**Dimension Tables:**
- `dim_asset` — รายชื่อสินทรัพย์ (Ticker, Name, Asset Class, Currency)
- `dim_source` — แหล่งข่าว (Source Name, Type, Credibility Score)
- `dim_date` — ตารางมิติวันที่ (Year, Month, Day, Day of Week, is_Weekend)

---

> **[รูปที่ 3.4]** โค้ด DDL ของ Star Schema จาก sql/ddl_star_schema.sql  
> 📸 แคปหน้าจอไฟล์ `sql/ddl_star_schema.sql` ทั้งไฟล์ใน VSCode

---

## 3.6 Web Dashboard (FastAPI + Jinja2)

Web Dashboard พัฒนาด้วย FastAPI ซึ่งเป็น Web Framework ยุคใหม่ของ Python ที่รองรับ Asynchronous และมีประสิทธิภาพสูง ส่วนแสดงผลใช้ Jinja2 Template Engine และ Chart.js สำหรับกราฟแบบ Interactive โดยมี 5 แท็บหลัก:

1. **News** — ตารางข่าวทั้งหมดพร้อมคะแนนและป้าย Sentiment
2. **Daily Summary** — สรุปข่าวรายวันแยกตามสินทรัพย์ พร้อมตัวเลขสถิติ
3. **Metrics** — ตารางราคาพร้อม Return และ Sentiment Index
4. **Correlations** — ตารางค่าสหสัมพันธ์ (Pearson Correlation) ระหว่างผลตอบแทนและ News Sentiment ในวันเดียวกัน (corr_t) และ 1-2 วันล่าช้า (corr_lag1, corr_lag2)
5. ~~**Heatmap**~~ *(ถอดออก ก.ย. 2026 — แสดงภาพรวมได้แต่ไม่ช่วยตัดสินใจ)* — เดิมเป็นแผนที่ความร้อนแสดง Sentiment และ Return ล่าสุดของสินทรัพย์ทั้งหมด

---

> **[รูปที่ 3.5]** หน้า Web Dashboard แท็บ Correlations  
> 📸 แคปหน้าจอเว็บโดย Click แท็บ Correlations บน http://localhost:8000

> **[รูปที่ 3.6]** หน้า Web Dashboard แท็บ Daily Summary  
> 📸 แคปหน้าจอเว็บโดย Click แท็บ Daily Summary บน http://localhost:8000

---

# บทที่ 4: การนำระบบขึ้นคลาวด์ (Cloud Deployment)

## 4.1 ภาพรวมโครงสร้างพื้นฐาน GCP

ระบบถูกออกแบบโดยใช้ GCP บริการสำคัญ 4 อย่าง ดังนี้:

| บริการ | ชื่อทรัพยากร | หน้าที่ |
|---|---|---|
| Cloud SQL (PostgreSQL 16) | `fin-sentiment-db` | ฐานข้อมูล Production |
| Artifact Registry | `fin-repo` | คลังเก็บ Docker Image |
| Cloud Run (Service) | `fin-web` | Web Dashboard สาธารณะ |
| Cloud Run (Job) | `fin-etl-job` | ETL Pipeline รันรายวัน |
| Cloud Scheduler | `fin-etl-trigger` | ตั้งเวลารัน ETL อัตโนมัติ 08.00 น. |

**Region:** `asia-southeast1` (Singapore)
**Project ID:** `project-sentiment-etl`

---

> **[รูปที่ 4.1]** ภาพรวม GCP Project Dashboard  
> 📸 แคปหน้าจอ https://console.cloud.google.com/home/dashboard?project=project-sentiment-etl

---

## 4.2 การสร้าง Docker Image และ Artifact Registry

ระบบถูกแบ่งเป็น Docker Image 2 ตัว แต่ละตัวใช้ Dockerfile แยกกัน:

- **`Dockerfile.web`** — สำหรับรัน Web Dashboard (FastAPI)
- **`Dockerfile.etl`** — สำหรับรัน ETL Pipeline และ FinBERT Model

Image ทั้งสองถูก Build ด้วยคำสั่ง `--platform linux/amd64` เพื่อให้รองรับ CPU Architecture ของ Cloud Run บน GCP (Google ใช้ AMD64 ทั้งหมด) จากนั้น Push ไปยัง Artifact Registry ที่ `asia-southeast1`

```bash
docker build --platform linux/amd64 -t asia-southeast1-docker.pkg.dev/project-sentiment-etl/fin-repo/fin-web -f Dockerfile.web .
docker push asia-southeast1-docker.pkg.dev/project-sentiment-etl/fin-repo/fin-web
```

---

> **[รูปที่ 4.2]** Artifact Registry แสดง Images ที่ Push ขึ้นไป  
> 📸 แคปหน้าจอ https://console.cloud.google.com/artifacts/docker/project-sentiment-etl/asia-southeast1/fin-repo

---

## 4.3 Cloud SQL และการเชื่อมต่อแบบ Unix Socket

Cloud SQL สร้างด้วย PostgreSQL 16 และตั้งชื่อ Instance ว่า `fin-sentiment-db` ฐานข้อมูลที่ใช้งานจริงชื่อ `fin_dw` ซึ่งถูกสร้างและกำหนด Schema ผ่านไฟล์ `sql/ddl_star_schema.sql`

การเชื่อมต่อจาก Cloud Run ไปยัง Cloud SQL ทำผ่าน **Cloud SQL Auth Proxy** โดยอัตโนมัติผ่าน **Unix Socket** ซึ่งเร็วกว่าการเชื่อมต่อผ่าน TCP/IP และปลอดภัยมากกว่า ไม่ต้องเปิด Public IP ของ Database

Connection String ที่ใช้มีรูปแบบพิเศษ:
```
postgresql+psycopg2://postgres:xxx@/fin_dw?host=/cloudsql/project-sentiment-etl:asia-southeast1:fin-sentiment-db
```

---

> **[รูปที่ 4.3]** หน้าจอ Cloud SQL Console แสดง Instance fin-sentiment-db  
> 📸 แคปหน้าจอ https://console.cloud.google.com/sql/instances/fin-sentiment-db/overview?project=project-sentiment-etl

---

## 4.4 การ Deploy Web Dashboard ด้วย Cloud Run

Web Dashboard ถูก Deploy เป็น Cloud Run Service โดยตั้งค่าเชื่อมต่อกับ Cloud SQL ผ่าน `--add-cloudsql-instances` ทำให้ Cloud Run รู้จัก Cloud SQL โดยอัตโนมัติ พร้อม Environment Variables สำคัญได้แก่ `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD` และ `POSTGRES_DB`

Service นี้เปิดรับ HTTP Traffic สาธารณะที่ Port 8000 มีการตั้ง Memory 512MB และ Maximum Scale 3 Instances เพื่อ Handle Load ได้ในกรณีมีผู้ใช้พร้อมกัน

---

> **[รูปที่ 4.4]** หน้าจอ Cloud Run Service fin-web แสดงสถานะ Revision และ URL  
> 📸 แคปหน้าจอ https://console.cloud.google.com/run/detail/asia-southeast1/fin-web/metrics?project=project-sentiment-etl

---

## 4.5 ETL Pipeline บน Cloud Run Jobs

ETL Pipeline ถูก Deploy เป็น Cloud Run Job (`fin-etl-job`) แทนที่จะเป็น Service เพราะมันต้องการรัน จบ และหยุดเอง (Run-to-Completion) ไม่ใช่รัน Long-running Server

การตั้งค่าที่สำคัญ:
- **Memory:** 4GB — จำเป็นสำหรับ PyTorch FinBERT Model ที่ต้องการ RAM มาก
- **CPU:** 1000m (1 vCPU)
- **Task Timeout:** 10 นาที
- **Cloud SQL Connection:** เชื่อมต่อผ่าน Unix Socket เช่นเดียวกับ Web

ผลการทดสอบการรัน Manual ครั้งแรก (Execution ID: `fin-etl-job-m2lj8`):
- ✅ **สำเร็จ** ใช้เวลา 1 นาที 14 วินาที
- ดึงข่าว 7 Ticker ผ่าน Google News RSS
- วิเคราะห์ Sentiment ทุกข่าวผ่าน FinBERT สำเร็จ
- บันทึกข้อมูลเข้า Cloud SQL สำเร็จ

---

> **[รูปที่ 4.5]** Cloud Run Jobs แสดงประวัติการรัน Execution ที่สำเร็จ  
> 📸 แคปหน้าจอ https://console.cloud.google.com/run/jobs/details/asia-southeast1/fin-etl-job/executions?project=project-sentiment-etl แสดงสถานะ Succeeded (เครื่องหมายติ๊กถูกสีเขียว)

> **[รูปที่ 4.6]** Logs ของ Cloud Run Job ETL แสดงผลลัพธ์การรัน  
> 📸 แคปหน้าจอ Cloud Logging หรือ Log ของ Execution fin-etl-job ที่แสดง "ETL DONE" พร้อม Price/News/Sentiment Row Counts

---

## 4.6 Cloud Scheduler: ระบบรันอัตโนมัติ

เพื่อให้ ETL ทำงานอย่างต่อเนื่องโดยอัตโนมัติ ได้ตั้งค่า Cloud Scheduler Job ชื่อ `fin-etl-trigger` ด้วย:
- **Cron Expression:** `0 8 * * *` (ทำงานทุกวันเวลา 08:00 น.)
- **Timezone:** `Asia/Bangkok` (UTC+7)
- **Target:** HTTP POST ไปยัง Cloud Run Jobs API เพื่อสั่ง Execute `fin-etl-job`
- **Authentication:** OAuth2 ด้วย Service Account ของ Cloud Run

---

> **[รูปที่ 4.7]** Cloud Scheduler แสดง Job fin-etl-trigger สถานะ Enabled  
> 📸 แคปหน้าจอ https://console.cloud.google.com/cloudscheduler?project=project-sentiment-etl แสดงตาราง Jobs พร้อม Next Run Time 08:00 ของวันพรุ่งนี้

---

## 4.7 ระบบการแจ้งเตือนทาง Email (SMTP Alert)

ระบบมีการแจ้งเตือนอัตโนมัติผ่าน Email เมื่อ ETL ทำงานเสร็จหรือเกิดข้อผิดพลาด โดยพัฒนาโมดูล `src/alerting.py` ที่ใช้ Python `smtplib` ส่งอีเมลผ่าน Gmail SMTP Server

Email แจ้งเตือนประกอบด้วย:
- วันที่รัน (Run Date)
- จำนวนแถวราคาที่บันทึก (Price Rows)
- จำนวนข่าวที่บันทึก (News Rows)
- จำนวน Sentiment Index ที่อัพเดต
- สถานะ DQ Check ว่าผ่านหรือไม่

ความปลอดภัยถูกควบคุมผ่าน Google **App Password** (รหัสผ่าน 16 ตัวอักษรที่สร้างเฉพาะสำหรับแอปพลิเคชัน) แทนรหัสผ่านบัญชีปกติ และถูกซ่อนไว้ใน Environment Variable ของ Cloud Run

```python
# src/alerting.py
def send_email_alert(subject: str, body: str):
    msg = EmailMessage()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        smtp.send_message(msg)
```

---

> **[รูปที่ 4.8]** ตัวอย่าง Email แจ้งเตือนที่ได้รับในกล่อง Inbox  
> 📸 แคปหน้าจอ Inbox ของ 66070324@kmitl.ac.th ที่แสดงอีเมลหัวข้อ "✅ ETL SUCCESS ✅" จาก anatomyaz1@gmail.com

---

# บทที่ 5: ผลลัพธ์ สรุปผล และข้อเสนอแนะ (Results, Conclusion & Future Work)

## 5.1 ผลการดำเนินงาน

โครงงานบรรลุวัตถุประสงค์ทุกข้อที่ตั้งไว้ ระบบสามารถทำงานบน Google Cloud Platform ได้อย่างเต็มรูปแบบและมีเสถียรภาพ สรุปผลที่ได้รับมีดังนี้:

| รายการ | ผลลัพธ์ |
|---|---|
| ETL Pipeline ทำงานสำเร็จ | ✅ สำเร็จ — แยก 3 task รวม ~3 นาที (30 สินทรัพย์) |
| Web Dashboard เข้าถึงได้ | ✅ รันบนเครื่องผ่าน Docker — http://localhost:8000 (7 แท็บ) |
| ระบบแจ้งเตือน Email | ✅ ส่งอีเมลสรุปหลังรัน ETL ทุกครั้ง |
| Cloud Scheduler ตั้งเวลาสำเร็จ | ⏸ ทดสอบผ่านแล้ว แต่หยุดทำงาน (billing ปิด) — ปัจจุบันใช้ Airflow บนเครื่อง 06:00 น. |
| การเชื่อมต่อ Cloud SQL | ⏸ instance อยู่สถานะ SUSPENDED — ปัจจุบันใช้ PostgreSQL ใน Docker |
| สินทรัพย์ที่ติดตาม | 7 รายการ (AAPL, TSLA, MSFT, BTC-USD, EURUSD=X, THBUSD=X, GC=F) |

---

> **[รูปที่ 5.1]** หน้า Web Dashboard แสดง Stat Cards (จำนวน Prices, News, Sentiments)  
> 📸 แคปหน้าจอส่วน Header ของ Dashboard ที่มีตัวเลขสถิติ 3 Card ด้านบน

> **[รูปที่ 5.2]** หน้า Web Dashboard แท็บ News แสดงข่าวพร้อม Sentiment Label  
> 📸 แคปหน้าจอ Dashboard แท็บ News ที่มีตาราง ข่าว Positive/Negative/Neutral พร้อม Badge สี

---

## 5.2 การวิเคราะห์ผลและการแปลความหมาย

จากข้อมูลที่ระบบเก็บสะสมได้ในช่วงแรก สามารถสรุปได้ว่า:

- **ความสัมพันธ์ระหว่าง News Sentiment กับ Price Return:** จากแท็บ Correlations บน Dashboard แสดงค่า Pearson Correlation ระหว่าง Sentiment Index ของวันนั้น (corr_t) และผลตอบแทนราคาของวันเดียวกัน ซึ่งเป็นการวัดความสอดคล้องเชิงเส้นตรง ค่าที่ใกล้ +1 หมายถึงข่าวดีมักมาพร้อมกับราคาสูงขึ้น และค่าใกล้ -1 หมายถึงข่าวแย่มักมาพร้อมกับราคาต่ำลง
- **ความล่าช้าของตลาด (Lag Effect):** ค่า `corr_lag1` และ `corr_lag2` แสดงว่าตลาดอาจยังตอบสนองต่อข่าวในวันถัดไปหรืออีก 2 วัน สะท้อน Information Latency ของตลาด
- **ประสิทธิภาพของโมเดล FinBERT:** จากการสังเกตข่าวเชิงบวก (เช่น "Record Earnings", "Stock Buyback Program") ระบบสามารถจำแนกได้อย่างถูกต้อง ในขณะที่ข่าวเชิงลบ (เช่น "Layoffs", "SEC Investigation") ก็ถูกจำแนกออกได้ชัดเจน

---

> **[รูปที่ 5.3]** ตาราง Correlation บน Dashboard แสดงค่า Pearson Correlation ของแต่ละ Ticker  
> 📸 แคปหน้าจอ Dashboard แท็บ Correlations แสดงตาราง Correlation ทุกคอลัมน์

---

## 5.3 ข้อจำกัดของระบบ

1. **ข้อมูลข่าวจากแหล่งฟรี:** ระบบาใช้ Google News RSS และ Yahoo Finance ซึ่งมีการจำกัดโควต้า (Rate Limit) ทำให้อาจพบข้อผิดพลาด `YFRateLimitError` หรือข่าวไม่ครบในบางวัน
2. **Batch Processing เท่านั้น:** ปัจจุบันระบบรันวันละ 1 ครั้ง จึงไม่สามารถตรวจจับข่าวฉับพลัน (Breaking News) และผลกระทบต่อราคาได้แบบ Real-time
3. **การจัดเก็บ Credentials:** Secret ต่างๆ เช่น DB Password ยังถูกส่งเป็น Environment Variables โดยตรงแทนที่จะใช้ Google Secret Manager ซึ่งปลอดภัยกว่า
4. **ข้อมูลย้อนหลังจำกัด:** ฐานข้อมูล GCP เพิ่งเริ่มเก็บข้อมูลตั้งแต่วันแรกที่ Deploy จึงยังมีข้อมูลจำนวนน้อย ต้องใช้เวลาสะสมข้อมูลอย่างน้อย 1-3 เดือนเพื่อการวิเคราะห์ที่มีนัยสำคัญทางสถิติ

## 5.4 ข้อเสนอแนะสำหรับการพัฒนาต่อยอด

1. **ยกระดับแหล่งข้อมูล:** เปลี่ยนไปใช้ Bloomberg API, Alpha Vantage, หรือ Settrade เพื่อข้อมูลราคาและข่าวที่แม่นยำและต่อเนื่อง
2. **Real-time Streaming Architecture:** ใช้ Google Pub/Sub หรือ Apache Kafka เพื่อประมวลผลข่าว Breaking News ในระดับวินาที แทน Batch Processing ทุกวัน
3. **Microservice สำหรับ AI:** แยก FinBERT Model ออกมาเป็น Dedicated Service บน Vertex AI Endpoint ที่รองรับ GPU หรือ TPU เพื่อเพิ่มความเร็วการ Inference และลด Memory ใน ETL Container
4. **Google Secret Manager:** ย้าย Credentials ทั้งหมดไปเก็บใน Google Secret Manager และให้ Cloud Run ดึงมาตอน Startup เพื่อความปลอดภัยระดับ Production
5. **หุ้นไทย:** ขยายการติดตามให้ครอบคลุมหุ้นในตลาดหลักทรัพย์แห่งประเทศไทย (SET) และเชื่อมต่อกับ Settrade API หรือ กลต. Open Data

## 5.5 สรุป

โครงงานนี้ประสบความสำเร็จในการออกแบบ พัฒนา และนำไปใช้งานระบบ ETL อัจฉริยะที่ผสมผสานเทคโนโลยี AI (FinBERT), วิศวกรรมข้อมูล (Star Schema, Python), และ Cloud Infrastructure (Google Cloud Platform) เข้าด้วยกันอย่างลงตัว ระบบสามารถทำงานได้อย่างอัตโนมัติ ปลอดภัย และเสถียรโดยไม่ต้องการการดูแลจากมนุษย์ในการรันประจำวัน ซึ่งถือเป็นการนำหลักการ MLOps (Machine Learning Operations) และ DataOps มาใช้ในระดับโครงงานวิจัยได้อย่างครบถ้วน

เมื่อระบบสะสมข้อมูลได้เพียงพอในระยะยาว Web Dashboard จะสามารถเปิดเผยข้อมูลเชิงลึกที่มีคุณค่า เช่น รูปแบบความสัมพันธ์ระยะยาวระหว่างข่าวและราคา ฤดูกาลของ Sentiment ในตลาด และความแม่นยำของ Lag Correlation ที่อาจนำไปสู่การพัฒนาระบบสนับสนุนการตัดสินใจลงทุนในอนาคต

---

## บรรณานุกรม (References)

1. Araci, D. (2019). FinBERT: Financial Sentiment Analysis with Pre-trained Language Models. *arXiv preprint arXiv:1908.10063*.
2. Devlin, J., Chang, M. W., Lee, K., & Toutanova, K. (2018). BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. *arXiv preprint arXiv:1810.04805*.
3. Tetlock, P. C. (2007). Giving Content to Investor Sentiment: The Role of Media in the Stock Market. *The Journal of Finance*, 62(3), 1139-1168.
4. Vaswani, A., et al. (2017). Attention is All You Need. *Advances in neural information processing systems*, 30.
5. Google Cloud. (2024). Cloud Run Documentation. https://cloud.google.com/run/docs
6. Google Cloud. (2024). Cloud SQL for PostgreSQL. https://cloud.google.com/sql/docs/postgres
7. HuggingFace. (2024). ProsusAI/finbert. https://huggingface.co/ProsusAI/finbert
8. Kimball, R., & Ross, M. (2013). *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling* (3rd ed.). John Wiley & Sons.

---
*รายงานฉบับนี้จัดทำขึ้นเพื่อประกอบการนำเสนอโครงงานวิศวกรรม ข้อมูลทั้งหมดมีความถูกต้องตามระบบจริงที่ Deploy บน Google Cloud Platform*
