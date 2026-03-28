"""Evaluation runner for testing AI system performance."""

import asyncio
import time
from typing import Any

import httpx
import structlog
from pydantic import BaseModel

from .golden_sets import load_golden_sets
from .validators import CitationValidator, HedgingValidator, SIUnitValidator

logger = structlog.get_logger()


class EvalResult(BaseModel):
    """Evaluation result model."""

    test_id: str
    prompt: str
    response: str
    expected_citations_min: int
    expected_sources: list[str]
    si_required: bool
    hedging_allowed: bool
    reference_uris: list[str]

    # Validation results
    citation_score: float
    si_unit_score: float
    hedging_score: float
    overall_score: float

    # Violations
    citation_violations: list[str]
    si_unit_violations: list[str]
    hedging_violations: list[str]

    # Metadata
    response_time: float
    timestamp: str
    run_id: str | None = None


class EvalRunner:
    """Runs evaluation tests against the AI system."""

    def __init__(
        self,
        api_base_url: str = "http://localhost:8080",
        wrkhrs_gateway_url: str = "http://localhost:8080",
    ):
        """Initialize evaluation runner.

        Args:
            api_base_url: Birtha API base URL
            wrkhrs_gateway_url: WrkHrs gateway URL
        """
        self.api_base_url = api_base_url
        self.wrkhrs_gateway_url = wrkhrs_gateway_url

        # Initialize validators
        self.citation_validator = CitationValidator()
        self.si_unit_validator = SIUnitValidator()
        self.hedging_validator = HedgingValidator()

        # HTTP client
        self.client = httpx.AsyncClient(timeout=60.0)

    async def run_evaluation(
        self,
        golden_set_name: str | None = None,
        test_ids: list[str] | None = None,
    ) -> list[EvalResult]:
        """Run evaluation tests.

        Args:
            golden_set_name: Name of golden set to use
            test_ids: Specific test IDs to run

        Returns:
            List of evaluation results
        """
        try:
            # Load golden sets
            golden_sets = load_golden_sets()

            if golden_set_name:
                if golden_set_name not in golden_sets:
                    raise ValueError(f"Golden set '{golden_set_name}' not found")
                test_sets = {golden_set_name: golden_sets[golden_set_name]}
            else:
                test_sets = golden_sets

            # Run tests
            results = []
            for set_name, tests in test_sets.items():
                logger.info(f"Running evaluation for golden set: {set_name}")

                for test in tests:
                    if test_ids and test["id"] not in test_ids:
                        continue

                    result = await self._run_single_test(test)
                    results.append(result)

            logger.info(f"Evaluation completed: {len(results)} tests run")
            return results

        except Exception as e:
            logger.error("Evaluation failed", error=str(e))
            raise

    async def _run_single_test(self, test: dict[str, Any]) -> EvalResult:
        """Run a single test.

        Args:
            test: Test configuration

        Returns:
            Evaluation result
        """
        test_id = test["id"]
        prompt = test["prompt"]

        logger.info(f"Running test: {test_id}")

        start_time = time.time()

        try:
            # Send request to AI system
            response = await self._send_ai_request(prompt)
            response_time = time.time() - start_time

            # Validate response
            validation_results = await self._validate_response(response, test)

            # Create result
            result = EvalResult(
                test_id=test_id,
                prompt=prompt,
                response=response,
                expected_citations_min=test.get("expected_citations_min", 0),
                expected_sources=test.get("expected_sources", []),
                si_required=test.get("SI_required", False),
                hedging_allowed=test.get("hedging_allowed", True),
                reference_uris=test.get("reference_uris", []),
                citation_score=validation_results["citation_score"],
                si_unit_score=validation_results["si_unit_score"],
                hedging_score=validation_results["hedging_score"],
                overall_score=validation_results["overall_score"],
                citation_violations=validation_results["citation_violations"],
                si_unit_violations=validation_results["si_unit_violations"],
                hedging_violations=validation_results["hedging_violations"],
                response_time=response_time,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

            logger.info(
                f"Test completed: {test_id}",
                overall_score=result.overall_score,
                response_time=response_time,
            )

            return result

        except Exception as e:
            logger.error(f"Test failed: {test_id}", error=str(e))

            # Return failed result
            return EvalResult(
                test_id=test_id,
                prompt=prompt,
                response=f"ERROR: {str(e)}",
                expected_citations_min=test.get("expected_citations_min", 0),
                expected_sources=test.get("expected_sources", []),
                si_required=test.get("SI_required", False),
                hedging_allowed=test.get("hedging_allowed", True),
                reference_uris=test.get("reference_uris", []),
                citation_score=0.0,
                si_unit_score=0.0,
                hedging_score=0.0,
                overall_score=0.0,
                citation_violations=[f"Test execution failed: {str(e)}"],
                si_unit_violations=[],
                hedging_violations=[],
                response_time=time.time() - start_time,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

    async def _send_ai_request(self, prompt: str) -> str:
        """Send request to AI system.

        Args:
            prompt: User prompt

        Returns:
            AI response
        """
        try:
            # Try Birtha API first
            try:
                response = await self.client.post(
                    f"{self.api_base_url}/v1/ai/chat",
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 1000,
                    },
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]

            except Exception as e:
                logger.warning("Birtha API failed, trying WrkHrs gateway", error=str(e))

                # Fallback to WrkHrs gateway
                response = await self.client.post(
                    f"{self.wrkhrs_gateway_url}/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 1000,
                    },
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error("AI request failed", error=str(e))
            raise

    async def _validate_response(
        self,
        response: str,
        test: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate AI response against test requirements.

        Args:
            response: AI response
            test: Test configuration

        Returns:
            Validation results
        """
        try:
            # Citation validation
            citation_result = await self.citation_validator.validate(
                response=response,
                min_citations=test.get("expected_citations_min", 0),
                expected_sources=test.get("expected_sources", []),
            )

            # SI unit validation
            si_unit_result = await self.si_unit_validator.validate(
                response=response,
                si_required=test.get("SI_required", False),
            )

            # Hedging validation
            hedging_result = await self.hedging_validator.validate(
                response=response,
                hedging_allowed=test.get("hedging_allowed", True),
            )

            # Calculate overall score
            scores = [
                citation_result["score"],
                si_unit_result["score"],
                hedging_result["score"],
            ]
            overall_score = sum(scores) / len(scores)

            return {
                "citation_score": citation_result["score"],
                "si_unit_score": si_unit_result["score"],
                "hedging_score": hedging_result["score"],
                "overall_score": overall_score,
                "citation_violations": citation_result["violations"],
                "si_unit_violations": si_unit_result["violations"],
                "hedging_violations": hedging_result["violations"],
            }

        except Exception as e:
            logger.error("Response validation failed", error=str(e))
            return {
                "citation_score": 0.0,
                "si_unit_score": 0.0,
                "hedging_score": 0.0,
                "overall_score": 0.0,
                "citation_violations": [f"Validation failed: {str(e)}"],
                "si_unit_violations": [],
                "hedging_violations": [],
            }

    async def generate_report(
        self,
        results: list[EvalResult],
        output_file: str | None = None,
    ) -> str:
        """Generate evaluation report.

        Args:
            results: Evaluation results
            output_file: Output file path

        Returns:
            Report content
        """
        try:
            # Calculate statistics
            total_tests = len(results)
            passed_tests = sum(1 for r in results if r.overall_score >= 0.7)
            failed_tests = total_tests - passed_tests

            avg_score = sum(r.overall_score for r in results) / total_tests if total_tests > 0 else 0
            avg_response_time = sum(r.response_time for r in results) / total_tests if total_tests > 0 else 0

            # Score distribution
            score_ranges = {
                "0.0-0.2": 0,
                "0.2-0.4": 0,
                "0.4-0.6": 0,
                "0.6-0.8": 0,
                "0.8-1.0": 0,
            }

            for result in results:
                score = result.overall_score
                if score < 0.2:
                    score_ranges["0.0-0.2"] += 1
                elif score < 0.4:
                    score_ranges["0.2-0.4"] += 1
                elif score < 0.6:
                    score_ranges["0.4-0.6"] += 1
                elif score < 0.8:
                    score_ranges["0.6-0.8"] += 1
                else:
                    score_ranges["0.8-1.0"] += 1

            # Common violations
            all_violations = []
            for result in results:
                all_violations.extend(result.citation_violations)
                all_violations.extend(result.si_unit_violations)
                all_violations.extend(result.hedging_violations)

            violation_counts = {}
            for violation in all_violations:
                violation_counts[violation] = violation_counts.get(violation, 0) + 1

            common_violations = sorted(
                violation_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]

            # Generate report
            report = f"""
# AI System Evaluation Report

## Summary
- **Total Tests**: {total_tests}
- **Passed Tests**: {passed_tests} ({passed_tests/total_tests*100:.1f}%)
- **Failed Tests**: {failed_tests} ({failed_tests/total_tests*100:.1f}%)
- **Average Score**: {avg_score:.3f}
- **Average Response Time**: {avg_response_time:.2f}s

## Score Distribution
"""

            for range_name, count in score_ranges.items():
                percentage = count / total_tests * 100 if total_tests > 0 else 0
                report += f"- **{range_name}**: {count} tests ({percentage:.1f}%)\n"

            report += """
## Common Violations
"""

            for violation, count in common_violations:
                percentage = count / total_tests * 100 if total_tests > 0 else 0
                report += f"- **{violation}**: {count} occurrences ({percentage:.1f}%)\n"

            report += """
## Test Results

| Test ID | Score | Response Time | Status | Violations |
|---------|-------|---------------|--------|------------|
"""

            for result in results:
                status = "PASS" if result.overall_score >= 0.7 else "FAIL"
                violation_count = len(result.citation_violations) + len(result.si_unit_violations) + len(result.hedging_violations)

                report += f"| {result.test_id} | {result.overall_score:.3f} | {result.response_time:.2f}s | {status} | {violation_count} |\n"

            report += """
## Detailed Results

"""

            for result in results:
                report += f"""
### {result.test_id}
- **Prompt**: {result.prompt[:100]}...
- **Score**: {result.overall_score:.3f}
- **Response Time**: {result.response_time:.2f}s
- **Citation Score**: {result.citation_score:.3f}
- **SI Unit Score**: {result.si_unit_score:.3f}
- **Hedging Score**: {result.hedging_score:.3f}

**Violations:**
"""

                if result.citation_violations:
                    report += "- Citation: " + ", ".join(result.citation_violations) + "\n"
                if result.si_unit_violations:
                    report += "- SI Units: " + ", ".join(result.si_unit_violations) + "\n"
                if result.hedging_violations:
                    report += "- Hedging: " + ", ".join(result.hedging_violations) + "\n"

                report += f"\n**Response**: {result.response[:200]}...\n\n"

            # Save report
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(report)
                logger.info(f"Report saved to: {output_file}")

            return report

        except Exception as e:
            logger.error("Report generation failed", error=str(e))
            raise

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


async def main():
    """Main evaluation function."""
    import argparse

    parser = argparse.ArgumentParser(description="Run AI system evaluation")
    parser.add_argument("--golden-set", help="Golden set name to use")
    parser.add_argument("--test-ids", nargs="+", help="Specific test IDs to run")
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument("--api-url", default="http://localhost:8080", help="API base URL")

    args = parser.parse_args()

    # Run evaluation
    runner = EvalRunner(api_base_url=args.api_url)

    try:
        results = await runner.run_evaluation(
            golden_set_name=args.golden_set,
            test_ids=args.test_ids,
        )

        # Generate report
        report = await runner.generate_report(results, args.output)

        if not args.output:
            print(report)

    finally:
        await runner.close()


if __name__ == "__main__":
    asyncio.run(main())











