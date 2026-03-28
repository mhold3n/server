"""MLflow provenance logging for complete request tracking."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import mlflow
import structlog
from mlflow.tracking import MlflowClient

from .mlflow_logger import (
    EnvironmentSnapshot,
    MLflowLogger,
    RetrievalDoc,
    RunSpec,
    ToolCall,
)

logger = structlog.get_logger()


class ProvenanceLogger:
    """Logs complete request provenance to MLflow with structured artifacts."""

    def __init__(self, mlflow_logger: MLflowLogger):
        """Initialize provenance logger."""
        self.mlflow_logger = mlflow_logger
        self.client = MlflowClient()

    def log_request_provenance(
        self,
        run_id: str,
        trace_id: str,
        run_spec: RunSpec,
        environment: EnvironmentSnapshot,
        retrieval_docs: list[RetrievalDoc] | None = None,
        tool_calls: list[ToolCall] | None = None,
        raw_output: str | None = None,
        postprocessed_output: str | None = None,
        policy_verdicts: dict[str, Any] | None = None,
    ) -> None:
        """Log complete request provenance with all artifacts.

        Args:
            run_id: MLflow run ID
            trace_id: OpenTelemetry trace ID
            run_spec: Request specification
            environment: Environment snapshot
            retrieval_docs: Retrieved documents with provenance
            tool_calls: Tool execution details
            raw_output: Raw LLM output
            postprocessed_output: Post-processed output
            policy_verdicts: Policy validation results
        """
        try:
            with mlflow.start_run(run_id=run_id):
                # Set trace ID tag
                mlflow.set_tag("trace_id", trace_id)
                mlflow.set_tag("service", "birtha-api")
                mlflow.set_tag("request_type", "chat_completion")

                # Log run specification
                self._log_run_spec(run_spec)

                # Log environment snapshot
                self._log_environment(environment)

                # Log retrieval provenance
                if retrieval_docs:
                    self._log_retrieval_provenance(retrieval_docs)

                # Log tool execution
                if tool_calls:
                    self._log_tool_execution(tool_calls)

                # Log outputs
                if raw_output:
                    self._log_raw_output(raw_output)

                if postprocessed_output:
                    self._log_postprocessed_output(postprocessed_output)

                # Log policy verdicts
                if policy_verdicts:
                    self._log_policy_verdicts(policy_verdicts)

                # Log aggregated metrics
                self._log_aggregated_metrics(
                    run_spec, retrieval_docs, tool_calls, policy_verdicts
                )

                logger.info(
                    "Request provenance logged",
                    run_id=run_id,
                    trace_id=trace_id,
                    retrieval_count=len(retrieval_docs) if retrieval_docs else 0,
                    tool_calls_count=len(tool_calls) if tool_calls else 0,
                )

        except Exception as e:
            logger.error("Failed to log request provenance", error=str(e))

    def _log_run_spec(self, run_spec: RunSpec) -> None:
        """Log run specification as JSON artifact."""
        spec_data = {
            "prompt": run_spec.prompt,
            "model": run_spec.model,
            "temperature": run_spec.temperature,
            "max_tokens": run_spec.max_tokens,
            "system": run_spec.system,
            "tools": run_spec.tools,
            "tool_args": run_spec.tool_args,
            "domain_weights": run_spec.domain_weights,
            "policies": run_spec.policies,
            "timestamp": datetime.utcnow().isoformat(),
        }

        mlflow.log_text(
            json.dumps(spec_data, indent=2),
            "run_spec.json"
        )

    def _log_environment(self, environment: EnvironmentSnapshot) -> None:
        """Log environment snapshot as JSON artifact."""
        env_data = {
            "timestamp": environment.timestamp.isoformat(),
            "service_version": environment.service_version,
            "model_version": environment.model_version,
            "config_hash": environment.config_hash,
            "dependencies": environment.dependencies,
            "environment_variables": environment.environment_variables,
            "system_info": environment.system_info,
        }

        mlflow.log_text(
            json.dumps(env_data, indent=2),
            "environment.json"
        )

    def _log_retrieval_provenance(self, retrieval_docs: list[RetrievalDoc]) -> None:
        """Log retrieval provenance with document metadata."""
        retrieval_data = []

        for doc in retrieval_docs:
            doc_info = {
                "doc_id": doc.doc_id,
                "source_uri": doc.source_uri,
                "content_hash": doc.content_hash,
                "score": doc.score,
                "page_range": doc.page_range,
                "index_version": doc.index_version,
                "embedding_model": doc.embedding_model,
                "metadata": doc.metadata,
                "content_preview": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
            }
            retrieval_data.append(doc_info)

        mlflow.log_text(
            json.dumps(retrieval_data, indent=2),
            "retrieval.json"
        )

        # Log retrieval metrics
        mlflow.log_metrics({
            "retrieval_count": len(retrieval_docs),
            "avg_retrieval_score": sum(doc.score for doc in retrieval_docs) / len(retrieval_docs),
            "unique_sources": len({doc.source_uri for doc in retrieval_docs}),
        })

    def _log_tool_execution(self, tool_calls: list[ToolCall]) -> None:
        """Log tool execution details."""
        tool_data = []

        for tool in tool_calls:
            tool_info = {
                "tool_name": tool.tool_name,
                "tool_args": tool.tool_args,
                "result": tool.result,
                "duration": tool.duration,
                "success": tool.success,
                "error": tool.error,
                "timestamp": datetime.utcnow().isoformat(),
            }
            tool_data.append(tool_info)

        mlflow.log_text(
            json.dumps(tool_data, indent=2),
            "tool_execution.json"
        )

        # Log tool metrics
        mlflow.log_metrics({
            "tool_calls_count": len(tool_calls),
            "successful_tools": sum(1 for tool in tool_calls if tool.success),
            "avg_tool_duration": sum(tool.duration for tool in tool_calls) / len(tool_calls),
        })

    def _log_raw_output(self, raw_output: str) -> None:
        """Log raw LLM output."""
        mlflow.log_text(raw_output, "raw_output.txt")

        # Log output metrics
        mlflow.log_metrics({
            "raw_output_length": len(raw_output),
            "raw_output_tokens": len(raw_output.split()),
        })

    def _log_postprocessed_output(self, postprocessed_output: str) -> None:
        """Log post-processed output."""
        mlflow.log_text(postprocessed_output, "postprocessed_output.txt")

        # Log processing metrics
        mlflow.log_metrics({
            "postprocessed_output_length": len(postprocessed_output),
            "postprocessed_output_tokens": len(postprocessed_output.split()),
        })

    def _log_policy_verdicts(self, policy_verdicts: dict[str, Any]) -> None:
        """Log policy validation results."""
        mlflow.log_text(
            json.dumps(policy_verdicts, indent=2),
            "policy_verdicts.json"
        )

        # Log policy metrics
        if "overall_passed" in policy_verdicts:
            mlflow.log_metric("policy_overall_passed", int(policy_verdicts["overall_passed"]))
        if "overall_score" in policy_verdicts:
            mlflow.log_metric("policy_overall_score", policy_verdicts["overall_score"])
        if "total_violations" in policy_verdicts:
            mlflow.log_metric("policy_violations", policy_verdicts["total_violations"])

    def _log_aggregated_metrics(
        self,
        run_spec: RunSpec,
        retrieval_docs: list[RetrievalDoc] | None,
        tool_calls: list[ToolCall] | None,
        policy_verdicts: dict[str, Any] | None,
    ) -> None:
        """Log aggregated metrics for the request."""
        metrics = {
            "prompt_length": len(run_spec.prompt),
            "model": run_spec.model,
            "temperature": run_spec.temperature,
        }

        if retrieval_docs:
            metrics.update({
                "retrieval_count": len(retrieval_docs),
                "avg_retrieval_score": sum(doc.score for doc in retrieval_docs) / len(retrieval_docs),
            })

        if tool_calls:
            metrics.update({
                "tool_calls_count": len(tool_calls),
                "successful_tools": sum(1 for tool in tool_calls if tool.success),
            })

        if policy_verdicts:
            metrics.update({
                "policy_overall_passed": int(policy_verdicts.get("overall_passed", False)),
                "policy_overall_score": policy_verdicts.get("overall_score", 0.0),
                "policy_violations": policy_verdicts.get("total_violations", 0),
            })

        mlflow.log_metrics(metrics)

    def log_feedback(
        self,
        run_id: str,
        rating: int,
        reasons: list[str],
        notes: str | None = None,
    ) -> None:
        """Log user feedback for a run.

        Args:
            run_id: MLflow run ID
            rating: User rating (1-5)
            reasons: List of feedback reasons
            notes: Optional notes
        """
        try:
            feedback_data = {
                "run_id": run_id,
                "rating": rating,
                "reasons": reasons,
                "notes": notes,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Log to MLflow
            with mlflow.start_run(run_id=run_id):
                mlflow.log_text(
                    json.dumps(feedback_data, indent=2),
                    "feedback.json"
                )
                mlflow.log_metrics({
                    "user_rating": rating,
                    "feedback_reasons_count": len(reasons),
                })
                mlflow.set_tag("has_feedback", "true")

            # Append to feedback log
            self._append_feedback_log(feedback_data)

            logger.info(
                "Feedback logged",
                run_id=run_id,
                rating=rating,
                reasons=reasons,
            )

        except Exception as e:
            logger.error("Failed to log feedback", error=str(e))

    def _append_feedback_log(self, feedback_data: dict[str, Any]) -> None:
        """Append feedback to persistent log file."""
        try:
            feedback_file = Path("/logs/feedback.jsonl")
            feedback_file.parent.mkdir(parents=True, exist_ok=True)

            with open(feedback_file, "a") as f:
                f.write(json.dumps(feedback_data) + "\n")

        except Exception as e:
            logger.error("Failed to append feedback log", error=str(e))
