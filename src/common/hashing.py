from __future__ import annotations
import hashlib
import re

_space_re = re.compile(r"\s+")

def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    return _space_re.sub(" ", s)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def build_news_hash(ticker: str, published_iso: str, title: str, url: str | None) -> str:
    key = f"{ticker}|{published_iso}|{normalize_text(title)}|{(url or '').strip()}"
    return sha256_hex(key)
