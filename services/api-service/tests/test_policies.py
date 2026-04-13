"""Unit tests for policy modules."""

import pytest

from src.policies.citations import CitationPolicy
from src.policies.evidence import EvidencePolicy
from src.policies.hedging import HedgingPolicy
from src.policies.middleware import PolicyEnforcer
from src.policies.units import SIUnitPolicy


class TestHedgingPolicy:
    """Test hedging policy validation."""

    @pytest.mark.asyncio
    async def test_hedging_detection(self):
        """Test hedging language detection."""
        policy = HedgingPolicy(ban_hedging=False, max_hedging_ratio=0.1)

        # Text with hedging
        text_with_hedging = "This might be correct, but it seems like it could work."
        result = await policy.validate(text_with_hedging)

        assert not result.passed
        assert result.score < 1.0
        assert len(result.violations) > 0
        assert "hedging" in result.violations[0].lower()

    @pytest.mark.asyncio
    async def test_no_hedging(self):
        """Test text without hedging passes."""
        policy = HedgingPolicy(ban_hedging=False, max_hedging_ratio=0.1)

        # Text without hedging (avoid vague "This is …" weak-language hits)
        text_without_hedging = "The coefficient matches the specification exactly."
        result = await policy.validate(text_without_hedging)

        assert result.passed
        assert result.score > 0.8
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_ban_hedging(self):
        """Test complete hedging ban."""
        policy = HedgingPolicy(ban_hedging=True)

        text_with_hedging = "This might be correct."
        result = await policy.validate(text_with_hedging)

        assert not result.passed
        assert "hedging language detected" in result.violations[0].lower()

    @pytest.mark.asyncio
    async def test_hedging_ratio_limit(self):
        """Test hedging ratio limit."""
        policy = HedgingPolicy(max_hedging_ratio=0.05)  # Very strict

        text_with_excessive_hedging = (
            "This might be correct, perhaps it could work, maybe it will succeed."
        )
        result = await policy.validate(text_with_excessive_hedging)

        assert not result.passed
        assert "excessive hedging" in result.violations[0].lower()


class TestEvidencePolicy:
    """Test evidence policy validation."""

    @pytest.mark.asyncio
    async def test_insufficient_citations(self):
        """Test insufficient citations detection."""
        policy = EvidencePolicy(min_citations=3)

        text_with_few_citations = (
            "A statement with no bracket or author-year citations."
        )
        result = await policy.validate(text_with_few_citations, [])

        assert not result.passed
        assert "insufficient citations" in result.violations[0].lower()

    @pytest.mark.asyncio
    async def test_sufficient_citations(self):
        """Test sufficient citations pass."""
        policy = EvidencePolicy(min_citations=2)

        text_with_citations = "This is a fact [1]. Another fact [2]. Third fact [3]."
        result = await policy.validate(text_with_citations, [])

        assert result.passed
        assert result.score > 0.5

    @pytest.mark.asyncio
    async def test_source_diversity(self):
        """Test source diversity requirements."""
        policy = EvidencePolicy(min_source_diversity=0.5)

        # Mock retrieval docs with low diversity
        retrieval_docs = [
            {"metadata": {"source_type": "textbook"}},
            {"metadata": {"source_type": "textbook"}},
            {"metadata": {"source_type": "textbook"}},
        ]

        text = "Some text with citations [1] [2] [3]."
        result = await policy.validate(text, retrieval_docs)

        assert not result.passed
        assert "low source diversity" in result.violations[0].lower()

    @pytest.mark.asyncio
    async def test_unsupported_claims(self):
        """Test unsupported claims detection."""
        policy = EvidencePolicy()

        text_with_claims = "The temperature is 25°C and the pressure is 1 atm."
        result = await policy.validate(text_with_claims, [])

        # Should detect unsupported claims
        assert len(result.violations) > 0
        assert any("unsupported" in v.lower() for v in result.violations)


class TestCitationPolicy:
    """Test citation policy validation."""

    @pytest.mark.asyncio
    async def test_citation_format_validation(self):
        """Test citation format validation."""
        policy = CitationPolicy()

        text_with_bad_citations = "This is a fact (bad citation)."
        result = await policy.validate(text_with_bad_citations, [])

        # Should detect format issues
        assert len(result.violations) > 0

    @pytest.mark.asyncio
    async def test_good_citation_format(self):
        """Test good citation format passes."""
        policy = CitationPolicy()

        text_with_good_citations = "Claim one [1]. Claim two [2]. Claim three [3]."
        result = await policy.validate(text_with_good_citations, [])

        assert result.passed or len(result.violations) == 0


