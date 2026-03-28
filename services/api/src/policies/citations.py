"""Citation policy for enforcing proper source attribution."""

import re
from typing import Any

import structlog

from .evidence import PolicyResult

logger = structlog.get_logger()


class CitationPolicy:
    """Policy for enforcing citation standards and source attribution."""

    def __init__(
        self,
        min_citations: int = 3,
        require_inline_citations: bool = True,
        citation_formats: list[str] | None = None,
        ban_unsupported_claims: bool = True,
    ):
        """Initialize citation policy.

        Args:
            min_citations: Minimum number of citations required
            require_inline_citations: Whether inline citations are required
            citation_formats: Allowed citation formats
            ban_unsupported_claims: Whether to ban claims without citations
        """
        self.min_citations = min_citations
        self.require_inline_citations = require_inline_citations
        self.citation_formats = citation_formats or [
            "numeric",  # [1], [2]
            "author-year",  # (Smith, 2023)
            "author-title",  # (Smith et al., 2023)
        ]
        self.ban_unsupported_claims = ban_unsupported_claims

    async def validate(
        self,
        output: str,
        retrieval_set: list[dict[str, Any]],
    ) -> PolicyResult:
        """Validate output against citation policy.

        Args:
            output: Generated output text
            retrieval_set: Retrieved documents with metadata

        Returns:
            Policy validation result
        """
        violations = []
        suggestions = []
        metadata = {}

        # Count citations
        citation_analysis = self._analyze_citations(output)
        metadata["citation_analysis"] = citation_analysis

        # Check minimum citations
        if citation_analysis["total_citations"] < self.min_citations:
            violations.append(
                f"Insufficient citations: {citation_analysis['total_citations']}/{self.min_citations}"
            )
            suggestions.append(
                f"Add at least {self.min_citations - citation_analysis['total_citations']} more citations"
            )

        # Check citation formats
        if citation_analysis["invalid_formats"]:
            violations.append(f"Invalid citation formats: {len(citation_analysis['invalid_formats'])}")
            suggestions.append("Use standard citation formats: [1], (Author, Year), or (Author et al., Year)")
            metadata["invalid_citations"] = citation_analysis["invalid_formats"]

        # Check for unsupported claims
        if self.ban_unsupported_claims:
            unsupported_claims = self._find_unsupported_claims(output, retrieval_set)
            if unsupported_claims:
                violations.append(f"Unsupported claims: {len(unsupported_claims)}")
                suggestions.append("Provide citations for all factual claims")
                metadata["unsupported_claims"] = unsupported_claims

        # Check citation distribution
        if citation_analysis["total_citations"] > 0:
            distribution_score = self._calculate_distribution_score(output, citation_analysis)
            if distribution_score < 0.5:
                violations.append("Poor citation distribution")
                suggestions.append("Distribute citations more evenly throughout the text")
            metadata["distribution_score"] = distribution_score

        # Calculate overall score
        score = self._calculate_score(citation_analysis, len(violations), len(retrieval_set))

        return PolicyResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata=metadata,
        )

    def _analyze_citations(self, text: str) -> dict[str, Any]:
        """Analyze citations in text.

        Args:
            text: Text to analyze

        Returns:
            Citation analysis results
        """
        # Citation patterns
        patterns = {
            "numeric": r'\[(\d+)\]',  # [1], [2], etc.
            "author_year": r'\(([A-Z][a-z]+(?:\s+et\s+al\.)?,\s*\d{4})\)',  # (Smith, 2023)
            "author_title": r'\(([A-Z][a-z]+(?:\s+et\s+al\.)?\s+[^,]+,\s*\d{4})\)',  # (Smith et al., 2023)
        }

        citations = {
            "numeric": [],
            "author_year": [],
            "author_title": [],
            "invalid": [],
        }

        total_citations = 0

        for format_name, pattern in patterns.items():
            matches = re.findall(pattern, text)
            citations[format_name] = matches
            total_citations += len(matches)

        # Find invalid citation patterns
        invalid_pattern = r'\[[^\]]*\]|\([^)]*\)'
        all_citations = re.findall(invalid_pattern, text)

        valid_citations = []
        for format_citations in citations.values():
            valid_citations.extend(format_citations)

        invalid_citations = []
        for citation in all_citations:
            if citation not in valid_citations and len(citation) > 3:
                invalid_citations.append(citation)

        citations["invalid"] = invalid_citations

        return {
            "citations": citations,
            "total_citations": total_citations,
            "invalid_formats": invalid_citations,
            "format_counts": {
                format_name: len(matches)
                for format_name, matches in citations.items()
            },
        }

    def _find_unsupported_claims(
        self,
        text: str,
        retrieval_set: list[dict[str, Any]],
    ) -> list[str]:
        """Find claims that may not be supported by retrieval set.

        Args:
            text: Generated text
            retrieval_set: Retrieved documents

        Returns:
            List of potentially unsupported claims
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        unsupported_claims = []

        # Keywords that indicate factual claims
        factual_indicators = [
            r'\b(is|are|was|were|has|have|had)\b',
            r'\b(according to|studies show|research indicates|data shows)\b',
            r'\b(typically|usually|generally|commonly|often|frequently)\b',
            r'\b\d+%',  # Percentages
            r'\b\d+\s*(mm|cm|m|kg|g|N|Pa|MPa|GPa|°C|°F)\b',  # Measurements
            r'\b(proven|demonstrated|established|confirmed)\b',
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 20:
                continue

            # Check if sentence contains factual indicators
            has_factual_content = any(
                re.search(pattern, sentence, re.IGNORECASE)
                for pattern in factual_indicators
            )

            if has_factual_content:
                # Check if sentence has nearby citation
                has_citation = any(
                    pattern in sentence
                    for pattern in ['[', '(', 'et al', '2023', '2024', '2025']
                )

                if not has_citation:
                    # Check if claim is supported by retrieval set
                    if not self._is_claim_supported(sentence, retrieval_set):
                        unsupported_claims.append(
                            sentence[:100] + "..." if len(sentence) > 100 else sentence
                        )

        return unsupported_claims

    def _is_claim_supported(
        self,
        claim: str,
        retrieval_set: list[dict[str, Any]],
    ) -> bool:
        """Check if a claim is supported by retrieval set.

        Args:
            claim: Claim to check
            retrieval_set: Retrieved documents

        Returns:
            True if claim appears to be supported
        """
        if not retrieval_set:
            return False

        claim_lower = claim.lower()

        # Check if claim keywords appear in retrieval content
        for doc in retrieval_set:
            content = doc.get("content", "").lower()
            doc.get("metadata", {})

            # Extract key terms from claim
            claim_terms = re.findall(r'\b\w{4,}\b', claim_lower)

            # Check if significant terms appear in document
            matching_terms = sum(1 for term in claim_terms if term in content)

            if matching_terms >= len(claim_terms) * 0.3:  # 30% term overlap
                return True

        return False

    def _calculate_distribution_score(
        self,
        text: str,
        citation_analysis: dict[str, Any],
    ) -> float:
        """Calculate citation distribution score.

        Args:
            text: Full text
            citation_analysis: Citation analysis results

        Returns:
            Distribution score (0.0 to 1.0)
        """
        if citation_analysis["total_citations"] == 0:
            return 0.0

        # Split text into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        if len(paragraphs) < 2:
            return 1.0  # Single paragraph, distribution is perfect

        # Count citations per paragraph
        citations_per_paragraph = []
        for paragraph in paragraphs:
            paragraph_citations = 0
            for format_citations in citation_analysis["citations"].values():
                for citation in format_citations:
                    if citation in paragraph:
                        paragraph_citations += 1
            citations_per_paragraph.append(paragraph_citations)

        # Calculate distribution variance
        if not citations_per_paragraph:
            return 0.0

        mean_citations = sum(citations_per_paragraph) / len(citations_per_paragraph)
        if mean_citations == 0:
            return 0.0

        variance = sum((x - mean_citations) ** 2 for x in citations_per_paragraph) / len(citations_per_paragraph)
        std_dev = variance ** 0.5

        # Normalize to 0-1 scale (lower std dev = better distribution)
        max_std_dev = mean_citations * 2  # Reasonable upper bound
        distribution_score = max(0.0, 1.0 - (std_dev / max_std_dev))

        return distribution_score

    def _calculate_score(
        self,
        citation_analysis: dict[str, Any],
        violation_count: int,
        retrieval_count: int,
    ) -> float:
        """Calculate policy compliance score.

        Args:
            citation_analysis: Citation analysis results
            violation_count: Number of violations
            retrieval_count: Number of retrieved documents

        Returns:
            Score between 0.0 and 1.0
        """
        # Base score from citation count
        citation_score = min(
            citation_analysis["total_citations"] / self.min_citations,
            1.0
        )

        # Penalty for violations
        violation_penalty = min(violation_count * 0.2, 0.8)

        # Bonus for having retrieval documents
        retrieval_bonus = min(retrieval_count / 10, 0.2)

        # Bonus for good distribution
        distribution_bonus = citation_analysis.get("distribution_score", 0.0) * 0.1

        score = citation_score - violation_penalty + retrieval_bonus + distribution_bonus
        return max(0.0, min(1.0, score))











