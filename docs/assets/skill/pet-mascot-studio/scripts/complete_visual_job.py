#!/usr/bin/env python3
"""Copy a selected visual output into a pet run and mark the job complete."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


CANONICAL_BASE = Path("references/canonical-base.png")


def image_metadata(path: Path) -> dict[str, object]:
    with Image.open(path) as opened:
        opened.verify()
    with Image.open(path) as opened:
        return {
            "width": opened.width,
            "height": opened.height,
            "mode": opened.mode,
            "format": opened.format,
        }


def find_job(manifest: dict[str, object], job_id: str) -> dict[str, object]:
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise SystemExit("invalid imagegen-jobs.json: jobs must be a list")
    for job in jobs:
        if isinstance(job, dict) and job.get("id") == job_id:
            return job
    raise SystemExit(f"unknown job id: {job_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--source", required=True, help="Selected generated PNG/WebP output.")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Refuse to overwrite an existing decoded output.",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    source = Path(args.source).expanduser().resolve()
    manifest_path = run_dir / "imagegen-jobs.json"
    if not manifest_path.is_file():
        raise SystemExit(f"missing job manifest: {manifest_path}")
    if not source.is_file():
        raise SystemExit(f"selected source does not exist: {source}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    job = find_job(manifest, args.job_id)
    output_path_raw = job.get("output_path")
    if not isinstance(output_path_raw, str) or not output_path_raw:
        raise SystemExit(f"job {args.job_id} has no output_path")
    output = run_dir / output_path_raw
    if output.exists() and args.keep_existing:
        raise SystemExit(f"decoded output already exists: {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    metadata = image_metadata(output)

    now = datetime.now(timezone.utc).isoformat()
    job["status"] = "complete"
    job["source_path"] = str(source)
    job["completed_at"] = now
    job["metadata"] = metadata
    for key in ["last_error", "repair_reason", "queued_at"]:
        job.pop(key, None)

    canonical = None
    if args.job_id == "base":
        canonical = run_dir / CANONICAL_BASE
        canonical.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, canonical)

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "job_id": args.job_id,
                "source": str(source),
                "output": str(output),
                "canonical_base": str(canonical) if canonical else None,
                "metadata": metadata,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
