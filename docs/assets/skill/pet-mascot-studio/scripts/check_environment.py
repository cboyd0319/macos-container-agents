#!/usr/bin/env python3
"""Check runtime dependencies for the pet and terminal mascot scripts."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import shutil
import sys


def package_version(distribution: str, module: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        spec = importlib.util.find_spec(module)
        if spec is None:
            return None
        loaded = __import__(module)
        return getattr(loaded, "__version__", "unknown")


def module_status(distribution: str, module: str, required: bool) -> dict[str, object]:
    version = package_version(distribution, module)
    ok = version is not None
    status: dict[str, object] = {"ok": ok, "required": required}
    if version:
        status["version"] = version
    else:
        status["install_hint"] = (
            f"{sys.executable} -m pip install --user {distribution}"
        )
    return status


def tool_status(name: str) -> dict[str, object]:
    path = shutil.which(name)
    return {"ok": path is not None, "path": path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-yaml",
        action="store_true",
        help="Fail if PyYAML is missing. Use when running skill validators.",
    )
    parser.add_argument("--min-python", default="3.10")
    args = parser.parse_args()

    min_python = tuple(int(part) for part in args.min_python.split("."))
    python_ok = sys.version_info[: len(min_python)] >= min_python
    required = {
        "Pillow": module_status("Pillow", "PIL", required=True),
    }
    optional = {
        "PyYAML": module_status("PyYAML", "yaml", required=args.require_yaml),
        "jq": tool_status("jq"),
        "magick": tool_status("magick"),
    }

    ok = python_ok and all(item["ok"] for item in required.values())
    if args.require_yaml:
        ok = ok and bool(optional["PyYAML"]["ok"])

    result = {
        "ok": ok,
        "python": {
            "ok": python_ok,
            "executable": sys.executable,
            "version": platform.python_version(),
            "minimum": args.min_python,
        },
        "required": required,
        "optional": optional,
        "install_all_hint": (
            f"{sys.executable} -m pip install --user pillow pyyaml"
        ),
    }
    print(json.dumps(result, indent=2))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
