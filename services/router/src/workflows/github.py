"""GitHub workflow integration for code-related prompts."""

import re
from typing import Any

import structlog

logger = structlog.get_logger()


class GitHubWorkflow:
    """GitHub workflow for handling code-related prompts."""

    def __init__(self, mcp_client: Any):
        """Initialize GitHub workflow.

        Args:
            mcp_client: MCP client for GitHub operations
        """
        self.mcp_client = mcp_client
        self.code_indicators = [
            "code", "function", "class", "method", "bug", "fix", "feature",
            "implementation", "refactor", "optimize", "debug", "test",
            "repository", "pull request", "issue", "commit", "branch",
            "merge", "review", "deploy", "build", "ci", "cd"
        ]

    async def process_prompt(
        self,
        prompt: str,
        context: dict[str, Any] = None,
    ) -> dict[str, Any]:
        """Process a code-related prompt through GitHub workflow.

        Args:
            prompt: User prompt
            context: Additional context

        Returns:
            Workflow result
        """
        try:
            # Detect if prompt is code-related
            if not self._is_code_related(prompt):
                return {
                    "workflow": "github",
                    "action": "skip",
                    "reason": "Not a code-related prompt",
                }

            # Classify the type of code request
            request_type = self._classify_request(prompt)

            # Execute appropriate workflow
            if request_type == "bug_report":
                return await self._handle_bug_report(prompt, context)
            elif request_type == "feature_request":
                return await self._handle_feature_request(prompt, context)
            elif request_type == "code_review":
                return await self._handle_code_review(prompt, context)
            elif request_type == "implementation":
                return await self._handle_implementation(prompt, context)
            else:
                return await self._handle_general_code_request(prompt, context)

        except Exception as e:
            logger.error("GitHub workflow failed", error=str(e))
            return {
                "workflow": "github",
                "action": "error",
                "error": str(e),
            }

    def _is_code_related(self, prompt: str) -> bool:
        """Check if prompt is code-related.

        Args:
            prompt: User prompt

        Returns:
            True if code-related
        """
        prompt_lower = prompt.lower()

        # Check for code-related keywords
        for indicator in self.code_indicators:
            if indicator in prompt_lower:
                return True

        # Check for code patterns
        code_patterns = [
            r'\b(def|class|function|method|import|from)\b',
            r'\b(bug|error|exception|traceback)\b',
            r'\b(feature|enhancement|improvement)\b',
            r'\b(review|refactor|optimize|debug)\b',
            r'\b(test|spec|assert|expect)\b',
            r'\b(commit|push|pull|merge|branch)\b',
        ]

        for pattern in code_patterns:
            if re.search(pattern, prompt_lower):
                return True

        return False

