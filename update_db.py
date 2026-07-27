from sqlalchemy import create_engine, text
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "fin_dw")
DB_USER = os.getenv("POSTGRES_USER", "fin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "fin")

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

with engine.begin() as conn:
    print("Adding credibility_score column...")
    conn.execute(text("ALTER TABLE dim_source ADD COLUMN IF NOT EXISTS credibility_score INT DEFAULT 50;"))
    print("Column added.")
    
    print("Updating initial scores based on common reputation...")
    update_sql = text("""
        UPDATE dim_source SET credibility_score = CASE 
            WHEN source_name ILIKE '%Bloomberg%' THEN 95
            WHEN source_name ILIKE '%Reuters%' THEN 95
            WHEN source_name ILIKE '%Financial Times%' THEN 95
            WHEN source_name ILIKE '%Wall Street Journal%' THEN 95
            WHEN source_name ILIKE '%WSJ%' THEN 95
            WHEN source_name ILIKE '%FT%' THEN 95
            WHEN source_name ILIKE '%CNBC%' THEN 85
            WHEN source_name ILIKE '%MarketWatch%' THEN 85
            WHEN source_name ILIKE '%Yahoo%Finance%' THEN 80
            WHEN source_name ILIKE '%Globe and Mail%' THEN 80
            WHEN source_name ILIKE '%Motley Fool%' THEN 60
            WHEN source_name ILIKE '%Investing.com%' THEN 70
            WHEN source_name ILIKE '%Seeking Alpha%' THEN 65
            WHEN source_name ILIKE '%CoinCentral%' THEN 60
            ELSE 50
        END;
    """)
    conn.execute(update_sql)
    print("Scores updated.")

with engine.connect() as conn:
    query = text("SELECT source_name, credibility_score FROM dim_source ORDER BY credibility_score DESC")
    print("\n--- Current Sources and Scores ---")
    df = pd.read_sql(query, conn)
    print(df.to_string())

