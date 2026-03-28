"""Non-generative conditioning for domain weighting and SI unit normalization."""

import re
from typing import Any

import structlog

logger = structlog.get_logger()


class NonGenerativeConditioning:
    """Applies non-generative conditioning to prompts without changing the original content."""

    def __init__(self):
        """Initialize conditioning with SI unit patterns and domain weights."""
        self.si_units = {
            # Length
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
            "mm": ("m", 0.001),
            "cm": ("m", 0.01),
            "km": ("m", 1000),
            # Mass
            "lb": ("kg", 0.453592),
            "lbs": ("kg", 0.453592),
            "pound": ("kg", 0.453592),
            "pounds": ("kg", 0.453592),
            "oz": ("kg", 0.0283495),
            "ounce": ("kg", 0.0283495),
            "ounces": ("kg", 0.0283495),
            "ton": ("kg", 907.185),
            "tons": ("kg", 907.185),
            "g": ("kg", 0.001),
            # Force
            "lbf": ("N", 4.44822),
            "pound-force": ("N", 4.44822),
            "pounds-force": ("N", 4.44822),
            "kip": ("N", 4448.22),
            "kips": ("N", 4448.22),
            # Pressure
            "psi": ("Pa", 6894.76),
            "psia": ("Pa", 6894.76),
            "psig": ("Pa", 6894.76),
            "ksi": ("Pa", 6894760),
            "atm": ("Pa", 101325),
            "bar": ("Pa", 100000),
            "torr": ("Pa", 133.322),
            "mmHg": ("Pa", 133.322),
            "inHg": ("Pa", 3386.39),
            # Temperature
            "°F": ("K", lambda f: (f - 32) * 5 / 9 + 273.15),
            "F": ("K", lambda f: (f - 32) * 5 / 9 + 273.15),
            "fahrenheit": ("K", lambda f: (f - 32) * 5 / 9 + 273.15),
            "°C": ("K", lambda c: c + 273.15),
            "C": ("K", lambda c: c + 273.15),
            "celsius": ("K", lambda c: c + 273.15),
            # Energy
            "BTU": ("J", 1055.06),
            "btu": ("J", 1055.06),
            "cal": ("J", 4.184),
            "kcal": ("J", 4184),
            "Wh": ("J", 3600),
            "kWh": ("J", 3600000),
            # Power
            "hp": ("W", 745.7),
            "horsepower": ("W", 745.7),
            "BTU/h": ("W", 0.293071),
            "btu/h": ("W", 0.293071),
        }

    def apply_domain_weighting(
        self,
        prompt: str,
        domain_weights: dict[str, float],
        context: str | None = None,
    ) -> dict[str, Any]:
        """Apply domain weighting to enhance context without changing prompt.

        Args:
            prompt: Original user prompt
            domain_weights: Domain weights (chemistry, mechanical, materials)
            context: Optional additional context

        Returns:
            Dictionary with conditioned prompt and metadata
        """
        # Create domain context
        domain_context = self._build_domain_context(domain_weights)

        # Build enhanced system context
        system_context = f"""Domain Analysis: {domain_context}

Context: You are responding to a technical query with the following domain relevance:
{self._format_domain_weights(domain_weights)}

Please provide a comprehensive, technically accurate response that draws from the most relevant domain knowledge."""

        if context:
            system_context += f"\n\nAdditional Context: {context}"

        return {
            "original_prompt": prompt,
            "system_context": system_context,
            "domain_weights": domain_weights,
            "domain_context": domain_context,
        }

    def apply_si_normalization(
        self,
        text: str,
        normalize: bool = True,
    ) -> dict[str, Any]:
        """Normalize units to SI system.

        Args:
            text: Text containing units to normalize
            normalize: Whether to actually convert units (False for detection only)

        Returns:
            Dictionary with normalized text and unit information
        """
        if not normalize:
            return self._detect_units(text)

        normalized_text = text
        unit_conversions = []

        # Find and convert units
        for unit, (si_unit, conversion) in self.si_units.items():
            pattern = rf"\b(\d+(?:\.\d+)?)\s*{re.escape(unit)}\b"

            def replace_unit(
                match,
                *,
                _unit=unit,
                _si_unit=si_unit,
                _conversion=conversion,
            ):
                value = float(match.group(1))

                if callable(_conversion):
                    si_value = _conversion(value)
                else:
                    si_value = value * _conversion

                unit_conversions.append(
                    {
                        "original": f"{value} {_unit}",
                        "converted": f"{si_value:.3f} {_si_unit}",
                        "value": value,
                        "si_value": si_value,
                        "unit": _unit,
                        "si_unit": _si_unit,
                    }
                )

                return f"{si_value:.3f} {_si_unit}"

            normalized_text = re.sub(
                pattern, replace_unit, normalized_text, flags=re.IGNORECASE
            )

        return {
            "original_text": text,
            "normalized_text": normalized_text,
            "unit_conversions": unit_conversions,
            "has_units": len(unit_conversions) > 0,
        }

    def apply_constraint_detection(
        self,
        text: str,
    ) -> dict[str, Any]:
        """Detect safety and operational constraints in text.

        Args:
            text: Text to analyze for constraints

        Returns:
            Dictionary with detected constraints
        """
        safety_keywords = [
            "safety",
            "safe",
            "hazard",
            "danger",
            "risk",
            "caution",
            "warning",
            "flammable",
            "toxic",
            "corrosive",
            "explosive",
            "pressure",
            "temperature",
            "limit",
            "maximum",
            "minimum",
            "critical",
            "failure",
            "breakdown",
        ]

        operational_keywords = [
            "operating",
            "operation",
            "maintenance",
            "inspection",
            "service",
            "lifecycle",
            "durability",
            "reliability",
            "efficiency",
            "performance",
            "cost",
            "budget",
            "schedule",
            "timeline",
            "deadline",
            "delivery",
        ]

        text_lower = text.lower()

        safety_constraints = [
            keyword for keyword in safety_keywords if keyword in text_lower
        ]

        operational_constraints = [
            keyword for keyword in operational_keywords if keyword in text_lower
        ]

        return {
            "safety_constraints": safety_constraints,
            "operational_constraints": operational_constraints,
            "has_safety_constraints": len(safety_constraints) > 0,
            "has_operational_constraints": len(operational_constraints) > 0,
        }

    def apply_evidence_weighting(
        self,
        prompt: str,
        evidence_sources: list[dict[str, Any]],
        min_sources: int = 3,
    ) -> dict[str, Any]:
        """Apply evidence weighting for RAG retrieval.

        Args:
            prompt: Original prompt
            evidence_sources: List of evidence sources with metadata
            min_sources: Minimum number of sources required

        Returns:
            Dictionary with evidence weighting information
        """
        if len(evidence_sources) < min_sources:
            return {
                "original_prompt": prompt,
                "evidence_sufficient": False,
                "evidence_count": len(evidence_sources),
                "min_required": min_sources,
                "evidence_context": "Insufficient evidence sources available.",
            }

        # Build evidence context
        evidence_context = "Evidence Sources:\n"
        for i, source in enumerate(evidence_sources, 1):
            evidence_context += f"{i}. {source.get('title', 'Unknown')} "
            evidence_context += f"(Score: {source.get('score', 0):.3f})\n"
            if source.get("snippet"):
                evidence_context += f"   {source['snippet'][:100]}...\n"

        return {
            "original_prompt": prompt,
            "evidence_sufficient": True,
            "evidence_count": len(evidence_sources),
            "min_required": min_sources,
            "evidence_context": evidence_context,
            "evidence_sources": evidence_sources,
        }

    def _build_domain_context(self, domain_weights: dict[str, float]) -> str:
        """Build domain context string from weights."""
        sorted_domains = sorted(
            domain_weights.items(), key=lambda x: x[1], reverse=True
        )

        context_parts = []
        for domain, weight in sorted_domains:
            if weight > 0.1:  # Only include significant domains
                context_parts.append(f"{domain.title()}: {weight:.2f}")

        return ", ".join(context_parts) if context_parts else "General"

    def _format_domain_weights(self, domain_weights: dict[str, float]) -> str:
        """Format domain weights for display."""
        formatted = []
        for domain, weight in domain_weights.items():
            formatted.append(f"- {domain.title()}: {weight:.1%}")
        return "\n".join(formatted)

    def _detect_units(self, text: str) -> dict[str, Any]:
        """Detect units in text without converting."""
        detected_units = []

        for unit, (si_unit, _conversion) in self.si_units.items():
            pattern = rf"\b(\d+(?:\.\d+)?)\s*{re.escape(unit)}\b"
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                value = float(match.group(1))
                detected_units.append(
                    {
                        "value": value,
                        "unit": unit,
                        "si_unit": si_unit,
                        "position": match.span(),
                        "text": match.group(0),
                    }
                )

        return {
            "original_text": text,
            "detected_units": detected_units,
            "has_units": len(detected_units) > 0,
        }
