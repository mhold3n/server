"""SI unit policy for enforcing metric system and unit consistency."""

import re
from typing import Any

import structlog

from .evidence import PolicyResult

logger = structlog.get_logger()


class SIUnitPolicy:
    """Policy for enforcing SI units and unit consistency."""

    def __init__(
        self,
        enforce_si_units: bool = True,
        allow_common_units: bool = True,
        require_unit_consistency: bool = True,
        unit_conversion_threshold: float = 0.01,
    ):
        """Initialize SI unit policy.

        Args:
            enforce_si_units: Whether to enforce SI units
            allow_common_units: Whether to allow common non-SI units (e.g., degrees, percentages)
            require_unit_consistency: Whether to require consistent units throughout
            unit_conversion_threshold: Threshold for unit conversion accuracy
        """
        self.enforce_si_units = enforce_si_units
        self.allow_common_units = allow_common_units
        self.require_unit_consistency = require_unit_consistency
        self.unit_conversion_threshold = unit_conversion_threshold

        # Unit conversion factors to SI
        self.unit_conversions = {
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

        # Common units that are allowed
        self.allowed_units = {
            "°C", "°F", "K",  # Temperature
            "%", "percent", "percentage",  # Percentages
            "°", "degrees", "deg",  # Angles
            "rad", "radians",  # Radians
            "mol", "mole", "moles",  # Moles
            "Hz", "hertz",  # Frequency
            "rpm", "rev/min",  # Rotational speed
        }

    async def validate(
        self,
        output: str,
        retrieval_set: list[dict[str, Any]] | None = None,
    ) -> PolicyResult:
        """Validate output against SI unit policy.

        Args:
            output: Generated output text
            retrieval_set: Optional retrieved documents for context

        Returns:
            Policy validation result
        """
        violations = []
        suggestions = []
        metadata = {}

        # Analyze units in text
        unit_analysis = self._analyze_units(output)
        metadata["unit_analysis"] = unit_analysis

        # Check for non-SI units
        if self.enforce_si_units:
            non_si_units = self._find_non_si_units(unit_analysis)
            if non_si_units:
                violations.append(f"Non-SI units detected: {len(non_si_units)} instances")
                suggestions.append("Convert all units to SI system (meters, kilograms, seconds, etc.)")
                metadata["non_si_units"] = non_si_units

        # Check unit consistency
        if self.require_unit_consistency:
            consistency_issues = self._check_unit_consistency(unit_analysis)
            if consistency_issues:
                violations.append(f"Unit consistency issues: {len(consistency_issues)}")
                suggestions.append("Use consistent units throughout the document")
                metadata["consistency_issues"] = consistency_issues

        # Check for unit conversion errors
        conversion_errors = self._check_conversion_errors(unit_analysis)
        if conversion_errors:
            violations.append(f"Unit conversion errors: {len(conversion_errors)}")
            suggestions.append("Verify unit conversions are accurate")
            metadata["conversion_errors"] = conversion_errors

        # Check for missing units
        missing_units = self._find_missing_units(output)
        if missing_units:
            violations.append(f"Missing units: {len(missing_units)} instances")
            suggestions.append("Include units for all numerical values")
            metadata["missing_units"] = missing_units

        # Calculate overall score
        score = self._calculate_score(unit_analysis, len(violations))

        return PolicyResult(
            passed=len(violations) == 0,
            score=score,
            violations=violations,
            suggestions=suggestions,
            metadata=metadata,
        )

    def _analyze_units(self, text: str) -> dict[str, Any]:
        """Analyze units in text.

        Args:
            text: Text to analyze

        Returns:
            Unit analysis results
        """
        # Pattern to find numbers with units
        unit_pattern = r'\b(\d+(?:\.\d+)?)\s*([a-zA-Z°%]+(?:\s*[a-zA-Z°%]+)*)\b'

        unit_instances = []
        unit_types = {}

        matches = re.finditer(unit_pattern, text, re.IGNORECASE)

        for match in matches:
            value = float(match.group(1))
            unit = match.group(2).strip()

            # Normalize unit
            unit_normalized = self._normalize_unit(unit)

            unit_instances.append({
                "value": value,
                "unit": unit,
                "unit_normalized": unit_normalized,
                "position": match.start(),
                "text": match.group(0),
            })

            # Count unit types
            unit_types[unit_normalized] = unit_types.get(unit_normalized, 0) + 1

        return {
            "unit_instances": unit_instances,
            "unit_types": unit_types,
            "total_units": len(unit_instances),
            "unique_unit_types": len(unit_types),
        }

    def _normalize_unit(self, unit: str) -> str:
        """Normalize unit string.

        Args:
            unit: Unit string to normalize

        Returns:
            Normalized unit string
        """
        # Convert to lowercase and remove extra spaces
        normalized = re.sub(r'\s+', ' ', unit.lower().strip())

        # Handle common variations
        variations = {
            "degrees": "°",
            "deg": "°",
            "percent": "%",
            "percentage": "%",
            "hertz": "Hz",
            "rev/min": "rpm",
            "revolutions per minute": "rpm",
        }

        return variations.get(normalized, normalized)

    def _find_non_si_units(
        self,
        unit_analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Find non-SI units in the analysis.

        Args:
            unit_analysis: Unit analysis results

        Returns:
            List of non-SI unit instances
        """
        non_si_units = []

        for instance in unit_analysis["unit_instances"]:
            unit = instance["unit_normalized"]

            # Check if unit is non-SI
            if self._is_non_si_unit(unit):
                non_si_units.append({
                    "instance": instance,
                    "si_equivalent": self._get_si_equivalent(unit),
                    "conversion_factor": self._get_conversion_factor(unit),
                })

        return non_si_units

    def _is_non_si_unit(self, unit: str) -> bool:
        """Check if unit is non-SI.

        Args:
            unit: Unit to check

        Returns:
            True if unit is non-SI
        """
        # SI base units and derived units
        si_units = {
            "m", "kg", "s", "A", "K", "mol", "cd",  # Base units
            "N", "Pa", "J", "W", "V", "F", "Ω", "S", "Wb", "T", "H", "lm", "lx", "Bq", "Gy", "Sv", "kat",  # Derived units
            "Hz", "rad", "sr", "°C", "°F",  # Special units
        }

        # Check if unit is in conversion table (non-SI)
        if unit in self.unit_conversions:
            return True

        # Check if unit is allowed common unit
        if unit in self.allowed_units:
            return False

        # Check if unit is SI
        if unit in si_units:
            return False

        # Check for SI prefixes
        si_prefixes = ["k", "M", "G", "T", "P", "E", "Z", "Y", "m", "μ", "n", "p", "f", "a", "z", "y"]
        for prefix in si_prefixes:
            if unit.startswith(prefix) and unit[1:] in si_units:
                return False

        return True

    def _get_si_equivalent(self, unit: str) -> str | None:
        """Get SI equivalent of unit.

        Args:
            unit: Unit to convert

        Returns:
            SI equivalent unit or None
        """
        if unit in self.unit_conversions:
            return self.unit_conversions[unit][0]
        return None

    def _get_conversion_factor(self, unit: str) -> float | None:
        """Get conversion factor to SI.

        Args:
            unit: Unit to convert

        Returns:
            Conversion factor or None
        """
        if unit in self.unit_conversions:
            return self.unit_conversions[unit][1]
        return None

    def _check_unit_consistency(
        self,
        unit_analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Check for unit consistency issues.

        Args:
            unit_analysis: Unit analysis results

        Returns:
            List of consistency issues
        """
        consistency_issues = []

        # Group units by physical quantity
        quantity_groups = self._group_units_by_quantity(unit_analysis["unit_instances"])

        for quantity, instances in quantity_groups.items():
            if len(instances) > 1:
                # Check if all instances use the same unit type
                unit_types = {instance["unit_normalized"] for instance in instances}

                if len(unit_types) > 1:
                    consistency_issues.append({
                        "quantity": quantity,
                        "instances": instances,
                        "unit_types": list(unit_types),
                        "issue": "Mixed units for same physical quantity",
                    })

        return consistency_issues

    def _group_units_by_quantity(
        self,
        unit_instances: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Group units by physical quantity.

        Args:
            unit_instances: List of unit instances

        Returns:
            Dictionary mapping quantities to instances
        """
        quantity_groups = {}

        for instance in unit_instances:
            unit = instance["unit_normalized"]
            quantity = self._get_physical_quantity(unit)

            if quantity not in quantity_groups:
                quantity_groups[quantity] = []
            quantity_groups[quantity].append(instance)

        return quantity_groups

    def _get_physical_quantity(self, unit: str) -> str:
        """Get physical quantity for unit.

        Args:
            unit: Unit string

        Returns:
            Physical quantity name
        """
        # Length units
        length_units = ["m", "mm", "cm", "km", "in", "inch", "ft", "feet", "yard", "mile"]
        if any(unit.startswith(prefix) or unit == base for prefix in ["k", "M", "G", "m", "μ", "n"] for base in length_units):
            return "length"

        # Mass units
        mass_units = ["kg", "g", "lb", "pound", "oz", "ounce", "ton"]
        if any(unit.startswith(prefix) or unit == base for prefix in ["k", "M", "G", "m", "μ", "n"] for base in mass_units):
            return "mass"

        # Force units
        force_units = ["N", "lbf", "pound-force", "kip"]
        if any(unit.startswith(prefix) or unit == base for prefix in ["k", "M", "G", "m", "μ", "n"] for base in force_units):
            return "force"

        # Pressure units
        pressure_units = ["Pa", "psi", "atm", "bar", "torr", "mmHg"]
        if any(unit.startswith(prefix) or unit == base for prefix in ["k", "M", "G", "m", "μ", "n"] for base in pressure_units):
            return "pressure"

        # Energy units
        energy_units = ["J", "BTU", "cal", "Wh"]
        if any(unit.startswith(prefix) or unit == base for prefix in ["k", "M", "G", "m", "μ", "n"] for base in energy_units):
            return "energy"

        # Power units
        power_units = ["W", "hp", "horsepower"]
        if any(unit.startswith(prefix) or unit == base for prefix in ["k", "M", "G", "m", "μ", "n"] for base in power_units):
            return "power"

        # Temperature units
        if unit in ["°C", "°F", "K"]:
            return "temperature"

        # Default to "unknown"
        return "unknown"

    def _check_conversion_errors(
        self,
        unit_analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Check for unit conversion errors.

        Args:
            unit_analysis: Unit analysis results

        Returns:
            List of conversion errors
        """
        conversion_errors = []

        for instance in unit_analysis["unit_instances"]:
            unit = instance["unit_normalized"]

            if unit in self.unit_conversions:
                # Check if conversion seems reasonable
                value = instance["value"]
                conversion_factor = self.unit_conversions[unit][1]
                si_value = value * conversion_factor

                # Check for unreasonable conversions
                if self._is_unreasonable_conversion(value, si_value, unit):
                    conversion_errors.append({
                        "instance": instance,
                        "original_value": value,
                        "si_value": si_value,
                        "conversion_factor": conversion_factor,
                        "issue": "Unreasonable conversion result",
                    })

        return conversion_errors

    def _is_unreasonable_conversion(
        self,
        original_value: float,
        si_value: float,
        unit: str,
    ) -> bool:
        """Check if conversion result is unreasonable.

        Args:
            original_value: Original value
            si_value: Converted SI value
            unit: Original unit

        Returns:
            True if conversion seems unreasonable
        """
        # Check for extreme values
        if si_value > 1e12 or si_value < 1e-12:
            return True

        # Check for unit-specific reasonableness
        if unit in ["mm", "cm"] and si_value > 1000:  # Very large lengths
            return True

        if unit in ["kg", "g"] and si_value > 1000:  # Very large masses
            return True

        if unit in ["Pa", "psi"] and si_value > 1e9:  # Very high pressures
            return True

        return False

    def _find_missing_units(self, text: str) -> list[dict[str, Any]]:
        """Find numerical values without units.

        Args:
            text: Text to analyze

        Returns:
            List of missing unit instances
        """
        missing_units = []

        # Pattern for numbers that should have units
        number_pattern = r'\b(\d+(?:\.\d+)?)\s*([a-zA-Z°%]+(?:\s*[a-zA-Z°%]+)*)?\b'

        matches = re.finditer(number_pattern, text)

        for match in matches:
            value = float(match.group(1))
            unit = match.group(2) if match.group(2) else ""

            # Check if this number should have a unit
            if self._should_have_unit(value, unit, match.start(), text):
                missing_units.append({
                    "value": value,
                    "position": match.start(),
                    "text": match.group(0),
                    "context": text[max(0, match.start() - 50):match.end() + 50],
                })

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
        context = text[max(0, position - 100):position + 100].lower()

        # If context suggests units are expected
        unit_indicators = [
            "length", "width", "height", "diameter", "radius",
            "mass", "weight", "force", "pressure", "stress",
            "temperature", "energy", "power", "voltage", "current",
            "speed", "velocity", "acceleration", "frequency",
        ]

        if any(indicator in context for indicator in unit_indicators):
            return True

        return False

    def _calculate_score(
        self,
        unit_analysis: dict[str, Any],
        violation_count: int,
    ) -> float:
        """Calculate policy compliance score.

        Args:
            unit_analysis: Unit analysis results
            violation_count: Number of violations

        Returns:
            Score between 0.0 and 1.0
        """
        # Base score from unit compliance
        total_units = unit_analysis["total_units"]
        if total_units == 0:
            return 1.0  # No units to check

        # Penalty for violations
        violation_penalty = min(violation_count * 0.2, 0.8)

        # Bonus for good unit diversity (not too many different units)
        unit_diversity = unit_analysis["unique_unit_types"]
        diversity_bonus = max(0.0, 1.0 - (unit_diversity / 10))

        # Base score
        base_score = 1.0 - violation_penalty + diversity_bonus

        return max(0.0, min(1.0, base_score))











