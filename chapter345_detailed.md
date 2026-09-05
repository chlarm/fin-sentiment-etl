# บทที่ 3
# วิธีการดำเนินการวิจัย (Research Methodology)

การวิจัยครั้งนี้เป็นการวิจัยและพัฒนา (Research and Development: R&D) ที่มุ่งเน้นการออกแบบ พัฒนา และทดสอบระบบซอฟต์แวร์จริง โดยใช้กระบวนการพัฒนาแบบ Iterative ซึ่งทดสอบและปรับปรุงระบบในทุกๆ ขั้นตอนของการพัฒนา การดำเนินงานแบ่งออกเป็น 5 ขั้นตอนหลักดังต่อไปนี้

---

## 3.1 การออกแบบสถาปัตยกรรมระบบโดยรวม (Overall System Architecture)

ก่อนเริ่มพัฒนา ผู้วิจัยได้ออกแบบสถาปัตยกรรมของระบบทั้งหมดโดยคำนึงถึงหลักการสำคัญ 3 ประการ ได้แก่

1. **Separation of Concerns:** แยกส่วนประมวลผล (ETL) ออกจากส่วนแสดงผล (Web Dashboard) เพื่อให้สามารถพัฒนา ทดสอบ และปรับขนาดได้อย่างอิสระ
2. **Fault Tolerance:** ออกแบบให้ระบบยังทำงานได้แม้แหล่งข้อมูลหลักล้มเหลว โดยมีกลไก Fallback (Yahoo Finance → Stooq)
3. **Serverless-First:** เลือกใช้บริการ Managed Services บน GCP เพื่อลดภาระการบริหารจัดการโครงสร้างพื้นฐาน

สถาปัตยกรรมของระบบประกอบด้วย 4 Layer หลักดังภาพต่อไปนี้

---

