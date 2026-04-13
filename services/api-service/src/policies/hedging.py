"""Hedging policy for detecting and managing uncertain language."""

import re
from typing import Any

import structlog

from .evidence import PolicyResult

logger = structlog.get_logger()


class HedgingPolicy:
    """Policy for detecting and managing hedging language in outputs."""

    def __init__(
        self,
        ban_hedging: bool = False,
        max_hedging_ratio: float = 0.1,
        allow_justified_hedging: bool = True,
        hedging_indicators: list[str] | None = None,
    ):
        """Initialize hedging policy.

        Args:
            ban_hedging: Whether to completely ban hedging language
            max_hedging_ratio: Maximum ratio of hedging words to total words
            allow_justified_hedging: Whether to allow hedging with justification
            hedging_indicators: Custom list of hedging indicators
        """
        self.ban_hedging = ban_hedging
        self.max_hedging_ratio = max_hedging_ratio
        self.allow_justified_hedging = allow_justified_hedging
        self.hedging_indicators = hedging_indicators or [
            # Uncertainty indicators
            "maybe",
            "perhaps",
            "possibly",
            "potentially",
            "might",
            "could",
            "may",
            "likely",
            "unlikely",
            "probably",
            "presumably",
            "supposedly",
            # Tentative language
            "seems",
            "appears",
            "suggests",
            "indicates",
            "implies",
            "hints",
            "tends to",
            "generally",
            "typically",
            "usually",
            "often",
            "frequently",
            # Weak assertions
            "somewhat",
            "rather",
            "quite",
            "fairly",
            "relatively",
            "comparatively",
            "to some extent",
            "in some cases",
            "under certain conditions",
            # Conditional language
            "if",
            "unless",
            "provided that",
            "assuming",
            "given that",
            "depending on",
            "subject to",
            "contingent upon",
            # Approximation
            "approximately",
            "roughly",
            "about",
            "around",
            "nearly",
            "almost",
            "more or less",
            "give or take",
            "in the ballpark of",
        ]

    async def validate(
        self,
        output: str,
        retrieval_set: list[dict[str, Any]] | None = None,
    ) -> PolicyResult:
        """Validate output against hedging policy.

        Args:
            output: Generated output text
            retrieval_set: Optional retrieved documents for context

        Returns:
            Policy validation result
        """
        violations = []
        suggestions = []
        metadata = {}

        # Analyze hedging in text
        hedging_analysis = self._analyze_hedging(output)
        metadata["hedging_analysis"] = hedging_analysis

        # Check if hedging is banned
        if self.ban_hedging and hedging_analysis["hedging_count"] > 0:
            violations.append(
                f"Hedging language detected: {hedging_analysis['hedging_count']} instances"
            )
            suggestions.append("Remove all hedging language and state facts directly")
            metadata["hedging_instances"] = hedging_analysis["hedging_instances"]

        # Check hedging ratio
        if hedging_analysis["hedging_ratio"] > self.max_hedging_ratio:
            violations.append(
                f"Excessive hedging: {hedging_analysis['hedging_ratio']:.2%} > {self.max_hedging_ratio:.2%}"
            )
            suggestions.append("Reduce hedging language and be more direct")

        # Check for unjustified hedging
        if self.allow_justified_hedging:
            unjustified_hedging = self._find_unjustified_hedging(output, retrieval_set)
            if unjustified_hedging:
                violations.append(
                    f"Unjustified hedging: {len(unjustified_hedging)} instances"
                )
                suggestions.append(
                    "Provide justification for uncertain statements or remove hedging"
                )
                metadata["unjustified_hedging"] = unjustified_hedging

        # Check for weak language patterns
        weak_patterns = self._detect_weak_patterns(output)
        if weak_patterns:
            violations.append(f"Weak language patterns: {len(weak_patterns)} instances")
            suggestions.append("Use stronger, more definitive language")
            metadata["weak_patterns"] = weak_patterns

        # Calculate overall score
        score = self._calculate_score(hedging_analysis, len(violations))

        return PolicyResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata=metadata,
        )

    def _analyze_hedging(self, text: str) -> dict[str, Any]:
        """Analyze hedging language in text.

        Args:
            text: Text to analyze

        Returns:
            Hedging analysis results
        """
        text_lower = text.lower()
        words = text_lower.split()
        total_words = len(words)

        hedging_instances = []
        hedging_count = 0

        # Find hedging indicators
        for indicator in self.hedging_indicators:
            pattern = r"\b" + re.escape(indicator) + r"\b"
            matches = re.finditer(pattern, text_lower)

            for match in matches:
                # Get context around the hedging word
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()

                hedging_instances.append(
                    {
                        "word": indicator,
                        "position": match.start(),
                        "context": context,
                    }
                )
                hedging_count += 1

        # Calculate hedging ratio
        hedging_ratio = hedging_count / total_words if total_words > 0 else 0.0

        # Find hedging clusters (multiple hedging words close together)
        hedging_clusters = self._find_hedging_clusters(hedging_instances)

        return {
            "hedging_count": hedging_count,
            "hedging_ratio": hedging_ratio,
            "total_words": total_words,
            "hedging_instances": hedging_instances,
            "hedging_clusters": hedging_clusters,
            "unique_hedging_words": len(
                {instance["word"] for instance in hedging_instances}
            ),
        }

    def _find_hedging_clusters(
        self,
        hedging_instances: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Find clusters of hedging words close together.

        Args:
            hedging_instances: List of hedging instances

        Returns:
            List of hedging clusters
        """
        if len(hedging_instances) < 2:
            return []

        # Sort by position
        sorted_instances = sorted(hedging_instances, key=lambda x: x["position"])

        clusters = []
        current_cluster = [sorted_instances[0]]

        for instance in sorted_instances[1:]:
            # If within 100 characters of previous instance, add to cluster
            if instance["position"] - current_cluster[-1]["position"] <= 100:
                current_cluster.append(instance)
            else:
                # End current cluster if it has multiple instances
                if len(current_cluster) > 1:
                    clusters.append(
                        {
                            "instances": current_cluster,
                            "start_position": current_cluster[0]["position"],
                            "end_position": current_cluster[-1]["position"],
                            "cluster_size": len(current_cluster),
                        }
                    )
                current_cluster = [instance]

        # Don't forget the last cluster
        if len(current_cluster) > 1:
            clusters.append(
                {
                    "instances": current_cluster,
                    "start_position": current_cluster[0]["position"],
                    "end_position": current_cluster[-1]["position"],
                    "cluster_size": len(current_cluster),
                }
            )

        return clusters

    def _find_unjustified_hedging(
        self,
        text: str,
        retrieval_set: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Find hedging that lacks justification.

        Args:
            text: Generated text
            retrieval_set: Retrieved documents for context

        Returns:
            List of unjustified hedging instances
        """
        if not retrieval_set:
            return []

        # Split into sentences
        sentences = re.split(r"[.!?]+", text)
        unjustified_instances = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if sentence contains hedging
            sentence_lower = sentence.lower()
            hedging_in_sentence = [
                indicator
                for indicator in self.hedging_indicators
                if re.search(r"\b" + re.escape(indicator) + r"\b", sentence_lower)
            ]

            if hedging_in_sentence:
                # Check if hedging is justified by evidence
                if not self._is_hedging_justified(sentence, retrieval_set):
                    unjustified_instances.append(
                        {
                            "sentence": sentence,
                            "hedging_words": hedging_in_sentence,
                            "reason": "No supporting evidence found",
                        }
                    )

        return unjustified_instances

    def _is_hedging_justified(
        self,
        sentence: str,
        retrieval_set: list[dict[str, Any]],
    ) -> bool:
        """Check if hedging in sentence is justified by evidence.

        Args:
            sentence: Sentence containing hedging
            retrieval_set: Retrieved documents

        Returns:
            True if hedging appears justified
        """
        # Extract key terms from sentence
        key_terms = re.findall(r"\b\w{4,}\b", sentence.lower())

        # Check if key terms appear in retrieval set
        for doc in retrieval_set:
            content = doc.get("content", "").lower()
            doc.get("metadata", {})

            # Count matching terms
            matching_terms = sum(1 for term in key_terms if term in content)

            # If significant overlap, hedging might be justified
            if matching_terms >= len(key_terms) * 0.4:  # 40% term overlap
                return True

        return False

    def _detect_weak_patterns(self, text: str) -> list[dict[str, Any]]:
        """Detect weak language patterns.

        Args:
            text: Text to analyze

        Returns:
            List of weak language patterns
        """
        weak_patterns = []

        # Patterns that indicate weak language
        patterns = [
            {
                "name": "excessive_qualifiers",
                "pattern": r"\b(very|quite|rather|somewhat|fairly|relatively)\s+\w+",
                "description": "Excessive use of qualifiers",
            },
            {
                "name": "double_negatives",
                "pattern": r"\b(not\s+un\w+|not\s+in\w+)",
                "description": "Double negative constructions",
            },
            {
                "name": "passive_voice",
                "pattern": r"\b(is\s+\w+ed|are\s+\w+ed|was\s+\w+ed|were\s+\w+ed)",
                "description": "Passive voice constructions",
            },
            {
                "name": "vague_pronouns",
                "pattern": r"\b(this|that|these|those|it)\s+(is|are|was|were)",
                "description": "Vague pronoun references",
            },
        ]

        for pattern_info in patterns:
            matches = re.finditer(pattern_info["pattern"], text, re.IGNORECASE)

            for match in matches:
                weak_patterns.append(
                    {
                        "type": pattern_info["name"],
                        "description": pattern_info["description"],
                        "text": match.group(0),
                        "position": match.start(),
                    }
                )

        return weak_patterns

    def _calculate_score(
        self,
        hedging_analysis: dict[str, Any],
        violation_count: int,
    ) -> float:
        """Calculate policy compliance score.

        Args:
            hedging_analysis: Hedging analysis results
            violation_count: Number of violations

        Returns:
            Score between 0.0 and 1.0
        """
        # Base score from hedging ratio (lower is better)
        hedging_ratio = hedging_analysis["hedging_ratio"]
        ratio_score = max(0.0, 1.0 - (hedging_ratio / self.max_hedging_ratio))

        # Penalty for violations
        violation_penalty = min(violation_count * 0.2, 0.8)

        # Penalty for hedging clusters
        cluster_penalty = min(len(hedging_analysis["hedging_clusters"]) * 0.1, 0.3)

        # Bonus for low hedging count
        count_bonus = max(0.0, 1.0 - (hedging_analysis["hedging_count"] / 10))

        score = ratio_score - violation_penalty - cluster_penalty + count_bonus
        return max(0.0, min(1.0, score))
