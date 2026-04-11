#!/usr/bin/env python3
"""Promote queued Phase 3 packages by runtime wave."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_coding_tool_knowledge_pool as seed


LOG_ROOT = REPO_ROOT / ".cache" / "knowledge-runtime-logs"
ACTIVE_STATUSES = {"queued", "smoke_verified"}
RESUME_STATUSES = ACTIVE_STATUSES | {"blocked_runtime", "blocked_smoke"}
TERMINAL_FAILURE_STATUSES = {"blocked_runtime", "blocked_smoke", "blocked_external"}

PHASE3B_WAVES = [
    {
        "id": "wave01_ipopt_onemkl",
        "runtime_refs": ["artifact://environment-spec/eng_ipopt_onemkl_docker"],
        "module_slugs": ["ipopt", "ma57", "ma77", "ma86", "ma97", "pardiso", "pyoptsparse"],
    },
    {
        "id": "wave02_petsc_family",
        "runtime_refs": ["artifact://environment-spec/eng_petsc_family_docker"],
        "module_slugs": ["petsc", "petsc_ksp", "petsc_gamg", "hypre", "primme", "slepc", "petsc4py"],
    },
    {
        "id": "wave03_sparse_direct",
        "runtime_refs": [
            "artifact://environment-spec/eng_sparse_direct_family_docker",
            "artifact://environment-spec/eng_strumpack_docker",
        ],
        "module_slugs": ["mumps", "superlu", "superlu_dist", "suitesparse", "cholmod", "umfpack", "klu", "strumpack"],
    },
    {
        "id": "wave04_trilinos_family",
        "runtime_refs": ["artifact://environment-spec/eng_trilinos_family_docker"],
        "module_slugs": ["trilinos", "trilinos_belos", "trilinos_ifpack2", "trilinos_muelu"],
    },
    {
        "id": "wave05_openmodelica_and_system",
        "runtime_refs": [
            "artifact://environment-spec/eng_openmodelica_docker",
            "artifact://environment-spec/eng_system_docker",
            "artifact://environment-spec/eng_system_uv",
        ],
        "module_slugs": ["openmodelica", "modelica_standard_library", "pyfmi", "ompython", "pyphs"],
    },
    {
        "id": "wave06_openfoam_calculix_precice",
        "runtime_refs": [
            "artifact://environment-spec/eng_backbone_docker",
            "artifact://environment-spec/eng_openfoam_docker",
            "artifact://environment-spec/eng_calculix_docker",
        ],
        "module_slugs": ["openfoam", "calculix", "precice"],
    },
    {
        "id": "wave07_salome_paraview",
        "runtime_refs": [
            "artifact://environment-spec/eng_salome_docker",
            "artifact://environment-spec/eng_paraview_docker",
            "artifact://environment-spec/eng_backbone_uv",
        ],
        "module_slugs": ["salome", "medcoupling", "paraview", "vtk"],
    },
    {
        "id": "wave08_geometry_native",
        "runtime_refs": ["artifact://environment-spec/eng_geometry_native_family_docker"],
        "module_slugs": ["cgal", "opencamlib"],
    },
    {
        "id": "wave09_nlp_time_chem",
        "runtime_refs": [
            "artifact://environment-spec/eng_nlp_time_chem_family_docker",
            "artifact://environment-spec/eng_tchem_docker",
        ],
        "module_slugs": ["sundials", "tchem"],
    },
    {
        "id": "wave10_independent_docker_roots",
        "runtime_refs": [
            "artifact://environment-spec/eng_su2_docker",
            "artifact://environment-spec/eng_code_aster_docker",
            "artifact://environment-spec/eng_code_saturne_docker",
            "artifact://environment-spec/eng_openwam_docker",
            "artifact://environment-spec/eng_opensmokepp_docker",
            "artifact://environment-spec/eng_dakota_docker",
            "artifact://environment-spec/eng_kratos_multiphysics_docker",
            "artifact://environment-spec/eng_moose_docker",
            "artifact://environment-spec/eng_fenicsx_docker",
            "artifact://environment-spec/eng_dealii_docker",
            "artifact://environment-spec/eng_hermes_docker",
            "artifact://environment-spec/eng_project_chrono_docker",
            "artifact://environment-spec/eng_mbdyn_docker",
        ],
        "module_slugs": [
            "su2",
            "code_aster",
            "code_saturne",
            "openwam",
            "opensmokepp",
            "dakota",
            "kratos_multiphysics",
            "moose",
            "fenicsx",
            "dealii",
            "hermes",
            "project_chrono",
            "mbdyn",
        ],
    },
    {
        "id": "wave11_independent_uv_leaves",
        "runtime_refs": [
            "artifact://environment-spec/eng_structures_uv",
            "artifact://environment-spec/eng_thermochem_uv",
            "artifact://environment-spec/eng_rmg_py_docker",
        ],
        "module_slugs": ["porepy", "rmg_py"],
    },
]


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    log_path: Path

    @property
    def summary(self) -> str:
        detail = (self.stderr or self.stdout).strip()
        if not detail:
            detail = f"command exited with {self.returncode}"
        return detail.splitlines()[0]


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower()


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _verification_report_id_from_ref(report_ref: str) -> str:
    return report_ref.split("/", 3)[-1]


def _environment_spec_id_from_ref(environment_ref: str) -> str:
    return environment_ref.split("/", 3)[-1]


def _artifact_slug(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _verification_index(reports: list[dict]) -> dict[str, int]:
    index: dict[str, int] = {}
    for offset, record in enumerate(reports):
        payload = record.get("payload", {})
        report_id = payload.get("verification_report_id")
        if isinstance(report_id, str):
            index[report_id] = offset
    return index


def _set_verification_report(
    reports: list[dict],
    *,
    report_id: str,
    payload: dict[str, object],
    input_refs: list[str],
) -> None:
    index = _verification_index(reports)
    if report_id in index:
        record = reports[index[report_id]]
        record["payload"] = payload
        record["updated_at"] = _utcnow()
        record["input_artifact_refs"] = input_refs
        return
    reports.append(
        seed.typed_record(
            "verification-report",
            "VERIFICATION_REPORT",
            report_id,
            payload,
            input_refs,
        )
    )


def _run_shell(command: str, log_path: Path) -> CommandResult:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    body = [
        f"$ {command}",
        "",
        f"exit_code={result.returncode}",
        "",
        "[stdout]",
        result.stdout,
        "",
        "[stderr]",
        result.stderr,
    ]
    log_path.write_text("\n".join(body), encoding="utf-8")
    return CommandResult(
        command=command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        log_path=log_path,
    )


def _build_env_pass_payload(environment_ref: str, detail: str) -> dict[str, object]:
    report_id = seed.verification_payload_id(_environment_spec_id_from_ref(environment_ref))
    return {
        "verification_report_id": report_id,
        "schema_version": "1.0.0",
        "outcome": "PASS",
        "reasons": ["Runtime health check passed during Phase 3B queue drain."],
        "gate_results": [
            {
                "gate_id": "runtime_healthcheck",
                "gate_kind": "tests",
                "status": "PASS",
                "detail": detail or "Runtime health check passed.",
                "artifact_ref": environment_ref,
            }
        ],
        "recommended_next_action": "accept_runtime_environment",
        "validated_artifact_refs": [environment_ref],
        "created_at": _utcnow(),
    }


def _build_env_fail_payload(environment_ref: str, detail: str, *, stage: str) -> dict[str, object]:
    report_id = seed.verification_payload_id(_environment_spec_id_from_ref(environment_ref))
    return {
        "verification_report_id": report_id,
        "schema_version": "1.0.0",
        "outcome": "REWORK",
        "reasons": [detail],
        "blocking_findings": [
            {
                "code": f"phase3b_{stage}_failed",
                "severity": "high",
                "artifact_ref": environment_ref,
            }
        ],
        "gate_results": [
            {
                "gate_id": "runtime_healthcheck",
                "gate_kind": "tests",
                "status": "FAIL",
                "detail": detail,
                "remediation_hint": "Repair the runtime build or healthcheck command before retrying promotion.",
                "artifact_ref": environment_ref,
            }
        ],
        "recommended_next_action": "repair_runtime_environment",
        "validated_artifact_refs": [environment_ref],
        "created_at": _utcnow(),
    }


def _build_pack_pass_payload(entry: dict[str, object], detail: str) -> dict[str, object]:
    report_id = _verification_report_id_from_ref(str(entry["last_verification_ref"]))
    environment_ref = str(entry["canonical_runtime_ref"])
    pack_ref = str(entry["knowledge_pack_ref"])
    return {
        "verification_report_id": report_id,
        "schema_version": "1.0.0",
        "outcome": "PASS",
        "reasons": [f"{entry['module_slug']} passed package smoke verification during Phase 3B queue drain."],
        "gate_results": [
            {
                "gate_id": "phase3b_package_smoke",
                "gate_kind": "tests",
                "status": "PASS",
                "detail": detail or f"Package smoke passed for {entry['module_slug']}.",
                "artifact_ref": pack_ref,
            }
        ],
        "recommended_next_action": "accept_runtime_environment",
        "validated_artifact_refs": [environment_ref],
        "created_at": _utcnow(),
    }


def _build_pack_fail_payload(entry: dict[str, object], detail: str, *, stage: str) -> dict[str, object]:
    report_id = _verification_report_id_from_ref(str(entry["last_verification_ref"]))
    environment_ref = str(entry["canonical_runtime_ref"])
    pack_ref = str(entry["knowledge_pack_ref"])
    return {
        "verification_report_id": report_id,
        "schema_version": "1.0.0",
        "outcome": "REWORK",
        "reasons": [detail],
        "blocking_findings": [
            {
                "code": f"phase3b_{stage}_failed",
                "severity": "high",
                "artifact_ref": pack_ref,
            }
        ],
        "gate_results": [
            {
                "gate_id": f"phase3b_{stage}",
                "gate_kind": "tests",
                "status": "FAIL",
                "detail": detail,
                "remediation_hint": "Inspect the saved log, repair the runtime or smoke command, and resume promotion.",
                "artifact_ref": pack_ref,
            }
        ],
        "recommended_next_action": "repair_runtime_environment",
        "validated_artifact_refs": [environment_ref],
        "created_at": _utcnow(),
    }


def _mark_entry(
    entry: dict[str, object],
    *,
    status: str,
    attempted_at: str,
    reason: str,
    verification_ref: str,
    log_path: Path | None = None,
    failure_stage: str | None = None,
) -> None:
    entry["status"] = status
    entry["last_attempted_at"] = attempted_at
    entry["last_verification_ref"] = verification_ref
    entry["promotion_reason"] = reason
    entry["last_log_path"] = str(log_path) if log_path is not None else None
    if status == "promoted":
        entry["last_failure_stage"] = None
        entry["last_failure_summary"] = None
        return
    entry["last_failure_stage"] = failure_stage
    entry["last_failure_summary"] = reason


def _phase3_target_statuses(resume: bool) -> set[str]:
    return RESUME_STATUSES if resume else ACTIVE_STATUSES


def _selected_wave_entries(
    ledger_by_slug: dict[str, dict[str, object]],
    *,
    module_filters: set[str],
    runtime_filters: set[str],
    allowed_statuses: set[str],
) -> list[tuple[dict[str, object], list[dict[str, object]]]]:
    waves: list[tuple[dict[str, object], list[dict[str, object]]]] = []
    for wave in PHASE3B_WAVES:
        selected: list[dict[str, object]] = []
        for slug in wave["module_slugs"]:
            entry = ledger_by_slug.get(slug)
            if entry is None:
                continue
            if entry["status"] not in allowed_statuses:
                continue
            if module_filters and slug not in module_filters:
                continue
            if runtime_filters and entry["canonical_runtime_ref"] not in runtime_filters:
                continue
            selected.append(entry)
        if selected:
            waves.append((wave, selected))
    return waves


def _sync_generated_outputs() -> None:
    seed.build_seed_files()
    seed.build_compiled_contexts()


def _print_dry_run(waves: list[tuple[dict[str, object], list[dict[str, object]]]]) -> None:
    for wave, entries in waves:
        print(f"{wave['id']}:")
        print(f"  runtimes: {', '.join(wave['runtime_refs'])}")
        for entry in entries:
            print(f"  - {entry['module_slug']} [{entry['status']}] -> {entry['canonical_runtime_ref']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module-slug", action="append", default=[])
    parser.add_argument("--runtime-ref", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    allowed_statuses = _phase3_target_statuses(args.resume)
    module_filters = set(args.module_slug)
    runtime_filters = set(args.runtime_ref)

    ledger_payload = _read_json(seed.PACKAGE_COMPLETION_LEDGER_PATH)
    if not isinstance(ledger_payload, dict):
        raise ValueError("Unexpected package completion ledger format")
    ledger_entries = ledger_payload["entries"]
    ledger_by_slug = {entry["module_slug"]: entry for entry in ledger_entries}

    verification_reports = _read_json(seed.OUTPUT_ROOT / "evidence" / "verification-reports.json")
    if not isinstance(verification_reports, list):
        raise ValueError("Unexpected verification report payload")

    selected_waves = _selected_wave_entries(
        ledger_by_slug,
        module_filters=module_filters,
        runtime_filters=runtime_filters,
        allowed_statuses=allowed_statuses,
    )
    if args.dry_run:
        _print_dry_run(selected_waves)
        return 0
    if not selected_waves:
        print("No matching queued packages found.")
        return 0

    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_log_root = LOG_ROOT / run_stamp
    run_log_root.mkdir(parents=True, exist_ok=True)

    for wave_index, (wave, wave_entries) in enumerate(selected_waves, start=1):
        wave_log_root = run_log_root / f"{wave_index:02d}_{wave['id']}"
        wave_log_root.mkdir(parents=True, exist_ok=True)
        runtime_results: dict[str, tuple[bool, str, Path | None, str | None]] = {}
        entries_by_runtime: dict[str, list[dict[str, object]]] = defaultdict(list)
        for entry in wave_entries:
            entries_by_runtime[str(entry["canonical_runtime_ref"])].append(entry)

        for runtime_ref in wave["runtime_refs"]:
            runtime_entries = entries_by_runtime.get(runtime_ref, [])
            if not runtime_entries:
                continue
            runtime_slug = _slugify(runtime_ref)
            bootstrap_log = wave_log_root / f"{runtime_slug}_bootstrap.log"
            bootstrap_result = _run_shell(str(runtime_entries[0]["bootstrap_command"]), bootstrap_log)
            if bootstrap_result.returncode != 0:
                summary = f"Bootstrap failed for {runtime_ref}: {bootstrap_result.summary}"
                runtime_results[runtime_ref] = (False, summary, bootstrap_result.log_path, "bootstrap")
                env_report_id = seed.verification_payload_id(_environment_spec_id_from_ref(runtime_ref))
                _set_verification_report(
                    verification_reports,
                    report_id=env_report_id,
                    payload=_build_env_fail_payload(runtime_ref, summary, stage="bootstrap"),
                    input_refs=[runtime_ref],
                )
                continue

            healthcheck_log = wave_log_root / f"{runtime_slug}_healthcheck.log"
            healthcheck_result = _run_shell(str(runtime_entries[0]["healthcheck_command"]), healthcheck_log)
            if healthcheck_result.returncode != 0:
                summary = f"Healthcheck failed for {runtime_ref}: {healthcheck_result.summary}"
                runtime_results[runtime_ref] = (False, summary, healthcheck_result.log_path, "healthcheck")
                env_report_id = seed.verification_payload_id(_environment_spec_id_from_ref(runtime_ref))
                _set_verification_report(
                    verification_reports,
                    report_id=env_report_id,
                    payload=_build_env_fail_payload(runtime_ref, summary, stage="healthcheck"),
                    input_refs=[runtime_ref],
                )
                continue

            detail = (healthcheck_result.stdout or bootstrap_result.stdout).strip() or "Runtime health check passed."
            runtime_results[runtime_ref] = (True, detail, healthcheck_result.log_path, None)
            env_report_id = seed.verification_payload_id(_environment_spec_id_from_ref(runtime_ref))
            _set_verification_report(
                verification_reports,
                report_id=env_report_id,
                payload=_build_env_pass_payload(runtime_ref, detail),
                input_refs=[runtime_ref],
            )

        for entry in wave_entries:
            slug = str(entry["module_slug"])
            runtime_ref = str(entry["canonical_runtime_ref"])
            report_id = _verification_report_id_from_ref(str(entry["last_verification_ref"]))
            attempted_at = _utcnow()
            runtime_ok, runtime_summary, runtime_log_path, runtime_failure_stage = runtime_results.get(
                runtime_ref,
                (False, f"No runtime result captured for {runtime_ref}.", None, "healthcheck"),
            )
            if not runtime_ok:
                reason = runtime_summary
                _mark_entry(
                    entry,
                    status="blocked_runtime",
                    attempted_at=attempted_at,
                    reason=reason,
                    verification_ref=seed.artifact_ref("verification-report", report_id),
                    log_path=runtime_log_path,
                    failure_stage=runtime_failure_stage or "healthcheck",
                )
                _set_verification_report(
                    verification_reports,
                    report_id=report_id,
                    payload=_build_pack_fail_payload(entry, reason, stage=runtime_failure_stage or "healthcheck"),
                    input_refs=[str(entry["knowledge_pack_ref"]), runtime_ref],
                )
                continue

            parent_refs = list(entry.get("parent_package_refs", []))
            parent_blockers = [
                parent_ref
                for parent_ref in parent_refs
                if ledger_by_slug[_artifact_slug(parent_ref)]["status"] != "promoted"
            ]
            if parent_blockers:
                reason = (
                    f"Parent packages not promoted for {slug}: {', '.join(parent_blockers)}."
                )
                parent_log_paths = [
                    ledger_by_slug[_artifact_slug(parent_ref)].get("last_log_path")
                    for parent_ref in parent_blockers
                    if ledger_by_slug[_artifact_slug(parent_ref)].get("last_log_path")
                ]
                _mark_entry(
                    entry,
                    status="blocked_runtime",
                    attempted_at=attempted_at,
                    reason=reason,
                    verification_ref=seed.artifact_ref("verification-report", report_id),
                    log_path=Path(parent_log_paths[0]) if parent_log_paths else runtime_log_path,
                    failure_stage="promotion",
                )
                _set_verification_report(
                    verification_reports,
                    report_id=report_id,
                    payload=_build_pack_fail_payload(entry, reason, stage="promotion"),
                    input_refs=[str(entry["knowledge_pack_ref"]), runtime_ref],
                )
                continue

            smoke_log = wave_log_root / f"{slug}_smoke.log"
            smoke_result = _run_shell(str(entry["smoke_command"]), smoke_log)
            if smoke_result.returncode != 0:
                reason = f"Smoke failed for {slug}: {smoke_result.summary}"
                _mark_entry(
                    entry,
                    status="blocked_smoke",
                    attempted_at=attempted_at,
                    reason=reason,
                    verification_ref=seed.artifact_ref("verification-report", report_id),
                    log_path=smoke_result.log_path,
                    failure_stage="smoke",
                )
                _set_verification_report(
                    verification_reports,
                    report_id=report_id,
                    payload=_build_pack_fail_payload(entry, reason, stage="smoke"),
                    input_refs=[str(entry["knowledge_pack_ref"]), runtime_ref],
                )
                continue

            reason = f"{slug} passed bootstrap, healthcheck, and package smoke during Phase 3B."
            _mark_entry(
                entry,
                status="promoted",
                attempted_at=attempted_at,
                reason=reason,
                verification_ref=seed.artifact_ref("verification-report", report_id),
                log_path=smoke_result.log_path,
            )
            _set_verification_report(
                verification_reports,
                report_id=report_id,
                payload=_build_pack_pass_payload(entry, smoke_result.stdout.strip()),
                input_refs=[str(entry["knowledge_pack_ref"]), runtime_ref],
            )

        _write_json(seed.PACKAGE_COMPLETION_LEDGER_PATH, ledger_payload)
        _write_json(seed.OUTPUT_ROOT / "evidence" / "verification-reports.json", verification_reports)
        _sync_generated_outputs()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