> **[รูปที่ 3.1]** แผนภาพ System Architecture Diagram ทั้งระบบ (GCP Workflow / Deployment)
> 📸 **คำแนะนำสำหรับแคปรูป:** ก๊อปปี้โค้ดด้านล่างนี้ไปวางใน [Mermaid Live Editor](https://mermaid.live) แล้วเซฟเป็นรูปภาพใส่ได้เลยครับ

```mermaid
flowchart TD
    %% Define Styles
    classDef gcp fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1
    classDef external fill:#f5f5f5,stroke:#9e9e9e,stroke-width:2px,color:#424242
    classDef user fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20
    classDef alert fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100

    %% External Sources
    subgraph External_Sources ["🌐 External Sources"]
        YF(Yahoo Finance API):::external
        STQ(Stooq CSV):::external
        GN(Google News RSS):::external
    end

    %% GCP Ecosystem
    subgraph GCP ["☁️ Google Cloud Platform (GCP)"]
        direction TB
        
        %% Control Layer
        subgraph GCP_Control ["⚙️ Control Layer"]
            CS(Cloud Scheduler\nCron: 0 8 * * *):::gcp
        end

        %% Image Layer
        subgraph GCP_Registry ["📦 Image / Build Layer"]
            AR(Artifact Registry\nfin-etl & fin-web images):::gcp
        end
        
        %% Compute Layer
        subgraph GCP_Compute ["🚀 Compute Layer (Serverless)"]
            ETL(Cloud Run Job\nfin-etl-job\n+ FinBERT Inference):::gcp
            WEB(Cloud Run Service\nfin-web\nDashboard App):::gcp
        end
        
        %% Storage Layer
        subgraph GCP_Storage ["🗄️ Storage Layer"]
            SQL[(Cloud SQL\nPostgreSQL 16\nStar Schema)]:::gcp
        end
    end

    %% Alerts
    subgraph Monitoring ["🔔 Monitoring & Alerts"]
        SMTP(SMTP Email Alert):::alert
        LOGS(Cloud Logging):::alert
    end

    %% Users
    USR((Web Browser\nFrontend User)):::user

    %% Define Flows (Arrows)
    AR -.->|Deploy Images| ETL
    AR -.->|Deploy Images| WEB
    
    CS -->|Trigger POST via HTTP| ETL
    
    ETL -->|Fetch Prices| YF
    ETL -->|Fallback Fetch| STQ
    ETL -->|Fetch News| GN
    
    ETL -->|Load/Upsert Data| SQL
    ETL -->|Send Status| SMTP
    ETL -->|Write Logs| LOGS
    
    WEB -->|Query Dashboard Data| SQL
    
    USR <-->|HTTPS Request/Response| WEB
```

---

## 3.2 การพัฒนาระบบ ETL Pipeline

### 3.2.1 โมดูลสกัดข้อมูลราคาสินทรัพย์ (Price Extraction Module)

ระบบกำหนดสินทรัพย์เป้าหมายทั้งหมด **30 รายการ** ผ่าน Environment Variable `TICKERS` ครอบคลุมสินทรัพย์ 5 ประเภทเพื่อความหลากหลายในการวิเคราะห์ (ร่างฉบับก่อนหน้าระบุ 7 รายการ ซึ่งเป็นขอบเขตในช่วง เม.ย. 2026)

| ประเภท | จำนวน | รายการ |
|---|---|---|
| หุ้น US (Stocks) | 21 | AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, NFLX, AMD, ORCL, INTC, JPM, V, JNJ, XOM, PG, KO, WMT, HD, DIS, BA |
| ดัชนี (Index) | 3 | ^GSPC (S&P 500), ^DJI (Dow Jones), ^IXIC (Nasdaq) |
| สินค้าโภคภัณฑ์ (Commodity) | 2 | GC=F (ทองคำ), CL=F (น้ำมันดิบ WTI) |
| คริปโทเคอร์เรนซี (Crypto) | 2 | BTC-USD, ETH-USD |
| อัตราแลกเปลี่ยน (Forex) | 2 | EURUSD=X, THBUSD=X |

การขยายจาก 7 เป็น 30 รายการมีความสำคัญต่อความน่าเชื่อถือของผลการวิจัย ดังที่แสดงใน §5.2.1 ซึ่งความได้เปรียบที่วัดได้จากสินทรัพย์ 5 ตัวไม่คงอยู่เมื่อขยายเป็น 29 ตัว

โมดูลดึงข้อมูลราคาผ่านไลบรารี `yfinance` ข้อมูลที่ดึงได้แก่ OHLCV (Open, High, Low, Close, Volume) และ Adj Close สำหรับการปรับราคาหลังจ่ายปันผล

**การกำหนดช่วงเวลาที่ดึงย้อนหลัง** ร่างเดิมใช้ค่าคงที่ `lookback_days=14` ซึ่งพบภายหลังว่าทำให้ช่องว่างของข้อมูลกลายเป็นถาวร เมื่อระบบหยุดทำงานระหว่างวันที่ 12-21 ส.ค. 2026 การรันครั้งถัดไปใช้หน้าต่าง 14 วันซึ่งเริ่มต้น**หลัง**ช่องว่าง จึงเติมเฉพาะวันล่าสุดและรายงานว่าสำเร็จ โดยทิ้งวันที่ขาดหายไว้อย่างถาวร เนื่องจากหน้าต่างเลื่อนไปข้างหน้าเสมอ

ปัจจุบันระบบคำนวณช่วงเวลาที่ต้องดึงจากข้อมูลจริง (14-400 วัน) โดยตรวจสอบสองกรณี

- **ช่องว่างท้ายชุดข้อมูล** — วันล่าสุดที่มีข้อมูลตามหลังวันปัจจุบัน ตรวจพบด้วย `max(d)`
- **ช่องว่างภายใน** — วันที่ขาดหายตรงกลางโดยมีข้อมูลขนาบทั้งสองด้าน ซึ่ง `max(d)` เป็นปัจจุบันและไม่รายงานความผิดปกติใดๆ กรณีนี้คือกรณีที่หลบเลี่ยงการตรวจจับ

ช่องว่างภายในถูกตรวจพบโดยการหาวันในปฏิทินที่ไม่มีแถวราคาเลยภายในช่วงที่จัดเก็บ ซึ่งเป็นเกณฑ์ที่ชัดเจนเพราะสินทรัพย์คริปโทเคอร์เรนซีซื้อขายทุกวันรวมวันหยุด (BTC-USD มีข้อมูล 3,693 จาก 3,705 วันปฏิทินที่ครอบคลุม และ 12 วันที่ขาดคือวันที่ระบบหยุดทำงานพอดี) วันที่ไม่มีข้อมูลเลยจึงเป็นช่องว่างเสมอ ไม่ใช่วันหยุดตลาด

กรณีที่ Yahoo Finance ไม่ตอบสนองหรือคืนข้อมูลว่างเปล่า ระบบจะ Fallback ไปยัง Stooq โดยอัตโนมัติ ซึ่งเป็นบริการข้อมูลราคาสำรองที่ไม่มีข้อจำกัดเรื่อง Rate Limit

**กระบวนการ Cleansing ข้อมูลราคา:**
- Rename Column Headers จาก `Open, High, Low, Close, Adj Close` เป็น `open, high, low, close, adj_close` ตามมาตรฐาน Snake_case ของฐานข้อมูล
- แปลง Column วันที่จาก `Date` เป็น `d` ในรูปแบบ `datetime.date` ที่ไม่มี Timezone
- ลบแถวที่ค่าราคา Close เป็น NaN ออก (อาจเกิดจากวันหยุดหรือ Delistiment)
- คำนวณ `return_1d = (close_t - close_{t-1}) / close_{t-1}` และ `pct_change = return_1d × 100`

### 3.2.2 โมดูลสกัดข้อมูลข่าว (News Extraction Module)

ระบบดึงข่าวจาก Google News RSS Feed โดยสร้าง URL ค้นหาแบบ Dynamic สำหรับแต่ละ Ticker เพื่อรับประกันว่าข่าวที่ดึงมาตรงกับสินทรัพย์เป้าหมาย โดยเฉพาะ Ticker ที่ชื่อสัญลักษณ์ไม่ตรงกับชื่อที่ใช้ค้นหาข่าว เช่น `GC=F` ซึ่งถ้าค้นหาตรงๆ จะไม่พบข่าวที่เกี่ยวข้อง ระบบจึงมีการ Map Ticker กับ Search Term พิเศษ

**คำค้นทุกตัวถูกกำหนดจากการวัดกับ feed จริง ไม่ใช่การออกแบบตามสัญชาตญาณ** เนื่องจากการทดลองแสดงว่าสัญชาตญาณให้ผลตรงกันข้าม รายละเอียดการวัดอยู่ใน `thesis_methodology_revised.md` §3.3 ค่าปัจจุบัน (5 ก.ย. 2026):

```python
# src/config.py
_DEFAULT_TICKER_SEARCH_TERMS = {
    # สินทรัพย์ที่ไม่ใช่หุ้น — ใช้ "ชื่อเรียกมาตรฐาน" ไม่ใช่คำบรรยาย
    "GC=F":     "gold",          # เดิม "gold price USD futures":  4 -> 39 ข่าว
    "CL=F":     "WTI crude",     # เดิม "crude oil price futures WTI": 30 -> 42
    "EURUSD=X": "EUR USD",       # เดิม "euro dollar exchange rate":  5 -> 52
    "THBUSD=X": "Thai baht",     # เดิม "Thai baht USD exchange rate": 1 -> 9
    "BTC-USD":  "Bitcoin",       # เดิม "Bitcoin USD price crypto":  16 -> 37
    "ETH-USD":  "ETH crypto",    # เดิม "Ethereum USD price crypto": 13 -> 38
    "^GSPC":    "S&P 500",       # เดิม "S&P 500 stock market index": 44 -> 56
    "^DJI":     "Dow Jones",     # เดิม "Dow Jones industrial average": 52 -> 59
    "^IXIC":    "Nasdaq",        # เดิม "NASDAQ stock market index":  30 -> 83
    # หุ้นสามัญ — "<สัญลักษณ์> stock" ยกเว้น NFLX ที่วัดแล้วแย่ลง
    "AAPL": "AAPL stock", "MSFT": "MSFT stock", ...   # 20 จาก 21 ตัว
}
```

**URL Pattern ที่ใช้:**
```
https://news.google.com/rss/search?q={search_term}%20market&hl=en-US&gl=US&ceid=US:en
```

การประกอบ URL ต้องเข้ารหัสคำค้นแบบ percent-encoding ทั้งสตริง มิใช่แทนที่เฉพาะช่องว่าง เนื่องจากเครื่องหมาย `&` ในคำค้น (เช่น "S&P 500") จะปิดพารามิเตอร์ `q=` ทำให้ Google ได้รับคำค้นเพียง `q=S` ข้อผิดพลาดนี้ไม่แสดงอาการ เพราะ feed ยังคืนผลลัพธ์ที่มีรูปแบบถูกต้องประมาณ 100 รายการ สังเกตได้เฉพาะจากจำนวนข่าวที่ผ่านตัวกรอง (3 จาก 102) เมื่อแก้ไขแล้ว ^GSPC ได้ข่าวเพิ่มเป็น 43 รายการ

**กระบวนการ Cleansing ข้อมูลข่าว:**
1. **Time Filtering:** ใช้ `LOOKBACK_HOURS = 2160` กรองข่าวภายใน 90 วันล่าสุด

   ค่าเดิมคือ 168 (7 วัน) โดยให้เหตุผลว่าเพื่อป้องกันการวิเคราะห์ข่าวเก่าที่ตลาดรับรู้ไปแล้ว การตรวจสอบพบว่าเหตุผลดังกล่าวไม่ถูกต้อง เนื่องจากข่าวแต่ละชิ้นถูกบันทึกตามวันที่เผยแพร่ (`published_d`) ไม่ใช่วันที่ดึงข้อมูล ตัวกรองนี้จึงไม่ได้ป้องกันการวิเคราะห์ข่าวเก่า แต่เป็นการทิ้งข่าวที่ดึงมาได้แล้ว

   นอกจากนี้ยังพบว่าสมมติฐานที่ว่า Google News RSS ให้เฉพาะข่าวปัจจุบันเป็นเท็จ การวัดพบว่า query หนึ่งคืนผลลัพธ์ประมาณ 100 รายการ ย้อนหลังได้ถึงราว 140 วัน เมื่อวัดจำนวนข่าวจากแหล่งที่เชื่อถือได้ข้าม 10 สินทรัพย์: หน้าต่าง 7 วันได้ 171 ข่าว, 30 วันได้ 250 ข่าว และ 90 วันได้ 507 ข่าว

   การขยายหน้าต่างไม่มีต้นทุนด้านเครือข่าย เพราะเป็น HTTP request เดียวกันและตัวกรองทำงานกับผลลัพธ์ที่ได้มาแล้ว ส่วนต้นทุนการประมวลผลถูกควบคุมด้วยการตรวจ `news_hash` ก่อนเรียก FinBERT (ดูข้อ 4) ผลที่สำคัญคือ pipeline สามารถเก็บข้อมูลย้อนหลังได้เองเมื่อเกิดการหยุดทำงาน
2. **Source Credibility Filtering:** กรองเฉพาะข่าวจากแหล่งที่อยู่ใน Trusted Sources List เช่น Bloomberg, Reuters, CNBC, Yahoo Finance, Seeking Alpha เพื่อลด Noise จากบทความ Blog หรือเว็บที่ไม่น่าเชื่อถือ
3. **Timestamp Normalization:** แปลงวันและเวลาเผยแพร่ทุกรูปแบบ (RFC 2822, ISO 8601) ให้เป็น UTC Timezone เสมอ
4. **Deduplication:** สร้าง `news_hash = SHA256(ticker + published_at + title + url)` เพื่อเป็น Unique Identifier ของข่าวแต่ละชิ้น ถ้า Hash ซ้ำ Database จะปฏิเสธการ Insert โดย UNIQUE Constraint โดยอัตโนมัติ

   ระบบตรวจสอบ `news_hash` กับฐานข้อมูล**ก่อน**เรียกใช้ FinBERT ไม่ใช่อาศัยการปฏิเสธของ UNIQUE Constraint เพียงอย่างเดียว เนื่องจากการให้คะแนน sentiment เป็นขั้นตอนที่ใช้เวลามากที่สุด การกรองก่อนทำให้ต้นทุนแปรผันตามจำนวนข่าวใหม่จริง ไม่ใช่ตามความกว้างของหน้าต่างเวลา ในรอบที่ข้อมูลอิ่มตัวแล้ว ระบบดึงข่าว 1,351 รายการแต่พบข่าวใหม่เพียง 12 รายการ ใช้เวลาทั้งขั้นตอน 54 วินาที

### 3.2.3 โมดูลวิเคราะห์ Sentiment ด้วย FinBERT (Transform Module)

เป็นขั้นตอนที่ซับซ้อนและใช้ทรัพยากรสูงที่สุดในไปป์ไลน์ โดยโหลดโมเดล `ProsusAI/finbert` จาก HuggingFace Hub และ Tokenizer มาไว้บน RAM ตั้งแต่เริ่มต้นโปรแกรม (Load Once)

**ขั้นตอนการ Inference FinBERT สำหรับข่าวทุกชิ้น:**

```
Input: "Apple Reports Record Q1 Earnings, Stock Surges 5%"
         ↓
    WordPiece Tokenizer
         ↓
Token IDs: [101, 6207, 7292, 2501, 2275, 1053, 1016, 22578, ..., 102]
         ↓
    FinBERT Encoder (12 Transformer Layers)
         ↓
Logits: [positive=2.83, negative=-1.74, neutral=0.21]
         ↓
    Softmax
         ↓
Probabilities: [P(pos)=0.89, P(neg)=0.04, P(neu)=0.07]
         ↓
sentiment_score = P(pos) - P(neg) = 0.89 - 0.04 = 0.85
sentiment_label = "positive"
```

**การสร้าง Sentiment Index รายวัน:**
หลังจากวิเคราะห์ข่าวทุกชิ้นแล้ว ระบบจะรวม Sentiment Score ของข่าวทั้งหมดในแต่ละวันและแต่ละ Ticker เพื่อสร้าง Daily Sentiment Index โดยคำนวณค่าเฉลี่ย (Mean) ของ `sentiment_score` ทั้งหมดพร้อมนับจำนวนข่าว Positive, Negative, Neutral แล้วบันทึกลงตาราง `fact_sentiment_daily`

### 3.2.4 โมดูลโหลดข้อมูล (Load Module)

ระบบโหลดข้อมูลทั้งหมดผ่าน SQLAlchemy ORM และใช้กลยุทธ์ต่างกันตามลักษณะของข้อมูล:

| ตาราง | กลยุทธ์ | เหตุผล |
|---|---|---|
| `fact_price_daily` | UPSERT (`ON CONFLICT DO UPDATE`) | ราคาอาจมีการแก้ไขย้อนหลังได้ |
| `fact_news` | INSERT ถ้า `news_hash` ไม่ซ้ำ | ข่าวไม่เปลี่ยนแปลง แค่ป้องกันซ้ำ |
| `fact_sentiment_daily` | UPSERT | Sentiment Index ถูกคำนวณใหม่เสมอ |
| `dim_asset / dim_source / dim_date` | UPSERT (`ON CONFLICT DO NOTHING`) | Dimension ไม่ค่อยเปลี่ยนแปลง |

ก่อน Load ข้อมูล Fact ใดๆ ระบบจะ Ensure Dimension Tables ก่อนเสมอ เพื่อป้องกัน Foreign Key Constraint Violation:
```
ensure_dim_dates() → ensure_assets() → ensure_sources()
→ upsert_price_daily() → insert_news() → upsert_daily_sentiment()
```

### 3.2.5 ระบบตรวจสอบคุณภาพข้อมูล (Data Quality Checks)

หลังจากโหลดข้อมูลเสร็จทุกครั้ง ระบบจะรัน DQ Check อัตโนมัติผ่านโมดูล `src/dq/checks.py` เพื่อตรวจสอบความสมบูรณ์ของข้อมูลก่อนส่ง Email Alert ผลลัพธ์ DQ Check (`Pass/Fail`) จะถูกส่งรวมไปใน Email รายงานประจำวัน

---

## 3.3 การออกแบบฐานข้อมูล (Database Design)

### 3.3.1 โครงสร้างฐานข้อมูลแบบ Star Schema

เพื่อตอบสนองต่อลักษณะของข้อมูลที่มีปริมาณมากและต้องการนำไปแสดงผลบน Dashboard อย่างรวดเร็ว (OLAP Workload) ระบบบัญชีข้อมูล (`fin_dw`) บน Cloud SQL จึงถูกออกแบบโดยใช้หลักการ **Star Schema**

**จุดประสงค์ของการใช้ Star Schema ในโครงงานนี้:**
1. **เพิ่มประสิทธิภาพการ Query ข้อมูล (Performance):** ลดการ Join ตารางที่ซับซ้อน ทำให้ Web Dashboard สามารถดึงข้อมูลจำนวนมาก (Aggregated Data) ไปพล็อตกราฟได้อย่างรวดเร็วในระดับหลักมิลลิวินาที
2. **แยกมิติและข้อเท็จจริงชัดเจน (Separation of Data):** แยกข้อมูลที่เป็นตัวเลขเชิงปริมาณ เช่น ราคาหุ้น หรือ คะแนน Sentiment ไว้ใน **Fact Tables** และแยกข้อมูลเชิงบรรยายที่จะใช้เป็นตัวกรอง (Filters) ไว้ใน **Dimension Tables** 
3. **รองรับการขยายตัว (Scalability):** หากในอนาคตต้องการเพิ่มสินทรัพย์ (Asset) แนวใหม่ โครงสร้างนี้สามารถรองรับได้ทันทีโดยไม่ต้องแก้โครงสร้างตารางหลัก

**ขั้นตอนการออกแบบและสร้าง Star Schema:**
1. **การวิเคราะห์ Business Process:** กำหนดว่าระบบต้องการวัดผลอะไร (Metrics) ซึ่งในที่นี้คือ ราคาเปิด/ปิดประจำวัน, เปอร์เซ็นต์การเปลี่ยนแปลงของราคา, และดัชนีความรู้สึก (Sentiment Index)
2. **การกำหนด Granularity:** กำหนดระดับความละเอียดของข้อมูล โดยให้ข้อมูลราคามีความละเอียดระดับ "รายวัน" (Daily) และข้อมูลข่าวมีความละเอียดระดับ "รายชิ้นข่าว" (Per Article)
3. **การออกแบบ Dimension Tables:** สร้างมิติข้อมูลเพื่อใช้มุมมองในการวิเคราะห์ ได้แก่ `dim_asset` (สินทรัพย์), `dim_source` (แหล่งข่าว), และ `dim_date` (มิติเวลา)
4. **การออกแบบ Fact Tables:** สร้างตารางเก็บข้อเท็จจริง ได้แก่ `fact_price_daily` (ราคารายวัน), `fact_news` (ข่าวรายชิ้น), และ `fact_sentiment_daily` (สรุปความรู้สึกรายวัน)

---

> **[รูปที่ 3.2]** แผนภาพ Entity-Relationship (ER) Diagram ของ Star Schema 
> 📸 **คำแนะนำสำหรับแคปรูป:** 
> 1. ไปที่เว็บไซต์ https://dbdiagram.io/ และวางโค้ด SQL DDL ลงไปเพื่อให้เว็บวาดความสัมพันธ์โยงเส้นให้อัตโนมัติ 
> 2. หรือแคปหน้าจอโครงสร้างตารางจากโปรแกรม DBeaver / pgAdmin โดยให้ตาราง Fact อยู่ตรงกลาง และ Dimension ล้อมรอบเป็นรูปดาว

---

โครงสร้างสคริปต์ DDL (Data Definition Language) ที่สำคัญในการสร้าง Schema มีดังต่อไปนี้:

**Dimension Tables:**
ตารางมิติข้อมูล (Dimension Tables) ทำหน้าที่เก็บข้อมูลเชิงบริบทที่ไม่ค่อยมีการเปลี่ยนแปลง

```sql
-- dim_asset: เก็บข้อมูลมิติของสินทรัพย์ (เช่น หุ้น, ทองคำ, อัตราแลกเปลี่ยน)
CREATE TABLE IF NOT EXISTS dim_asset (
  asset_id    SERIAL PRIMARY KEY,
  ticker      TEXT NOT NULL UNIQUE,
  asset_name  TEXT,
  asset_class TEXT,       -- แยกประเภทกลุ่มสินทรัพย์
  currency    TEXT,
  exchange    TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- dim_source: เก็บข้อมูลมิติของแหล่งข่าวเพื่อวิเคราะห์ความน่าเชื่อถือ
CREATE TABLE IF NOT EXISTS dim_source (
  source_id       SERIAL PRIMARY KEY,
  source_name     TEXT NOT NULL,
  source_type     TEXT NOT NULL DEFAULT 'rss',
  base_url        TEXT,
  credibility_score NUMERIC(3,1) DEFAULT 5.0,
  UNIQUE (source_name, source_type)
);

-- dim_date: ปฏิทินกลางสำหรับวิเคราะห์ข้อมูลข้ามตาราง (Time-series)
CREATE TABLE IF NOT EXISTS dim_date (
  d         DATE PRIMARY KEY,
  y         INT NOT NULL,  -- ปี
  m         INT NOT NULL,  -- เดือน
  day       INT NOT NULL,  -- วัน
  dow       INT NOT NULL,  -- วันในสัปดาห์ 
  is_weekend BOOLEAN NOT NULL
);
```

**Fact Tables:**
ตารางข้อเท็จจริง (Fact Tables) ทำหน้าที่เก็บข้อมูลธุรกรรมและตัวเลขชี้วัด โดยชี้ Foreign Key กลับไปยัง Dimension

```sql
-- fact_price_daily: เก็บข้อเท็จจริงของราคาและผลตอบแทนรายวัน
CREATE TABLE IF NOT EXISTS fact_price_daily (
  asset_id   INT NOT NULL REFERENCES dim_asset(asset_id),
  d          DATE NOT NULL REFERENCES dim_date(d),
  open       NUMERIC, high  NUMERIC, low   NUMERIC,
  close      NUMERIC, adj_close NUMERIC,
  volume     BIGINT,
  return_1d  NUMERIC,  -- ผลตอบแทนรายวันคำนวณจาก (close_t - close_{t-1})/close_{t-1}
  pct_change NUMERIC,  
  PRIMARY KEY (asset_id, d)
);

-- fact_news: เก็บข้อเท็จจริงของข่าวแต่ละชิ้น (Granularity ระดับ Article)
CREATE TABLE IF NOT EXISTS fact_news (
  news_id         BIGSERIAL PRIMARY KEY,
  asset_id        INT NOT NULL REFERENCES dim_asset(asset_id),
  source_id       INT NOT NULL REFERENCES dim_source(source_id),
  published_at    TIMESTAMPTZ NOT NULL,
  published_d     DATE NOT NULL REFERENCES dim_date(d),
  title           TEXT NOT NULL,
  url             TEXT,
  news_hash       TEXT NOT NULL UNIQUE,  -- MD5 Hash ป้องกันข่าวซ้ำ
  sentiment_score NUMERIC,   -- ค่า Sentiment Score จาก FinBERT [-1, 1]
  sentiment_label TEXT       -- 'positive' | 'negative' | 'neutral'
);

-- fact_sentiment_daily: เก็บข้อเท็จจริงดัชนีความรู้สึกรวมรายวัน
CREATE TABLE IF NOT EXISTS fact_sentiment_daily (
  asset_id         INT NOT NULL REFERENCES dim_asset(asset_id),
  d                DATE NOT NULL REFERENCES dim_date(d),
  news_count       INT NOT NULL,
  sentiment_mean   NUMERIC, -- ค่าดัชนีความรู้สึก (Sentiment Index)
  pos_count        INT NOT NULL,
  neu_count        INT NOT NULL,
  neg_count        INT NOT NULL,
  PRIMARY KEY (asset_id, d)
);
```

### 3.3.2 Analytical View

นอกจาก Table หลักแล้ว ระบบยังสร้าง **Database View** ชื่อ `vw_daily_asset_metrics` เพื่อรวมข้อมูลจากหลายตารางไว้ในที่เดียว ลดความซับซ้อนของ Query ใน Web Dashboard

```sql
CREATE OR REPLACE VIEW vw_daily_asset_metrics AS
SELECT
    a.ticker,
    p.d,
    p.open, p.high, p.low, p.close,
    p.return_1d,
    p.pct_change,
    COALESCE(s.sentiment_mean, 0)  AS sentiment_index,
    COALESCE(s.news_count, 0)      AS news_count
FROM fact_price_daily p
JOIN dim_asset a ON p.asset_id = a.asset_id
LEFT JOIN fact_sentiment_daily s
    ON p.asset_id = s.asset_id AND p.d = s.d;
```

---

## 3.4 การพัฒนา Web Dashboard

### 3.4.1 โครงสร้างเทคโนโลยีของ Web Dashboard

Web Dashboard พัฒนาด้วย Stack ดังต่อไปนี้:

| เทคโนโลยี | หน้าที่ | เหตุผลที่เลือก |
|---|---|---|
| **FastAPI** | Web Framework / API Server | รวดเร็ว, รองรับ Async, Type Hints |
| **SQLAlchemy** | ORM / Database Connection | รองรับทั้ง Local PostgreSQL และ Cloud SQL Unix Socket |
| **Jinja2** | Template Engine | Flexible, Fast Server-side Rendering |
| **Chart.js** | Library กราฟ | Interactive Charts บน Browser |
| **Pandas** | ประมวลผลข้อมูลใน Python | Data Manipulation ก่อนส่งสู่ Template |
| **Uvicorn** | ASGI Server | Production-grade สำหรับ FastAPI |

### 3.4.2 หน้าจอ Dashboard หลัก

Dashboard หลักมี URL Pattern เป็น `/?tab=<tab>&ticker=<ticker>&start_d=&end_d=` รองรับการ Filter ข้อมูลหลายมิติพร้อมกัน ปัจจุบันประกอบด้วย **7 แท็บ** โดยโครงสร้างถูกจัดวางใหม่ตามข้อสังเกตของคณะกรรมการที่ว่าเว็บควรให้ประโยชน์มากกว่าการแสดงข่าวและค่าสหสัมพันธ์

**แท็บ Home:**
หน้าแรก แสดงข่าวล่าสุด สินทรัพย์ที่มีข่าวมากที่สุด และรายการที่ราคาปรับขึ้น/ลงมากที่สุด

**แท็บ Signal — แท็บหลักที่เพิ่มใหม่:**
แสดงผลการทำนายทิศทางราคาจากแบบจำลอง พร้อมข้อมูลที่จำเป็นต่อการประเมินความน่าเชื่อถือของตัวเลขนั้น ได้แก่ ความแม่นยำบนชุดทดสอบที่แบบจำลองไม่เคยเห็น เส้นฐานเปรียบเทียบ (majority baseline) ผลตอบแทนสะสมเทียบกับการถือครองระยะยาว ช่วงความแม่นยำจาก walk-forward validation และการอธิบายการทำนายรายวันด้วยค่า SHAP

แท็บนี้ตอบข้อสังเกตของคณะกรรมการโดยตรง เนื่องจากรายงานว่า "การทำตามสัญญาณนี้จะให้ผลอย่างไร" แทนที่จะรายงานค่าสัมประสิทธิ์สหสัมพันธ์

**แท็บ Watchlist:**
รายการสินทรัพย์ที่ผู้ใช้ติดตาม ระบบตรวจสอบสัญญาณทุกครั้งที่เปิดหน้า และแจ้งเตือนเมื่อสัญญาณเปลี่ยนทิศทางจากครั้งก่อน

**แท็บ Fundamentals:**
งบการเงินรายไตรมาสจาก SEC EDGAR ย้อนหลังสูงสุด 19 ปีต่อบริษัท แสดงการ์ดสรุป (รายได้พร้อมอัตราเติบโตเทียบปีก่อน กำไรสุทธิ อัตรากำไร EPS กระแสเงินสดอิสระ) กราฟแท่งรายได้ 20 ไตรมาสล่าสุด และตารางเต็ม

**แท็บ News:**
แสดงตารางข่าวทั้งหมด พร้อม Badge สีตาม Sentiment Label (เขียว=Positive, แดง=Negative, เทา=Neutral) มีระบบ Pagination 15 ข่าวต่อหน้า สามารถคลิก URL เพื่อเปิดต้นฉบับข่าวได้โดยตรง

**แท็บ Daily Summary:**
แสดงสรุปข่าวรายวันจัดกลุ่มตาม Ticker พร้อมสถิติข้อมูล ได้แก่ จำนวนข่าว Positive / Negative / Neutral และค่า Average Sentiment Score รองรับการแปลหัวข่าวเป็นภาษาไทยแบบ On-demand ผ่าน Google Translate API (Free Endpoint)

**แท็บ Metrics:**
แสดงตารางราคาประจำวันของแต่ละ Ticker พร้อม Columns ทางการเงิน ได้แก่ Open, Close, Daily Return (%), Sentiment Index และ News Count

**แท็บ Correlations:**
แสดงตารางค่าสหสัมพันธ์ (Pearson Correlation Coefficient) ระหว่าง Daily Return และ Sentiment Index ในสามช่วงเวลา ได้แก่ วันเดียวกัน (`corr_t`), Sentiment ล่าช้า 1 วัน (`corr_lag1`) และ Sentiment ล่าช้า 2 วัน (`corr_lag2`)

แท็บนี้มีแถบคำอธิบายกำกับไว้ชัดเจนว่าเป็น **หลักฐานประกอบ ไม่ใช่ผลลัพธ์หลัก** พร้อมระบุขนาดตัวอย่าง ช่วงความเชื่อมั่น และการปรับค่าจากการทดสอบหลายครั้ง เหตุผลอยู่ใน §4.3

> **แท็บ Heatmap ถูกถอดออก** ร่างเดิมระบุแท็บที่ 5 เป็น Heatmap ของ Sentiment เทียบผลตอบแทน แท็บนี้ถูกถอดออกเนื่องจากแสดงภาพรวมได้แต่ไม่ให้ข้อมูลที่นำไปใช้ตัดสินใจได้ ซึ่งเป็นประเด็นเดียวกับที่คณะกรรมการตั้งข้อสังเกต

### 3.4.3 กราฟ Market Dynamics

ส่วนที่โดดเด่นที่สุดของ Dashboard คือกราฟ Market Dynamics ซึ่งรวมข้อมูล 2 ชุดในกราฟเดียว ได้แก่ เส้นราคา (Price Line) และแถบ Sentiment Score (Sentiment Bar) ทำให้เห็นความสัมพันธ์ระหว่างข่าวและราคาได้อย่างชัดเจน ข้อมูลถูกดึงผ่าน View `vw_daily_asset_metrics` และส่งเป็น JSON ไปยัง Chart.js บน Browser

---

## 3.5 การปรับใช้ระบบบน Google Cloud Platform (Deployment)

> **สถานะ ณ 5 ก.ย. 2026** หัวข้อนี้บันทึกขั้นตอนการ deploy ที่ดำเนินการจริงและทดสอบผ่านแล้วในช่วง เม.ย.-ก.ค. 2026 แต่ **ระบบไม่ได้ทำงานบน GCP ในปัจจุบัน** เนื่องจาก billing ของโครงการถูกปิด ทำให้ Cloud SQL instance (`fin-sentiment-db`) อยู่ในสถานะ `SUSPENDED` และ Cloud Scheduler ไม่สามารถเรียกใช้งานได้ (API ตอบกลับ `PERMISSION_DENIED: This API method requires billing to be enabled`)
>
> สภาพแวดล้อมที่ใช้งานจริงในปัจจุบันคือเครื่องส่วนบุคคล รัน PostgreSQL และ Apache Airflow ผ่าน Docker Compose ผลการทดลองทั้งหมดในบทที่ 4 มาจากสภาพแวดล้อมนี้ ข้อจำกัดที่ตามมาถูกอภิปรายใน §5.4 ของ `thesis_methodology_revised.md`
>
> Container images และ Cloud Run service/job ที่สร้างไว้ยังคงอยู่ หากเปิด billing อีกครั้งสามารถกลับมาใช้งานได้ตามขั้นตอนด้านล่าง

### 3.5.1 ขั้นตอนการ Deploy บน GCP

การนำระบบขึ้น GCP ดำเนินการตามลำดับขั้นตอนดังนี้:

**ขั้นที่ 1: เตรียมโครงสร้างพื้นฐาน GCP**
```bash
# เปิดใช้งาน API ที่จำเป็น
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  artifactregistry.googleapis.com cloudscheduler.googleapis.com

# สร้าง Artifact Registry
gcloud artifacts repositories create fin-repo \
  --repository-format=docker --location=asia-southeast1
```

**ขั้นที่ 2: สร้าง Cloud SQL Instance**
```bash
gcloud sql instances create fin-sentiment-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=asia-southeast1
```

**ขั้นที่ 3: Build และ Push Docker Images**
```bash
# Build สำหรับ linux/amd64 (Cloud Run Architecture)
docker build --platform linux/amd64 \
  -t asia-southeast1-docker.pkg.dev/project-sentiment-etl/fin-repo/fin-etl \
  -f Dockerfile.etl .
docker push asia-southeast1-docker.pkg.dev/project-sentiment-etl/fin-repo/fin-etl
```

**ขั้นที่ 4: Deploy Cloud Run Service (Web Dashboard)**
```bash
gcloud run deploy fin-web \
  --image .../fin-web \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --add-cloudsql-instances project-sentiment-etl:asia-southeast1:fin-sentiment-db \
  --set-env-vars="POSTGRES_HOST=/cloudsql/...,POSTGRES_DB=fin_dw"
```

**ขั้นที่ 5: Deploy Cloud Run Job (ETL)**
```bash
gcloud run jobs create fin-etl-job \
  --image .../fin-etl \
  --region asia-southeast1 \
  --memory 4Gi \  # จำเป็นสำหรับ FinBERT
  --add-cloudsql-instances project-sentiment-etl:asia-southeast1:fin-sentiment-db
```

**ขั้นที่ 6: ตั้ง Cloud Scheduler**
```bash
gcloud scheduler jobs create http fin-etl-trigger \
  --schedule="0 8 * * *" \
  --time-zone="Asia/Bangkok" \
  --uri="https://.../jobs/fin-etl-job:run" \
  --http-method=POST \
  --oauth-service-account-email=...
```

### 3.5.2 การแก้ปัญหา Cloud SQL Connection (Unix Socket)

ปัญหาสำคัญที่พบในการพัฒนาคือการเชื่อมต่อ Cloud SQL จาก Cloud Run ซึ่งต้องใช้รูปแบบ **Unix Socket Connection String** แทน TCP แบบปกติ Connection String มีรูปแบบพิเศษดังนี้

```python
# src/config.py
@property
def sqlalchemy_url(self) -> str:
    if self.pg_host.startswith("/cloudsql"):
        # Unix Socket (สำหรับ Cloud Run)
        return f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}@/{self.pg_db}?host={self.pg_host}"
    # TCP (สำหรับ Local Development)
    return f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_db}"
```

การออกแบบนี้ทำให้ Code เดียวกันรันได้ทั้งบนเครื่อง Developer (TCP) และบน GCP (Unix Socket) โดยไม่ต้องแก้ Code เลย เพียงแค่ตั้งค่า Environment Variable `POSTGRES_HOST` ให้ต่างกัน

---

## 3.6 ระบบแจ้งเตือนทาง Email (SMTP Alert System)

ระบบแจ้งเตือนถูกพัฒนาในโมดูล `src/alerting.py` โดยใช้ Python Standard Library `smtplib` ส่งอีเมลผ่าน Gmail SMTP Server พอร์ต 465 (SSL) ความปลอดภัยถูกควบคุมด้วย Google App Password แทนรหัสผ่านปกติ ระบบจะส่ง Email แจ้งเตือนอัตโนมัติใน 2 กรณี:

1. **ETL SUCCESS:** ส่งสรุปผลการรัน ได้แก่ จำนวน Price Rows, News Rows, Sentiment Index Rows และสถานะ DQ Check
2. **ETL FAILED:** ส่งข้อความ Error ที่เกิดขึ้น เพื่อให้ Admin แก้ไขได้ทันท่วงที

---

# บทที่ 4
# ผลการทดลองและระบบต้นแบบ (Experimental Results & Prototype)

## 4.1 ผลการ Deploy และทดสอบระบบบน GCP

### 4.1.1 ผลการทดสอบ ETL Pipeline (Cloud Run Job)

ภายหลังการแก้ไขปัญหาสำคัญ 2 ประเด็น ได้แก่ การกำหนด IAM Permission (`roles/cloudsql.client`) ให้แก่ Service Account และการแก้ไข Connection String ให้ใช้ Unix Socket ETL Pipeline สามารถทำงานได้สำเร็จอย่างสมบูรณ์ในการรันครั้งแรก ผลการรัน Execution ID: `fin-etl-job-m2lj8` มีดังนี้

**(ก) ผลการรันบน Cloud Run — เม.ย. 2026, ติดตาม 7 สินทรัพย์**

| รายการ | ผลลัพธ์ |
|---|---|
| สถานะการรัน | ✅ Succeeded |
| ระยะเวลาทั้งหมด | 1 นาที 14 วินาที |
| Price Rows ที่ Upsert | 258 แถว |
| News Rows ที่ Insert (หลัง Dedup) | 93 ข่าว |
| Sentiment Index ที่ Upsert | 20 แถว |
| DQ Check | Pass |
| หน่วยความจำที่ใช้สูงสุด | ~3.2 GB จากทั้งหมด 4 GB |

**(ข) ผลการรันในสภาพแวดล้อมปัจจุบัน — ก.ย. 2026, ติดตาม 30 สินทรัพย์**

ตัวเลขในตาราง (ก) มาจากช่วงที่ระบบยังติดตามเพียง 7 สินทรัพย์และใช้หน้าต่างข่าว 7 วัน จึงไม่สะท้อนขนาดของระบบปัจจุบัน ผลการรันบน Docker + Airflow ในเครื่องเป็นดังนี้

| รายการ | ผลลัพธ์ |
|---|---|
| สถานะการรัน | ✅ สำเร็จทั้ง 3 task |
| `fetch_prices` | 43 วินาที |
| `fetch_news` | 2 นาที 36 วินาที (รอบแรก) / 54 วินาที (รอบที่ข้อมูลอิ่มตัว) |
| `data_quality` | 9 วินาที |
| ข่าวที่ดึงต่อรอบ | ~1,350-1,580 รายการ (หน้าต่าง 90 วัน) |
| ข่าวใหม่ที่ต้องให้คะแนน | 12-857 รายการ ขึ้นกับช่องว่างที่ต้องเก็บย้อนหลัง |
| DQ Check | Pass ทั้ง 8 รายการ |

**ตารางที่ 4.2 ปริมาณข้อมูลสะสมในฐานข้อมูล ณ 5 ก.ย. 2026**

| ตาราง | จำนวนแถว | ช่วงเวลา |
|---|---|---|
| `fact_price_daily` | 145,918 | 2006-09-11 → 2026-09-05 |
| `fact_technical_daily` | 145,918 | 2006-09-11 → 2026-09-05 |
| `fact_news` | 7,518 | 2025-12-16 → 2026-09-05 |
| `fact_sentiment_daily` | 1,589 | 2025-12-16 → 2026-09-05 |
| `fact_fundamentals_quarterly` | 1,134 | 2007-09-30 → 2026-06-30 |

จำนวนสินทรัพย์ที่มีข้อมูล sentiment ครบเกณฑ์ 30 วันขึ้นไป: **29 จาก 30 รายการ** (ไม่ผ่านเกณฑ์เฉพาะ THB/USD ด้วยเหตุผลที่อธิบายใน §5.1 ของ `thesis_methodology_revised.md`)

---

> **[รูปที่ 4.1]** หน้าจอ Cloud Run Jobs Executions แสดงสถานะ Succeeded (เครื่องหมายถูกสีเขียว)
> 📸 แคปหน้าจอ https://console.cloud.google.com/run/jobs/details/asia-southeast1/fin-etl-job/executions?project=project-sentiment-etl

> **[รูปที่ 4.2]** Cloud Run Job Logs แสดง "=== ETL DONE ===" พร้อมสรุปจำนวนแถว
> 📸 แคปหน้าจอ Log ที่มีข้อความ ETL DONE, price_source=yahoo, prices_upsert_rows=258 เป็นต้น

---

### 4.1.2 ผลการทดสอบ Web Dashboard

Web Dashboard เปิดให้บริการที่ URL สาธารณะ **https://fin-web-nnebdwza6q-as.a.run.app** โหลดและแสดงข้อมูลได้อย่างสมบูรณ์ โดยผลการทดสอบมีดังนี้

| รายการ | ผลลัพธ์ |
|---|---|
| URL | https://fin-web-nnebdwza6q-as.a.run.app |
| สถานะ HTTP | 200 OK |
| เวลาโหลดเฉลี่ย (Cold Start) | ~3-5 วินาที |
| เวลาโหลดเฉลี่ย (Warm) | ~0.5-1.5 วินาที |
| ข้อมูลราคาที่แสดง | 258 Prices (7 Tickers, 90 วันล่าสุด) |
| ข่าวที่แสดง | 93 ข่าว (แบ่ง Pagination 15 ต่อหน้า) |
| Sentiment Analyses | 20 รายการ |

> ตัวเลขข้างต้นเป็นสถานะ ณ เม.ย. 2026 บน Cloud Run ซึ่งขณะนั้นติดตาม 7 สินทรัพย์ ปัจจุบัน Dashboard ทำงานบนเครื่องส่วนบุคคล ติดตาม 30 สินทรัพย์ และมีแท็บเพิ่มขึ้นเป็น 7 แท็บ (Home, Signal, Watchlist, Fundamentals, News, Metrics, Correlations) ปริมาณข้อมูลปัจจุบันดูตารางที่ 4.2

---

> **[รูปที่ 4.3]** หน้า Web Dashboard หลัก แสดง Stat Cards, กราฟ Market Dynamics และ Sparklines
> 📸 แคปหน้าจอ https://fin-web-nnebdwza6q-as.a.run.app ทั้งหน้า (ควรรวมทั้ง Header, Chart และส่วน Tickers)

---

## 4.2 ผลการวิเคราะห์ Sentiment ด้วย FinBERT

### 4.2.1 ตัวอย่างผลลัพธ์การวิเคราะห์ข่าว

ตัวอย่างผลลัพธ์จากการวิเคราะห์ข่าวจริงด้วย FinBERT แสดงให้เห็นความสามารถของโมเดลในการแยกแยะอารมณ์ของข่าวการเงิน

| หัวข่าว | sentiment_score | sentiment_label |
|---|---|---|
| "Apple Reports Record Q1 Earnings, Beating Estimates" | +0.92 | positive |
| "Bitcoin Surges Past $70,000 on ETF Approval News" | +0.88 | positive |
| "Tesla Reports Worst Quarter in Two Years, Layoffs Loom" | -0.81 | negative |
| "Fed Signals Potential Rate Hike Amid Inflation Concern" | -0.74 | negative |
| "Gold Prices Stable as Markets Await CPI Data" | +0.03 | neutral |
| "MSFT Announces Partnership with OpenAI for New Products" | +0.77 | positive |

จากตัวอย่างข้างต้น โมเดล FinBERT สามารถจำแนกข่าวที่เกี่ยวกับ "Record Earnings" ได้ถูกต้องเป็น Positive และข่าว "Layoffs Loom" ที่ใช้ภาษาเชิงลบในบริบทธุรกิจได้ถูกต้องเป็น Negative ซึ่งสะท้อนความสามารถในการเข้าใจ Domain-specific Language ทางการเงิน

### 4.2.2 การกระจายตัวของ Sentiment

---

> **[รูปที่ 4.4]** กราฟ Donut แสดงสัดส่วน Positive / Negative / Neutral ของข่าวทั้งหมด
> 📸 แคปหน้าจอส่วน Sentiment Distribution Chart บน Dashboard (แท็บ News ด้านขวา)

> **[รูปที่ 4.5]** ตาราง News แสดงข่าวพร้อม Badge Sentiment สีต่างๆ
> 📸 แคปหน้าจอตาราง News บน Dashboard (แท็บ News ส่วนล่าง)

---

## 4.3 ผลการวิเคราะห์ความสัมพันธ์ (Correlation Analysis)

> **หมายเหตุสำคัญ** หัวข้อนี้เดิมนำเสนอค่าสหสัมพันธ์เป็นผลการวิจัยหลัก ภายหลังการตรวจสอบพบว่าค่าเหล่านี้ไม่สามารถใช้เป็นข้อสรุปได้ หัวข้อนี้จึงถูกจัดวางใหม่ให้เป็น **สถิติเชิงพรรณนาประกอบ** ผลการวิจัยหลักอยู่ที่การประเมินนอกกลุ่มตัวอย่างใน `thesis_methodology_revised.md` §4.1-4.2

Dashboard แสดงค่า Pearson Correlation Coefficient ระหว่าง Daily Return และ Sentiment Index ซึ่งจะถูกอัพเดตทุกวันพร้อมกับ ETL โดยอธิบายได้ดังนี้

- **corr_t (Same-day Correlation):** ความสัมพันธ์ระหว่าง Sentiment ของวันนั้นกับผลตอบแทนวันนั้น
- **corr_lag1 (1-day Lag):** ความสัมพันธ์ระหว่าง Sentiment ของวัน T กับผลตอบแทนของวัน T+1
- **corr_lag2 (2-day Lag):** ความสัมพันธ์ระหว่าง Sentiment ของวัน T กับผลตอบแทนของวัน T+2

**เหตุผลที่ค่าสหสัมพันธ์ไม่ถูกใช้เป็นข้อสรุป** มีสามประการ ซึ่งได้จากการตรวจสอบชุดข้อมูล Track B ที่มีขนาดใหญ่และย้อนหลังได้ไกลกว่า

**1. ค่า Pearson ไวต่อค่าผิดปกติมาก** เมื่อเทียบกับค่า Spearman ซึ่งวัดด้วยอันดับ พบว่าค่าที่มีนัยสำคัญสูงส่วนใหญ่หายไป

| ตัวแปร @ ขอบเขต | Pearson | Spearman |
|---|---|---|
| revenue_growth_qoq @ 63 วัน | +0.254 \*\*\* | +0.046 (ns) |
| revenue_growth_qoq @ 252 วัน | +0.237 \*\*\* | +0.041 (ns) |
| net_margin @ 252 วัน | −0.228 \*\*\* | −0.053 (\*) |

**2. ค่า p ที่คำนวณจากจำนวนแถวสูงเกินจริง** เนื่องจากแถวในชุดข้อมูลไม่เป็นอิสระต่อกัน ทั้งจากการซ้อนทับของหน้าต่างผลตอบแทนและจากการที่สินทรัพย์เคลื่อนไหวตามตลาดพร้อมกัน (ค่าสหสัมพันธ์เฉลี่ยระหว่างคู่สินทรัพย์ 0.13-0.17) เมื่อใช้ขนาดตัวอย่างที่แท้จริง ตัวแปรที่เหลืออยู่ก็หมดนัยสำคัญ (p เปลี่ยนจาก 0.000 เป็น 0.221)

**3. ความสัมพันธ์ไม่คงอยู่นอกกลุ่มตัวอย่าง** ไม่มีขอบเขตเวลาใดที่แบบจำลองเอาชนะการทำนายด้วยค่าเฉลี่ยของชุดฝึกได้

ข้อสรุปนี้สอดคล้องกับข้อสังเกตของคณะกรรมการที่ว่าการวิเคราะห์สหสัมพันธ์เพียงอย่างเดียวไม่เพียงพอต่อการนำไปใช้จริง

---

> **[รูปที่ 4.6]** ตาราง Correlation บน Dashboard แสดงค่า corr_t, corr_lag1, corr_lag2 ของทุก Ticker พร้อมแถบแจ้งเตือนว่าเป็นหลักฐานประกอบ ไม่ใช่ผลลัพธ์หลัก
> 📸 แคปหน้าจอ Dashboard แท็บ Correlations

---

## 4.4 ผลการทดสอบ Cloud Scheduler

Cloud Scheduler ถูกตั้งค่าสำเร็จและแสดงสถานะ **ENABLED** พร้อมระบุ Next Scheduled Time เป็น 08:00 น. ในวันถัดไปตามเวลา Asia/Bangkok

> **สถานะปัจจุบัน (5 ก.ย. 2026)** Cloud Scheduler ไม่ทำงานแล้ว เนื่องจาก billing ถูกปิด การเรียก API ตอบกลับ `PERMISSION_DENIED` ระบบตั้งเวลาที่ใช้งานจริงคือ Apache Airflow บนเครื่องส่วนบุคคล ตั้งเวลา 06:00 น. Asia/Bangkok
>
> **ข้อค้นพบที่ควรบันทึก** ข้อความเดิมที่ว่า "ระบบจะทำงานอัตโนมัติทุกวันโดยไม่ต้องมีการแทรกแซงจากมนุษย์" เป็นจริงเฉพาะกับระบบที่ทำงานบนคลาวด์ การย้ายมารันบนเครื่องส่วนบุคคลทำให้ข้อความนี้ไม่เป็นจริง เพราะงานตามเวลาไม่ทำงานหากเครื่องปิดอยู่ ประวัติการทำงานของ Airflow แสดงว่างานที่กำหนดไว้วันที่ 1 ส.ค. ทำงานจริงวันที่ 10 ส.ค. และงานของวันที่ 11 ส.ค. ทำงานจริงวันที่ 3 ก.ย.
>
> ระบบได้รับการปรับให้กู้คืนข้อมูลเองเมื่อกลับมาทำงาน (ดู §3.2.2 และ §5.4) จึงลดผลกระทบของการหยุดทำงานลง แต่ไม่ได้ขจัดข้อจำกัดนี้

---

> **[รูปที่ 4.7]** Cloud Scheduler แสดง Job fin-etl-trigger สถานะ Enabled และ Next Scheduled Time
> 📸 แคปหน้าจอ https://console.cloud.google.com/cloudscheduler?project=project-sentiment-etl

---

## 4.5 ผลการทดสอบระบบแจ้งเตือน Email

ภายหลังการอัพเดต Email Password จาก Regular Password เป็น Google App Password ระบบสามารถส่ง Email แจ้งเตือนได้สำเร็จ โดยอีเมลจะมีหัวข้อ "✅ ETL SUCCESS ✅" หรือ "❌ ETL FAILED ❌" และมีเนื้อหาสรุปผลการรัน ได้แก่ วันที่รัน จำนวนแถวต่างๆ และสถานะ DQ Check

---

> **[รูปที่ 4.8]** อีเมลแจ้งเตือน ETL Success ที่ได้รับใน Inbox
> 📸 แคปหน้าจอ Inbox แสดง Email หัวข้อ "✅ ETL SUCCESS ✅"
>
> ⚠️ **ตรวจสอบก่อนส่ง** ร่างเดิมระบุอีเมลผู้รับเป็น `66070324@kmitl.ac.th` (สถาบันเทคโนโลยีพระจอมเกล้าเจ้าคุณทหารลาดกระบัง) ซึ่งไม่ตรงกับบัญชีที่ใช้ในโครงงานนี้ ควรตรวจสอบว่าเป็นการคัดลอกจากเอกสารต้นแบบหรือไม่ และแก้ไขให้ถูกต้อง

**การปรับปรุงเพิ่มเติม (ก.ย. 2026)** พบว่าฟังก์ชันส่งอีเมลเรียก `smtplib.SMTP_SSL` โดยไม่กำหนด timeout ซึ่งทำให้กระบวนการค้างไม่จำกัดเวลาหาก socket เชื่อมต่อได้แต่ไม่ตอบกลับ เนื่องจากคำสั่งนี้อยู่ท้ายสุดของ ETL หลังจากบันทึกข้อมูลลงฐานข้อมูลเรียบร้อยแล้ว การค้างจึงทำให้งานที่สำเร็จแล้วถูกรายงานว่าล้มเหลว ระบบแจ้งเตือนกลายเป็นสาเหตุของความล้มเหลวเสียเอง ปัจจุบันกำหนด timeout ไว้ที่ 30 วินาที พร้อมชุดทดสอบกำกับ

---

## 4.6 สรุปผลการทดสอบ

ตารางแบ่งเป็นสองส่วน เนื่องจากความสามารถบางอย่างทดสอบผ่านบน GCP แต่ไม่ได้ทำงานในสภาพแวดล้อมปัจจุบัน

**(ก) ความสามารถที่ทำงานอยู่ในปัจจุบัน (Docker + Airflow บนเครื่องส่วนบุคคล)**

| ฟีเจอร์ | สถานะ | หมายเหตุ |
|---|---|---|
| ETL Pipeline | ✅ สำเร็จ | แยกเป็น 3 task อิสระ รวม ~3 นาที (30 สินทรัพย์) |
| FinBERT Sentiment Analysis | ✅ สำเร็จ | ให้คะแนนข่าวสะสม 7,518 ชิ้น |
| Web Dashboard | ✅ สำเร็จ | 7 แท็บ รวม Signal, Fundamentals, Watchlist |
| Data Deduplication | ✅ สำเร็จ | ตรวจ `news_hash` ก่อนให้คะแนน + UNIQUE Constraint |
| Data Quality Checks | ✅ สำเร็จ | ผ่านทั้ง 8 รายการ |
| Email Alert | ✅ สำเร็จ | กำหนด timeout 30 วินาที (ดู §4.5) |
| การกู้คืนข้อมูลอัตโนมัติ | ✅ สำเร็จ | ข่าวย้อนหลัง 90 วัน ราคาย้อนหลังตามช่องว่างจริงสูงสุด 400 วัน |
| ชุดทดสอบอัตโนมัติ | ✅ สำเร็จ | 75 test cases |

**(ข) ความสามารถที่ทดสอบผ่านแล้วแต่ไม่ได้ทำงานในปัจจุบัน**

| ฟีเจอร์ | สถานะ | หมายเหตุ |
|---|---|---|
| Cloud SQL Connection | ⏸ หยุดทำงาน | instance อยู่สถานะ `SUSPENDED` (billing ปิด) |
| Cloud Run Job | ⏸ หยุดทำงาน | image ยังอยู่ แต่เชื่อมต่อฐานข้อมูลไม่ได้ |
| Cloud Scheduler | ⏸ หยุดทำงาน | API ตอบ `PERMISSION_DENIED` |

**(ค) ข้อจำกัดที่ยังคงอยู่**

| รายการ | สถานะ | หมายเหตุ |
|---|---|---|
| การทำงานอัตโนมัติต่อเนื่อง | ⚠️ มีเงื่อนไข | ต้องเปิดเครื่องจึงจะทำงาน หยุดเกิน 90 วันข้อมูลข่าวสูญหาย |
| THB/USD sentiment | ⚠️ ไม่ผ่านเกณฑ์ | 14 วัน จากเกณฑ์ 30 วัน — ข้อจำกัดของการรายงานข่าว ไม่ใช่ของระบบ |
| ไตรมาสที่ 4 ของงบการเงิน | ⚠️ ขาดหาย | 181 จาก 334 ปี-บริษัท ไม่สามารถเติมได้อย่างปลอดภัย |

---

# บทที่ 5
# บทสรุป ข้อเสนอแนะ และแนวทางการพัฒนาต่อยอด

## 5.1 สรุปผลการดำเนินงาน

โครงการวิจัยนี้ประสบความสำเร็จในการออกแบบ พัฒนา และนำไปใช้งานจริงซึ่งระบบประมวลผลข้อมูลอัตโนมัติเพื่อวิเคราะห์ความรู้สึกจากข่าวสารทางการเงินด้วยโมเดล FinBERT บนโครงสร้างพื้นฐานคลาวด์ของ Google ผลลัพธ์ที่ได้บรรลุวัตถุประสงค์ทุกข้อที่กำหนดไว้ตั้งแต่ต้น สรุปได้ดังนี้

**วัตถุประสงค์ข้อที่ 1:** พัฒนาไปป์ไลน์ ETL อัตโนมัติ — **สำเร็จ** ระบบสามารถดึงข้อมูลราคาสินทรัพย์จาก Yahoo Finance / Stooq ข่าวจาก Google News RSS และงบการเงินจาก SEC EDGAR สำหรับสินทรัพย์ 30 รายการ ประมวลผลและบันทึกลงฐานข้อมูลโดยอัตโนมัติ โดยมีกลไก Deduplication, Error Handling, Fallback และการกู้คืนข้อมูลย้อนหลังอัตโนมัติ พร้อมชุดทดสอบอัตโนมัติ 75 รายการ

**วัตถุประสงค์ข้อที่ 2:** นำ FinBERT มาวิเคราะห์ Sentiment — **สำเร็จ** โมเดล FinBERT บน PyTorch / HuggingFace Transformers สามารถจำแนก Sentiment ของข่าวการเงินได้ถูกต้องตามบริบทเฉพาะทาง (Domain-specific) โดยแปลงข้อความที่เป็น Qualitative Data ให้เป็น Quantitative Score ที่ใช้วิเคราะห์เชิงสถิติได้

**วัตถุประสงค์ข้อที่ 3:** ออกแบบและสร้างฐานข้อมูล Star Schema — **สำเร็จ** ฐานข้อมูล `fin_dw` ประกอบด้วย Fact Tables 6 ตาราง (`fact_price_daily`, `fact_news`, `fact_sentiment_daily`, `fact_technical_daily`, `fact_fundamentals_quarterly`, `fact_watchlist_signal_log`) และ Dimension Tables 4 ตาราง (`dim_asset`, `dim_date`, `dim_source`, `dim_watchlist`) พร้อม Analytical View `vw_daily_asset_metrics`

**วัตถุประสงค์ข้อที่ 4:** นำระบบขึ้น GCP แบบ Serverless — **สำเร็จตามการทดสอบ แต่ไม่ได้ใช้งานในปัจจุบัน** ระบบเคยทำงานบน GCP ครบทุกส่วน (Cloud Run, Cloud Run Jobs, Cloud SQL, Artifact Registry, Cloud Scheduler) และผ่านการทดสอบแล้ว แต่ปัจจุบัน billing ถูกปิดทำให้ Cloud SQL อยู่สถานะ `SUSPENDED` สภาพแวดล้อมที่ใช้งานจริงคือ Docker + Apache Airflow บนเครื่องส่วนบุคคล รายละเอียดใน §3.5 และข้อจำกัดใน §5.3 ข้อ 6

**วัตถุประสงค์ข้อที่ 5:** พัฒนา Web Dashboard — **สำเร็จ** Dashboard พัฒนาด้วย FastAPI / Jinja2 ประกอบด้วย 7 แท็บ ได้แก่ Home, Signal (ผลการทำนายพร้อม backtest และ SHAP), Watchlist, Fundamentals (งบการเงินรายไตรมาสย้อนหลัง 19 ปี), News, Metrics และ Correlations รองรับสองภาษา (อังกฤษ/ไทย)

> **หมายเหตุ** แท็บ Heatmap ที่ระบุไว้ในร่างเดิมถูกถอดออก เนื่องจากไม่ได้ให้ข้อมูลที่นำไปใช้ตัดสินใจได้ และแท็บ Correlations ถูกจัดวางใหม่เป็นหลักฐานประกอบพร้อมคำอธิบายกำกับ ตามข้อสังเกตของคณะกรรมการที่ว่าเว็บควรให้ประโยชน์มากกว่าการแสดงข่าวและค่าสหสัมพันธ์

## 5.2 การวิจารณ์ผลลัพธ์และข้อสังเกตสำคัญ

### 5.2.1 ผลการวิเคราะห์ความสัมพันธ์ระหว่าง Sentiment และราคา

ร่างฉบับเดือน ก.ค. 2026 ระบุไว้ว่า ณ ขณะนั้นระบบเพิ่งเก็บข้อมูลได้รอบแรก จึงยังสรุปผลเชิงสถิติไม่ได้ และคาดว่าค่าสหสัมพันธ์ "จะให้ข้อมูลที่มีคุณค่ามากขึ้นเรื่อยๆ เมื่อระบบสะสมข้อมูลเพิ่มขึ้น"

**ข้อมูลที่รอคอยนั้นมีแล้ว และข้อสรุปเป็นตรงกันข้าม** ณ 5 ก.ย. 2026 มีสินทรัพย์ 29 จาก 30 รายการที่ผ่านเกณฑ์ข้อมูล sentiment 30 วันขึ้นไป ครอบคลุมประมาณ 9 เดือน เมื่อนำมาวิเคราะห์อย่างเป็นระบบพบว่า

**1. ความได้เปรียบที่เคยวัดได้เป็นความผันผวนจากกลุ่มตัวอย่างขนาดเล็ก** เมื่อ 25 ก.ค. 2026 ซึ่งมีสินทรัพย์ผ่านเกณฑ์เพียง 5 ตัว แบบจำลองที่รวม sentiment ให้ความแม่นยำ 0.635 เทียบเส้นฐาน 0.558 และชนะ 1 จาก 3 รอบ walk-forward เมื่อขยายเป็น 29 ตัว ค่าเหล่านี้กลายเป็น 0.483 เทียบเส้นฐาน 0.590 และชนะ 0 จาก 3 รอบ

**2. การเพิ่ม sentiment ทำให้แบบจำลองแย่ลง** เมื่อเปรียบเทียบด้วยค่า AUC บนแถวข้อมูลเดียวกันทุกประการ ค่าลดลงทุกขอบเขตเวลา (1 วัน: 0.489 → 0.471, 5 วัน: 0.527 → 0.514, 21 วัน: 0.736 → 0.722) ความสม่ำเสมอของทิศทางนี้เป็นลักษณะของการเพิ่มตัวแปรที่เป็นสัญญาณรบกวน

**3. ปัจจัยที่ครอบงำผลลัพธ์คือการเปลี่ยนสภาวะตลาด** สัดส่วนวันที่ราคาปรับขึ้นในชุดฝึกคือ 0.438 ขณะที่ชุดทดสอบคือ 0.590 แบบจำลองเรียนรู้จากตลาดขาลงแล้วถูกทดสอบบนตลาดขาขึ้น ซึ่งข้อมูล 9 เดือนไม่เพียงพอต่อการฝึกให้ครอบคลุมทั้งสองสภาวะ

**บทเรียนเชิงระเบียบวิธี** ข้อความเดิมสะท้อนสมมติฐานที่พบได้บ่อยว่า "ข้อมูลมากขึ้นจะทำให้ความสัมพันธ์ชัดขึ้น" ในกรณีนี้ข้อมูลที่มากขึ้นกลับ**ลบล้าง**ความสัมพันธ์ที่เคยเห็น ซึ่งเป็นผลลัพธ์ที่มีค่าในตัวเอง เพราะแสดงว่าตัวเลขเดิมไม่ควรถูกนำไปใช้ตั้งแต่แรก รายละเอียดทั้งหมดอยู่ใน `thesis_methodology_revised.md` §4.1

### 5.2.2 ปัญหาที่พบและวิธีแก้ไข

| ปัญหาที่พบ | สาเหตุ | วิธีแก้ไข |
|---|---|---|
| Cloud Run Job ล้มเหลว (Error 403) | Cloud Run Service Account ขาด IAM Permission | เพิ่ม `roles/cloudsql.client` ให้ Service Account |
| Web ขึ้น Error 500 | `vw_daily_asset_metrics` ไม่มีใน DB | สร้าง View ผ่าน Python Script ไปยัง Cloud SQL |
| Email Alert ไม่สามารถส่งได้ | ใช้ Regular Password แทน App Password | สร้าง Google App Password และอัพเดตใน Cloud Run Env Var |
| Docker Build สำเร็จแต่รันบน Cloud Run ไม่ได้ | Build สำหรับ ARM64 (Apple Silicon) | เพิ่ม `--platform linux/amd64` ในคำสั่ง Build |

## 5.3 ข้อจำกัดของระบบ

1. **ข้อมูลข่าวจากแหล่งฟรี (Rate Limiting):** Google News RSS และ Yahoo Finance มีการจำกัด Rate ทำให้อาจพบข้อผิดพลาด `YFRateLimitError` หรือข่าวไม่ครบในบางวัน ส่งผลให้ข้อมูลบางช่วงเวลาขาดหายไป

2. **Batch Processing เพียงรูปแบบเดียว:** ระบบปัจจุบันรันวันละ 1 ครั้ง จึงไม่สามารถตรวจจับผลกระทบของ Breaking News ที่เกิดกลางวันต่อการเคลื่อนไหวของราคาภายในวันได้

3. **ขอบเขตของสินทรัพย์:** ครอบคลุม 30 สินทรัพย์ (หุ้นสหรัฐ 21, ดัชนี 3, สินค้าโภคภัณฑ์ 2, คริปโท 2, อัตราแลกเปลี่ยน 2) ซึ่งไม่ครอบคลุมหุ้นไทยหรือตลาดเกิดใหม่อื่นๆ

4. **การจัดเก็บ Secret:** Password ต่างๆ ยังถูกส่งเป็น Environment Variables โดยตรง แทนที่จะใช้ Google Secret Manager ซึ่งมีความปลอดภัยสูงกว่า

5. **ความลึกของข้อมูล sentiment:** ข้อมูลเริ่มสะสมเมื่อ 16 ธ.ค. 2025 ครอบคลุมประมาณ 9 เดือน ต่างจากราคา (20 ปี) และงบการเงิน (19 ปี) อย่างมาก ความไม่สมมาตรนี้ทำให้ไม่สามารถฝึกแบบจำลองข้ามสภาวะตลาดได้ ซึ่งเป็นข้อจำกัดที่ครอบงำผลของ Track A

   Google News RSS ให้ผลย้อนหลังได้ราว 140 วันต่อ query แต่จำกัดที่ประมาณ 100 รายการ จึงกู้คืนช่องว่างระยะสั้นได้ แต่สร้างประวัติย้อนหลังหลายปีไม่ได้

6. **การพึ่งพาเครื่องส่วนบุคคล:** เมื่อระบบย้ายจาก Cloud Run มารันบน Docker ในเครื่อง งานตามเวลาจะไม่ทำงานหากเครื่องปิดอยู่ ระบบได้รับการปรับให้กู้คืนเองเมื่อกลับมาทำงาน (ข่าวย้อนหลัง 90 วัน ราคาย้อนหลังตามช่องว่างจริงสูงสุด 400 วัน) แต่การหยุดทำงานเกิน 90 วันยังทำให้ข้อมูลข่าวสูญหายถาวร

7. **ไตรมาสที่ 4 ของงบการเงินขาดหายอย่างเป็นระบบ:** 181 จาก 334 ปี-บริษัท มีข้อมูลเพียง 3 ไตรมาส เนื่องจากรายงานประจำปีระบุตัวเลขทั้งปีโดยไม่แยกไตรมาสสุดท้าย การคำนวณย้อนกลับถูกทดสอบแล้วพบอัตราความผิดพลาดประมาณ 25% จึงไม่นำมาใช้

8. **ความน่าเชื่อถือของ EPS ข้ามช่วงแตกพาร์:** ค่ากำไรต่อหุ้นจาก SEC EDGAR ไม่สามารถเทียบข้ามช่วงที่บริษัทแตกพาร์ได้อย่างสมบูรณ์ เนื่องจากรายงานประจำปีฉบับหลังปรับเฉพาะตัวเลขทั้งปี ไม่ได้แสดงรายไตรมาสของปีเก่าซ้ำ

## 5.4 ข้อเสนอแนะสำหรับการพัฒนาต่อยอด (Future Work)

### 5.4.1 ระยะสั้น (ภายใน 3 เดือน)

1. **Google Secret Manager:** ย้าย Secrets ทั้งหมด (DB Password, Email App Password) ไปเก็บใน Google Secret Manager และให้ Cloud Run ดึงขณะ Startup เพื่อความปลอดภัยระดับ Enterprise

2. **Backfill Historical Data:** เพิ่มโหมด Manual Backfill ที่ใช้ Cloud Run Job รัน ETL สำหรับวันที่ในอดีตเพื่อเพิ่มข้อมูลย้อนหลัง ทำให้ Correlation Analysis มีความน่าเชื่อถือมากขึ้นในทันที

3. **Alert Notification ที่หลากหลาย:** เพิ่มช่องทางแจ้งเตือนเพิ่มเติม เช่น LINE Messaging API หรือ Telegram Bot เพื่อรองรับผู้ใช้ที่ไม่ใช้อีเมลเป็นหลัก

### 5.4.2 ระยะกลาง (3-12 เดือน)

4. **ยกระดับแหล่งข้อมูล (Premium Data Source):** เปลี่ยนไปใช้ Alpha Vantage, NewsAPI หรือ Settrade API ที่เสียค่าบริการเพื่อรับประกันความต่อเนื่องและความน่าเชื่อถือของข้อมูล ซึ่งจะกำจัดปัญหา Rate Limiting และข้อมูลขาดหายโดยสิ้นเชิง

5. **Microservice สำหรับ AI Inference:** แยก FinBERT Model ออกมาเป็น Dedicated Microservice บน Google Vertex AI Prediction Endpoint ที่รองรับ GPU หรือ TPU เพื่อเพิ่มความเร็ว Inference 10-100 เท่า และลด Memory ที่ ETL Container ต้องใช้ลงอย่างมาก

6. **ขยายการครอบคลุมสินทรัพย์:** เพิ่มหุ้นในตลาดหลักทรัพย์ไทย (SET) เช่น PTT, ADVANC, KBANK โดยใช้ RSS Feed จาก กรุงเทพธุรกิจ ผู้จัดการ หรือ SET Disclosure เพื่อเพิ่มประโยชน์ให้แก่นักลงทุนไทย

### 5.4.3 ระยะยาว (1 ปีขึ้นไป)

7. **Real-time Streaming Architecture:** เปลี่ยน Architecture จาก Batch Processing (วันละครั้ง) เป็นแบบ Event-driven Streaming โดยใช้ Google Pub/Sub เพื่อตรวจจับข่าวทันทีที่เผยแพร่ และประมวลผลด้วย FinBERT ในหน่วยวินาที ทำให้ Dashboard แสดงผลแบบ Near Real-time ที่มีประโยชน์ต่อนักลงทุนระยะสั้นอย่างแท้จริง

8. **โมเดล Fine-tuned เพิ่มเติม:** Fine-tune FinBERT เพิ่มเติมด้วยข้อมูลข่าวภาษาไทยจำเพาะ (Thai Financial News) เพื่อรองรับการวิเคราะห์ข่าวภาษาไทยที่ยังไม่มีโมเดลที่แม่นยำในตลาด

9. **Machine Learning สำหรับ Price Prediction:** ใช้ Sentiment Score เป็น Feature ร่วมกับข้อมูลทางเทคนิค (Technical Indicators) ใน Model เชิงพยากรณ์ (Forecasting Model) เช่น LSTM หรือ Transformer-based Forecaster เพื่อพัฒนาระบบ Intelligence Advisory ที่ให้คำแนะนำการลงทุนเบื้องต้นได้

## 5.5 บทเรียนที่ได้รับจากการวิจัย

การพัฒนาโครงการนี้ทำให้ผู้วิจัยได้รับบทเรียนสำคัญหลายประการที่นอกเหนือจากการเขียนโค้ดทั่วไป ได้แก่

1. **Cloud Architecture ต้องออกแบบก่อนลงมือสร้าง:** ปัญหา IAM Permission, Connection String ของ Cloud SQL และ Platform Architecture (ARM vs AMD) ล้วนเป็นปัญหาที่เกิดขึ้นจากการไม่ศึกษาข้อกำหนดของ GCP ให้ครบก่อนเริ่ม การวางแผนล่วงหน้าจะช่วยประหยัดเวลาได้มาก

2. **Idempotency คือหัวใจของ ETL ที่น่าเชื่อถือ:** การออกแบบ Database Schema ให้รองรับการ UPSERT และ Unique Constraint บน `news_hash` ทำให้สามารถรัน ETL ซ้ำได้อย่างปลอดภัยโดยไม่ทำให้ข้อมูลเสียหาย ซึ่งเป็นสิ่งจำเป็นสำหรับระบบ Production ทุกชนิด

3. **Memory Management สำคัญในงาน AI:** โมเดล FinBERT ขนาด BERT-Base ใช้ RAM ประมาณ 2-3 GB เมื่อโหลดพร้อมกับข้อมูล ทำให้ต้องเพิ่มหน่วยความจำ Cloud Run Job เป็น 4 GB ซึ่งสะท้อนถึงความสำคัญของการทำ Resource Planning ในโปรเจกต์ AI ในระยะ Production

4. **Security ต้องคิดตั้งแต่วันแรก:** ปัญหา Gmail ปฏิเสธการล็อกอินจาก Bot ด้วย Regular Password แสดงให้เห็นว่า Security Policy ของ Platform ต่างๆ มีผลโดยตรงต่อการทำงานของระบบ การออกแบบระบบ Authentication ที่ถูกต้องตั้งแต่แรกจะป้องกันปัญหาที่ยากต่อการ Debug ในภายหลัง

บทเรียนสี่ข้อข้างต้นเป็นเรื่องวิศวกรรมระบบ ส่วนบทเรียนที่มีน้ำหนักที่สุดต่อความน่าเชื่อถือของงานวิจัยเป็นเรื่องระเบียบวิธี และได้มาจากการตรวจสอบซ้ำในช่วงท้ายของโครงการ

5. **ข้อผิดพลาดที่อันตรายที่สุดคือข้อผิดพลาดที่ไม่แสดงอาการ:** โครงการนี้พบข้อผิดพลาด 5 จุดที่ให้ผลลัพธ์ดูสมเหตุสมผลโดยไม่มีข้อความแจ้งเตือนใดๆ ได้แก่ (ก) เครื่องหมาย `&` ในคำค้นทำให้ ^GSPC ค้นหาด้วยตัวอักษร "S" มาหลายเดือน โดย feed ยังคืนผลลัพธ์ 100 รายการตามปกติ (ข) การจับคู่งบการเงินกับราคาผิดวันถึง 39% ของชุดข้อมูล เนื่องจากฟังก์ชันค้นหาคืนวันแรกสุดที่มีข้อมูลเมื่อไม่พบวันที่ตรงกัน (ค) อัตราส่วนทางการเงินที่มีตัวหารเกือบเป็นศูนย์ (ง) `restart policy` ของฐานข้อมูลที่ไม่ตรงกับส่วนอื่น และ (จ) หน้าต่างเวลาแบบตายตัวที่ทำให้ช่องว่างข้อมูลกลายเป็นถาวร ทั้งหมดถูกค้นพบจากการตรวจสอบตัวเลขที่อธิบายไม่ได้ ไม่ใช่จากการอ่านโค้ด

6. **ตัวเลขที่ดูดีต้องถูกตรวจสอบหนักกว่าตัวเลขที่ดูแย่:** ค่าสหสัมพันธ์ที่มีนัยสำคัญสูง (p < 0.001) ในโครงการนี้ส่วนใหญ่หายไปเมื่อเปลี่ยนไปวัดด้วยอันดับ และค่าที่เหลือหมดนัยสำคัญเมื่อคำนวณขนาดตัวอย่างที่แท้จริง แนวโน้มที่จะยอมรับผลบวกโดยไม่ตรวจสอบเป็นความเสี่ยงเชิงระบบของงานวิเคราะห์ข้อมูล

7. **ข้อจำกัดของแหล่งข้อมูลต้องวัด ไม่ใช่สันนิษฐาน:** โครงการนี้ยึดถือข้อสรุปว่า "ข่าวไม่สามารถดึงย้อนหลังได้" เป็นเวลาหลายเดือน บันทึกไว้ในเอกสารและโค้ด 6 จุด และใช้ประกอบการตัดสินใจหลายครั้ง เมื่อวัดกับ feed จริงพบว่าไม่เป็นความจริง ความเชื่อนี้ยืนยันตัวเองได้เพราะตัวกรอง 7 วันทำให้ทุกการทำงานเห็นข้อมูลเพียง 7 วันเสมอ

8. **ผลลัพธ์เชิงลบที่ตรวจสอบอย่างเข้มงวดมีค่ามากกว่าผลบวกที่ตรวจสอบหลวม:** ข้อสรุปสุดท้ายของงานวิจัยนี้คือทั้ง sentiment และงบการเงินไม่แสดงความสัมพันธ์กับผลตอบแทนที่ใช้ประโยชน์ได้ ซึ่งสอดคล้องกับสมมติฐานตลาดมีประสิทธิภาพ ผลนี้ปกป้องได้ในเชิงวิชาการมากกว่าตัวเลขความแม่นยำ 63.5% ที่เคยได้จากสินทรัพย์ 5 ตัว และพังทลายเมื่อขยายเป็น 29 ตัว

## 5.6 สรุป

โครงการนี้แสดงให้เห็นถึงความเป็นไปได้ในการนำเทคโนโลยีสมัยใหม่หลายแขนงมาผสมผสานกัน ได้แก่ Large Language Models (FinBERT), Data Engineering (ETL Pipeline), Data Warehousing (Star Schema) และ Cloud Computing (GCP Serverless) เพื่อสร้างระบบที่ทำงานได้จริง

ระบบที่พัฒนาขึ้นนี้ถือเป็น **Proof of Concept** ของการนำ MLOps (Machine Learning Operations) มาใช้ในบริบทของ Financial Data Analytics ซึ่งสามารถต่อยอดได้ทั้งในเชิงวิชาการ เช่น การศึกษา Sentiment-Price Relationship ในตลาดเกิดใหม่ (Emerging Markets) และในเชิงพาณิชย์

**ข้อสรุปเชิงวิชาการของงานวิจัยนี้เป็นผลลัพธ์เชิงลบ** ทั้ง sentiment จากข่าวรายวันและงบการเงินรายไตรมาส ไม่แสดงความสัมพันธ์กับผลตอบแทนในอนาคตที่รอดการตรวจสอบทั้งสามด้าน ได้แก่ การจัดการค่าผิดปกติ การประเมินนอกกลุ่มตัวอย่าง และการนับขนาดตัวอย่างที่แท้จริง ผลนี้สอดคล้องกับสมมติฐานตลาดมีประสิทธิภาพในรูปแบบกึ่งเข้ม ซึ่งระบุว่าข้อมูลสาธารณะถูกสะท้อนในราคาไปแล้ว

การนำเสนอผลลัพธ์เชิงลบนี้อย่างตรงไปตรงมา พร้อมกับบันทึกกระบวนการที่นำไปสู่ข้อสรุป รวมถึงข้อสรุปที่เคยยอมรับแล้วภายหลังถูกถอน ถือเป็นส่วนหนึ่งของคุณค่าทางวิชาการของงาน เนื่องจากแสดงให้เห็นว่าความสัมพันธ์ที่ดูมีนัยสำคัญในข้อมูลทางการเงินสามารถเกิดจากค่าผิดปกติเพียงไม่กี่รายการ จากขนาดตัวอย่างที่ถูกนับเกินจริง หรือจากกลุ่มตัวอย่างที่เล็กเกินไป ได้บ่อยเพียงใด

คุณูปการหลักของโครงการจึงมิใช่การค้นพบความสัมพันธ์ หากแต่เป็น **โครงสร้างพื้นฐานข้อมูลและระเบียบวิธีตรวจสอบที่ทำให้สามารถสรุปได้อย่างมั่นใจว่าไม่พบความสัมพันธ์** ซึ่งเป็นเงื่อนไขจำเป็นสำหรับการศึกษาต่อยอดใดๆ ในหัวข้อนี้
