"""Clarify-first planning heuristics for code-oriented tasks."""

from __future__ import annotations

import re

from .models import (
    ClarificationAnswer,
    ClarificationQuestion,
    PatchPlanRecord,
    ProjectRecord,
    PublishIntent,
    TaskCreateRequest,
    TaskPlan,
    VerificationBlock,
)

_AMBIGUOUS_HINTS = (
    "fix",
    "improve",
    "support",
    "update",
    "handle",
    "work on",
    "help with",
    "issue",
    "bug",
    "feature",
    "pipeline",
)


def slugify(value: str) -> str:
    """Return a filesystem- and branch-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "task"


class TaskPlanner:
    """Build task plans and clarification prompts from user intent."""

    def suggest_verification_plan(
        self,
        *,
        user_context: dict[str, object],
        discovered_commands: list[str],
    ) -> list[str]:
        explicit = user_context.get("verification_commands")
        if isinstance(explicit, list):
            commands = [str(item).strip() for item in explicit if str(item).strip()]
            if commands:
                return commands
        if discovered_commands:
            return discovered_commands
        return ["git status --short"]

    def build_questions(
        self,
        request: TaskCreateRequest,
        *,
        project: ProjectRecord,
        existing_answers: list[ClarificationAnswer],
    ) -> list[ClarificationQuestion]:
        """Return material clarification prompts when intent is underspecified."""
        if existing_answers:
            return []

        text = request.user_intent.strip()
        questions: list[ClarificationQuestion] = []
        lowered = text.lower()
        has_acceptance = bool(request.context.get("acceptance_criteria"))
        has_constraints = bool(request.context.get("constraints"))
        has_ref = bool(request.repo_ref_hint)

        if len(text.split()) < 8 or any(hint in lowered for hint in _AMBIGUOUS_HINTS):
            questions.append(
                ClarificationQuestion(
                    question_id="objective_scope",
                    field="objective",
                    prompt=(
                        f"What concrete outcome should be delivered in project "
                        f"'{project.name}' for this task?"
                    ),
                )
            )

        if not has_acceptance:
            questions.append(
                ClarificationQuestion(
                    question_id="acceptance_criteria",
                    field="acceptance_criteria",
                    prompt=(
                        "What acceptance criteria or proof of completion should the "
                        "agent satisfy before the task is considered done?"
                    ),
                )
            )

        if not has_constraints and not has_ref:
            questions.append(
                ClarificationQuestion(
                    question_id="constraints",
                    field="constraints",
                    prompt=(
                        "Are there constraints on files, subsystems, tooling, or "
                        "branches that the agent should respect?"
                    ),
                )
            )

        return questions[:3]

    def build_plan(
        self,
        request: TaskCreateRequest,
        *,
        project: ProjectRecord,
        discovered_verification: list[str],
        answers: list[ClarificationAnswer],
    ) -> tuple[TaskPlan, PatchPlanRecord]:
        """Build a normalized plan and empty patch plan scaffold."""
        answer_map = {answer.question_id: answer.answer.strip() for answer in answers}
        constraints: list[str] = []
        raw_constraints = request.context.get("constraints")
        if isinstance(raw_constraints, list):
            constraints.extend(
                str(item).strip() for item in raw_constraints if str(item).strip()
            )
        elif isinstance(raw_constraints, str) and raw_constraints.strip():
            constraints.append(raw_constraints.strip())
        if request.repo_ref_hint:
            constraints.append(
                f"Prefer working relative to ref hint: {request.repo_ref_hint}"
            )
        if "constraints" in answer_map:
            constraints.append(answer_map["constraints"])

        acceptance_criteria: list[str] = []
        raw_acceptance = request.context.get("acceptance_criteria")
        if isinstance(raw_acceptance, list):
            acceptance_criteria.extend(
                str(item).strip() for item in raw_acceptance if str(item).strip()
            )
        elif isinstance(raw_acceptance, str) and raw_acceptance.strip():
            acceptance_criteria.append(raw_acceptance.strip())
        if "acceptance_criteria" in answer_map:
            acceptance_criteria.append(answer_map["acceptance_criteria"])
        if not acceptance_criteria:
            acceptance_criteria = [
                "The requested code or configuration change is present in the isolated workspace.",
                "Relevant verification commands complete without errors or their failures are documented.",
                "The task dossier records files changed, commands executed, and publish state.",
            ]

        objective = answer_map.get("objective_scope", request.user_intent.strip())
        verification_plan = self.suggest_verification_plan(
            user_context=request.context,
            discovered_commands=discovered_verification,
        )
        planned_branch = f"birtha/{slugify(objective)}"
        plan = TaskPlan(
            project_id=project.project_id,
            objective=objective,
            constraints=constraints,
            acceptance_criteria=acceptance_criteria,
            delegation_hints=[
                "Lead executor owns implementation and may delegate focused review or verification work when needed.",
                "Keep all delegated work inside the isolated task workspace.",
            ],
            work_items=[
                "Inspect the task packet and current project state.",
                "Implement the requested code or configuration changes.",
                "Collect deterministic verification evidence before handoff.",
            ],
            implementation_outline=[
                "Review the registered project workspace and task packet context.",
                "Identify the minimal file set required to satisfy the objective.",
                "Implement code or configuration changes inside the isolated task worktree.",
                "Run the planned verification commands and capture outputs in the dossier.",
                "Prepare the branch and publish metadata for PR delivery.",
            ],
            verification_plan=verification_plan,
            verification_blocks=[
                VerificationBlock(
                    name=f"verification_{idx + 1}",
                    command=command,
                )
                for idx, command in enumerate(verification_plan)
            ],
            publish_intent=PublishIntent(remote_name=project.remote_name),
            repo_ref_hint=request.repo_ref_hint,
            planned_branch=planned_branch,
        )
        patch_plan = PatchPlanRecord()
        return (plan, patch_plan)
