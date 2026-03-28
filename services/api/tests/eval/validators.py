"""Validators for evaluation tests."""

import re
from typing import Any

import structlog

logger = structlog.get_logger()


class CitationValidator:
    """Validates citation requirements in responses."""

    def __init__(self):
        """Initialize citation validator."""
        self.citation_patterns = [
            r"\[\d+\]",  # [1], [2]
            r"\(Source \d+\)",  # (Source 1)
            r"\(Ref\. \d+\)",  # (Ref. 1)
            r"\(p\.\d+\)",  # (p.123)
            r"\(.+?, \d{4}\)",  # (Author, 2023)
        ]

    async def validate(
        self,
        response: str,
        min_citations: int = 0,
        expected_sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """Validate citations in response.

        Args:
            response: Response text
            min_citations: Minimum number of citations required
            expected_sources: Expected source types

        Returns:
            Validation results
        """
        violations = []
        score = 1.0

        # Count citations
        citation_count = 0
        for pattern in self.citation_patterns:
            matches = re.findall(pattern, response)
            citation_count += len(matches)

        # Check minimum citations
        if citation_count < min_citations:
            violations.append(
                f"Insufficient citations: {citation_count}/{min_citations}"
            )
            score -= 0.3

        # Check for source diversity
        if expected_sources:
            source_diversity_score = self._check_source_diversity(
                response, expected_sources
            )
            if source_diversity_score < 0.5:
                violations.append("Poor source diversity")
                score -= 0.2

        # Check citation quality
        quality_score = self._check_citation_quality(response)
        if quality_score < 0.7:
            violations.append("Poor citation quality")
            score -= 0.2

        return {
            "score": max(0.0, score),
            "violations": violations,
            "citation_count": citation_count,
            "source_diversity_score": (
                source_diversity_score if expected_sources else 1.0
            ),
            "quality_score": quality_score,
        }

    def _check_source_diversity(
        self,
        response: str,
        expected_sources: list[str],
    ) -> float:
        """Check source diversity in response.

        Args:
            response: Response text
            expected_sources: Expected source types

        Returns:
            Diversity score (0.0 to 1.0)
        """
        # Simple keyword-based source detection
        source_indicators = {
            "textbook": ["textbook", "book", "reference"],
            "paper": ["paper", "study", "research", "journal"],
            "standard": ["standard", "specification", "code"],
            "documentation": ["documentation", "manual", "guide"],
        }

        found_sources = set()
        for source_type in expected_sources:
            if source_type in source_indicators:
                for indicator in source_indicators[source_type]:
                    if indicator.lower() in response.lower():
                        found_sources.add(source_type)
                        break

        return len(found_sources) / len(expected_sources) if expected_sources else 1.0

    def _check_citation_quality(self, response: str) -> float:
        """Check citation quality.

        Args:
            response: Response text

        Returns:
            Quality score (0.0 to 1.0)
        """
        # Check for proper citation formatting
        quality_indicators = [
            r"\[\d+\]",  # Numeric citations
            r"\([^)]+\d{4}[^)]*\)",  # Author-year citations
        ]

        quality_score = 0.0
        for pattern in quality_indicators:
            if re.search(pattern, response):
                quality_score += 0.5

        return min(1.0, quality_score)


class SIUnitValidator:
    """Validates SI unit usage in responses."""

    def __init__(self):
        """Initialize SI unit validator."""
        # Non-SI units that should be converted
        self.non_si_units = {
            "inch": ("m", 0.0254),
            "inches": ("m", 0.0254),
            "in": ("m", 0.0254),
            "ft": ("m", 0.3048),
            "feet": ("m", 0.3048),
            "foot": ("m", 0.3048),
            "yard": ("m", 0.9144),
            "yards": ("m", 0.9144),
            "mile": ("m", 1609.344),
            "miles": ("m", 1609.344),
            "lb": ("kg", 0.453592),
            "lbs": ("kg", 0.453592),
            "pound": ("kg", 0.453592),
            "pounds": ("kg", 0.453592),
            "oz": ("kg", 0.0283495),
            "ounce": ("kg", 0.0283495),
            "ounces": ("kg", 0.0283495),
            "ton": ("kg", 907.185),
            "tons": ("kg", 907.185),
            "psi": ("Pa", 6894.76),
            "psia": ("Pa", 6894.76),
            "psig": ("Pa", 6894.76),
            "ksi": ("Pa", 6894760),
            "atm": ("Pa", 101325),
            "bar": ("Pa", 100000),
            "torr": ("Pa", 133.322),
            "mmHg": ("Pa", 133.322),
            "inHg": ("Pa", 3386.39),
            "BTU": ("J", 1055.06),
            "btu": ("J", 1055.06),
            "cal": ("J", 4.184),
            "kcal": ("J", 4184),
            "Wh": ("J", 3600),
            "kWh": ("J", 3600000),
            "hp": ("W", 745.7),
            "horsepower": ("W", 745.7),
        }

        # Allowed non-SI units
        self.allowed_units = {
            "°C",
            "°F",
            "K",  # Temperature
            "%",
            "percent",
            "percentage",  # Percentages
            "°",
            "degrees",
            "deg",  # Angles
            "rad",
            "radians",  # Radians
            "mol",
            "mole",
            "moles",  # Moles
            "Hz",
            "hertz",  # Frequency
            "rpm",
            "rev/min",  # Rotational speed
        }

    async def validate(
        self,
        response: str,
        si_required: bool = True,
    ) -> dict[str, Any]:
        """Validate SI unit usage in response.

        Args:
            response: Response text
            si_required: Whether SI units are required

        Returns:
            Validation results
        """
        violations = []
        score = 1.0

        if not si_required:
            return {
                "score": 1.0,
                "violations": [],
                "non_si_units_found": [],
                "missing_units": [],
            }

        # Find non-SI units
        non_si_units_found = []
        for unit, (_si_unit, _factor) in self.non_si_units.items():
            pattern = r"\b\d+(?:\.\d+)?\s*" + re.escape(unit) + r"\b"
            if re.search(pattern, response, re.IGNORECASE):
                non_si_units_found.append(unit)

        # Check for missing units
        missing_units = self._find_missing_units(response)

        # Calculate score
        if non_si_units_found:
            violations.append(f"Non-SI units found: {', '.join(non_si_units_found)}")
            score -= 0.3

        if missing_units:
            violations.append(f"Missing units: {len(missing_units)} instances")
            score -= 0.2

        return {
            "score": max(0.0, score),
            "violations": violations,
            "non_si_units_found": non_si_units_found,
            "missing_units": missing_units,
        }

    def _find_missing_units(self, response: str) -> list[str]:
        """Find numerical values without units.

        Args:
            response: Response text

        Returns:
            List of missing unit instances
        """
        missing_units = []

        # Pattern for numbers that should have units
        number_pattern = r"\b(\d+(?:\.\d+)?)\s*([a-zA-Z°%]+(?:\s*[a-zA-Z°%]+)*)?\b"

        matches = re.finditer(number_pattern, response)

        for match in matches:
            value = float(match.group(1))
            unit = match.group(2) if match.group(2) else ""

            # Check if this number should have a unit
            if self._should_have_unit(value, unit, match.start(), response):
                missing_units.append(match.group(0))

        return missing_units

    def _should_have_unit(
        self,
        value: float,
        unit: str,
        position: int,
        text: str,
    ) -> bool:
        """Check if a number should have a unit.

        Args:
            value: Numerical value
            unit: Existing unit (if any)
            position: Position in text
            text: Full text

        Returns:
            True if number should have a unit
        """
        # If already has unit, no issue
        if unit:
            return False

        # Skip very small numbers (likely percentages or ratios)
        if value < 1 and value > 0:
            return False

        # Skip integers that are likely counts
        if value == int(value) and value < 100:
            return False

        # Check context for unit indicators
        context = text[max(0, position - 100) : position + 100].lower()

        # If context suggests units are expected
        unit_indicators = [
            "length",
            "width",
            "height",
            "diameter",
            "radius",
            "mass",
            "weight",
            "force",
            "pressure",
            "stress",
            "temperature",
            "energy",
            "power",
            "voltage",
            "current",
            "speed",
            "velocity",
            "acceleration",
            "frequency",
        ]

        if any(indicator in context for indicator in unit_indicators):
            return True

        return False


class HedgingValidator:
    """Validates hedging language in responses."""

    def __init__(self):
        """Initialize hedging validator."""
        self.hedging_indicators = [
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
        response: str,
        hedging_allowed: bool = True,
    ) -> dict[str, Any]:
        """Validate hedging language in response.

        Args:
            response: Response text
            hedging_allowed: Whether hedging is allowed

        Returns:
            Validation results
        """
        violations = []
        score = 1.0

        if hedging_allowed:
            return {
                "score": 1.0,
                "violations": [],
                "hedging_count": 0,
                "hedging_ratio": 0.0,
            }

        # Count hedging instances
        hedging_count = 0
        text_lower = response.lower()

        for indicator in self.hedging_indicators:
            pattern = r"\b" + re.escape(indicator) + r"\b"
            matches = re.findall(pattern, text_lower)
            hedging_count += len(matches)

        # Calculate hedging ratio
        words = text_lower.split()
        total_words = len(words)
        hedging_ratio = hedging_count / total_words if total_words > 0 else 0.0

        # Check for excessive hedging
        if hedging_count > 0:
            violations.append(f"Hedging language detected: {hedging_count} instances")
            score -= 0.3

        if hedging_ratio > 0.1:  # More than 10% hedging
            violations.append(f"Excessive hedging: {hedging_ratio:.2%}")
            score -= 0.2

        return {
            "score": max(0.0, score),
            "violations": violations,
            "hedging_count": hedging_count,
            "hedging_ratio": hedging_ratio,
        }
