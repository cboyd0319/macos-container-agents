#!/usr/bin/env python3
"""Run deterministic frame extraction, atlas composition, validation, and QA media."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROW_FRAME_COUNTS = {
    "idle": 6,
    "running-right": 8,
    "running-left": 8,
    "waving": 4,
    "jumping": 5,
    "failed": 8,
    "waiting": 6,
    "running": 6,
    "review": 6,
}


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def parse_states(raw: str) -> list[str]:
    if not raw.strip():
        return []
    states = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = sorted(set(states) - set(ROW_FRAME_COUNTS))
    if unknown:
        raise SystemExit(f"unknown stable-slots state(s): {', '.join(unknown)}")
    return states


def rewrite_manifest_paths(frames_root: Path, stable_states: list[str]) -> None:
    manifest_path = frames_root / "frames-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest.get("rows")
    if not isinstance(rows, list):
        raise SystemExit(f"invalid frames manifest: {manifest_path}")
    stable_set = set(stable_states)
    for row in rows:
        if not isinstance(row, dict) or row.get("state") not in stable_set:
            continue
        state = str(row["state"])
        row["method"] = "stable-slots"
        row["frames"] = [
            str(frames_root / state / f"{index:02d}.png")
            for index in range(ROW_FRAME_COUNTS[state])
        ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--stable-slots",
        default="",
        help="Comma-separated rows to re-extract with stable-slots after auto extraction.",
    )
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    decoded_dir = run_dir / "decoded"
    if not decoded_dir.is_dir():
        raise SystemExit(f"missing decoded row directory: {decoded_dir}")

    stable_states = parse_states(args.stable_slots)
    frames = run_dir / "frames"
    qa = run_dir / "qa"
    final = run_dir / "final"
    previews = qa / "previews"
    temp_stable = run_dir / "frames-stable-slots"

    for path in [
        frames,
        temp_stable,
        previews,
        qa / "review.json",
        final / "spritesheet.png",
        final / "spritesheet.webp",
        final / "validation.json",
        qa / "contact-sheet.png",
    ]:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    qa.mkdir(parents=True, exist_ok=True)
    final.mkdir(parents=True, exist_ok=True)

    scripts = script_dir()
    run(
        [
            args.python,
            str(scripts / "extract_strip_frames.py"),
            "--decoded-dir",
            str(decoded_dir),
            "--output-dir",
            str(frames),
            "--states",
            "all",
            "--method",
            "auto",
        ]
    )

    for state in stable_states:
        run(
            [
                args.python,
                str(scripts / "extract_strip_frames.py"),
                "--decoded-dir",
                str(decoded_dir),
                "--output-dir",
                str(temp_stable),
                "--states",
                state,
                "--method",
                "stable-slots",
            ]
        )
        shutil.rmtree(frames / state)
        shutil.copytree(temp_stable / state, frames / state)
    if stable_states:
        rewrite_manifest_paths(frames, stable_states)

    inspect_command = [
        args.python,
        str(scripts / "inspect_frames.py"),
        "--frames-root",
        str(frames),
        "--json-out",
        str(qa / "review.json"),
        "--require-components",
    ]
    if stable_states:
        inspect_command.append("--allow-stable-slots")
    run(inspect_command)

    run(
        [
            args.python,
            str(scripts / "compose_atlas.py"),
            "--frames-root",
            str(frames),
            "--output",
            str(final / "spritesheet.png"),
            "--webp-output",
            str(final / "spritesheet.webp"),
        ]
    )
    run(
        [
            args.python,
            str(scripts / "validate_atlas.py"),
            str(final / "spritesheet.webp"),
            "--json-out",
            str(final / "validation.json"),
        ]
    )
    run(
        [
            args.python,
            str(scripts / "make_contact_sheet.py"),
            str(final / "spritesheet.webp"),
            "--output",
            str(qa / "contact-sheet.png"),
        ]
    )
    run(
        [
            args.python,
            str(scripts / "render_animation_previews.py"),
            "--frames-root",
            str(frames),
            "--output-dir",
            str(previews),
        ]
    )

    print(
        json.dumps(
            {
                "ok": True,
                "run_dir": str(run_dir),
                "spritesheet": str(final / "spritesheet.webp"),
                "validation": str(final / "validation.json"),
                "review": str(qa / "review.json"),
                "contact_sheet": str(qa / "contact-sheet.png"),
                "previews": str(previews),
                "stable_slots": stable_states,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
