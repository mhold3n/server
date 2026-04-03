"""Domain classification for chemistry, mechanical, and materials engineering."""

import re

import structlog

logger = structlog.get_logger()


class DomainClassifier:
    """Classifies text into engineering domains: chemistry, mechanical, materials."""

    def __init__(self):
        """Initialize domain classifier with keyword patterns."""
        self.domain_patterns = {
            "chemistry": {
                "keywords": [
                    # Chemical compounds and elements
                    "molecule",
                    "compound",
                    "element",
                    "atom",
                    "ion",
                    "bond",
                    "reaction",
                    "catalyst",
                    "synthesis",
                    "oxidation",
                    "reduction",
                    "acid",
                    "base",
                    "pH",
                    "solvent",
                    "solution",
                    "concentration",
                    "molarity",
                    "molality",
                    "stoichiometry",
                    "equilibrium",
                    "thermodynamics",
                    "kinetics",
                    "activation energy",
                    # Chemical processes
                    "polymerization",
                    "crystallization",
                    "precipitation",
                    "distillation",
                    "extraction",
                    "chromatography",
                    # Chemical properties
                    "viscosity",
                    "density",
                    "boiling point",
                    "melting point",
                    "solubility",
                    "reactivity",
                    "stability",
                    "purity",
                ],
                "formulas": [
                    r"\b[A-Z][a-z]?\d*\b",  # Chemical formulas like H2O, NaCl
                    r"\b\d+[A-Z][a-z]?\d*\b",  # Formulas with numbers like 2H2O
                    r"\b[A-Z][a-z]?\d*[A-Z][a-z]?\d*\b",  # Complex formulas
                ],
                "units": [
                    "mol",
                    "molar",
                    "M",
                    "ppm",
                    "ppb",
                    "pH",
                    "pKa",
                    "pKb",
                    "kJ/mol",
                    "kcal/mol",
                    "atm",
                    "bar",
                    "torr",
                    "mmHg",
                ],
            },
            "mechanical": {
                "keywords": [
                    # Mechanical systems and components
                    "gear",
                    "bearing",
                    "shaft",
                    "motor",
                    "engine",
                    "pump",
                    "valve",
                    "spring",
                    "damper",
                    "actuator",
                    "transmission",
                    "clutch",
                    "brake",
                    "coupling",
                    "joint",
                    "linkage",
                    # Mechanical properties and analysis
                    "stress",
                    "strain",
                    "tension",
                    "compression",
                    "shear",
                    "torque",
                    "moment",
                    "force",
                    "pressure",
                    "load",
                    "deflection",
                    "deformation",
                    "fatigue",
                    "creep",
                    "yield strength",
                    "tensile strength",
                    "elastic modulus",
                    # Mechanical processes
                    "machining",
                    "welding",
                    "casting",
                    "forging",
                    "rolling",
                    "extrusion",
                    "milling",
                    "turning",
                    "drilling",
                    "grinding",
                    # Mechanical design
                    "tolerance",
                    "clearance",
                    "interference",
                    "fit",
                    "dimension",
                    "specification",
                    "drawing",
                    "blueprint",
                ],
                "formulas": [
                    r"\bF\s*=\s*ma\b",  # Force = mass * acceleration
                    r"\bσ\s*=\s*F/A\b",  # Stress = Force / Area
                    r"\bτ\s*=\s*T*r/J\b",  # Shear stress
                    r"\bE\s*=\s*σ/ε\b",  # Young's modulus
                ],
                "units": [
                    "N",
                    "kN",
                    "MPa",
                    "GPa",
                    "Pa",
                    "psi",
                    "ksi",
                    "Nm",
                    "lb-ft",
                    "rpm",
                    "Hz",
                    "rad/s",
                    "m/s²",
                    "mm",
                    "μm",
                    "in",
                    "ft",
                    "m",
                    "kg",
                    "lb",
                ],
            },
            "materials": {
                "keywords": [
                    # Material types
                    "steel",
                    "aluminum",
                    "titanium",
                    "copper",
                    "brass",
                    "bronze",
                    "plastic",
                    "polymer",
                    "ceramic",
                    "composite",
                    "alloy",
                    "carbon fiber",
                    "glass fiber",
                    "epoxy",
                    "resin",
                    # Material properties
                    "hardness",
                    "toughness",
                    "ductility",
                    "brittleness",
                    "corrosion",
                    "oxidation",
                    "wear",
                    "friction",
                    "lubrication",
                    "thermal conductivity",
                    "electrical conductivity",
                    "magnetic properties",
                    "optical properties",
                    # Material processing
                    "heat treatment",
                    "annealing",
                    "quenching",
                    "tempering",
                    "case hardening",
                    "surface treatment",
                    "coating",
                    "galvanizing",
                    "anodizing",
                    "plating",
                    # Material testing
                    "tensile test",
                    "compression test",
                    "bend test",
                    "impact test",
                    "fatigue test",
                    "creep test",
                    "microstructure",
                    "grain size",
                    "phase",
                    "crystal",
                ],
                "formulas": [
                    r"\b[A-Z][a-z]?\d*[A-Z][a-z]?\d*\b",  # Alloy compositions
                    r"\b\d+%[A-Z][a-z]?\b",  # Percentage compositions
                ],
                "units": [
                    "HRC",
                    "HRB",
                    "HV",
                    "HB",
                    "MPa",
                    "GPa",
                    "J/m²",
                    "W/m·K",
                    "Ω·m",
                    "S/m",
                    "°C",
                    "°F",
                    "K",
                ],
            },
            "software_engineering": {
                "keywords": [
                    "algorithm",
                    "backend",
                    "frontend",
                    "database",
                    "api",
                    "framework",
                    "server",
                    "client",
                    "kubernetes",
                    "docker",
                    "python",
                    "rust",
                    "javascript",
                    "typescript",
                    "html",
                    "css",
                    "git",
                    "repository",
                    "commit",
                    "branch",
                    "merge",
                    "pull request",
                    "debugging",
                    "exception",
                    "compiler",
                    "interpreter",
                    "runtime",
                    "dependency",
                    "module",
                    "package",
                    "deployment",
                    "continuous integration",
                    "pipeline",
                    "function",
                    "class",
                    "object",
                    "interface",
                    "Birtha",
                    "Claw",
                    "mbmh",
                ],
                "formulas": [
                    r"def \w+\(",  # Python function definition
                    r"fn \w+\(",  # Rust function definition
                    r"class \w+",  # Class definition
                    r"=>",  # Arrow function / match arm
                    r"import \w+",  # Python/TS import
                    r"from \w+ import",
                ],
                "units": [
                    "KB",
                    "MB",
                    "GB",
                    "TB",
                    "PB",
                    "Kbps",
                    "Mbps",
                    "Gbps",
                    "ms",
                    "ns",
                ],
            },
            "systems_administration": {
                "keywords": [
                    "linux",
                    "ubuntu",
                    "debian",
                    "macos",
                    "bash",
                    "shell",
                    "terminal",
                    "ssh",
                    "firewall",
                    "port",
                    "daemon",
                    "service",
                    "proxy",
                    "nginx",
                    "apache",
                    "dns",
                    "ip address",
                    "subnet",
                    "router",
                    "switch",
                    "permissions",
                    "chmod",
                    "chown",
                    "sudo",
                    "root",
                    "filesystem",
                    "mount",
                    "cron",
                    "log",
                    "metrics",
                    "monitoring",
                    "prometheus",
                    "grafana",
                ],
                "formulas": [
                    r"sudo \w+",
                    r"chmod [0-7]{3,4}",
                    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",  # IPv4 address
                ],
                "units": ["KB", "MB", "GB", "TB", "IOPS", "RPM"],
            },
            "ai_ml": {
                "keywords": [
                    "model",
                    "training",
                    "inference",
                    "dataset",
                    "neural network",
                    "deep learning",
                    "machine learning",
                    "transformer",
                    "llm",
                    "rag",
                    "embedding",
                    "vector db",
                    "prompt",
                    "fine-tuning",
                    "lora",
                    "peft",
                    "quantization",
                    "gguf",
                    "safetensors",
                    "huggingface",
                    "pytorch",
                    "tensorflow",
                    "gradient",
                    "loss",
                    "optimizer",
                    "learning rate",
                    "epoch",
                    "batch size",
                    "activation function",
                ],
                "formulas": [
                    r"nn\.Module",
                    r"import torch",
                ],
                "units": ["VRAM", "FLOPS", "TFLOPS", "parameters", "tokens"],
            },
        }

    def classify(
        self,
        text: str,
        domains: list[str] | None = None,
        threshold: float = 0.1,
    ) -> dict[str, float]:
        """Classify text into engineering domains.

        Args:
            text: Text to classify
            domains: Optional list of domains to consider (default: all)
            threshold: Minimum score threshold for inclusion

        Returns:
            Dictionary mapping domain names to confidence scores
        """
        if domains is None:
            domains = list(self.domain_patterns.keys())

        text_lower = text.lower()
        scores = {}

        for domain in domains:
            if domain not in self.domain_patterns:
                continue

            domain_score = self._calculate_domain_score(
                text_lower, self.domain_patterns[domain]
            )

            if domain_score >= threshold:
                scores[domain] = domain_score

        # Normalize scores to sum to 1.0
        total_score = sum(scores.values())
        if total_score > 0:
            scores = {k: v / total_score for k, v in scores.items()}

        logger.debug(
            "Domain classification completed",
            text_length=len(text),
            scores=scores,
        )

        return scores

    def _calculate_domain_score(
        self,
        text: str,
        patterns: dict[str, list[str]],
    ) -> float:
        """Calculate domain score based on keyword and pattern matches.

        Args:
            text: Lowercase text to analyze
            patterns: Domain-specific patterns (keywords, formulas, units)

        Returns:
            Domain confidence score (0.0 to 1.0)
        """
        score = 0.0
        total_matches = 0

        # Keyword matching (weight: 1.0)
        keywords = patterns.get("keywords", [])
        keyword_matches = sum(1 for keyword in keywords if keyword in text)
        score += keyword_matches * 1.0
        total_matches += keyword_matches

        # Formula pattern matching (weight: 2.0)
        formulas = patterns.get("formulas", [])
        formula_matches = 0
        for pattern in formulas:
            if re.search(pattern, text, re.IGNORECASE):
                formula_matches += 1
        score += formula_matches * 2.0
        total_matches += formula_matches

        # Unit matching (weight: 1.5)
        units = patterns.get("units", [])
        unit_matches = sum(1 for unit in units if unit in text)
        score += unit_matches * 1.5
        total_matches += unit_matches

        # Normalize by text length and total possible matches
        if total_matches == 0:
            return 0.0

        # Normalize by text length (longer texts can have more matches)
        text_length_factor = min(
            len(text) / 100, 1.0
        )  # Cap at 1.0 for texts > 100 chars

        # Normalize by total possible matches
        max_possible_matches = len(keywords) + len(formulas) + len(units)
        match_ratio = (
            total_matches / max_possible_matches if max_possible_matches > 0 else 0
        )

        # Combine factors
        normalized_score = (score / total_matches) * match_ratio * text_length_factor

        return min(normalized_score, 1.0)  # Cap at 1.0

    def get_primary_domain(
        self,
        text: str,
        domains: list[str] | None = None,
        threshold: float = 0.3,
    ) -> str | None:
        """Get the primary domain for the text.

        Args:
            text: Text to classify
            domains: Optional list of domains to consider
            threshold: Minimum score threshold

        Returns:
            Primary domain name or None if below threshold
        """
        scores = self.classify(text, domains, threshold)

        if not scores:
            return None

        return max(scores.items(), key=lambda x: x[1])[0]

    def get_domain_weights(
        self,
        text: str,
        domains: list[str] | None = None,
    ) -> dict[str, float]:
        """Get domain weights for content weighting.

        Args:
            text: Text to classify
            domains: Optional list of domains to consider

        Returns:
            Dictionary mapping domain names to weights (0.0 to 1.0)
        """
        scores = self.classify(text, domains, threshold=0.0)

        # Ensure all domains have a weight (minimum 0.1)
        if domains is None:
            domains = list(self.domain_patterns.keys())

        weights = {}
        for domain in domains:
            weights[domain] = max(scores.get(domain, 0.0), 0.1)

        # Normalize to sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        return weights
