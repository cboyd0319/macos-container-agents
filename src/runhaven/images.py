from __future__ import annotations

import hashlib
import shlex
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from .plans import validate_image_reference
from .profiles import AgentProfile

RUNHAVEN_PROFILE_LABEL = "org.runhaven.profile"
RUNHAVEN_SOURCE_DIGEST_LABEL = "org.runhaven.source-sha256"


@dataclass(frozen=True)
class ImageBuildPlan:
    command: tuple[str, ...]
    context: Path
    containerfile: Path
    tag: str

    def shell_command(self) -> str:
        return shlex.join(self.command)


def build_image_plan(profile: AgentProfile, *, tag: str | None = None) -> ImageBuildPlan:
    if profile.image_context is None:
        raise ValueError(f"agent {profile.name!r} does not have a bundled image template")

    context = files("runhaven").joinpath("images")
    context_path = Path(str(context))
    containerfile = context_path / profile.image_context / "Containerfile"
    if not containerfile.exists():
        raise ValueError(f"missing bundled Containerfile for agent {profile.name!r}")

    image_tag = tag or profile.image
    validate_image_reference(image_tag, "image tag")
    source_digest = image_source_digest(profile)
    command = (
        "container",
        "build",
        "-t",
        image_tag,
        "--label",
        f"{RUNHAVEN_PROFILE_LABEL}={profile.name}",
        "--label",
        f"{RUNHAVEN_SOURCE_DIGEST_LABEL}={source_digest}",
        "-f",
        str(containerfile),
        str(context_path),
    )
    return ImageBuildPlan(
        command=command,
        context=context_path,
        containerfile=containerfile,
        tag=image_tag,
    )


def image_source_digest(profile: AgentProfile) -> str:
    digest = hashlib.sha256()
    context_path = image_context_root()
    for path in image_source_files(profile):
        relative_path = path.relative_to(context_path).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def image_source_files(profile: AgentProfile) -> tuple[Path, ...]:
    if profile.image_context is None:
        raise ValueError(f"agent {profile.name!r} does not have a bundled image template")

    context_path = image_context_root()
    source_roots = (
        context_path / "common",
        context_path / profile.image_context,
    )
    files_by_path: dict[Path, Path] = {}
    for path in walk_existing_files(source_roots):
        files_by_path[path.resolve()] = path
    return tuple(files_by_path[key] for key in sorted(files_by_path))


def image_context_root() -> Path:
    return Path(str(files("runhaven").joinpath("images")))


def walk_existing_files(paths: Iterable[Path]) -> tuple[Path, ...]:
    found: list[Path] = []
    for path in paths:
        if path.is_file():
            found.append(path)
        elif path.is_dir():
            found.extend(child for child in path.rglob("*") if child.is_file())
    return tuple(found)
