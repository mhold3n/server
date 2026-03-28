"""Evidence policy for requiring citations and source diversity."""

import re
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class PolicyResult(BaseModel):
    """Policy validation result."""

    passed: bool
    score: float
    violations: list[str]
    suggestions: list[str]
    metadata: dict[str, Any] = {}


class EvidencePolicy:
    """Policy for enforcing evidence requirements and citation standards."""

    def __init__(
        self,
        min_citations: int = 3,
        evidence_required: bool = True,
        source_quotas: dict[str, float] | None = None,
        min_source_diversity: float = 0.3,
    ):
        """Initialize evidence policy.

        Args:
            min_citations: Minimum number of citations required
            evidence_required: Whether evidence is required
            source_quotas: Optional source type quotas (e.g., {"textbook": 0.4, "paper": 0.3})
            min_source_diversity: Minimum source diversity ratio
        """
        self.min_citations = min_citations
        self.evidence_required = evidence_required
        self.source_quotas = source_quotas or {}
        self.min_source_diversity = min_source_diversity

    async def validate(
        self,
        output: str,
        retrieval_set: list[dict[str, Any]],
    ) -> PolicyResult:
        """Validate output against evidence policy.

        Args:
            output: Generated output text
            retrieval_set: Retrieved documents with metadata

        Returns:
            Policy validation result
        """
        violations = []
        suggestions = []
        metadata = {}

        # Count citations in output
        citation_count = self._count_citations(output)
        metadata["citation_count"] = citation_count

        # Check minimum citations
        if citation_count < self.min_citations:
            violations.append(
                f"Insufficient citations: {citation_count}/{self.min_citations}"
            )
            suggestions.append(
                f"Add at least {self.min_citations - citation_count} more citations"
            )

        # Analyze source diversity
        if retrieval_set:
            source_analysis = self._analyze_sources(retrieval_set)
            metadata["source_analysis"] = source_analysis

            diversity_score = source_analysis["diversity_score"]
            if diversity_score < self.min_source_diversity:
                violations.append(
                    f"Low source diversity: {diversity_score:.2f}/{self.min_source_diversity}"
                )
                suggestions.append("Include more diverse source types")

            # Check source quotas
            quota_violations = self._check_source_quotas(
                source_analysis["source_types"]
            )
            violations.extend(quota_violations)

        # Check for unsupported claims
        unsupported_claims = self._find_unsupported_claims(output, retrieval_set)
        if unsupported_claims:
            violations.append(f"Unsupported claims found: {len(unsupported_claims)}")
            suggestions.append("Provide citations for all factual claims")
            metadata["unsupported_claims"] = unsupported_claims

        # Calculate overall score
        score = self._calculate_score(
            citation_count, len(violations), len(retrieval_set)
        )

        return PolicyResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata=metadata,
        )

    def _count_citations(self, text: str) -> int:
        """Count citations in text.

        Args:
            text: Text to analyze

        Returns:
            Number of citations found
        """
        # Common citation patterns
        patterns = [
            r"\[(\d+)\]",  # [1], [2], etc.
            r"\([^)]*\d{4}[^)]*\)",  # (Author, 2023)
            r"\[([^\]]*)\]",  # [Author, 2023]
            r"\([^)]*et al\.[^)]*\)",  # (Smith et al., 2023)
            r"\([^)]*\d{4}[^)]*\)",  # (2023)
        ]

        total_citations = 0
        for pattern in patterns:
            matches = re.findall(pattern, text)
            total_citations += len(matches)

        return total_citations

    def _analyze_sources(self, retrieval_set: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze source diversity and types.

        Args:
            retrieval_set: Retrieved documents

        Returns:
            Source analysis results
        """
        source_types = {}
        total_sources = len(retrieval_set)

        for doc in retrieval_set:
            metadata = doc.get("metadata", {})
            source_type = metadata.get("source_type", "unknown")
            source_types[source_type] = source_types.get(source_type, 0) + 1

        # Calculate diversity score (Shannon entropy normalized)
        if total_sources > 1:
            entropy = 0
            for count in source_types.values():
                p = count / total_sources
                entropy -= p * (p.bit_length() - 1) if p > 0 else 0
            diversity_score = entropy / (total_sources.bit_length() - 1)
        else:
            diversity_score = 0.0

        return {
            "source_types": source_types,
            "total_sources": total_sources,
            "diversity_score": diversity_score,
            "unique_types": len(source_types),
        }

    def _check_source_quotas(self, source_types: dict[str, int]) -> list[str]:
        """Check if source types meet quotas.

        Args:
            source_types: Source type counts

        Returns:
            List of quota violations
        """
        violations = []
        total_sources = sum(source_types.values())

        if total_sources == 0:
            return violations

        for source_type, required_ratio in self.source_quotas.items():
            actual_count = source_types.get(source_type, 0)
            actual_ratio = actual_count / total_sources

            if actual_ratio < required_ratio:
                violations.append(
                    f"Insufficient {source_type} sources: {actual_ratio:.2f}/{required_ratio}"
                )

        return violations

    def _find_unsupported_claims(
        self, text: str, retrieval_set: list[dict[str, Any]]
    ) -> list[str]:
        """Find claims that may not be supported by retrieval set.

        Args:
            text: Generated text
            retrieval_set: Retrieved documents

        Returns:
            List of potentially unsupported claims
        """
        # Simple heuristic: look for factual statements without nearby citations
        sentences = re.split(r"[.!?]+", text)
        unsupported_claims = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if sentence contains factual indicators
            factual_indicators = [
                r"\b(is|are|was|were|has|have|had)\b",
                r"\b(according to|studies show|research indicates)\b",
                r"\b(typically|usually|generally|commonly)\b",
                r"\b\d+%",  # Percentages
                r"\b\d+\s*(mm|cm|m|kg|g|N|Pa|MPa|GPa)\b",  # Measurements
            ]

            has_factual_content = any(
                re.search(pattern, sentence, re.IGNORECASE)
                for pattern in factual_indicators
            )

            if has_factual_content:
                # Check if sentence has nearby citation
                has_citation = any(
                    pattern in sentence
                    for pattern in ["[", "(", "et al", "2023", "2024"]
                )

                if not has_citation:
                    unsupported_claims.append(
                        sentence[:100] + "..." if len(sentence) > 100 else sentence
                    )

        return unsupported_claims

    def _calculate_score(
        self,
        citation_count: int,
        violation_count: int,
        retrieval_count: int,
    ) -> float:
        """Calculate policy compliance score.

        Args:
            citation_count: Number of citations
            violation_count: Number of violations
            retrieval_count: Number of retrieved documents

        Returns:
            Score between 0.0 and 1.0
        """
        # Base score from citations
        citation_score = min(citation_count / self.min_citations, 1.0)

        # Penalty for violations
        violation_penalty = min(violation_count * 0.2, 0.8)

        # Bonus for having retrieval documents
        retrieval_bonus = min(retrieval_count / 10, 0.2)

        score = citation_score - violation_penalty + retrieval_bonus
        return max(0.0, min(1.0, score))
