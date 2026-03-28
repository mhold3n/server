"""Executable hedging policy with actual validation logic."""

import re
from typing import Any

import structlog

from .base import BasePolicy, PolicyResult

logger = structlog.get_logger()


class HedgingPolicy(BasePolicy):
    """Policy that detects and flags hedging language."""

    def __init__(
        self,
        ban_hedging: bool = False,
        max_hedging_ratio: float = 0.1,
        hedging_phrases: list[str] | None = None,
    ):
        """Initialize hedging policy.

        Args:
            ban_hedging: Whether to completely ban hedging language
            max_hedging_ratio: Maximum allowed ratio of hedging words to total words
            hedging_phrases: Custom list of hedging phrases to detect
        """
        super().__init__("hedging")
        self.ban_hedging = ban_hedging
        self.max_hedging_ratio = max_hedging_ratio
        self.hedging_phrases = hedging_phrases or self._get_default_hedging_phrases()

    async def validate(
        self,
        output: str,
        retrieval_docs: list[dict[str, Any]] | None = None,
    ) -> PolicyResult:
        """Validate output against hedging policy.

        Args:
            output: Generated output text
            retrieval_docs: Retrieved documents for context

        Returns:
            Policy validation result
        """
        violations = []
        suggestions = []
        score = 1.0

        # Detect hedging language
        hedging_instances = self._detect_hedging(output)

        if hedging_instances:
            # Calculate hedging ratio
            total_words = len(output.split())
            hedging_ratio = len(hedging_instances) / total_words if total_words > 0 else 0

            # Check for complete ban
            if self.ban_hedging:
                violations.append(f"Hedging language detected: {len(hedging_instances)} instances")
                suggestions.append("Remove all hedging language and state facts directly")
                score = 0.0
            else:
                # Check ratio threshold
                if hedging_ratio > self.max_hedging_ratio:
                    violations.append(
                        f"Excessive hedging: {hedging_ratio:.2f} > {self.max_hedging_ratio}"
                    )
                    suggestions.append("Reduce hedging language and be more direct")
                    score -= 0.5
                else:
                    # Mild warning for any hedging
                    violations.append(f"Hedging language detected: {len(hedging_instances)} instances")
                    suggestions.append("Consider being more direct in your statements")
                    score -= 0.2

        # Calculate final score
        score = max(0.0, min(1.0, score))
        passed = len(violations) == 0 or (not self.ban_hedging and score > 0.5)

        return PolicyResult(
            passed=passed,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata={
                "hedging_instances": len(hedging_instances),
                "hedging_ratio": hedging_ratio if hedging_instances else 0.0,
                "detected_phrases": hedging_instances,
            },
        )

    def _get_default_hedging_phrases(self) -> list[str]:
        """Get default list of hedging phrases."""
        return [
            # Uncertainty markers
            "might", "may", "could", "possibly", "perhaps", "maybe",
            "potentially", "likely", "unlikely", "probably", "probably not",

            # Softening language
            "seems", "appears", "suggests", "indicates", "implies",
            "tends to", "often", "sometimes", "usually", "generally",
            "typically", "commonly", "frequently", "rarely",

            # Tentative language
            "I think", "I believe", "I feel", "I suspect", "I assume",
            "I guess", "I suppose", "I imagine", "I wonder",

            # Qualifiers
            "somewhat", "rather", "quite", "fairly", "relatively",
            "more or less", "sort of", "kind of", "pretty much",

            # Conditional language
            "if", "unless", "provided that", "assuming", "supposing",
            "in case", "contingent on", "dependent on",

            # Approximation
            "about", "approximately", "roughly", "around", "nearly",
            "almost", "close to", "in the vicinity of",
        ]

    def _detect_hedging(self, text: str) -> list[str]:
        """Detect hedging language in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected hedging phrases
        """
        detected = []
        text_lower = text.lower()

        for phrase in self.hedging_phrases:
            # Use word boundaries for exact phrase matching
            pattern = r'\b' + re.escape(phrase.lower()) + r'\b'
            matches = re.findall(pattern, text_lower)
            detected.extend(matches)

        return detected

    def _calculate_hedging_ratio(self, text: str) -> float:
        """Calculate ratio of hedging words to total words.

        Args:
            text: Text to analyze

        Returns:
            Hedging ratio between 0.0 and 1.0
        """
        words = text.split()
        if not words:
            return 0.0

        hedging_count = 0
        for word in words:
            if word.lower() in [phrase.lower() for phrase in self.hedging_phrases]:
                hedging_count += 1

        return hedging_count / len(words)

    def _get_hedging_suggestions(self, detected_phrases: list[str]) -> list[str]:
        """Get specific suggestions for detected hedging phrases.

        Args:
            detected_phrases: List of detected hedging phrases

        Returns:
            List of specific suggestions
        """
        suggestions = []

        # Group similar phrases
        uncertainty_phrases = ["might", "may", "could", "possibly", "perhaps", "maybe"]
        softening_phrases = ["seems", "appears", "suggests", "indicates"]
        tentative_phrases = ["I think", "I believe", "I feel", "I suspect"]

        if any(phrase in detected_phrases for phrase in uncertainty_phrases):
            suggestions.append("Replace uncertainty markers with direct statements")

        if any(phrase in detected_phrases for phrase in softening_phrases):
            suggestions.append("Use more definitive language instead of softening phrases")

        if any(phrase in detected_phrases for phrase in tentative_phrases):
            suggestions.append("Remove personal opinions and state facts directly")

        return suggestions
