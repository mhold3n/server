"""Schema-backed engineering knowledge pool loader, resolver, and runtime linker."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import secrets
import socket
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import NAMESPACE_URL, uuid5

from .contracts import (
    ArtifactStatus,
    ArtifactType,
    ArtifactValidationState,
    DecisionLogPayload,
    EnvironmentSpecPayload,
    EvidenceBundlePayload,
    ExecutionAdapterSpecPayload,
    GuiSessionSpecPayload,
    KnowledgePackPayload,
    Producer,
    RecipeObjectPayload,
    RoleContextBundlePayload,
    SourceHashRecord,
    TypedArtifactRecord,
    VerificationFinding,
    VerificationGateResult,
    VerificationOutcome,
    VerificationReportPayload,
)
from .validation import (
    validate_decision_log_json,
    validate_environment_spec_json,
    validate_evidence_bundle_json,
    validate_execution_adapter_spec_json,
    validate_gui_session_spec_json,
    validate_knowledge_pack_json,
    validate_recipe_object_json,
    validate_role_context_bundle_json,
    validate_typed_artifact_json,
    validate_verification_report_json,
)


PayloadValidator = Callable[[dict[str, Any]], Any]

ROLE_SECTIONS: dict[str, tuple[str, ...]] = {
    "general": (
        "capability boundaries",
        "tradeoffs",
        "fidelity and cost",
        "integration fit",
        "expected outputs",
    ),
    "coder": (
        "apis and objects",
        "file contracts",
        "adapter usage",
        "minimal scaffolds",
        "implementation failure modes",
    ),
    "reviewer": (
        "invariants",
        "unit checks",
        "validation cases",
        "anti-patterns",
        "acceptance thresholds",
    ),
}

ALL_SECTIONS = tuple(section for sections in ROLE_SECTIONS.values() for section in sections)


@dataclass(frozen=True)
class LoadedArtifact:
    ref: str
    file_path: Path
    record: TypedArtifactRecord
    payload: (
        KnowledgePackPayload
        | RecipeObjectPayload
        | ExecutionAdapterSpecPayload
        | EvidenceBundlePayload
        | GuiSessionSpecPayload
        | RoleContextBundlePayload
        | DecisionLogPayload
        | EnvironmentSpecPayload
        | VerificationReportPayload
    )


@dataclass(frozen=True)
class RankedCandidate:
    knowledge_pack_ref: str
    score: int
    matched_terms: tuple[str, ...]
    recipe_refs: tuple[str, ...]
    adapter_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    environment_refs: tuple[str, ...]
    runtime_verification_refs: tuple[str, ...]


@dataclass(frozen=True)
class PackLookupHit:
    knowledge_pack_ref: str
    score: int
    matched_terms: tuple[str, ...]
    runtime_gated: bool


@dataclass(frozen=True)
class GuiSessionHandle:
    gui_session_ref: str
    container_id: str
    container_name: str
    url: str
    novnc_port: int
    password: str
    artifact_output_dir: str


class KnowledgePoolCatalog:
    """Loaded, validated engineering knowledge pool."""

    def __init__(
        self,
        *,
        root: Path,
        artifacts: dict[str, LoadedArtifact],
        minutes_inventory: dict[str, Any] | None,
    ) -> None:
        self.root = root
        self.artifacts = artifacts
        self.minutes_inventory = minutes_inventory or {}

        self.knowledge_packs = {
            ref: artifact
            for ref, artifact in artifacts.items()
            if artifact.record.artifact_type is ArtifactType.KNOWLEDGE_PACK
        }
        self.recipe_objects = {
            ref: artifact
            for ref, artifact in artifacts.items()
            if artifact.record.artifact_type is ArtifactType.RECIPE_OBJECT
        }
        self.execution_adapters = {
            ref: artifact
            for ref, artifact in artifacts.items()
            if artifact.record.artifact_type is ArtifactType.EXECUTION_ADAPTER_SPEC
        }
        self.evidence_bundles = {
            ref: artifact
            for ref, artifact in artifacts.items()
            if artifact.record.artifact_type is ArtifactType.EVIDENCE_BUNDLE
        }
        self.role_context_bundles = {
            ref: artifact
            for ref, artifact in artifacts.items()
            if artifact.record.artifact_type is ArtifactType.ROLE_CONTEXT_BUNDLE
        }
        self.environment_specs = {
            ref: artifact
            for ref, artifact in artifacts.items()
            if artifact.record.artifact_type is ArtifactType.ENVIRONMENT_SPEC
        }
        self.gui_session_specs = {
            ref: artifact
            for ref, artifact in artifacts.items()
            if artifact.record.artifact_type is ArtifactType.GUI_SESSION_SPEC
        }
        self.verification_reports = {
            ref: artifact
            for ref, artifact in artifacts.items()
            if artifact.record.artifact_type is ArtifactType.VERIFICATION_REPORT
        }
        self.decision_logs = {
            ref: artifact
            for ref, artifact in artifacts.items()
            if artifact.record.artifact_type is ArtifactType.DECISION_LOG
        }

    @classmethod
    def load(cls, root: Path | None = None) -> KnowledgePoolCatalog:
        knowledge_root = resolve_engineering_knowledge_pool_root(root)
        artifacts: dict[str, LoadedArtifact] = {}
        for relative_path in (
            "substrate/knowledge-packs.json",
            "substrate/recipe-objects.json",
            "substrate/decision-logs.json",
            "environments/environment-specs.json",
            "gui/gui-session-specs.json",
            "adapters/execution-adapter-specs.json",
            "evidence/evidence-bundles.json",
            "evidence/verification-reports.json",
            "compiled/general-context.json",
            "compiled/coder-context.json",
            "compiled/reviewer-context.json",
        ):
            path = knowledge_root / relative_path
            if not path.exists():
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                artifact = _load_artifact_record(item, path)
                if artifact.ref in artifacts:
                    raise ValueError(f"Duplicate artifact ref detected: {artifact.ref}")
                artifacts[artifact.ref] = artifact
        inventory_path = knowledge_root / "substrate" / "minutes-inventory.json"
        minutes_inventory = None
        if inventory_path.exists():
            minutes_inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        catalog = cls(root=knowledge_root, artifacts=artifacts, minutes_inventory=minutes_inventory)
        errors = catalog.validate_cross_links()
        if errors:
            raise ValueError("Knowledge pool cross-link validation failed: " + "; ".join(errors))
        return catalog

    def validate_cross_links(self) -> list[str]:
        errors: list[str] = []
        for ref, artifact in self.knowledge_packs.items():
            payload = artifact.payload
            assert isinstance(payload, KnowledgePackPayload)
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.integration_refs,
                    allowed_types=(
                        ArtifactType.DECISION_LOG,
                        ArtifactType.KNOWLEDGE_PACK,
                        ArtifactType.RECIPE_OBJECT,
                    ),
                    source_ref=ref,
                    field_name="integration_refs",
                )
            )
            for integration_ref in payload.integration_refs:
                linked = self.artifacts.get(integration_ref)
                if linked and linked.record.artifact_type is ArtifactType.DECISION_LOG:
                    decision_payload = linked.payload
                    assert isinstance(decision_payload, DecisionLogPayload)
                    if decision_payload.status == "superseded":
                        errors.append(f"{ref} references stale decision log {integration_ref}")
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.recipe_refs,
                    allowed_types=(ArtifactType.RECIPE_OBJECT,),
                    source_ref=ref,
                    field_name="recipe_refs",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.adapter_refs,
                    allowed_types=(ArtifactType.EXECUTION_ADAPTER_SPEC,),
                    source_ref=ref,
                    field_name="adapter_refs",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.evidence_refs,
                    allowed_types=(ArtifactType.EVIDENCE_BUNDLE,),
                    source_ref=ref,
                    field_name="evidence_refs",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.environment_refs,
                    allowed_types=(ArtifactType.ENVIRONMENT_SPEC,),
                    source_ref=ref,
                    field_name="environment_refs",
                )
            )
        for ref, artifact in self.recipe_objects.items():
            payload = artifact.payload
            assert isinstance(payload, RecipeObjectPayload)
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=[payload.knowledge_pack_ref],
                    allowed_types=(ArtifactType.KNOWLEDGE_PACK,),
                    source_ref=ref,
                    field_name="knowledge_pack_ref",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.adapter_refs,
                    allowed_types=(ArtifactType.EXECUTION_ADAPTER_SPEC,),
                    source_ref=ref,
                    field_name="adapter_refs",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.evidence_refs,
                    allowed_types=(ArtifactType.EVIDENCE_BUNDLE,),
                    source_ref=ref,
                    field_name="evidence_refs",
                )
            )
        for ref, artifact in self.execution_adapters.items():
            payload = artifact.payload
            assert isinstance(payload, ExecutionAdapterSpecPayload)
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=[payload.knowledge_pack_ref],
                    allowed_types=(ArtifactType.KNOWLEDGE_PACK,),
                    source_ref=ref,
                    field_name="knowledge_pack_ref",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=[payload.preferred_environment_ref],
                    allowed_types=(ArtifactType.ENVIRONMENT_SPEC,),
                    source_ref=ref,
                    field_name="preferred_environment_ref",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.environment_refs,
                    allowed_types=(ArtifactType.ENVIRONMENT_SPEC,),
                    source_ref=ref,
                    field_name="environment_refs",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.healthcheck_refs,
                    allowed_types=(ArtifactType.VERIFICATION_REPORT,),
                    source_ref=ref,
                    field_name="healthcheck_refs",
                )
            )
            if payload.preferred_environment_ref not in payload.environment_refs:
                errors.append(
                    f"{ref} preferred environment {payload.preferred_environment_ref} is not listed in environment_refs"
                )
            knowledge_pack = self.artifacts.get(payload.knowledge_pack_ref)
            if knowledge_pack is not None:
                pack_payload = knowledge_pack.payload
                assert isinstance(pack_payload, KnowledgePackPayload)
                if payload.supported_library_version != pack_payload.library_version:
                    errors.append(
                        f"{ref} supports library version {payload.supported_library_version} "
                        f"but linked pack {payload.knowledge_pack_ref} is {pack_payload.library_version}"
                    )
        for ref, artifact in self.evidence_bundles.items():
            payload = artifact.payload
            assert isinstance(payload, EvidenceBundlePayload)
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=[payload.knowledge_pack_ref],
                    allowed_types=(ArtifactType.KNOWLEDGE_PACK,),
                    source_ref=ref,
                    field_name="knowledge_pack_ref",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.recipe_refs,
                    allowed_types=(ArtifactType.RECIPE_OBJECT,),
                    source_ref=ref,
                    field_name="recipe_refs",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.adapter_refs,
                    allowed_types=(ArtifactType.EXECUTION_ADAPTER_SPEC,),
                    source_ref=ref,
                    field_name="adapter_refs",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.runtime_verification_refs,
                    allowed_types=(ArtifactType.VERIFICATION_REPORT,),
                    source_ref=ref,
                    field_name="runtime_verification_refs",
                )
            )
        for ref, artifact in self.environment_specs.items():
            payload = artifact.payload
            assert isinstance(payload, EnvironmentSpecPayload)
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.gui_session_refs,
                    allowed_types=(ArtifactType.GUI_SESSION_SPEC,),
                    source_ref=ref,
                    field_name="gui_session_refs",
                )
            )
            if payload.default_gui_session_ref:
                errors.extend(
                    _check_refs_exist(
                        artifacts=self.artifacts,
                        refs=[payload.default_gui_session_ref],
                        allowed_types=(ArtifactType.GUI_SESSION_SPEC,),
                        source_ref=ref,
                        field_name="default_gui_session_ref",
                    )
                )
                if payload.default_gui_session_ref not in payload.gui_session_refs:
                    errors.append(
                        f"{ref} default GUI session {payload.default_gui_session_ref} is not listed in gui_session_refs"
                    )
        for ref, artifact in self.gui_session_specs.items():
            payload = artifact.payload
            assert isinstance(payload, GuiSessionSpecPayload)
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=[payload.base_environment_ref, payload.gui_environment_ref],
                    allowed_types=(ArtifactType.ENVIRONMENT_SPEC,),
                    source_ref=ref,
                    field_name="environment_refs",
                )
            )
            if payload.verification_ref:
                errors.extend(
                    _check_refs_exist(
                        artifacts=self.artifacts,
                        refs=[payload.verification_ref],
                        allowed_types=(ArtifactType.VERIFICATION_REPORT,),
                        source_ref=ref,
                        field_name="verification_ref",
                    )
                )
        for ref, artifact in self.verification_reports.items():
            payload = artifact.payload
            assert isinstance(payload, VerificationReportPayload)
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.validated_artifact_refs,
                    allowed_types=(
                        ArtifactType.ENVIRONMENT_SPEC,
                        ArtifactType.KNOWLEDGE_PACK,
                        ArtifactType.EXECUTION_ADAPTER_SPEC,
                        ArtifactType.EVIDENCE_BUNDLE,
                        ArtifactType.GUI_SESSION_SPEC,
                    ),
                    source_ref=ref,
                    field_name="validated_artifact_refs",
                )
            )
        for ref, artifact in self.decision_logs.items():
            payload = artifact.payload
            assert isinstance(payload, DecisionLogPayload)
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.chosen_refs,
                    allowed_types=(
                        ArtifactType.KNOWLEDGE_PACK,
                        ArtifactType.RECIPE_OBJECT,
                        ArtifactType.EXECUTION_ADAPTER_SPEC,
                        ArtifactType.EVIDENCE_BUNDLE,
                        ArtifactType.ENVIRONMENT_SPEC,
                        ArtifactType.GUI_SESSION_SPEC,
                    ),
                    source_ref=ref,
                    field_name="chosen_refs",
                )
            )
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.rejected_refs,
                    allowed_types=(
                        ArtifactType.KNOWLEDGE_PACK,
                        ArtifactType.RECIPE_OBJECT,
                        ArtifactType.EXECUTION_ADAPTER_SPEC,
                        ArtifactType.EVIDENCE_BUNDLE,
                        ArtifactType.ENVIRONMENT_SPEC,
                        ArtifactType.GUI_SESSION_SPEC,
                    ),
                    source_ref=ref,
                    field_name="rejected_refs",
                )
            )
        for ref, artifact in self.role_context_bundles.items():
            payload = artifact.payload
            assert isinstance(payload, RoleContextBundlePayload)
            errors.extend(
                _check_refs_exist(
                    artifacts=self.artifacts,
                    refs=payload.source_artifact_refs,
                    allowed_types=(
                        ArtifactType.KNOWLEDGE_PACK,
                        ArtifactType.RECIPE_OBJECT,
                        ArtifactType.EXECUTION_ADAPTER_SPEC,
                        ArtifactType.EVIDENCE_BUNDLE,
                        ArtifactType.DECISION_LOG,
                        ArtifactType.ENVIRONMENT_SPEC,
                        ArtifactType.GUI_SESSION_SPEC,
                        ArtifactType.VERIFICATION_REPORT,
                    ),
                    source_ref=ref,
                    field_name="source_artifact_refs",
                )
            )
        return errors

    def validate_candidate_pack_set(self, candidate_refs: list[str]) -> list[str]:
        """Check whether a selected pack set has explicit integration support."""
        errors: list[str] = []
        unique_refs = list(dict.fromkeys(candidate_refs))
        for ref in unique_refs:
            if ref not in self.knowledge_packs:
                errors.append(f"{ref} is not a known knowledge-pack ref")
        if errors:
            return errors
        for idx, left_ref in enumerate(unique_refs):
            left_payload = self.knowledge_packs[left_ref].payload
            assert isinstance(left_payload, KnowledgePackPayload)
            left_links = set(left_payload.integration_refs)
            left_decisions = {
                item
                for item in left_links
                if item.startswith("artifact://decision-log/")
            }
            for right_ref in unique_refs[idx + 1 :]:
                right_payload = self.knowledge_packs[right_ref].payload
                assert isinstance(right_payload, KnowledgePackPayload)
                right_links = set(right_payload.integration_refs)
                right_decisions = {
                    item
                    for item in right_links
                    if item.startswith("artifact://decision-log/")
                }
                if right_ref in left_links or left_ref in right_links:
                    continue
                if left_decisions & right_decisions:
                    continue
                errors.append(
                    f"Incompatible integration pairing: {left_ref} has no declared integration with {right_ref}"
                )
        return errors

    def validate_adapter_inputs(self, adapter_ref: str, provided_inputs: dict[str, Any]) -> list[str]:
        """Validate required adapter inputs and declared unit policy."""
        artifact = self.execution_adapters.get(adapter_ref)
        if artifact is None:
            return [f"Unknown execution adapter ref: {adapter_ref}"]
        payload = artifact.payload
        assert isinstance(payload, ExecutionAdapterSpecPayload)
        errors: list[str] = []
        for field in payload.typed_inputs:
            value = provided_inputs.get(field.name)
            if field.required and value is None:
                errors.append(f"Missing required input: {field.name}")
                continue
            if (
                payload.unit_policy.require_declared_units
                and field.type in {"number", "array", "table", "object"}
                and value is not None
                and field.name != "problem"
                and not _value_has_unit(value)
            ):
                errors.append(f"Unit-policy violation for input: {field.name}")
        return errors

    def validate_decision_consistency(self) -> list[str]:
        """Detect stale or contradictory decision records when titles collide."""
        errors: list[str] = []
        accepted_by_title: dict[str, list[DecisionLogPayload]] = {}
        for artifact in self.decision_logs.values():
            payload = artifact.payload
            assert isinstance(payload, DecisionLogPayload)
            if payload.status == "accepted":
                accepted_by_title.setdefault(payload.title.lower(), []).append(payload)
        for title, decisions in accepted_by_title.items():
            for idx, left in enumerate(decisions):
                for right in decisions[idx + 1 :]:
                    if set(left.chosen_refs) != set(right.chosen_refs) or set(left.rejected_refs) != set(
                        right.rejected_refs
                    ):
                        errors.append(
                            f"Conflicting accepted decisions for title '{title}': "
                            f"{left.decision_id} vs {right.decision_id}"
                        )
        return errors

    def resolve_stack(
        self,
        problem_spec: dict[str, Any],
        project_constraints: dict[str, Any],
    ) -> list[RankedCandidate]:
        """
        Rank valid knowledge packs based on deterministic runtime verification and constraint matching.
        
        Why: We cannot rely on LLMs to invent tool chains. This algorithm tokenizes the incoming problem
        spec (e.g., 'simulate fluid flow') and scores it strictly against the `positive_text` 
        and `negative_text` of explicitly modeled `knowledge_packs` within the `coding-tools` pool.
        Any tool lacking a verified runtime environment (`_pack_has_passing_runtime_verification`) is 
        instantly stripped from the candidate list.
        """
        problem_terms = _tokenize_structure(problem_spec)
        constraint_terms = _tokenize_structure(project_constraints)
        language_terms = {
            token
            for token in constraint_terms
            if token in {"python", "c", "c++", "cpp", "c#", "dotnet", "fortran", "cli", "mpi"}
        }
        ranked: list[RankedCandidate] = []
        for ref, artifact in sorted(self.knowledge_packs.items()):
            if artifact.record.validation_state is not ArtifactValidationState.VALID:
                continue
            payload = artifact.payload
            assert isinstance(payload, KnowledgePackPayload)
            if not payload.recipe_refs or not payload.evidence_refs or not payload.environment_refs:
                continue
            runtime_refs = self._runtime_verification_refs_for_pack(payload)
            if not self._pack_has_passing_runtime_verification(payload, runtime_refs):
                continue

            positive_text = " ".join(
                [
                    payload.tool_id,
                    payload.tool_name,
                    *payload.alias_names,
                    payload.substitution_note or "",
                    payload.module_class,
                    *payload.bindings,
                    *payload.scope.solves,
                    *payload.best_for,
                    *payload.anti_patterns,
                    *payload.interfaces.inputs,
                    *payload.interfaces.outputs,
                ]
            )
            negative_text = " ".join(payload.scope.not_for)
            positive_terms = _tokenize_text(positive_text)
            negative_terms = _tokenize_text(negative_text)
            if problem_terms & negative_terms:
                continue

            matched_terms = sorted((problem_terms | constraint_terms) & positive_terms)
            score = 1 + (3 * len(matched_terms))

            for recipe_ref in payload.recipe_refs:
                recipe_artifact = self.recipe_objects.get(recipe_ref)
                if recipe_artifact is None:
                    continue
                recipe_payload = recipe_artifact.payload
                assert isinstance(recipe_payload, RecipeObjectPayload)
                recipe_terms = _tokenize_text(recipe_payload.task_class.replace("_", " "))
                if recipe_terms and recipe_terms <= problem_terms:
                    score += 12
                else:
                    score += 5 * len(recipe_terms & problem_terms)

            scope_terms = _tokenize_text(" ".join(payload.scope.solves))
            score += 4 * len(scope_terms & problem_terms)

            binding_terms = {_normalize_binding(binding) for binding in payload.bindings}
            if language_terms:
                overlap = binding_terms & language_terms
                if overlap:
                    score += 4 * len(overlap)
                else:
                    score -= 2

            if any("integration" in value for value in constraint_terms):
                score += len(payload.integration_refs)

            ranked.append(
                RankedCandidate(
                    knowledge_pack_ref=ref,
                    score=score,
                    matched_terms=tuple(matched_terms),
                    recipe_refs=tuple(payload.recipe_refs),
                    adapter_refs=tuple(payload.adapter_refs),
                    evidence_refs=tuple(payload.evidence_refs),
                    environment_refs=tuple(payload.environment_refs),
                    runtime_verification_refs=tuple(runtime_refs),
                )
            )
        return sorted(ranked, key=lambda item: (-item.score, item.knowledge_pack_ref))

    def recommendable_pack_refs(self) -> list[str]:
        refs: list[str] = []
        for ref, artifact in sorted(self.knowledge_packs.items()):
            if artifact.record.validation_state is not ArtifactValidationState.VALID:
                continue
            payload = artifact.payload
            assert isinstance(payload, KnowledgePackPayload)
            runtime_refs = self._runtime_verification_refs_for_pack(payload)
            if self._pack_has_passing_runtime_verification(payload, runtime_refs):
                refs.append(ref)
        return refs

    def lookup_knowledge_packs(
        self,
        query: str,
        *,
        include_runtime_gated: bool = False,
    ) -> list[PackLookupHit]:
        query_terms = _tokenize_text(query)
        hits: list[PackLookupHit] = []
        for ref, artifact in sorted(self.knowledge_packs.items()):
            payload = artifact.payload
            assert isinstance(payload, KnowledgePackPayload)
            runtime_refs = self._runtime_verification_refs_for_pack(payload)
            runtime_gated = not self._pack_has_passing_runtime_verification(payload, runtime_refs)
            if runtime_gated and not include_runtime_gated:
                continue
            searchable_text = " ".join(
                [
                    payload.tool_id,
                    payload.tool_name,
                    *payload.alias_names,
                    payload.substitution_note or "",
                    *payload.scope.solves,
                    *payload.best_for,
                    *payload.anti_patterns,
                ]
            )
            searchable_terms = _tokenize_text(searchable_text)
            matched = sorted(query_terms & searchable_terms)
            if not matched:
                continue
            hits.append(
                PackLookupHit(
                    knowledge_pack_ref=ref,
                    score=len(matched),
                    matched_terms=tuple(matched),
                    runtime_gated=runtime_gated,
                )
            )
        return sorted(hits, key=lambda item: (-item.score, item.knowledge_pack_ref))

    def resolve_runtime(
        self,
        module_or_adapter_ref: str,
        host_profile: dict[str, Any] | None = None,
    ) -> EnvironmentSpecPayload:
        """
        Resolve the best linked environment for a module or adapter.
        
        Why: An agent needs to know not just *what* tool to run, but *where* to run it.
        This function evaluates the target's preferred execution profile (e.g. docker vs native uv_venv)
        and scores environments against the host's actual capability profile, guaranteeing the returned
        Launcher/GUI ref will actually execute on the user's OS infrastructure.
        """
        host_profile = host_profile or {}
        preferred_kinds = host_profile.get(
            "preferred_delivery_kinds",
            ["uv_venv", "dotnet_toolchain", "host_app", "docker_image"],
        )
        platform_tag = host_profile.get("platform", _current_platform_tag())
        verified_only = bool(host_profile.get("verified_only", True))

        candidate_env_refs: list[str]
        preferred_ref: str | None = None
        if module_or_adapter_ref in self.execution_adapters:
            payload = self.execution_adapters[module_or_adapter_ref].payload
            assert isinstance(payload, ExecutionAdapterSpecPayload)
            candidate_env_refs = list(payload.environment_refs)
            preferred_ref = payload.preferred_environment_ref
        elif module_or_adapter_ref in self.knowledge_packs:
            payload = self.knowledge_packs[module_or_adapter_ref].payload
            assert isinstance(payload, KnowledgePackPayload)
            candidate_env_refs = list(payload.environment_refs)
        else:
            raise ValueError(f"Unknown module or adapter ref: {module_or_adapter_ref}")

        ranked: list[tuple[int, EnvironmentSpecPayload]] = []
        for env_ref in candidate_env_refs:
            artifact = self.environment_specs.get(env_ref)
            if artifact is None:
                continue
            payload = artifact.payload
            assert isinstance(payload, EnvironmentSpecPayload)
            if verified_only and not self._environment_has_passing_verification(env_ref):
                continue
            score = 0
            if env_ref == preferred_ref:
                score += 100
            if payload.delivery_kind in preferred_kinds:
                score += 20 * (len(preferred_kinds) - preferred_kinds.index(payload.delivery_kind))
            if platform_tag in payload.supported_host_platforms:
                score += 10
            ranked.append((score, payload))
        if not ranked:
            raise ValueError(f"No environment matched for {module_or_adapter_ref}")
        return sorted(
            ranked,
            key=lambda item: (-item[0], item[1].environment_spec_id),
        )[0][1]

    def resolve_gui_session(
        self,
        module_or_environment_ref: str,
        host_profile: dict[str, Any] | None = None,
    ) -> GuiSessionSpecPayload:
        """Resolve the best noVNC/OpenClaw GUI session for a module or environment."""
        host_profile = host_profile or {}
        verified_only = bool(host_profile.get("verified_only", True))
        platform_tag = host_profile.get("docker_platform") or host_profile.get("platform", "linux/amd64")

        candidate_refs: list[str] = []
        if module_or_environment_ref in self.gui_session_specs:
            candidate_refs = [module_or_environment_ref]
        elif module_or_environment_ref in self.environment_specs:
            env_payload = self.environment_specs[module_or_environment_ref].payload
            assert isinstance(env_payload, EnvironmentSpecPayload)
            candidate_refs = list(env_payload.gui_session_refs)
            if env_payload.default_gui_session_ref:
                candidate_refs.insert(0, env_payload.default_gui_session_ref)
        elif module_or_environment_ref in self.execution_adapters:
            adapter_payload = self.execution_adapters[module_or_environment_ref].payload
            assert isinstance(adapter_payload, ExecutionAdapterSpecPayload)
            for env_ref in adapter_payload.environment_refs:
                env_payload = self.environment_specs.get(env_ref)
                if env_payload is None:
                    continue
                payload = env_payload.payload
                assert isinstance(payload, EnvironmentSpecPayload)
                candidate_refs.extend(payload.gui_session_refs)
        elif module_or_environment_ref in self.knowledge_packs:
            pack_payload = self.knowledge_packs[module_or_environment_ref].payload
            assert isinstance(pack_payload, KnowledgePackPayload)
            for env_ref in pack_payload.environment_refs:
                env_payload = self.environment_specs.get(env_ref)
                if env_payload is None:
                    continue
                payload = env_payload.payload
                assert isinstance(payload, EnvironmentSpecPayload)
                candidate_refs.extend(payload.gui_session_refs)
        else:
            raise ValueError(f"Unknown module, environment, adapter, or GUI session ref: {module_or_environment_ref}")

        ranked: list[tuple[int, GuiSessionSpecPayload]] = []
        for gui_ref in dict.fromkeys(candidate_refs):
            artifact = self.gui_session_specs.get(gui_ref)
            if artifact is None:
                continue
            payload = artifact.payload
            assert isinstance(payload, GuiSessionSpecPayload)
            if verified_only and not self._gui_session_has_passing_verification(gui_ref):
                continue
            score = 0
            if payload.control_provider == "openclaw_browser":
                score += 40
            if payload.display_protocol == "novnc_web":
                score += 30
            if payload.docker_platform == platform_tag:
                score += 20
            if payload.base_environment_ref == module_or_environment_ref:
                score += 10
            ranked.append((score, payload))
        if not ranked:
            raise ValueError(f"No GUI session matched for {module_or_environment_ref}")
        return sorted(
            ranked,
            key=lambda item: (-item[0], item[1].gui_session_spec_id),
        )[0][1]

    def launch_gui_session(
        self,
        gui_session_ref: str,
        launch_profile: dict[str, Any] | None = None,
    ) -> GuiSessionHandle:
        """Launch a noVNC/OpenClaw-controlled GUI container and return its handle."""
        launch_profile = launch_profile or {}
        artifact = self.gui_session_specs.get(gui_session_ref)
        if artifact is None:
            raise ValueError(f"Unknown GUI session ref: {gui_session_ref}")
        payload = artifact.payload
        assert isinstance(payload, GuiSessionSpecPayload)
        if payload.security_policy.allow_host_desktop:
            raise ValueError("Host desktop GUI control is not allowed for canonical GUI sessions")
        if payload.security_policy.bind_host != "127.0.0.1":
            raise ValueError("GUI sessions must bind noVNC to 127.0.0.1")

        docker_bin = subprocess.run(
            ["which", "docker"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=False,
        )
        if docker_bin.returncode != 0:
            raise RuntimeError("docker CLI is not available in this environment")

        novnc_port = int(launch_profile.get("novnc_port") or _free_loopback_port())
        password = str(launch_profile.get("password") or secrets.token_urlsafe(18))
        session_suffix = secrets.token_hex(4)
        container_name = (
            f"knowledge-gui-{payload.gui_session_spec_id.replace('_', '-')}-{session_suffix}"
        )
        artifact_dir = _resolve_repo_path(
            str(launch_profile.get("artifact_output_dir") or payload.artifact_output_dir)
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)

        display_env = dict(payload.display_env)
        display_env["NOVNC_PASSWORD"] = password
        display_env["KNOWLEDGE_GUI_SESSION_REF"] = gui_session_ref
        display_env["KNOWLEDGE_GUI_ARTIFACT_DIR"] = "/artifacts"

        docker_cmd = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--platform",
            payload.docker_platform,
            "--name",
            container_name,
            "-p",
            f"127.0.0.1:{novnc_port}:{payload.container_ports.novnc}",
            "-v",
            f"{_repo_root()}:{_repo_root()}",
            "-w",
            str(_repo_root()),
            "-v",
            f"{artifact_dir}:/artifacts",
        ]
        for key, value in sorted(display_env.items()):
            docker_cmd.extend(["-e", f"{key}={value}"])
        docker_cmd.append(payload.docker_image)

        result = subprocess.run(
            docker_cmd,
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"GUI container launch failed for {gui_session_ref}: {detail}")

        container_id = result.stdout.strip()
        url = payload.openclaw_entry_url.format(novnc_port=novnc_port)
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}password={password}"
        return GuiSessionHandle(
            gui_session_ref=gui_session_ref,
            container_id=container_id,
            container_name=container_name,
            url=url,
            novnc_port=novnc_port,
            password=password,
            artifact_output_dir=str(artifact_dir),
        )

    def close_gui_session(self, container_id_or_name: str) -> None:
        """Close a launched GUI container."""
        if not container_id_or_name.strip():
            raise ValueError("container_id_or_name must not be empty")
        result = subprocess.run(
            ["docker", "rm", "-f", container_id_or_name],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"Failed to close GUI container {container_id_or_name}: {detail}")

    def verify_runtime(self, environment_ref: str) -> VerificationReportPayload:
        """Run the environment health check command and return a verification report."""
        artifact = self.environment_specs.get(environment_ref)
        if artifact is None:
            raise ValueError(f"Unknown environment ref: {environment_ref}")
        payload = artifact.payload
        assert isinstance(payload, EnvironmentSpecPayload)
        result = subprocess.run(
            payload.healthcheck_command,
            cwd=_repo_root(),
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        report_id = str(uuid5(NAMESPACE_URL, f"runtime-verification:{environment_ref}"))
        if result.returncode == 0:
            return VerificationReportPayload.model_validate(
                {
                    "verification_report_id": report_id,
                    "schema_version": "1.0.0",
                    "outcome": VerificationOutcome.PASS,
                    "reasons": ["Runtime health check passed."],
                    "gate_results": [
                        VerificationGateResult(
                            gate_id="env_healthcheck",
                            gate_kind="tests",
                            status="PASS",
                            detail=result.stdout.strip() or "Health check completed successfully.",
                            artifact_ref=environment_ref,
                        ).model_dump(mode="json")
                    ],
                    "recommended_next_action": "accept_runtime_environment",
                    "validated_artifact_refs": [environment_ref],
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
        return VerificationReportPayload.model_validate(
            {
                "verification_report_id": report_id,
                "schema_version": "1.0.0",
                "outcome": VerificationOutcome.REWORK,
                "reasons": ["Runtime health check failed."],
                "blocking_findings": [
                    VerificationFinding(
                        code="runtime_healthcheck_failed",
                        severity="high",
                        artifact_ref=environment_ref,
                    ).model_dump(mode="json")
                ],
                "gate_results": [
                    VerificationGateResult(
                        gate_id="env_healthcheck",
                        gate_kind="tests",
                        status="FAIL",
                        detail=(result.stderr or result.stdout).strip() or "Health check failed.",
                        remediation_hint="Bootstrap the environment and rerun the verification command.",
                        artifact_ref=environment_ref,
                    ).model_dump(mode="json")
                ],
                "recommended_next_action": "repair_runtime_environment",
                "validated_artifact_refs": [environment_ref],
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    def verify_gui_session(self, gui_session_ref: str) -> VerificationReportPayload:
        """Run the GUI session health check command and return a verification report."""
        artifact = self.gui_session_specs.get(gui_session_ref)
        if artifact is None:
            raise ValueError(f"Unknown GUI session ref: {gui_session_ref}")
        payload = artifact.payload
        assert isinstance(payload, GuiSessionSpecPayload)
        result = subprocess.run(
            payload.healthcheck_command,
            cwd=_repo_root(),
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        report_id = str(uuid5(NAMESPACE_URL, f"gui-session-verification:{gui_session_ref}"))
        if result.returncode == 0:
            return VerificationReportPayload.model_validate(
                {
                    "verification_report_id": report_id,
                    "schema_version": "1.0.0",
                    "outcome": VerificationOutcome.PASS,
                    "reasons": ["GUI session health check passed."],
                    "gate_results": [
                        VerificationGateResult(
                            gate_id="gui_session_healthcheck",
                            gate_kind="tests",
                            status="PASS",
                            detail=result.stdout.strip() or "GUI health check completed successfully.",
                            artifact_ref=gui_session_ref,
                        ).model_dump(mode="json")
                    ],
                    "recommended_next_action": "accept_gui_session",
                    "validated_artifact_refs": [gui_session_ref, payload.gui_environment_ref],
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
        return VerificationReportPayload.model_validate(
            {
                "verification_report_id": report_id,
                "schema_version": "1.0.0",
                "outcome": VerificationOutcome.REWORK,
                "reasons": ["GUI session health check failed."],
                "blocking_findings": [
                    VerificationFinding(
                        code="gui_session_healthcheck_failed",
                        severity="high",
                        artifact_ref=gui_session_ref,
                    ).model_dump(mode="json")
                ],
                "gate_results": [
                    VerificationGateResult(
                        gate_id="gui_session_healthcheck",
                        gate_kind="tests",
                        status="FAIL",
                        detail=(result.stderr or result.stdout).strip() or "GUI health check failed.",
                        remediation_hint="Bootstrap the GUI environment and rerun the GUI verification command.",
                        artifact_ref=gui_session_ref,
                    ).model_dump(mode="json")
                ],
                "recommended_next_action": "repair_gui_session",
                "validated_artifact_refs": [gui_session_ref, payload.gui_environment_ref],
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    def compile_role_context(
        self,
        role: str,
        candidate_refs: list[str],
        task_class: str,
        project_constraints: dict[str, Any],
    ) -> RoleContextBundlePayload:
        """Compile a deterministic role-specific context bundle."""
        if role not in ROLE_SECTIONS:
            raise ValueError(f"Unsupported role: {role}")
        if not candidate_refs:
            raise ValueError("candidate_refs must not be empty")

        pack_refs = list(dict.fromkeys(candidate_refs))
        promotion_only = bool(project_constraints.get("promotion_only"))
        source_refs: set[str] = set()
        summary_chunks: list[str] = []
        retrieval_keys = sorted(set([role, task_class, *_tokenize_structure(project_constraints)]))
        for pack_ref in pack_refs:
            artifact = self.knowledge_packs.get(pack_ref)
            if artifact is None:
                raise ValueError(f"Unknown knowledge pack ref: {pack_ref}")
            payload = artifact.payload
            assert isinstance(payload, KnowledgePackPayload)
            runtime_refs = self._runtime_verification_refs_for_pack(payload)
            source_refs.add(pack_ref)
            integration_refs = list(payload.integration_refs)
            if promotion_only:
                integration_refs = [
                    ref
                    for ref in integration_refs
                    if ref not in self.knowledge_packs or ref in pack_refs
                ]
            source_refs.update(integration_refs)
            source_refs.update(payload.recipe_refs)
            source_refs.update(payload.adapter_refs)
            source_refs.update(payload.evidence_refs)
            source_refs.update(payload.environment_refs)
            source_refs.update(runtime_refs)
            for env_ref in payload.environment_refs:
                env_artifact = self.environment_specs.get(env_ref)
                if env_artifact is None:
                    continue
                env_payload = env_artifact.payload
                assert isinstance(env_payload, EnvironmentSpecPayload)
                source_refs.update(env_payload.gui_session_refs)
                for gui_ref in env_payload.gui_session_refs:
                    gui_artifact = self.gui_session_specs.get(gui_ref)
                    if gui_artifact is None:
                        continue
                    gui_payload = gui_artifact.payload
                    assert isinstance(gui_payload, GuiSessionSpecPayload)
                    source_refs.add(gui_payload.gui_environment_ref)
                    if gui_payload.verification_ref:
                        source_refs.add(gui_payload.verification_ref)
            summary_chunks.append(self._summary_for_role(role, payload, runtime_refs))

        sorted_source_refs = sorted(source_refs)
        source_hashes = [
            SourceHashRecord(
                artifact_ref=artifact_ref,
                sha256=_artifact_sha256(self.artifacts[artifact_ref]),
            )
            for artifact_ref in sorted_source_refs
        ]
        included_sections = list(ROLE_SECTIONS[role])
        excluded_sections = [section for section in ALL_SECTIONS if section not in included_sections]
        bundle_key = json.dumps(
            {
                "role": role,
                "task_class": task_class,
                "candidate_refs": pack_refs,
                "project_constraints": project_constraints,
            },
            sort_keys=True,
        )
        bundle_id = f"{role}_{hashlib.sha256(bundle_key.encode('utf-8')).hexdigest()[:16]}"
        return RoleContextBundlePayload.model_validate(
            {
                "role_context_bundle_id": bundle_id,
                "schema_version": "1.0.0",
                "role": role,
                "task_class": task_class,
                "source_artifact_refs": sorted_source_refs,
                "source_hashes": [item.model_dump(mode="json") for item in source_hashes],
                "compiled_summary": "\n".join(summary_chunks),
                "included_sections": included_sections,
                "excluded_sections": excluded_sections,
                "retrieval_keys": retrieval_keys,
            }
        )

    def compile_role_context_record(
        self,
        role: str,
        candidate_refs: list[str],
        task_class: str,
        project_constraints: dict[str, Any],
    ) -> TypedArtifactRecord:
        payload = self.compile_role_context(role, candidate_refs, task_class, project_constraints)
        artifact_id = uuid5(NAMESPACE_URL, payload.role_context_bundle_id)
        return TypedArtifactRecord.model_validate(
            {
                "artifact_id": str(artifact_id),
                "artifact_type": ArtifactType.ROLE_CONTEXT_BUNDLE,
                "schema_version": "1.0.0",
                "status": ArtifactStatus.ACTIVE,
                "validation_state": ArtifactValidationState.VALID,
                "producer": Producer(
                    component="control_plane.knowledge_pool",
                    executor="deterministic_compiler",
                ).model_dump(mode="json"),
                "input_artifact_refs": payload.source_artifact_refs,
                "supersedes": [],
                "payload": payload.model_dump(mode="json", by_alias=True),
                "created_at": "2026-04-08T00:00:00Z",
                "updated_at": "2026-04-08T00:00:00Z",
            }
        )

    def _runtime_verification_refs_for_pack(self, payload: KnowledgePackPayload) -> list[str]:
        runtime_refs: set[str] = set()
        for evidence_ref in payload.evidence_refs:
            evidence_artifact = self.evidence_bundles.get(evidence_ref)
            if evidence_artifact is None:
                continue
            evidence_payload = evidence_artifact.payload
            assert isinstance(evidence_payload, EvidenceBundlePayload)
            runtime_refs.update(evidence_payload.runtime_verification_refs)
        for adapter_ref in payload.adapter_refs:
            adapter_artifact = self.execution_adapters.get(adapter_ref)
            if adapter_artifact is None:
                continue
            adapter_payload = adapter_artifact.payload
            assert isinstance(adapter_payload, ExecutionAdapterSpecPayload)
            runtime_refs.update(adapter_payload.healthcheck_refs)
        return sorted(runtime_refs)

    def _environment_has_passing_verification(self, environment_ref: str) -> bool:
        return any(
            environment_ref in report.payload.validated_artifact_refs
            and report.payload.outcome is VerificationOutcome.PASS
            for report in self.verification_reports.values()
            if isinstance(report.payload, VerificationReportPayload)
        )

    def _gui_session_has_passing_verification(self, gui_session_ref: str) -> bool:
        return any(
            gui_session_ref in report.payload.validated_artifact_refs
            and report.payload.outcome is VerificationOutcome.PASS
            for report in self.verification_reports.values()
            if isinstance(report.payload, VerificationReportPayload)
        )

    def _pack_has_passing_runtime_verification(
        self,
        payload: KnowledgePackPayload,
        runtime_refs: list[str],
    ) -> bool:
        environment_refs = set(payload.environment_refs)
        for runtime_ref in runtime_refs:
            artifact = self.verification_reports.get(runtime_ref)
            if artifact is None:
                continue
            report_payload = artifact.payload
            assert isinstance(report_payload, VerificationReportPayload)
            if report_payload.outcome is not VerificationOutcome.PASS:
                continue
            if environment_refs & set(report_payload.validated_artifact_refs):
                return True
        return False

    def _summary_for_role(
        self,
        role: str,
        payload: KnowledgePackPayload,
        runtime_refs: list[str],
    ) -> str:
        recipe = self.recipe_objects[payload.recipe_refs[0]].payload
        adapter = self.execution_adapters[payload.adapter_refs[0]].payload
        evidence = self.evidence_bundles[payload.evidence_refs[0]].payload
        assert isinstance(recipe, RecipeObjectPayload)
        assert isinstance(adapter, ExecutionAdapterSpecPayload)
        assert isinstance(evidence, EvidenceBundlePayload)
        env = self.environment_specs[adapter.preferred_environment_ref].payload
        assert isinstance(env, EnvironmentSpecPayload)
        runtime_label = (
            f"Runtime {env.runtime_profile}/{env.delivery_kind} at {env.runtime_locator}; "
            f"environment ref {adapter.preferred_environment_ref}; "
            f"healthcheck commands {', '.join(evidence.healthcheck_commands)}; "
            f"verification refs {', '.join(runtime_refs)}."
        )
        gui_text = (
            f" GUI state {env.gui_capability_state}; "
            f"default GUI session {env.default_gui_session_ref}; "
            "control provider noVNC via OpenClaw browser."
            if env.default_gui_session_ref
            else f" GUI state {env.gui_capability_state}."
        )
        alias_text = (
            f" Aliases: {', '.join(payload.alias_names)}."
            if payload.alias_names
            else ""
        )
        substitution_text = (
            f" Substitution: {payload.substitution_note}."
            if payload.substitution_note
            else ""
        )
        gating_text = ""
        if runtime_refs:
            gating_reports = [
                self.verification_reports[runtime_ref].payload
                for runtime_ref in runtime_refs
                if runtime_ref in self.verification_reports
            ]
            non_pass = [
                report
                for report in gating_reports
                if isinstance(report, VerificationReportPayload)
                and report.outcome is not VerificationOutcome.PASS
            ]
            if non_pass:
                gating_text = f" Runtime gate: {non_pass[0].reasons[0]}."
        if role == "general":
            return (
                f"{payload.tool_name}: solves {', '.join(payload.scope.solves)}. "
                f"Best for {', '.join(payload.best_for)}. "
                f"Avoid {', '.join(payload.scope.not_for)}. "
                f"{runtime_label}{gui_text}{alias_text}{substitution_text}{gating_text}"
            )
        if role == "coder":
            object_names = ", ".join(obj.name for obj in payload.core_objects)
            input_names = ", ".join(item.name for item in adapter.typed_inputs)
            return (
                f"{payload.tool_name}: use {object_names}. "
                f"Adapter {adapter.callable_interface.entrypoint} takes {input_names}. "
                f"Launcher {adapter.launcher_ref}. "
                f"Recipe {recipe.title} follows {', '.join(recipe.implementation_pattern)}. "
                f"{runtime_label}{gui_text}{alias_text}{substitution_text}{gating_text}"
            )
        return (
            f"{payload.tool_name}: review {', '.join(evidence.smoke_tests)}. "
            f"Checklist {', '.join(evidence.reviewer_checklist)}. "
            f"Watch anti-patterns {', '.join(payload.anti_patterns)}. "
            f"Healthcheck commands {', '.join(evidence.healthcheck_commands)}. "
            f"{runtime_label}{gui_text}{alias_text}{substitution_text}{gating_text}"
        )


def load_knowledge_pool(root: Path | None = None) -> KnowledgePoolCatalog:
    return KnowledgePoolCatalog.load(root=root)


def load_minutes_inventory(root: Path | None = None) -> dict[str, Any]:
    catalog = load_knowledge_pool(root=root)
    return catalog.minutes_inventory


def resolve_stack(
    problem_spec: dict[str, Any],
    project_constraints: dict[str, Any],
) -> list[RankedCandidate]:
    return load_knowledge_pool().resolve_stack(problem_spec, project_constraints)


def lookup_knowledge_packs(
    query: str,
    *,
    include_runtime_gated: bool = False,
) -> list[PackLookupHit]:
    return load_knowledge_pool().lookup_knowledge_packs(
        query,
        include_runtime_gated=include_runtime_gated,
    )


def resolve_runtime(
    module_or_adapter_ref: str,
    host_profile: dict[str, Any] | None = None,
) -> EnvironmentSpecPayload:
    return load_knowledge_pool().resolve_runtime(module_or_adapter_ref, host_profile)


def verify_runtime(environment_ref: str) -> VerificationReportPayload:
    return load_knowledge_pool().verify_runtime(environment_ref)


def resolve_gui_session(
    module_or_environment_ref: str,
    host_profile: dict[str, Any] | None = None,
) -> GuiSessionSpecPayload:
    return load_knowledge_pool().resolve_gui_session(module_or_environment_ref, host_profile)


def launch_gui_session(
    gui_session_ref: str,
    launch_profile: dict[str, Any] | None = None,
) -> GuiSessionHandle:
    return load_knowledge_pool().launch_gui_session(gui_session_ref, launch_profile)


def close_gui_session(container_id_or_name: str) -> None:
    return load_knowledge_pool().close_gui_session(container_id_or_name)


def verify_gui_session(gui_session_ref: str) -> VerificationReportPayload:
    return load_knowledge_pool().verify_gui_session(gui_session_ref)


def compile_role_context(
    role: str,
    candidate_refs: list[str],
    task_class: str,
    project_constraints: dict[str, Any],
) -> RoleContextBundlePayload:
    return load_knowledge_pool().compile_role_context(
        role=role,
        candidate_refs=candidate_refs,
        task_class=task_class,
        project_constraints=project_constraints,
    )


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for path in [here, *here.parents]:
        if (path / "knowledge").exists() and (path / "services" / "response-control-framework" / "schemas" / "control-plane" / "v1").exists():
            return path
    raise RuntimeError("Could not locate repo root for knowledge pool")


def resolve_engineering_knowledge_pool_root(root: Path | None = None) -> Path:
    """Return the engineering ``coding-tools`` directory (packaged or legacy repo layout).

    Search order matches the historical ``KnowledgePoolCatalog.load`` behavior: explicit
    ``root`` if it exists, then packaged domain-engineering data, then repo
    ``knowledge/coding-tools``. If none exist, returns ``root`` or the legacy repo path
    for clearer downstream errors.

    Parameters
    ----------
    root
        Optional explicit directory (used when tests or callers pin a temp tree).

    Returns
    -------
    pathlib.Path
        Resolved knowledge pool root directory.
    """
    repo_root = _repo_root()
    candidate_roots: list[Path | None] = [
        root,
        repo_root
        / "services"
        / "domain-engineering"
        / "src"
        / "domain_engineering"
        / "data"
        / "coding-tools",
        repo_root / "knowledge" / "coding-tools",
    ]
    resolved = next((r for r in candidate_roots if r is not None and r.exists()), None)
    if resolved is not None:
        return resolved
    return root if root is not None else repo_root / "knowledge" / "coding-tools"


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    return path if path.is_absolute() else (_repo_root() / path).resolve()


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _artifact_ref_for(
    artifact_type: ArtifactType,
    payload: dict[str, Any],
) -> str:
    if artifact_type is ArtifactType.KNOWLEDGE_PACK:
        return f"artifact://knowledge-pack/{payload['tool_id']}"
    if artifact_type is ArtifactType.RECIPE_OBJECT:
        return f"artifact://recipe-object/{payload['recipe_id']}"
    if artifact_type is ArtifactType.EXECUTION_ADAPTER_SPEC:
        return f"artifact://execution-adapter-spec/{payload['adapter_spec_id']}"
    if artifact_type is ArtifactType.EVIDENCE_BUNDLE:
        return f"artifact://evidence-bundle/{payload['evidence_bundle_id']}"
    if artifact_type is ArtifactType.ROLE_CONTEXT_BUNDLE:
        return f"artifact://role-context-bundle/{payload['role_context_bundle_id']}"
    if artifact_type is ArtifactType.ENVIRONMENT_SPEC:
        return f"artifact://environment-spec/{payload['environment_spec_id']}"
    if artifact_type is ArtifactType.GUI_SESSION_SPEC:
        return f"artifact://gui-session-spec/{payload['gui_session_spec_id']}"
    if artifact_type is ArtifactType.VERIFICATION_REPORT:
        return f"artifact://verification-report/{payload['verification_report_id']}"
    if artifact_type is ArtifactType.DECISION_LOG:
        return f"artifact://decision-log/{payload['decision_id']}"
    raise ValueError(f"Unsupported artifact type for knowledge pool: {artifact_type}")


def _load_artifact_record(item: dict[str, Any], file_path: Path) -> LoadedArtifact:
    validate_typed_artifact_json(item)
    record = TypedArtifactRecord.model_validate(item)
    payload = _validate_payload(record.artifact_type, record.payload)
    ref = _artifact_ref_for(record.artifact_type, record.payload)
    return LoadedArtifact(ref=ref, file_path=file_path, record=record, payload=payload)


def _validate_payload(
    artifact_type: ArtifactType,
    payload: dict[str, Any],
) -> (
    KnowledgePackPayload
    | RecipeObjectPayload
    | ExecutionAdapterSpecPayload
    | EvidenceBundlePayload
    | GuiSessionSpecPayload
    | RoleContextBundlePayload
    | DecisionLogPayload
    | EnvironmentSpecPayload
    | VerificationReportPayload
):
    validators: dict[ArtifactType, PayloadValidator] = {
        ArtifactType.KNOWLEDGE_PACK: validate_knowledge_pack_json,
        ArtifactType.RECIPE_OBJECT: validate_recipe_object_json,
        ArtifactType.EXECUTION_ADAPTER_SPEC: validate_execution_adapter_spec_json,
        ArtifactType.EVIDENCE_BUNDLE: validate_evidence_bundle_json,
        ArtifactType.GUI_SESSION_SPEC: validate_gui_session_spec_json,
        ArtifactType.ROLE_CONTEXT_BUNDLE: validate_role_context_bundle_json,
        ArtifactType.ENVIRONMENT_SPEC: validate_environment_spec_json,
        ArtifactType.VERIFICATION_REPORT: validate_verification_report_json,
        ArtifactType.DECISION_LOG: validate_decision_log_json,
    }
    validator = validators.get(artifact_type)
    if validator is None:
        raise ValueError(f"Artifact type {artifact_type} is not supported by the knowledge pool")
    return validator(payload)


def _check_refs_exist(
    *,
    artifacts: dict[str, LoadedArtifact],
    refs: list[str],
    allowed_types: tuple[ArtifactType, ...],
    source_ref: str,
    field_name: str,
) -> list[str]:
    errors: list[str] = []
    for ref in refs:
        artifact = artifacts.get(ref)
        if artifact is None:
            errors.append(f"{source_ref} -> {field_name} missing ref {ref}")
            continue
        if artifact.record.artifact_type not in allowed_types:
            allowed = ", ".join(item.value for item in allowed_types)
            errors.append(
                f"{source_ref} -> {field_name} ref {ref} expected types [{allowed}] "
                f"but found {artifact.record.artifact_type.value}"
            )
    return errors


def _artifact_sha256(artifact: LoadedArtifact) -> str:
    canonical = json.dumps(
        artifact.record.model_dump(mode="json", by_alias=True),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _current_platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "darwin-arm64"
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux-amd64"
    return f"{system}-{machine}"


def _tokenize_structure(value: Any) -> set[str]:
    tokens: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            tokens |= _tokenize_structure(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            tokens |= _tokenize_structure(item)
    elif value is not None:
        tokens |= _tokenize_text(str(value))
    return tokens


def _tokenize_text(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-zA-Z0-9#+._-]+", text.lower()) if token}


def _normalize_binding(binding: str) -> str:
    lowered = binding.lower()
    return {
        "c++": "c++",
        "cpp": "c++",
        "c#": "c#",
        ".net": "dotnet",
        "dotnet": "dotnet",
        "python": "python",
        "fortran": "fortran",
        "cli": "cli",
        "mpi": "mpi",
    }.get(lowered, lowered)


def _value_has_unit(value: Any) -> bool:
    if isinstance(value, dict):
        if {"value", "unit"} <= set(value.keys()):
            return True
        return any(_value_has_unit(item) for item in value.values())
    if isinstance(value, list):
        return any(_value_has_unit(item) for item in value)
    return False
