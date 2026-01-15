from __future__ import annotations
from dataclasses import dataclass
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

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