class TestSIUnitPolicy:
    """Test SI units policy validation."""

    @pytest.mark.asyncio
    async def test_si_units_enforcement(self):
        """Test SI units enforcement."""
        policy = SIUnitPolicy()

        text_with_imperial = "The length is 12 inches and weight is 5 pounds."
        result = await policy.validate(text_with_imperial)

        assert not result.passed
        assert any("unit" in v.lower() for v in result.violations)

    @pytest.mark.asyncio
    async def test_si_units_compliance(self):
        """Test SI units compliance."""
        policy = SIUnitPolicy()

        text_with_si = "The length is 30.48 cm and mass is 2.27 kg."
        result = await policy.validate(text_with_si)

        assert result.passed or result.score > 0.8

    @pytest.mark.asyncio
    async def test_unit_consistency(self):
        """Test unit consistency validation."""
        policy = SIUnitPolicy()

        text_mixed_units = "The temperature is 25°C and 298 K."
        result = await policy.validate(text_mixed_units)

        # Should detect unit inconsistency
        assert len(result.violations) > 0


class TestPolicyEnforcer:
    """Test policy enforcer integration."""

    @pytest.fixture
    def policy_enforcer(self):
        """Create policy enforcer instance."""
        return PolicyEnforcer()

    def test_policy_enforcer_initialization(self, policy_enforcer):
        """Test policy enforcer initialization."""
        assert policy_enforcer is not None
        assert policy_enforcer.registry is not None

    @pytest.mark.asyncio
    async def test_policy_enforcement(self, policy_enforcer):
        """Test policy enforcement with multiple policies."""
        output = "This might be correct [1]. The temperature is 25°C."

        verdict = await policy_enforcer.validate(output, [])

        assert verdict is not None
        assert hasattr(verdict, "overall_passed")
        assert hasattr(verdict, "overall_score")
        assert hasattr(verdict, "total_violations")
        assert hasattr(verdict, "policy_results")

    @pytest.mark.asyncio
    async def test_policy_enforcement_with_retrieval(self, policy_enforcer):
        """Test policy enforcement with retrieval documents."""
        output = "This is a fact [1]."
        retrieval_docs = [
            {"content": "Some content", "metadata": {"source_type": "paper"}},
            {"content": "More content", "metadata": {"source_type": "textbook"}},
        ]

        verdict = await policy_enforcer.validate(output, retrieval_docs)

        assert verdict is not None
        assert len(verdict.policy_results) > 0

    def test_get_enabled_policies(self, policy_enforcer):
        """Test getting enabled policies."""
        enabled = policy_enforcer.get_enabled_policies()

        assert isinstance(enabled, list)
        assert len(enabled) > 0
        assert "evidence" in enabled
        assert "hedging" in enabled

    def test_policy_summary(self, policy_enforcer):
        """Test policy summary."""
        summary = policy_enforcer.get_policy_summary()

        assert "total_policies" in summary
        assert "enabled_policies" in summary
        assert "policies" in summary
        assert summary["total_policies"] > 0

    def test_enable_disable_policy(self, policy_enforcer):
        """Test enabling and disabling policies."""
        # Test disabling a policy
        result = policy_enforcer.disable_policy("hedging")
        assert result is True

        # Test enabling a policy
        result = policy_enforcer.enable_policy("hedging")
        assert result is True


class TestPolicyIntegration:
    """Test policy integration scenarios."""

    @pytest.mark.asyncio
    async def test_academic_paper_validation(self):
        """Test validation of academic paper-style content."""
        enforcer = PolicyEnforcer()

        # Academic-style content with proper citations
        academic_text = """
        The results show that the temperature coefficient is 0.0043 K⁻¹ [1].
        Previous studies have confirmed this relationship [2, 3].
        The experimental data supports this conclusion [4].
        """

        retrieval_docs = [
            {"content": "Temperature studies", "metadata": {"source_type": "paper"}},
            {"content": "Experimental data", "metadata": {"source_type": "paper"}},
            {"content": "Previous research", "metadata": {"source_type": "paper"}},
        ]

        verdict = await enforcer.validate(academic_text, retrieval_docs)

        # Should pass most policies (threshold allows minor citation noise)
        assert verdict.overall_score >= 0.55
        assert verdict.total_violations < 12

    @pytest.mark.asyncio
    async def test_uncertain_content_validation(self):
        """Test validation of uncertain content."""
        enforcer = PolicyEnforcer()

        # Uncertain content with hedging
        uncertain_text = """
        This might be correct, but it seems like it could work.
        Perhaps the results are accurate, maybe the data is reliable.
        """

        verdict = await enforcer.validate(uncertain_text, [])

        # Should fail hedging policy
        assert not verdict.overall_passed
        assert verdict.total_violations > 0

    @pytest.mark.asyncio
    async def test_technical_content_validation(self):
        """Test validation of technical content with units."""
        enforcer = PolicyEnforcer()

        # Technical content with proper SI units
        technical_text = """
        The force is 100 N and the distance is 2.5 m.
        The pressure is 101.3 kPa and the temperature is 298 K.
        """

        verdict = await enforcer.validate(technical_text, [])

        # Should meet minimum aggregate score
        assert verdict.overall_score >= 0.5