class CodeDetector:
    """Detects code-related prompts and classifies them."""

    def __init__(self):
        """Initialize code detector."""
        self.classifiers = {
            "bug_report": [
                "bug", "error", "exception", "traceback", "crash", "fail",
                "broken", "not working", "issue", "problem", "fix"
            ],
            "feature_request": [
                "feature", "enhancement", "improvement", "add", "new",
                "implement", "create", "build", "develop"
            ],
            "code_review": [
                "review", "check", "look at", "examine", "analyze",
                "evaluate", "assess", "inspect"
            ],
            "implementation": [
                "implement", "code", "write", "create", "build",
                "develop", "program", "script", "function"
            ],
        }

    def classify_request(self, prompt: str) -> str:
        """Classify the type of code request.

        Args:
            prompt: User prompt

        Returns:
            Request type
        """
        prompt_lower = prompt.lower()

        # Score each category
        scores = {}
        for category, keywords in self.classifiers.items():
            score = sum(1 for keyword in keywords if keyword in prompt_lower)
            scores[category] = score

        # Return highest scoring category
        if not any(scores.values()):
            return "general"

        return max(scores, key=scores.get)

    def _classify_request(self, prompt: str) -> str:
        """Classify the type of code request.

        Args:
            prompt: User prompt

        Returns:
            Request type
        """
        detector = CodeDetector()
        return detector.classify_request(prompt)

    async def _handle_bug_report(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle bug report workflow.

        Args:
            prompt: User prompt
            context: Additional context

        Returns:
            Workflow result
        """
        try:
            # Extract bug information
            bug_info = self._extract_bug_info(prompt)

            # Create issue using template
            issue_result = await self.mcp_client.call_tool(
                "apply_issue_template",
                {
                    "owner": context.get("owner", "mhold3n"),
                    "repo": context.get("repo", "server"),
                    "template_name": "bug_report",
                    "title": bug_info["title"],
                    "template_data": {
                        "description": bug_info["description"],
                        "steps_to_reproduce": bug_info["steps"],
                        "expected_behavior": bug_info["expected"],
                        "actual_behavior": bug_info["actual"],
                        "environment": bug_info["environment"],
                    },
                    "labels": ["bug", "needs-triage"],
                }
            )

            # Add to project if specified
            if context.get("project_id"):
                await self.mcp_client.call_tool(
                    "add_issue_to_project",
                    {
                        "project_id": context["project_id"],
                        "issue_id": issue_result["number"],
                        "field_id": "status",
                        "value": "New",
                    }
                )

            return {
                "workflow": "github",
                "action": "bug_report_created",
                "issue_number": issue_result["number"],
                "issue_url": issue_result["html_url"],
                "template_used": "bug_report",
            }

        except Exception as e:
            logger.error("Bug report workflow failed", error=str(e))
            return {
                "workflow": "github",
                "action": "error",
                "error": str(e),
            }

    async def _handle_feature_request(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle feature request workflow.

        Args:
            prompt: User prompt
            context: Additional context

        Returns:
            Workflow result
        """
        try:
            # Extract feature information
            feature_info = self._extract_feature_info(prompt)

            # Create issue using template
            issue_result = await self.mcp_client.call_tool(
                "apply_issue_template",
                {
                    "owner": context.get("owner", "mhold3n"),
                    "repo": context.get("repo", "server"),
                    "template_name": "feature_request",
                    "title": feature_info["title"],
                    "template_data": {
                        "description": feature_info["description"],
                        "use_case": feature_info["use_case"],
                        "acceptance_criteria": feature_info["criteria"],
                        "alternatives": feature_info["alternatives"],
                    },
                    "labels": ["enhancement", "needs-discussion"],
                }
            )

            # Add to project if specified
            if context.get("project_id"):
                await self.mcp_client.call_tool(
                    "add_issue_to_project",
                    {
                        "project_id": context["project_id"],
                        "issue_id": issue_result["number"],
                        "field_id": "status",
                        "value": "Under Consideration",
                    }
                )

            return {
                "workflow": "github",
                "action": "feature_request_created",
                "issue_number": issue_result["number"],
                "issue_url": issue_result["html_url"],
                "template_used": "feature_request",
            }

        except Exception as e:
            logger.error("Feature request workflow failed", error=str(e))
            return {
                "workflow": "github",
                "action": "error",
                "error": str(e),
            }

    async def _handle_code_review(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle code review workflow.

        Args:
            prompt: User prompt
            context: Additional context

        Returns:
            Workflow result
        """
        try:
            # Extract review information
            review_info = self._extract_review_info(prompt)

            # Create pull request for review
            pr_result = await self.mcp_client.call_tool(
                "create_pull_request",
                {
                    "owner": context.get("owner", "mhold3n"),
                    "repo": context.get("repo", "server"),
                    "title": review_info["title"],
                    "head": review_info["head_branch"],
                    "base": review_info["base_branch"],
                    "body": review_info["description"],
                    "draft": True,  # Create as draft for review
                }
            )

            # Link to issue if specified
            if review_info.get("issue_number"):
                await self.mcp_client.call_tool(
                    "link_pr_to_issue",
                    {
                        "owner": context.get("owner", "mhold3n"),
                        "repo": context.get("repo", "server"),
                        "pull_number": pr_result["number"],
                        "issue_number": review_info["issue_number"],
                    }
                )

            return {
                "workflow": "github",
                "action": "code_review_created",
                "pull_number": pr_result["number"],
                "pr_url": pr_result["html_url"],
                "draft": True,
            }

        except Exception as e:
            logger.error("Code review workflow failed", error=str(e))
            return {
                "workflow": "github",
                "action": "error",
                "error": str(e),
            }

    async def _handle_implementation(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle implementation workflow.

        Args:
            prompt: User prompt
            context: Additional context

        Returns:
            Workflow result
        """
        try:
            # Extract implementation information
            impl_info = self._extract_implementation_info(prompt)

            # Create issue for implementation
            issue_result = await self.mcp_client.call_tool(
                "apply_issue_template",
                {
                    "owner": context.get("owner", "mhold3n"),
                    "repo": context.get("repo", "server"),
                    "template_name": "implementation",
                    "title": impl_info["title"],
                    "template_data": {
                        "description": impl_info["description"],
                        "requirements": impl_info["requirements"],
                        "technical_specs": impl_info["specs"],
                        "testing": impl_info["testing"],
                    },
                    "labels": ["implementation", "needs-assignment"],
                }
            )

            # Create branch for implementation
            branch_name = f"implement/{impl_info['title'].lower().replace(' ', '-')}"

            # Add to project if specified
            if context.get("project_id"):
                await self.mcp_client.call_tool(
                    "add_issue_to_project",
                    {
                        "project_id": context["project_id"],
                        "issue_id": issue_result["number"],
                        "field_id": "status",
                        "value": "In Progress",
                    }
                )

            return {
                "workflow": "github",
                "action": "implementation_created",
                "issue_number": issue_result["number"],
                "issue_url": issue_result["html_url"],
                "suggested_branch": branch_name,
                "template_used": "implementation",
            }

        except Exception as e:
            logger.error("Implementation workflow failed", error=str(e))
            return {
                "workflow": "github",
                "action": "error",
                "error": str(e),
            }

    async def _handle_general_code_request(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle general code request.

        Args:
            prompt: User prompt
            context: Additional context

        Returns:
            Workflow result
        """
        try:
            # Create general issue
            issue_result = await self.mcp_client.call_tool(
                "create_issue",
                {
                    "owner": context.get("owner", "mhold3n"),
                    "repo": context.get("repo", "server"),
                    "title": f"Code request: {prompt[:50]}...",
                    "body": prompt,
                    "labels": ["code", "needs-triage"],
                }
            )

            return {
                "workflow": "github",
                "action": "general_issue_created",
                "issue_number": issue_result["number"],
                "issue_url": issue_result["html_url"],
            }

        except Exception as e:
            logger.error("General code request workflow failed", error=str(e))
            return {
                "workflow": "github",
                "action": "error",
                "error": str(e),
            }

    def _extract_bug_info(self, prompt: str) -> dict[str, str]:
        """Extract bug information from prompt.

        Args:
            prompt: User prompt

        Returns:
            Bug information
        """
        return {
            "title": f"Bug: {prompt[:50]}...",
            "description": prompt,
            "steps": "1. Steps to reproduce the bug",
            "expected": "Expected behavior",
            "actual": "Actual behavior",
            "environment": "Environment details",
        }

    def _extract_feature_info(self, prompt: str) -> dict[str, str]:
        """Extract feature information from prompt.

        Args:
            prompt: User prompt

        Returns:
            Feature information
        """
        return {
            "title": f"Feature: {prompt[:50]}...",
            "description": prompt,
            "use_case": "Use case description",
            "criteria": "Acceptance criteria",
            "alternatives": "Alternative solutions considered",
        }

    def _extract_review_info(self, prompt: str) -> dict[str, str]:
        """Extract review information from prompt.

        Args:
            prompt: User prompt

        Returns:
            Review information
        """
        return {
            "title": f"Review: {prompt[:50]}...",
            "description": prompt,
            "head_branch": "feature/review-branch",
            "base_branch": "main",
        }

    def _extract_implementation_info(self, prompt: str) -> dict[str, str]:
        """Extract implementation information from prompt.

        Args:
            prompt: User prompt

        Returns:
            Implementation information
        """
        return {
            "title": f"Implement: {prompt[:50]}...",
            "description": prompt,
            "requirements": "Implementation requirements",
            "specs": "Technical specifications",
            "testing": "Testing requirements",
        }











