"""MLflow integration for run provenance tracking."""

import json
import os
import socket
import unittest.mock
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import mlflow
import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class RunSpec(BaseModel):
    """Run specification for MLflow logging."""

    prompt: str
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    domain_weights: dict[str, float] | None = None
    policies: list[str] | None = None
    user_id: str | None = None
    session_id: str | None = None


class RetrievalDoc(BaseModel):
    """Retrieved document for provenance tracking."""

    content: str
    metadata: dict[str, Any]
    score: float
    source: str
    chunk_id: str | None = None


class ToolCall(BaseModel):
    """Tool call for provenance tracking."""

    tool_name: str
    tool_args: dict[str, Any]
    result: Any
    duration: float
    success: bool


class EnvironmentSnapshot(BaseModel):
    """Environment snapshot for provenance tracking."""

    timestamp: datetime
    service_version: str
    model_version: str
    config_hash: str
    dependencies: dict[str, str]


class MLflowLogger:
    """MLflow logger for run provenance tracking."""

    def __init__(
        self,
        tracking_uri: str = "http://mlflow:5000",
        experiment_name: str = "birtha-ai-runs",
    ):
        """Initialize MLflow logger.

        Args:
            tracking_uri: MLflow tracking server URI
            experiment_name: MLflow experiment name
        """
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self._setup_mlflow()

    def _tracking_server_reachable(self, timeout_s: float = 1.0) -> bool:
        """
        Fail fast if the tracking server isn't reachable.

        MLflow's internal HTTP client does not consistently apply short timeouts
        during experiment lookup/creation, which can stall local CI/tests.
        """

        try:
            # Unit tests patch `mlflow` with a mock; don't attempt any real
            # networking in that case.
            if isinstance(mlflow, unittest.mock.Mock):
                return True

            parsed = urlparse(self.tracking_uri)
            if parsed.scheme not in ("http", "https"):
                return True

            host = parsed.hostname
            if not host:
                return True

            port = parsed.port
            if port is None:
                port = 443 if parsed.scheme == "https" else 80

            with socket.create_connection((host, port), timeout=timeout_s):
                return True
        except OSError:
            return False

    def _setup_mlflow(self) -> None:
        """Setup MLflow client and experiment."""
        try:
            mlflow.set_tracking_uri(self.tracking_uri)

            if not self._tracking_server_reachable():
                self.experiment_id = None
                return

            # Get or create experiment
            try:
                experiment = mlflow.get_experiment_by_name(self.experiment_name)
                if experiment is None:
                    experiment_id = mlflow.create_experiment(self.experiment_name)
                    logger.info(
                        "Created MLflow experiment", experiment_id=experiment_id
                    )
                else:
                    experiment_id = experiment.experiment_id
                    logger.info(
                        "Using existing MLflow experiment", experiment_id=experiment_id
                    )

                self.experiment_id = experiment_id

            except Exception as e:
                logger.warning("Failed to setup MLflow experiment", error=str(e))
                self.experiment_id = None

        except Exception as e:
            logger.error("Failed to setup MLflow", error=str(e))
            self.experiment_id = None

    async def log_run(
        self,
        run_spec: RunSpec,
        retrieval_docs: list[RetrievalDoc],
        raw_output: str,
        postprocessed_output: str,
        tool_calls: list[ToolCall],
        environment: EnvironmentSnapshot,
        feedback: dict[str, Any] | None = None,
    ) -> str:
        """Log complete run to MLflow with provenance.

        Args:
            run_spec: Run specification
            retrieval_docs: Retrieved documents
            raw_output: Raw LLM output
            postprocessed_output: Post-processed output
            tool_calls: Tool calls made during execution
            environment: Environment snapshot
            feedback: Optional user feedback

        Returns:
            MLflow run ID
        """
        if not self.experiment_id:
            logger.warning("MLflow not available, skipping run logging")
            return "no-mlflow"

        try:
            with mlflow.start_run(experiment_id=self.experiment_id) as run:
                run_id = run.info.run_id

                # Log parameters
                self._log_parameters(run_spec, environment)

                # Log metrics
                self._log_metrics(run_spec, retrieval_docs, tool_calls, feedback)

                # Log artifacts
                await self._log_artifacts(
                    run_id,
                    run_spec,
                    retrieval_docs,
                    raw_output,
                    postprocessed_output,
                    tool_calls,
                    environment,
                )

                # Log tags
                self._log_tags(run_spec, environment, feedback)

                logger.info(
                    "Logged run to MLflow",
                    run_id=run_id,
                    experiment=self.experiment_name,
                )

                return run_id

        except Exception as e:
            logger.error("Failed to log run to MLflow", error=str(e))
            return "error"

    def _log_parameters(
        self,
        run_spec: RunSpec,
        environment: EnvironmentSnapshot,
    ) -> None:
        """Log run parameters to MLflow."""
        params = {
            "model": run_spec.model,
            "temperature": run_spec.temperature,
            "max_tokens": run_spec.max_tokens or 0,
            "service_version": environment.service_version,
            "model_version": environment.model_version,
            "config_hash": environment.config_hash,
        }

        if run_spec.domain_weights:
            for domain, weight in run_spec.domain_weights.items():
                params[f"domain_weight_{domain}"] = weight

        if run_spec.policies:
            params["policies"] = ",".join(run_spec.policies)

        if run_spec.user_id:
            params["user_id"] = run_spec.user_id

        if run_spec.session_id:
            params["session_id"] = run_spec.session_id

        mlflow.log_params(params)

    def _log_metrics(
        self,
        run_spec: RunSpec,
        retrieval_docs: list[RetrievalDoc],
        tool_calls: list[ToolCall],
        feedback: dict[str, Any] | None,
    ) -> None:
        """Log run metrics to MLflow."""
        metrics = {
            "prompt_length": len(run_spec.prompt),
            "retrieval_count": len(retrieval_docs),
            "tool_calls_count": len(tool_calls),
            "successful_tool_calls": sum(1 for tc in tool_calls if tc.success),
        }

        if retrieval_docs:
            metrics["avg_retrieval_score"] = sum(
                doc.score for doc in retrieval_docs
            ) / len(retrieval_docs)
            metrics["max_retrieval_score"] = max(doc.score for doc in retrieval_docs)
            metrics["min_retrieval_score"] = min(doc.score for doc in retrieval_docs)

        if tool_calls:
            metrics["total_tool_duration"] = sum(tc.duration for tc in tool_calls)
            metrics["avg_tool_duration"] = sum(tc.duration for tc in tool_calls) / len(
                tool_calls
            )

        if feedback:
            metrics["user_rating"] = feedback.get("rating", 0)
            metrics["feedback_reasons_count"] = len(feedback.get("reasons", []))

        mlflow.log_metrics(metrics)

    async def _log_artifacts(
        self,
        run_id: str,
        run_spec: RunSpec,
        retrieval_docs: list[RetrievalDoc],
        raw_output: str,
        postprocessed_output: str,
        tool_calls: list[ToolCall],
        environment: EnvironmentSnapshot,
    ) -> None:
        """Log artifacts to MLflow."""
        artifacts_dir = f"/tmp/mlflow_artifacts_{run_id}"
        os.makedirs(artifacts_dir, exist_ok=True)

        try:
            # Run specification
            with open(f"{artifacts_dir}/run_spec.json", "w") as f:
                json.dump(run_spec.dict(), f, indent=2, default=str)

            # Environment snapshot
            with open(f"{artifacts_dir}/environment.json", "w") as f:
                json.dump(environment.dict(), f, indent=2, default=str)

            # Retrieval documents
            retrieval_data = [doc.dict() for doc in retrieval_docs]
            with open(f"{artifacts_dir}/retrieval.json", "w") as f:
                json.dump(retrieval_data, f, indent=2, default=str)

            # Tool calls
            tool_calls_data = [tc.dict() for tc in tool_calls]
            with open(f"{artifacts_dir}/tool_calls.json", "w") as f:
                json.dump(tool_calls_data, f, indent=2, default=str)

            # Outputs
            with open(f"{artifacts_dir}/raw_output.txt", "w") as f:
                f.write(raw_output)

            with open(f"{artifacts_dir}/postprocessed_output.txt", "w") as f:
                f.write(postprocessed_output)

            # Log all artifacts
            mlflow.log_artifacts(artifacts_dir)

        finally:
            # Cleanup
            import shutil

            shutil.rmtree(artifacts_dir, ignore_errors=True)

    def _log_tags(
        self,
        run_spec: RunSpec,
        environment: EnvironmentSnapshot,
        feedback: dict[str, Any] | None,
    ) -> None:
        """Log tags to MLflow."""
        tags = {
            "service": "birtha-api",
            "timestamp": environment.timestamp.isoformat(),
        }

        if run_spec.domain_weights:
            primary_domain = max(run_spec.domain_weights.items(), key=lambda x: x[1])[0]
            tags["primary_domain"] = primary_domain

        if run_spec.policies:
            tags["policies_applied"] = ",".join(run_spec.policies)

        if feedback:
            tags["has_feedback"] = "true"
            tags["feedback_rating"] = str(feedback.get("rating", 0))
            if feedback.get("reasons"):
                tags["feedback_reasons"] = ",".join(feedback["reasons"])

        mlflow.set_tags(tags)

    def log_feedback(
        self,
        run_id: str,
        feedback: dict[str, Any],
    ) -> bool:
        """Log user feedback to existing MLflow run.

        Args:
            run_id: MLflow run ID
            feedback: User feedback data

        Returns:
            True if successful, False otherwise
        """
        if not self.experiment_id:
            logger.warning("MLflow not available, skipping feedback logging")
            return False

        try:
            with mlflow.start_run(run_id=run_id):
                # Log feedback metrics
                mlflow.log_metrics(
                    {
                        "user_rating": feedback.get("rating", 0),
                        "feedback_reasons_count": len(feedback.get("reasons", [])),
                    }
                )

                # Log feedback tags
                mlflow.set_tags(
                    {
                        "has_feedback": "true",
                        "feedback_rating": str(feedback.get("rating", 0)),
                        "feedback_timestamp": datetime.now().isoformat(),
                    }
                )

                if feedback.get("reasons"):
                    mlflow.set_tag("feedback_reasons", ",".join(feedback["reasons"]))

                # Log feedback artifact
                feedback_file = f"/tmp/feedback_{run_id}.json"
                with open(feedback_file, "w") as f:
                    json.dump(feedback, f, indent=2, default=str)

                mlflow.log_artifact(feedback_file)

                # Cleanup
                os.remove(feedback_file)

                logger.info("Logged feedback to MLflow", run_id=run_id)
                return True

        except Exception as e:
            logger.error(
                "Failed to log feedback to MLflow", run_id=run_id, error=str(e)
            )
            return False

    def get_run_info(self, run_id: str) -> dict[str, Any] | None:
        """Get information about a specific run.

        Args:
            run_id: MLflow run ID

        Returns:
            Run information or None if not found
        """
        if not self.experiment_id:
            return None

        try:
            run = mlflow.get_run(run_id)
            return {
                "run_id": run.info.run_id,
                "status": run.info.status,
                "start_time": run.info.start_time,
                "end_time": run.info.end_time,
                "experiment_id": run.info.experiment_id,
                "params": run.data.params,
                "metrics": run.data.metrics,
                "tags": run.data.tags,
            }
        except Exception as e:
            logger.error("Failed to get run info", run_id=run_id, error=str(e))
            return None

    def search_runs(
        self,
        filter_string: str | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Search runs in the experiment.

        Args:
            filter_string: Optional MLflow filter string
            max_results: Maximum number of results

        Returns:
            List of run information
        """
        if not self.experiment_id:
            return []

        try:
            runs = mlflow.search_runs(
                experiment_ids=[self.experiment_id],
                filter_string=filter_string,
                max_results=max_results,
            )

            return runs.to_dict("records")

        except Exception as e:
            logger.error("Failed to search runs", error=str(e))
            return []
