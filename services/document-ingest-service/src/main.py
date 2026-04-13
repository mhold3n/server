import os
import time
import asyncio
import traceback
from pathlib import Path
from typing import Optional

import httpx
import structlog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = structlog.get_logger()

INPUT_DIR = Path(os.getenv("INPUT_DIR", "/documents"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/processed"))
ERROR_WEBHOOK_URL = os.getenv("ERROR_WEBHOOK_URL", "").strip() or None


def report_error(message: str, exc: Optional[BaseException] = None):
    logger.error("marker_error", message=message, error=str(exc) if exc else None)
    if ERROR_WEBHOOK_URL:
        try:
            payload = {
                "source": "marker-watcher",
                "message": message,
                "error": str(exc) if exc else None,
                "trace": traceback.format_exc() if exc else None,
            }
            # Fire and forget
            asyncio.get_event_loop().create_task(async_post(payload))
        except Exception:  # pragma: no cover
            pass


async def async_post(payload):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(ERROR_WEBHOOK_URL, json=payload)
    except Exception:
        pass


def safe_stem(p: Path) -> str:
    return p.stem.replace(" ", "_")


def process_pdf(input_pdf: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    out_md = output_dir / f"{safe_stem(input_pdf)}.md"
    out_txt = output_dir / f"{safe_stem(input_pdf)}.txt"

    # Skip if already processed and newer than input
    if out_md.exists() and out_md.stat().st_mtime >= input_pdf.stat().st_mtime:
        logger.info("already_processed", file=str(input_pdf))
        return

    try:
        # Prefer marker-pdf if available
        try:
            import importlib

            importlib.import_module("marker")
            # Some marker distributions use command-line; fallback to shell call
            # Try: marker --output-format markdown input.pdf
            import subprocess

            cmd = [
                "python",
                "-m",
                "marker",
                "--output-format",
                "markdown",
                str(input_pdf),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout:
                out_md.write_text(res.stdout, encoding="utf-8")
                logger.info("marker_success", file=str(input_pdf), output=str(out_md))
                return
            else:
                logger.warning(
                    "marker_cli_failed",
                    file=str(input_pdf),
                    code=res.returncode,
                    stderr=res.stderr[-4000:] if res.stderr else None,
                )
        except Exception as e:
            logger.warning("marker_unavailable", file=str(input_pdf), error=str(e))

        # Fallback: extract text with PyMuPDF, else pdfminer
        try:
            import fitz  # PyMuPDF

            text_chunks = []
            with fitz.open(str(input_pdf)) as doc:
                for page in doc:
                    text_chunks.append(page.get_text("text"))
            text = "\n\n".join(text_chunks)
            out_txt.write_text(text, encoding="utf-8")
            logger.info("pymupdf_success", file=str(input_pdf), output=str(out_txt))
            return
        except Exception as e:
            logger.warning("pymupdf_failed", file=str(input_pdf), error=str(e))

        from pdfminer.high_level import extract_text

        text = extract_text(str(input_pdf))
        out_txt.write_text(text, encoding="utf-8")
        logger.info("pdfminer_success", file=str(input_pdf), output=str(out_txt))
    except Exception as e:
        report_error(f"Failed to process {input_pdf}", e)


class PDFHandler(FileSystemEventHandler):
    def on_created(self, event):  # pragma: no cover
        self._maybe_process(event)

    def on_modified(self, event):  # pragma: no cover
        self._maybe_process(event)

    def _maybe_process(self, event):
        try:
            if event.is_directory:
                return
            path = Path(event.src_path)
            if path.suffix.lower() != ".pdf":
                return
            # Wait for file to finish writing
            time.sleep(2)
            rel = (
                path.relative_to(INPUT_DIR) if INPUT_DIR in path.parents else path.name
            )
            out_dir = OUTPUT_DIR / (rel.parent if isinstance(rel, Path) else "")
            process_pdf(path, out_dir)
        except Exception as e:
            report_error(f"Watcher failed on event: {event}", e)


def initial_scan():
    for pdf in INPUT_DIR.rglob("*.pdf"):
        try:
            rel = pdf.relative_to(INPUT_DIR)
            out_dir = OUTPUT_DIR / rel.parent
            process_pdf(pdf, out_dir)
        except Exception as e:
            report_error(f"Initial scan failed for {pdf}", e)


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    handler = PDFHandler()
    observer = Observer()
    observer.schedule(handler, str(INPUT_DIR), recursive=True)
    observer.start()
    try:
        initial_scan()
        while True:
            time.sleep(5)
    except KeyboardInterrupt:  # pragma: no cover
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
