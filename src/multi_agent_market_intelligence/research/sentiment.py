"""Financial sentiment analysis domain models and specialized lexicon engine."""

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from multi_agent_market_intelligence.research.models import (
    FinancialReport,
    NewsArticle,
)


class SentimentLabel(str, Enum):
    """Categorical classification of market sentiment."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SentimentAnalysisResult(BaseModel):
    """Structured outcome of financial sentiment analysis."""

    model_config = ConfigDict(extra="allow")

    score: float = Field(..., ge=-1.0, le=1.0, description="Normalized score between -1.0 and 1.0")
    label: SentimentLabel
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level from 0.0 to 1.0")
    breakdown: dict[str, float] = Field(default_factory=dict)
    key_drivers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __eq__(self, other: Any) -> bool:
        """Allow comparison against raw dicts for testing and adapter compatibility."""
        if isinstance(other, dict):
            for k, v in other.items():
                val = getattr(self, k, None)
                if val is None and self.__pydantic_extra__:
                    val = self.__pydantic_extra__.get(k)
                if val != v:
                    return False
            return True
        return super().__eq__(other)


class FinancialSentimentAnalyzer:
    """Specialized financial sentiment engine using domain lexicon, negations, and intensifiers."""

    # Positive financial keywords with assigned directional weights
    POSITIVE_LEXICON: dict[str, float] = {
        "accelerate": 1.2,
        "accelerated": 1.2,
        "accelerating": 1.2,
        "acceleration": 1.2,
        "beat": 1.5,
        "beats": 1.5,
        "beating": 1.5,
        "bullish": 1.5,
        "dividend": 1.0,
        "exceeded": 1.4,
        "expansion": 1.2,
        "gain": 1.0,
        "gains": 1.0,
        "growth": 1.2,
        "higher": 0.8,
        "improved": 1.0,
        "improving": 1.0,
        "innovation": 1.0,
        "momentum": 1.0,
        "optimistic": 1.2,
        "outperform": 1.5,
        "outperformed": 1.5,
        "profit": 1.2,
        "profitable": 1.4,
        "profitability": 1.4,
        "rally": 1.3,
        "rebound": 1.1,
        "record": 1.3,
        "resilient": 1.1,
        "resilience": 1.1,
        "robust": 1.1,
        "solid": 0.9,
        "strong": 1.0,
        "surge": 1.3,
        "surged": 1.3,
        "upgrade": 1.5,
        "upgraded": 1.5,
        "upside": 1.2,
    }

    # Negative financial keywords with assigned directional weights
    NEGATIVE_LEXICON: dict[str, float] = {
        "bankruptcy": 2.0,
        "bearish": 1.5,
        "bottleneck": 1.0,
        "breach": 1.5,
        "decline": 1.2,
        "declined": 1.2,
        "declining": 1.2,
        "default": 1.8,
        "downgrade": 1.5,
        "downgraded": 1.5,
        "drop": 1.0,
        "dropped": 1.0,
        "headwind": 1.3,
        "headwinds": 1.3,
        "impairment": 1.5,
        "inflation": 0.8,
        "investigation": 1.5,
        "lawsuit": 1.4,
        "litigation": 1.4,
        "loss": 1.3,
        "losses": 1.3,
        "miss": 1.5,
        "missed": 1.5,
        "pessimistic": 1.2,
        "recession": 1.6,
        "restructuring": 0.8,
        "risk": 0.9,
        "risks": 0.9,
        "selloff": 1.4,
        "slump": 1.2,
        "tightness": 0.9,
        "volatility": 0.8,
        "volatile": 0.8,
        "warning": 1.2,
        "weak": 1.1,
        "weakness": 1.2,
    }

    # Multi-word financial phrases checked with precedence
    PHRASE_LEXICON: dict[str, float] = {
        "margin expansion": 1.8,
        "operating margin expansion": 1.8,
        "price target raised": 1.6,
        "revenue growth": 1.5,
        "cash flow generation": 1.3,
        "supply chain bottleneck": -1.5,
        "operating loss": -1.6,
        "price target cut": -1.6,
        "guidance lowered": -1.8,
        "guidance raised": 1.8,
        "regulatory scrutiny": -1.4,
    }

    NEGATION_WORDS: set[str] = {
        "not",
        "no",
        "never",
        "hardly",
        "scarcely",
        "barely",
        "without",
        "neither",
        "nor",
        "lack",
        "failed",
        "fails",
        "unable",
    }

    INTENSIFIERS: dict[str, float] = {
        "very": 1.4,
        "highly": 1.5,
        "strongly": 1.5,
        "substantially": 1.5,
        "significantly": 1.5,
        "markedly": 1.4,
        "exceptionally": 1.6,
        "notably": 1.4,
        "sharply": 1.4,
        "slightly": 0.6,
        "modestly": 0.7,
        "somewhat": 0.7,
        "marginally": 0.6,
        "partially": 0.7,
    }

    def analyze_text(self, text: str) -> SentimentAnalysisResult:
        """Evaluate financial sentiment of raw text using domain lexicon and contextual rules.

        Args:
            text: Raw input text.

        Returns:
            Structured SentimentAnalysisResult.
        """
        if not text or not text.strip():
            return SentimentAnalysisResult(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                confidence=0.0,
                breakdown={"positive": 0.0, "negative": 0.0, "neutral": 1.0},
                key_drivers=[],
                metadata={"word_count": 0},
            )

        tokens = re.findall(r"\b[a-zA-Z0-9_\'-]+\b", text.lower())
        word_count = len(tokens)
        if word_count == 0:
            return SentimentAnalysisResult(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                confidence=0.0,
                breakdown={"positive": 0.0, "negative": 0.0, "neutral": 1.0},
                key_drivers=[],
                metadata={"word_count": 0},
            )

        pos_score = 0.0
        neg_score = 0.0
        key_drivers: list[str] = []

        tokenized_phrases: list[tuple[list[str], str, float]] = []
        for phrase, weight in self.PHRASE_LEXICON.items():
            tokenized_phrases.append((phrase.split(), phrase, weight))
        tokenized_phrases.sort(key=lambda x: len(x[0]), reverse=True)

        i = 0
        while i < word_count:
            multiplier = 1.0
            is_negated = False

            window_start = max(0, i - 4)
            preceding = tokens[window_start:i]
            for prev in preceding:
                if prev in self.NEGATION_WORDS:
                    is_negated = True
                if prev in self.INTENSIFIERS:
                    multiplier *= self.INTENSIFIERS[prev]

            matched_phrase = False
            for p_tokens, phrase_str, weight in tokenized_phrases:
                p_len = len(p_tokens)
                if i + p_len <= word_count and tokens[i : i + p_len] == p_tokens:
                    effective_weight = abs(weight) * multiplier
                    if weight > 0:
                        if is_negated:
                            neg_score += effective_weight
                            key_drivers.append(f"not_{phrase_str}")
                        else:
                            pos_score += effective_weight
                            key_drivers.append(phrase_str)
                    else:
                        if is_negated:
                            pos_score += effective_weight * 0.5
                            key_drivers.append(f"not_{phrase_str}")
                        else:
                            neg_score += effective_weight
                            key_drivers.append(phrase_str)
                    i += p_len
                    matched_phrase = True
                    break

            if matched_phrase:
                continue

            token = tokens[i]
            if token in self.POSITIVE_LEXICON:
                token_weight = self.POSITIVE_LEXICON[token] * multiplier
                if is_negated:
                    neg_score += token_weight
                    key_drivers.append(f"not_{token}")
                else:
                    pos_score += token_weight
                    key_drivers.append(token)
            elif token in self.NEGATIVE_LEXICON:
                token_weight = self.NEGATIVE_LEXICON[token] * multiplier
                if is_negated:
                    pos_score += token_weight * 0.5
                    key_drivers.append(f"not_{token}")
                else:
                    neg_score += token_weight
                    key_drivers.append(token)

            i += 1

        total_sentiment_weight = pos_score + neg_score
        if total_sentiment_weight == 0.0:
            score = 0.0
            confidence = 0.0
            label = SentimentLabel.NEUTRAL
            breakdown = {"positive": 0.0, "negative": 0.0, "neutral": 1.0}
        else:
            # Normalized score bounded between -1.0 and 1.0
            raw_score = (pos_score - neg_score) / (total_sentiment_weight + 0.5)
            score = round(max(-1.0, min(1.0, raw_score)), 3)

            # Confidence scales with signal density and count of drivers
            density = min(1.0, (len(key_drivers) * 5) / max(10, word_count))
            volume_factor = min(1.0, len(key_drivers) / 4.0)
            confidence = round(max(0.2, min(1.0, 0.4 * density + 0.6 * volume_factor)), 2)

            pos_ratio = round(pos_score / total_sentiment_weight, 3)
            neg_ratio = round(neg_score / total_sentiment_weight, 3)
            breakdown = {
                "positive": pos_ratio,
                "negative": neg_ratio,
                "neutral": round(max(0.0, 1.0 - (pos_ratio + neg_ratio)), 3),
            }

            if score >= 0.15:
                label = SentimentLabel.BULLISH
            elif score <= -0.15:
                label = SentimentLabel.BEARISH
            else:
                label = SentimentLabel.NEUTRAL

        # Deduplicate key drivers preserving order
        dedup_drivers: list[str] = list(dict.fromkeys(key_drivers))[:8]

        return SentimentAnalysisResult(
            score=score,
            label=label,
            confidence=confidence,
            breakdown=breakdown,
            key_drivers=dedup_drivers,
            metadata={"word_count": word_count},
        )

    def analyze_article(self, article: NewsArticle) -> SentimentAnalysisResult:
        """Evaluate sentiment for a NewsArticle with headline weighting.

        Args:
            article: NewsArticle to evaluate.

        Returns:
            SentimentAnalysisResult.
        """
        headline_res = self.analyze_text(article.headline)
        content_res = self.analyze_text(article.content)

        if content_res.confidence == 0.0:
            return headline_res

        # Weighted combination: headline 40%, body content 60%
        combined_score = round(0.4 * headline_res.score + 0.6 * content_res.score, 3)
        combined_conf = round(0.4 * headline_res.confidence + 0.6 * content_res.confidence, 2)

        if combined_score >= 0.15:
            label = SentimentLabel.BULLISH
        elif combined_score <= -0.15:
            label = SentimentLabel.BEARISH
        else:
            label = SentimentLabel.NEUTRAL

        drivers = list(dict.fromkeys(headline_res.key_drivers + content_res.key_drivers))[:8]

        return SentimentAnalysisResult(
            score=combined_score,
            label=label,
            confidence=combined_conf,
            breakdown={
                "headline_score": headline_res.score,
                "content_score": content_res.score,
            },
            key_drivers=drivers,
            metadata={
                "source": article.source,
                "symbol": article.symbol,
            },
        )

    def analyze_report(
        self,
        report: FinancialReport,
        target_sections: list[str] | None = None,
    ) -> SentimentAnalysisResult:
        """Evaluate sentiment for a FinancialReport, optionally targeting specific sections.

        Args:
            report: FinancialReport to analyze.
            target_sections: Specific section keys to analyze (e.g. ['management_discussion']).

        Returns:
            SentimentAnalysisResult.
        """
        if target_sections:
            selected_texts = [
                report.sections[sec] for sec in target_sections if sec in report.sections
            ]
            eval_text = "\n\n".join(selected_texts) if selected_texts else report.content
        elif report.sections:
            # By default analyze MD&A, highlights, and guidance, excluding standalone risk factors
            priority_sections = ["financial_highlights", "management_discussion", "guidance"]
            selected_texts = [
                report.sections[sec] for sec in priority_sections if sec in report.sections
            ]
            eval_text = "\n\n".join(selected_texts) if selected_texts else report.content
        else:
            eval_text = report.content

        result = self.analyze_text(eval_text)
        metadata = dict(result.metadata)
        metadata["symbol"] = report.symbol
        metadata["period"] = report.period
        metadata["target_sections"] = target_sections or list(report.sections.keys())

        return SentimentAnalysisResult(
            score=result.score,
            label=result.label,
            confidence=result.confidence,
            breakdown=result.breakdown,
            key_drivers=result.key_drivers,
            metadata=metadata,
        )

    @classmethod
    def aggregate_sentiment(
        cls,
        results: list[SentimentAnalysisResult],
    ) -> SentimentAnalysisResult:
        """Compute confidence-weighted aggregate sentiment across multiple analysis results.

        Args:
            results: List of sentiment analysis results.

        Returns:
            Composite SentimentAnalysisResult.
        """
        if not results:
            return SentimentAnalysisResult(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                confidence=0.0,
                breakdown={"positive": 0.0, "negative": 0.0, "neutral": 1.0},
                key_drivers=[],
                metadata={"total_items": 0},
            )

        total_weight = 0.0
        weighted_score_sum = 0.0
        all_drivers: list[str] = []

        for res in results:
            weight = max(0.1, res.confidence)
            total_weight += weight
            weighted_score_sum += res.score * weight
            all_drivers.extend(res.key_drivers)

        agg_score = round(weighted_score_sum / total_weight, 3)
        agg_conf = round(min(1.0, sum(r.confidence for r in results) / len(results)), 2)

        if agg_score >= 0.15:
            label = SentimentLabel.BULLISH
        elif agg_score <= -0.15:
            label = SentimentLabel.BEARISH
        else:
            label = SentimentLabel.NEUTRAL

        dedup_drivers = list(dict.fromkeys(all_drivers))[:10]

        return SentimentAnalysisResult(
            score=agg_score,
            label=label,
            confidence=agg_conf,
            breakdown={"total_weight": round(total_weight, 3)},
            key_drivers=dedup_drivers,
            metadata={"total_items": len(results)},
        )
