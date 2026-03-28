"""Executable SI units policy with actual validation logic."""

import re
from typing import Any

import structlog

from .base import BasePolicy, PolicyResult

logger = structlog.get_logger()


class SIUnitPolicy(BasePolicy):
    """Policy that enforces SI units and normalizes measurements."""

    def __init__(
        self,
        enforce_si: bool = True,
        normalize_units: bool = True,
        allowed_units: list[str] | None = None,
    ):
        """Initialize SI units policy.

        Args:
            enforce_si: Whether to enforce SI units only
            normalize_units: Whether to normalize units to SI
            allowed_units: List of allowed non-SI units
        """
        super().__init__("units")
        self.enforce_si = enforce_si
        self.normalize_units = normalize_units
        self.allowed_units = allowed_units or []
        self.si_units = self._get_si_units()
        self.unit_conversions = self._get_unit_conversions()

    async def validate(
        self,
        output: str,
        retrieval_docs: list[dict[str, Any]] | None = None,
    ) -> PolicyResult:
        """Validate output against SI units policy.

        Args:
            output: Generated output text
            retrieval_docs: Retrieved documents for context

        Returns:
            Policy validation result
        """
        violations = []
        suggestions = []
        score = 1.0

        # Detect measurements in text
        measurements = self._detect_measurements(output)

        if measurements:
            # Check for non-SI units
            non_si_units = self._find_non_si_units(measurements)

            if non_si_units:
                if self.enforce_si:
                    violations.append(
                        f"Non-SI units detected: {', '.join(non_si_units)}"
                    )
                    suggestions.append("Convert all measurements to SI units")
                    score -= 0.5
                else:
                    # Check if units are allowed
                    disallowed_units = [
                        unit for unit in non_si_units if unit not in self.allowed_units
                    ]
                    if disallowed_units:
                        violations.append(
                            f"Disallowed units: {', '.join(disallowed_units)}"
                        )
                        suggestions.append("Use only SI units or approved alternatives")
                        score -= 0.3

            # Check for unit consistency
            consistency_issues = self._check_unit_consistency(measurements)
            if consistency_issues:
                violations.append(
                    f"Unit consistency issues: {', '.join(consistency_issues)}"
                )
                suggestions.append("Use consistent units throughout")
                score -= 0.2

            # Check for proper unit formatting
            formatting_issues = self._check_unit_formatting(measurements)
            if formatting_issues:
                violations.append(
                    f"Unit formatting issues: {', '.join(formatting_issues)}"
                )
                suggestions.append(
                    "Use proper unit formatting (e.g., '25°C' not '25 degrees C')"
                )
                score -= 0.1

        # Calculate final score
        score = max(0.0, min(1.0, score))
        passed = len(violations) == 0

        return PolicyResult(
            passed=passed,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata={
                "measurements_found": len(measurements),
                "non_si_units": non_si_units if measurements else [],
                "consistency_issues": consistency_issues if measurements else [],
                "formatting_issues": formatting_issues if measurements else [],
            },
        )

    def _get_si_units(self) -> dict[str, str]:
        """Get SI units and their symbols."""
        return {
            # Length
            "meter": "m",
            "metre": "m",
            "m": "m",
            "kilometer": "km",
            "kilometre": "km",
            "km": "km",
            "centimeter": "cm",
            "centimetre": "cm",
            "cm": "cm",
            "millimeter": "mm",
            "millimetre": "mm",
            "mm": "mm",
            # Mass
            "kilogram": "kg",
            "kg": "kg",
            "gram": "g",
            "g": "g",
            "milligram": "mg",
            "mg": "mg",
            # Time
            "second": "s",
            "s": "s",
            "minute": "min",
            "min": "min",
            "hour": "h",
            "h": "h",
            # Temperature
            "kelvin": "K",
            "K": "K",
            "celsius": "°C",
            "°C": "°C",
            # Pressure
            "pascal": "Pa",
            "Pa": "Pa",
            "kilopascal": "kPa",
            "kPa": "kPa",
            "megapascal": "MPa",
            "MPa": "MPa",
            # Force
            "newton": "N",
            "N": "N",
            "kilonewton": "kN",
            "kN": "kN",
            # Energy
            "joule": "J",
            "J": "J",
            "kilojoule": "kJ",
            "kJ": "kJ",
            "megajoule": "MJ",
            "MJ": "MJ",
            # Power
            "watt": "W",
            "W": "W",
            "kilowatt": "kW",
            "kW": "kW",
            "megawatt": "MW",
            "MW": "MW",
        }

    def _get_unit_conversions(self) -> dict[str, dict[str, float]]:
        """Get unit conversion factors to SI."""
        return {
            # Length conversions to meters
            "length": {
                "inch": 0.0254,
                "in": 0.0254,
                "foot": 0.3048,
                "ft": 0.3048,
                "yard": 0.9144,
                "yd": 0.9144,
                "mile": 1609.344,
                "mi": 1609.344,
            },
            # Mass conversions to kilograms
            "mass": {
                "pound": 0.453592,
                "lb": 0.453592,
                "ounce": 0.0283495,
                "oz": 0.0283495,
                "ton": 1000,
                "t": 1000,
            },
            # Temperature conversions to Kelvin
            "temperature": {
                "fahrenheit": lambda f: (f - 32) * 5 / 9 + 273.15,
                "celsius": lambda c: c + 273.15,
            },
            # Pressure conversions to Pascal
            "pressure": {
                "psi": 6894.76,
                "bar": 100000,
                "atm": 101325,
                "torr": 133.322,
                "mmHg": 133.322,
            },
        }

    def _detect_measurements(self, text: str) -> list[dict[str, Any]]:
        """Detect measurements in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected measurements with values and units
        """
        measurements = []

        # Pattern for number + unit
        pattern = r"(\d+(?:\.\d+)?)\s*([a-zA-Z°]+(?:\^?[0-9]*)?)"
        matches = re.finditer(pattern, text)

        for match in matches:
            value = float(match.group(1))
            unit = match.group(2)

            measurements.append(
                {
                    "value": value,
                    "unit": unit,
                    "position": match.start(),
                    "text": match.group(0),
                }
            )

        return measurements

    def _find_non_si_units(self, measurements: list[dict[str, Any]]) -> list[str]:
        """Find non-SI units in measurements.

        Args:
            measurements: List of detected measurements

        Returns:
            List of non-SI units found
        """
        non_si_units = []
        si_units = self._get_si_units()

        for measurement in measurements:
            unit = measurement["unit"].lower()

            # Check if unit is SI
            if unit not in si_units and unit not in [
                v.lower() for v in si_units.values()
            ]:
                non_si_units.append(measurement["unit"])

        return list(set(non_si_units))

    def _check_unit_consistency(self, measurements: list[dict[str, Any]]) -> list[str]:
        """Check for unit consistency issues.

        Args:
            measurements: List of detected measurements

        Returns:
            List of consistency issues
        """
        issues = []

        # Group measurements by type
        length_measurements = []
        temperature_measurements = []
        pressure_measurements = []

        for measurement in measurements:
            unit = measurement["unit"].lower()

            if unit in ["m", "cm", "mm", "km", "inch", "ft", "yd", "mi"]:
                length_measurements.append(measurement)
            elif unit in ["°c", "°f", "k", "celsius", "fahrenheit", "kelvin"]:
                temperature_measurements.append(measurement)
            elif unit in ["pa", "kpa", "mpa", "psi", "bar", "atm"]:
                pressure_measurements.append(measurement)

        # Check for mixed units in same category
        if len(length_measurements) > 1:
            units = [m["unit"] for m in length_measurements]
            if len(set(units)) > 1:
                issues.append(f"Mixed length units: {', '.join(set(units))}")

        if len(temperature_measurements) > 1:
            units = [m["unit"] for m in temperature_measurements]
            if len(set(units)) > 1:
                issues.append(f"Mixed temperature units: {', '.join(set(units))}")

        if len(pressure_measurements) > 1:
            units = [m["unit"] for m in pressure_measurements]
            if len(set(units)) > 1:
                issues.append(f"Mixed pressure units: {', '.join(set(units))}")

        return issues

    def _check_unit_formatting(self, measurements: list[dict[str, Any]]) -> list[str]:
        """Check for unit formatting issues.

        Args:
            measurements: List of detected measurements

        Returns:
            List of formatting issues
        """
        issues = []

        for measurement in measurements:
            measurement["unit"]
            text = measurement["text"]

            # Check for common formatting issues
            if "degrees" in text.lower() and "°" not in text:
                issues.append(f"Use '°C' instead of 'degrees C' in '{text}'")

            if "per" in text.lower() and "/" not in text:
                issues.append(f"Use '/' instead of 'per' in '{text}'")

            if "squared" in text.lower() and "²" not in text:
                issues.append(f"Use '²' instead of 'squared' in '{text}'")

            if "cubed" in text.lower() and "³" not in text:
                issues.append(f"Use '³' instead of 'cubed' in '{text}'")

        return issues

    def _normalize_units(
        self, measurements: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize units to SI.

        Args:
            measurements: List of measurements to normalize

        Returns:
            List of normalized measurements
        """
        normalized = []
        conversions = self._get_unit_conversions()

        for measurement in measurements:
            unit = measurement["unit"].lower()
            value = measurement["value"]

            # Convert to SI
            if unit in conversions.get("length", {}):
                factor = conversions["length"][unit]
                normalized_value = value * factor
                normalized_unit = "m"
            elif unit in conversions.get("mass", {}):
                factor = conversions["mass"][unit]
                normalized_value = value * factor
                normalized_unit = "kg"
            elif unit in conversions.get("pressure", {}):
                factor = conversions["pressure"][unit]
                normalized_value = value * factor
                normalized_unit = "Pa"
            else:
                # Already SI or unknown
                normalized_value = value
                normalized_unit = unit

            normalized.append(
                {
                    "original": measurement,
                    "normalized": {
                        "value": normalized_value,
                        "unit": normalized_unit,
                    },
                }
            )

        return normalized
