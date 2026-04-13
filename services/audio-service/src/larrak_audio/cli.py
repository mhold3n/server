from __future__ import annotations

import argparse
import json
import sys

from larrak_audio.batch_run import run_test_files
from larrak_audio.config import load_audiobook_config
from larrak_audio.index_meili import MeiliClient
from larrak_audio.pipeline import build_source, ingest_source, source_paths
from larrak_audio.preflight import ensure_marker_ready, run_doctor
from larrak_audio.queue import JobQueue
from larrak_audio.service import run_api
from larrak_audio.utils import infer_source_type
from larrak_audio.worker import run_worker_loop, run_worker_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Larrak Audio local pipeline CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_doctor = sub.add_parser("doctor", help="Validate local dependencies and services")
    p_doctor.add_argument("--skip-services", action="store_true")

    p_ingest = sub.add_parser("ingest", help="Ingest source into markdown + manifests")
    p_ingest.add_argument("--source", required=True)
    p_ingest.add_argument("--type", choices=["pdf", "md", "txt"], default=None)
    p_ingest.add_argument(
        "--marker-extra-arg",
        action="append",
        default=[],
        help="Extra arg passed to marker binary (repeatable)",
    )

    p_build = sub.add_parser("build", help="Enhance/index/tts from source manifest")
    p_build.add_argument("--source-id", required=True)
    p_build.add_argument("--enhance", choices=["on", "off"], default="on")

    p_run_test_files = sub.add_parser(
        "run-test-files", help="Run ingest+build for files in a directory"
    )
    p_run_test_files.add_argument("--input-dir", default="test files")
    p_run_test_files.add_argument("--glob", default="*.pdf")
    p_run_test_files.add_argument("--recursive", action="store_true")
    p_run_test_files.add_argument("--enhance", choices=["on", "off"], default="on")
    p_run_test_files.add_argument(
        "--marker-extra-arg",
        action="append",
        default=[],
        help="Extra arg passed to marker binary (repeatable)",
    )
    p_run_test_files.add_argument("--summary-path", default=None)

    p_worker = sub.add_parser("worker", help="Run queued ingest/build jobs")
    p_worker.add_argument("--loop", action="store_true", help="Run forever")
    p_worker.add_argument("--interval-s", type=float, default=2.0)
    p_worker.add_argument("--max-retries", type=int, default=2)

    p_search = sub.add_parser("search", help="Search chunk index for source")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--source-id", required=True)
    p_search.add_argument("--limit", type=int, default=10)

    p_serve = sub.add_parser("serve", help="Run local REST API")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8787)

    # NOTE: Research + GUI flows are intentionally omitted from the extracted service.
    # The automation plane only needs deterministic ingest/build/doctor/run-test-files.

    args = parser.parse_args(argv)
    cfg = load_audiobook_config()

    if args.cmd == "doctor":
        report = run_doctor(cfg=cfg, check_services=not bool(args.skip_services))
        print(json.dumps(report, indent=2))
        return 0 if bool(report.get("ok")) else 1

    if args.cmd == "ingest":
        ensure_marker_ready(cfg)
        source_type = args.type or infer_source_type(args.source)
        manifest = ingest_source(
            source_path=args.source,
            source_type=source_type,
            cfg=cfg,
            marker_extra_args=list(args.marker_extra_arg),
        )
        print(
            json.dumps(
                {"source_id": manifest.source_id, "paths": source_paths(manifest.source_id, cfg)},
                indent=2,
            )
        )
        return 0

    if args.cmd == "build":
        ensure_marker_ready(cfg)
        enhance = args.enhance == "on"
        payload = build_source(source_id=args.source_id, cfg=cfg, enhance=enhance)
        print(json.dumps(payload, indent=2))
        return 0

    if args.cmd == "run-test-files":
        payload = run_test_files(
            cfg=cfg,
            input_dir=args.input_dir,
            glob_pattern=args.glob,
            recursive=bool(args.recursive),
            enhance=args.enhance == "on",
            marker_extra_args=list(args.marker_extra_arg),
            summary_path=args.summary_path,
        )
        print(json.dumps(payload, indent=2))
        return int(payload.get("exit_code", 1))

    if args.cmd == "worker":
        queue = JobQueue(cfg.queue_db)
        if args.loop:
            run_worker_loop(
                queue=queue,
                cfg=cfg,
                interval_s=args.interval_s,
                max_retries=args.max_retries,
            )
            return 0

        worked = run_worker_once(queue=queue, cfg=cfg, max_retries=args.max_retries)
        print(json.dumps({"processed": bool(worked)}, indent=2))
        return 0

    if args.cmd == "search":
        client = MeiliClient(cfg)
        result = client.search_chunks(
            query=args.query, source_id=args.source_id, limit=args.limit
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.cmd == "serve":
        run_api(host=args.host, port=args.port, cfg=cfg)
        return 0

    # Research + GUI commands were removed in the extracted service package.
    # If they are needed later, reintroduce them behind optional deps and explicit tooling.

    raise RuntimeError(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())

