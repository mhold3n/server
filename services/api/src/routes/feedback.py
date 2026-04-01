"""Feedback routes for human-in-the-loop feedback collection."""

import json
import os
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..observability.mlflow_logger import MLflowLogger

logger = structlog.get_logger()

router = APIRouter(prefix="/feedback", tags=["feedback"])

# Initialize MLflow logger
mlflow_logger = MLflowLogger()


class FeedbackRequest(BaseModel):
    """Feedback request model."""

    run_id: str = Field(..., description="MLflow run ID")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    reasons: list[str] = Field(
        default_factory=list, description="List of feedback reasons"
    )
    notes: str | None = Field(None, description="Optional feedback notes")
    user_id: str | None = Field(None, description="User ID (if available)")
    session_id: str | None = Field(None, description="Session ID (if available)")


class FeedbackResponse(BaseModel):
    """Feedback response model."""

    feedback_id: str
    run_id: str
    rating: int
    reasons: list[str]
    notes: str | None
    timestamp: str
    status: str


class FeedbackSummary(BaseModel):
    """Feedback summary model."""

    total_feedback: int
    average_rating: float
    rating_distribution: dict[str, int]
    common_reasons: list[dict[str, Any]]
    recent_feedback: list[FeedbackResponse]


# Predefined feedback reasons
FEEDBACK_REASONS = [
    "needs_more_citations",
    "too_hedgy",
    "wrong_units",
    "inaccurate_information",
    "poor_formatting",
    "missing_context",
    "too_verbose",
    "too_concise",
    "unclear_explanation",
    "outdated_information",
    "irrelevant_content",
    "excellent_citations",
    "clear_explanation",
    "accurate_information",
    "good_formatting",
    "helpful_context",
    "appropriate_length",
    "up_to_date",
    "relevant_content",
]


