from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def check_npm_package(root: Path, relative: str, pins: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    package_path = root / relative / "package.json"
    lock_path = root / relative / "package-lock.json"
    package_json = json.loads(package_path.read_text(encoding="utf-8"))
    lock_json = json.loads(lock_path.read_text(encoding="utf-8"))
    agent_versions = {
        "src/runhaven/images/claude": (
            "@anthropic-ai/claude-code",
            pins["agent_cli"]["claude_code"],
            pins["agent_cli_integrity"]["claude_code"],
        ),
        "src/runhaven/images/codex": (
            "@openai/codex",
            pins["agent_cli"]["codex"],
            pins["agent_cli_integrity"]["codex"],
        ),
        "src/runhaven/images/gemini": (
            "@google/gemini-cli",
            pins["agent_cli"]["gemini_cli"],
            pins["agent_cli_integrity"]["gemini_cli"],
        ),
        "src/runhaven/images/copilot": (
            "@github/copilot",
            pins["agent_cli"]["copilot_cli"],
            pins["agent_cli_integrity"]["copilot_cli"],
        ),
    }
    if relative not in agent_versions:
        return [f"{relative}: missing agent package pins.toml ledger entry"]
    root_name, root_version, root_integrity = agent_versions[relative]

    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, version in package_json.get(section, {}).items():
            if not is_exact_npm_version(version):
                failures.append(f"{relative}/package.json: {name} is not exact-pinned")
    if package_json.get("dependencies", {}).get(root_name) != root_version:
        failures.append(f"{relative}/package.json: {root_name} does not match pins.toml")

    allow_scripts = package_json.get("allowScripts", {})
    for name, allowed in allow_scripts.items():
        if allowed is not True:
            failures.append(
                f"{relative}/package.json: {name} install script is not explicitly allowed"
            )
        if "@" not in name.lstrip("@"):
            failures.append(
                f"{relative}/package.json: {name} install script approval is not pinned"
            )

    packages = lock_json.get("packages", {})
    for path, details in packages.items():
        if path == "":
            continue
        if not isinstance(details, dict):
            failures.append(f"{relative}/package-lock.json: invalid package entry {path}")
            continue
        name = npm_package_name(path, details)
        version = details.get("version")
        resolved = details.get("resolved")
        integrity = details.get("integrity")
        if not isinstance(version, str) or not version:
            failures.append(f"{relative}/package-lock.json: {name} missing version")
        if not isinstance(resolved, str) or not resolved.startswith("https://registry.npmjs.org/"):
            failures.append(f"{relative}/package-lock.json: {name} missing registry tarball")
        if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
            failures.append(f"{relative}/package-lock.json: {name} missing sha512 integrity")
        if path == f"node_modules/{root_name}" and integrity != root_integrity:
            failures.append(
                f"{relative}/package-lock.json: {name} integrity differs from pins.toml"
            )
        if details.get("hasInstallScript") is True:
            approval = f"{name}@{version}"
            if allow_scripts.get(approval) is not True:
                failures.append(
                    f"{relative}/package.json: missing allowScripts approval for {approval}"
                )

    return failures


def is_exact_npm_version(value: Any) -> bool:
    return (
        isinstance(value, str)
        and re.match(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$", value) is not None
    )


def npm_package_name(path: str, details: dict[str, Any]) -> str:
    name = details.get("name")
    if isinstance(name, str):
        return name
    prefix = "node_modules/"
    if not path.startswith(prefix):
        return path
    remainder = path[len(prefix) :]
    parts = remainder.split("/")
    if remainder.startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]
