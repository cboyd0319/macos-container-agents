#!/usr/bin/env python3
"""Package a validated Codex pet under ${CODEX_HOME:-$HOME/.codex}/pets."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--pet-id", help="Override pet id/folder.")
    parser.add_argument("--display-name", help="Override manifest displayName.")
    parser.add_argument("--description", help="Override manifest description.")
    parser.add_argument("--pets-root", help="Defaults to ${CODEX_HOME:-$HOME/.codex}/pets.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    request_path = run_dir / "pet_request.json"
    spritesheet = run_dir / "final" / "spritesheet.webp"
    validation = run_dir / "final" / "validation.json"
    review = run_dir / "qa" / "review.json"
    contact = run_dir / "qa" / "contact-sheet.png"
    if not request_path.is_file():
        raise SystemExit(f"missing pet request: {request_path}")
    if not spritesheet.is_file():
        raise SystemExit(f"missing final spritesheet: {spritesheet}")
    for required in [validation, review, contact]:
        if not required.is_file():
            raise SystemExit(f"missing QA artifact: {required}")

    validation_data = json.loads(validation.read_text(encoding="utf-8"))
    review_data = json.loads(review.read_text(encoding="utf-8"))
    if not validation_data.get("ok"):
        raise SystemExit(f"validation failed: {validation}")
    if not review_data.get("ok"):
        raise SystemExit(f"frame review failed: {review}")

    request = json.loads(request_path.read_text(encoding="utf-8"))
    pet_id = args.pet_id or request.get("pet_id")
    display_name = args.display_name or request.get("display_name") or pet_id
    description = args.description or request.get("description") or "A custom Codex pet."
    if not isinstance(pet_id, str) or not pet_id:
        raise SystemExit("pet id is missing; pass --pet-id")

    default_pets_root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "pets"
    pets_root = Path(args.pets_root).expanduser().resolve() if args.pets_root else default_pets_root
    pet_dir = pets_root / pet_id
    pet_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(spritesheet, pet_dir / "spritesheet.webp")
    (pet_dir / "pet.json").write_text(
        json.dumps(
            {
                "id": pet_id,
                "displayName": display_name,
                "description": description,
                "spritesheetPath": "spritesheet.webp",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {
        "ok": True,
        "run_dir": str(run_dir),
        "spritesheet": str(spritesheet),
        "validation": str(validation),
        "contact_sheet": str(contact),
        "review": str(review),
        "package": str(pet_dir),
    }
    summary_path = run_dir / "qa" / "run-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