@router.post("/v1/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
) -> FeedbackResponse:
    """Submit feedback for a run.

    Args:
        request: Feedback request

    Returns:
        Feedback response

    Raises:
        HTTPException: If feedback submission fails
    """
    try:
        # Validate reasons
        invalid_reasons = [
            reason for reason in request.reasons if reason not in FEEDBACK_REASONS
        ]
        if invalid_reasons:
            raise HTTPException(
                status_code=400, detail=f"Invalid feedback reasons: {invalid_reasons}"
            )

        # Create feedback ID
        feedback_id = f"feedback_{request.run_id}_{int(datetime.utcnow().timestamp())}"

        # Log feedback to MLflow
        await _log_feedback_to_mlflow(request, feedback_id)

        # Store feedback in local storage (in production, use a database)
        feedback_data = {
            "feedback_id": feedback_id,
            "run_id": request.run_id,
            "rating": request.rating,
            "reasons": request.reasons,
            "notes": request.notes,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await _store_feedback(feedback_data)

        logger.info(
            "Feedback submitted successfully",
            feedback_id=feedback_id,
            run_id=request.run_id,
            rating=request.rating,
            reasons=request.reasons,
        )

        return FeedbackResponse(
            feedback_id=feedback_id,
            run_id=request.run_id,
            rating=request.rating,
            reasons=request.reasons,
            notes=request.notes,
            timestamp=feedback_data["timestamp"],
            status="submitted",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Feedback submission failed", error=str(e))
        raise HTTPException(status_code=500, detail="Feedback submission failed") from e


@router.get("/v1/feedback/summary", response_model=FeedbackSummary)
async def get_feedback_summary(
    limit: int = 100,
    days: int = 30,
) -> FeedbackSummary:
    """Get feedback summary.

    Args:
        limit: Maximum number of recent feedback items
        days: Number of days to include in summary

    Returns:
        Feedback summary

    Raises:
        HTTPException: If summary generation fails
    """
    try:
        # Get all feedback
        all_feedback = await _get_all_feedback(days=days)

        if not all_feedback:
            return FeedbackSummary(
                total_feedback=0,
                average_rating=0.0,
                rating_distribution={},
                common_reasons=[],
                recent_feedback=[],
            )

        # Calculate statistics
        total_feedback = len(all_feedback)
        average_rating = sum(fb["rating"] for fb in all_feedback) / total_feedback

        # Rating distribution
        rating_distribution = {}
        for fb in all_feedback:
            rating = str(fb["rating"])
            rating_distribution[rating] = rating_distribution.get(rating, 0) + 1

        # Common reasons
        reason_counts = {}
        for fb in all_feedback:
            for reason in fb["reasons"]:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        common_reasons = [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                reason_counts.items(), key=lambda x: x[1], reverse=True
            )
        ][
            :10
        ]  # Top 10 reasons

        # Recent feedback
        recent_feedback = sorted(
            all_feedback, key=lambda x: x["timestamp"], reverse=True
        )[:limit]

        recent_feedback_responses = [
            FeedbackResponse(
                feedback_id=fb["feedback_id"],
                run_id=fb["run_id"],
                rating=fb["rating"],
                reasons=fb["reasons"],
                notes=fb["notes"],
                timestamp=fb["timestamp"],
                status="submitted",
            )
            for fb in recent_feedback
        ]

        return FeedbackSummary(
            total_feedback=total_feedback,
            average_rating=round(average_rating, 2),
            rating_distribution=rating_distribution,
            common_reasons=common_reasons,
            recent_feedback=recent_feedback_responses,
        )

    except Exception as e:
        logger.error("Failed to generate feedback summary", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate summary") from e


@router.get("/v1/feedback/reasons")
async def get_feedback_reasons() -> dict[str, Any]:
    """Get available feedback reasons.

    Returns:
        Available feedback reasons
    """
    return {
        "reasons": FEEDBACK_REASONS,
        "categories": {
            "quality_issues": [
                "needs_more_citations",
                "too_hedgy",
                "wrong_units",
                "inaccurate_information",
                "poor_formatting",
                "missing_context",
                "too_verbose",
                "too_concise",
                "unclear_explanation",
                "outdated_information",
                "irrelevant_content",
            ],
            "quality_strengths": [
                "excellent_citations",
                "clear_explanation",
                "accurate_information",
                "good_formatting",
                "helpful_context",
                "appropriate_length",
                "up_to_date",
                "relevant_content",
            ],
        },
    }


@router.get("/v1/feedback/{run_id}")
async def get_feedback_for_run(run_id: str) -> list[FeedbackResponse]:
    """Get feedback for a specific run.

    Args:
        run_id: MLflow run ID

    Returns:
        List of feedback responses

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        feedback_list = await _get_feedback_for_run(run_id)

        return [
            FeedbackResponse(
                feedback_id=fb["feedback_id"],
                run_id=fb["run_id"],
                rating=fb["rating"],
                reasons=fb["reasons"],
                notes=fb["notes"],
                timestamp=fb["timestamp"],
                status="submitted",
            )
            for fb in feedback_list
        ]

    except Exception as e:
        logger.error("Failed to get feedback for run", run_id=run_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get feedback") from e


@router.delete("/v1/feedback/{feedback_id}")
async def delete_feedback(feedback_id: str) -> dict[str, str]:
    """Delete feedback.

    Args:
        feedback_id: Feedback ID

    Returns:
        Success message

    Raises:
        HTTPException: If deletion fails
    """
    try:
        success = await _delete_feedback(feedback_id)

        if not success:
            raise HTTPException(status_code=404, detail="Feedback not found")

        logger.info("Feedback deleted", feedback_id=feedback_id)

        return {"message": "Feedback deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete feedback", feedback_id=feedback_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete feedback") from e


async def _log_feedback_to_mlflow(request: FeedbackRequest, feedback_id: str) -> None:
    """Log feedback to MLflow.

    Args:
        request: Feedback request
        feedback_id: Feedback ID
    """
    try:
        # Create feedback artifact
        feedback_artifact = {
            "feedback_id": feedback_id,
            "rating": request.rating,
            "reasons": request.reasons,
            "notes": request.notes,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Log to MLflow
        mlflow_logger.log_dict(feedback_artifact, "feedback.json")

        # Update run tags
        mlflow_logger.log_params(
            {
                "feedback_rating": str(request.rating),
                "feedback_reasons": ",".join(request.reasons),
                "feedback_id": feedback_id,
            }
        )

        logger.info(
            "Feedback logged to MLflow", feedback_id=feedback_id, run_id=request.run_id
        )

    except Exception as e:
        logger.error("Failed to log feedback to MLflow", error=str(e))
        # Don't raise exception - feedback should still be stored locally


async def _store_feedback(feedback_data: dict[str, Any]) -> None:
    """Store feedback data.

    Args:
        feedback_data: Feedback data to store
    """
    try:
        # In production, this would store to a database
        # For now, store in a local JSON file
        feedback_file = os.getenv("FEEDBACK_FILE", "/tmp/feedback.json")

        # Load existing feedback
        if os.path.exists(feedback_file):
            with open(feedback_file) as f:
                all_feedback = json.load(f)
        else:
            all_feedback = []

        # Add new feedback
        all_feedback.append(feedback_data)

        # Save back to file
        with open(feedback_file, "w") as f:
            json.dump(all_feedback, f, indent=2)

        logger.info("Feedback stored locally", feedback_id=feedback_data["feedback_id"])

    except Exception as e:
        logger.error("Failed to store feedback", error=str(e))
        raise


async def _get_feedback_for_run(run_id: str) -> list[dict[str, Any]]:
    """Get feedback for a specific run.

    Args:
        run_id: MLflow run ID

    Returns:
        List of feedback data
    """
    try:
        feedback_file = os.getenv("FEEDBACK_FILE", "/tmp/feedback.json")

        if not os.path.exists(feedback_file):
            return []

        with open(feedback_file) as f:
            all_feedback = json.load(f)

        # Filter by run_id
        run_feedback = [fb for fb in all_feedback if fb["run_id"] == run_id]

        return run_feedback

    except Exception as e:
        logger.error("Failed to get feedback for run", run_id=run_id, error=str(e))
        return []


async def _get_all_feedback(days: int = 30) -> list[dict[str, Any]]:
    """Get all feedback within specified days.

    Args:
        days: Number of days to include

    Returns:
        List of feedback data
    """
    try:
        feedback_file = os.getenv("FEEDBACK_FILE", "/tmp/feedback.json")

        if not os.path.exists(feedback_file):
            return []

        with open(feedback_file) as f:
            all_feedback = json.load(f)

        # Filter by date if needed
        if days > 0:
            cutoff_date = datetime.utcnow().timestamp() - (days * 24 * 60 * 60)
            filtered_feedback = []

            for fb in all_feedback:
                try:
                    fb_timestamp = datetime.fromisoformat(fb["timestamp"]).timestamp()
                    if fb_timestamp >= cutoff_date:
                        filtered_feedback.append(fb)
                except ValueError:
                    # Skip feedback with invalid timestamps
                    continue

            return filtered_feedback

        return all_feedback

    except Exception as e:
        logger.error("Failed to get all feedback", error=str(e))
        return []


async def _delete_feedback(feedback_id: str) -> bool:
    """Delete feedback by ID.

    Args:
        feedback_id: Feedback ID

    Returns:
        True if deleted, False if not found
    """
    try:
        feedback_file = os.getenv("FEEDBACK_FILE", "/tmp/feedback.json")

        if not os.path.exists(feedback_file):
            return False

        with open(feedback_file) as f:
            all_feedback = json.load(f)

        # Find and remove feedback
        original_count = len(all_feedback)
        all_feedback = [fb for fb in all_feedback if fb["feedback_id"] != feedback_id]

        if len(all_feedback) == original_count:
            return False  # Not found

        # Save back to file
        with open(feedback_file, "w") as f:
            json.dump(all_feedback, f, indent=2)

        return True

    except Exception as e:
        logger.error("Failed to delete feedback", feedback_id=feedback_id, error=str(e))
        return False
