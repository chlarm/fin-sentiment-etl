from __future__ import annotations
from dataclasses import dataclass
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from transformers import pipeline

@dataclass
class SentimentResult:
    score: float
    label: str  # pos/neu/neg

def _label_from_compound(c: float) -> str:
    if c >= 0.05:
        return "pos"
    if c <= -0.05:
        return "neg"
    return "neu"

class VaderScorer:
    def __init__(self, finance_lexicon: dict[str, float] | None = None):
        self.analyzer = SentimentIntensityAnalyzer()
        if finance_lexicon:
            self.analyzer.lexicon.update({k.lower(): float(v) for k, v in finance_lexicon.items()})

    def score(self, text: str) -> SentimentResult:
        vs = self.analyzer.polarity_scores(text or "")
        c = float(vs.get("compound", 0.0))
        return SentimentResult(score=c, label=_label_from_compound(c))


class FinbertScorer:
    def __init__(self):
        # Using ProsusAI/finbert which maps to labels: positive, negative, neutral
        # We specify device=-1 to force CPU for maximum compatibility
        self.nlp = pipeline("sentiment-analysis", model="ProsusAI/finbert", device=-1)

    def score(self, text: str) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult(score=0.0, label="neu")
            
        try:
            # We want all scores to calculate the compound score
            result = self.nlp(text, top_k=None)
            
            # Extract probabilities
            prob_pos = next(r["score"] for r in result if r["label"] == "positive")
            prob_neg = next(r["score"] for r in result if r["label"] == "negative")
            prob_neu = next(r["score"] for r in result if r["label"] == "neutral")
            
            # Calculate a compound score: (Positive Probability - Negative Probability) 
            # This aligns the output to roughly [-1.0, 1.0], similar to VADER
            c = prob_pos - prob_neg
            
            # Determine label based on highest probability
            if prob_pos > prob_neg and prob_pos > prob_neu:
                label = "pos"
            elif prob_neg > prob_pos and prob_neg > prob_neu:
                label = "neg"
            else:
                label = "neu"
                
            return SentimentResult(score=c, label=label)
            
        except Exception as e:
            print(f"[FinbertScorer] Error scoring text: '{text}'. Error: {e}")
            return SentimentResult(score=0.0, label="neu")
