from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .active_records import read_active_run_records
from .images import (
    RUNHAVEN_SOURCE_DIGEST_LABEL,
    image_source_digest,
    image_source_files,
)
from .profiles import PROFILES, AgentProfile, get_profile
from .session_state import is_runhaven_state_volume


class ContainerRunner(Protocol):
    def __call__(
        self,
        args: tuple[str, ...],
        *,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        ...


@dataclass(frozen=True)
class LocalImage:
    names: frozenset[str]
    created_at: datetime | None
    source_digest: str | None


@dataclass(frozen=True)
class ImageDoctorEntry:
    profile: AgentProfile
    image: LocalImage | None
    current_source_digest: str
    latest_source_file: Path | None
    latest_source_updated_at: datetime | None

    @property
    def present(self) -> bool:
        return self.image is not None

    @property
    def stale(self) -> bool:
        if self.image is None:
            return False
        if self.image.source_digest is not None:
            return self.image.source_digest != self.current_source_digest
        if self.image.created_at is None or self.latest_source_updated_at is None:
            return False
        return self.latest_source_updated_at > self.image.created_at


def image_doctor(
    agent: str | None,
    *,
    require_container: Callable[[], None],
    run_container: ContainerRunner,
) -> int:
    require_container()
    local_images = list_local_images(run_container=run_container)
    state_volumes = list_state_volume_names(run_container=run_container)
    active_state_volumes = active_run_state_volumes()
    profiles = selected_profiles(agent)
    entries = tuple(
        image_doctor_entry(profile, local_images)
        for profile in profiles
    )

    print("Image doctor")
    for entry in entries:
        status = image_status(entry)
        print(f"{status} {entry.profile.name}: {entry.profile.image}")
        if not entry.present:
            print(f"fix: runhaven image rebuild {entry.profile.name}")
        elif entry.stale:
            print(f"reason: {stale_reason(entry)}")
            print(f"fix: runhaven image rebuild {entry.profile.name}")
    print_state_volume_review(
        profiles=profiles,
        state_volumes=state_volumes,
        active_state_volumes=active_state_volumes,
        agent=agent,
    )
    print_preflight_recovery(agent)
    return 0 if all(entry.present and not entry.stale for entry in entries) else 1


def selected_profiles(agent: str | None) -> tuple[AgentProfile, ...]:
    if agent is not None:
        return (get_profile(agent),)
    return tuple(PROFILES[name] for name in sorted(PROFILES))


def image_doctor_entry(
    profile: AgentProfile,
    local_images: tuple[LocalImage, ...],
) -> ImageDoctorEntry:
    local_image = find_local_image(profile.image, local_images)
    latest_file, latest_time = latest_source_update(profile)
    return ImageDoctorEntry(
        profile=profile,
        image=local_image,
        current_source_digest=image_source_digest(profile),
        latest_source_file=latest_file,
        latest_source_updated_at=latest_time,
    )


def image_status(entry: ImageDoctorEntry) -> str:
    if not entry.present:
        return "missing"
    if entry.stale:
        return "stale"
    return "ok"


def stale_reason(entry: ImageDoctorEntry) -> str:
    if entry.image is None:
        return "image is missing"
    if entry.image.source_digest is not None:
        return "bundled source digest differs from local image metadata"
    if entry.latest_source_file is not None:
        return f"template newer than local image: {entry.latest_source_file}"
    return "template newer than local image"


def find_local_image(image: str, local_images: tuple[LocalImage, ...]) -> LocalImage | None:
    candidates = set(candidate_image_names(image))
    for local_image in local_images:
        if candidates.intersection(local_image.names):
            return local_image
    return None


def candidate_image_names(image: str) -> tuple[str, ...]:
    return (image, f"docker.io/{image}")


def list_local_images(*, run_container: ContainerRunner) -> tuple[LocalImage, ...]:
    result = run_container(
        ("container", "image", "list", "--format", "json"),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("could not parse Apple container image list JSON") from exc
    if not isinstance(payload, list):
        raise ValueError("could not parse Apple container image list JSON")

    images: list[LocalImage] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        names = image_names(item)
        if not names:
            continue
        images.append(
            LocalImage(
                names=frozenset(names),
                created_at=image_created_at(item),
                source_digest=image_source_digest_label(item),
            )
        )
    return tuple(images)


def image_names(item: dict[str, object]) -> set[str]:
    names: set[str] = set()
    configuration = item.get("configuration")
    if not isinstance(configuration, dict):
        return names
    name = configuration.get("name")
    if isinstance(name, str):
        names.add(name)
    descriptor = configuration.get("descriptor")
    if not isinstance(descriptor, dict):
        return names
    annotations = descriptor.get("annotations")
    if not isinstance(annotations, dict):
        return names
    for value in annotations.values():
        if isinstance(value, str):
            names.add(value)
    return names


def image_source_digest_label(item: dict[str, object]) -> str | None:
    for labels in image_label_mappings(item):
        value = labels.get(RUNHAVEN_SOURCE_DIGEST_LABEL)
        if isinstance(value, str):
            return value
    return None


def image_created_at(item: dict[str, object]) -> datetime | None:
    timestamps: list[datetime] = []
    configuration = item.get("configuration")
    if isinstance(configuration, dict):
        created_at = parse_utc_timestamp(configuration.get("creationDate"))
        if created_at is not None:
            timestamps.append(created_at)
        descriptor = configuration.get("descriptor")
        if isinstance(descriptor, dict):
            annotations = descriptor.get("annotations")
            if isinstance(annotations, dict):
                created_at = parse_utc_timestamp(
                    annotations.get("org.opencontainers.image.created")
                )
                if created_at is not None:
                    timestamps.append(created_at)
    variants = item.get("variants")
    if isinstance(variants, list):
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            config = variant.get("config")
            if not isinstance(config, dict):
                continue
            created_at = parse_utc_timestamp(config.get("created"))
            if created_at is not None:
                timestamps.append(created_at)
    return max(timestamps) if timestamps else None


def image_label_mappings(item: dict[str, object]) -> tuple[dict[str, object], ...]:
    mappings: list[dict[str, object]] = []
    configuration = item.get("configuration")
    if isinstance(configuration, dict):
        labels = configuration.get("labels")
        if isinstance(labels, dict):
            mappings.append(labels)
    variants = item.get("variants")
    if isinstance(variants, list):
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            config = variant.get("config")
            if not isinstance(config, dict):
                continue
            nested_config = config.get("config")
            if not isinstance(nested_config, dict):
                continue
            labels = nested_config.get("Labels")
            if isinstance(labels, dict):
                mappings.append(labels)
    return tuple(mappings)


def parse_utc_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if "." in text:
        head, tail = text.split(".", maxsplit=1)
        plus_index = tail.find("+")
        minus_index = tail.find("-")
        suffix_index = min(
            index for index in (plus_index, minus_index) if index != -1
        ) if plus_index != -1 or minus_index != -1 else -1
        if suffix_index == -1:
            fraction = tail
            suffix = ""
        else:
            fraction = tail[:suffix_index]
            suffix = tail[suffix_index:]
        if len(fraction) > 6:
            text = f"{head}.{fraction[:6]}{suffix}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def latest_source_update(profile: AgentProfile) -> tuple[Path | None, datetime | None]:
    latest_path: Path | None = None
    latest_time: datetime | None = None
    for path in image_source_files(profile):
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if latest_time is None or updated_at > latest_time:
            latest_path = path
            latest_time = updated_at
    return latest_path, latest_time


def list_state_volume_names(*, run_container: ContainerRunner) -> tuple[str, ...]:
    result = run_container(
        ("container", "volume", "list", "--quiet"),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return tuple(
        line.strip()
        for line in result.stdout.splitlines()
        if is_runhaven_state_volume(line.strip())
    )


def active_run_state_volumes() -> frozenset[str]:
    volumes: set[str] = set()
    for record in read_active_run_records():
        state_volume = record.get("state_volume")
        if isinstance(state_volume, str) and is_runhaven_state_volume(state_volume):
            volumes.add(state_volume)
    return frozenset(volumes)


def profile_state_prefixes(profiles: tuple[AgentProfile, ...]) -> tuple[str, ...]:
    return tuple(f"runhaven-{profile.name}-" for profile in profiles)


def state_volume_matches_profiles(volume: str, profiles: tuple[AgentProfile, ...]) -> bool:
    return volume.startswith(profile_state_prefixes(profiles))


def print_state_volume_review(
    *,
    profiles: tuple[AgentProfile, ...],
    state_volumes: tuple[str, ...],
    active_state_volumes: frozenset[str],
    agent: str | None,
) -> None:
    inactive_volumes = tuple(
        volume
        for volume in state_volumes
        if state_volume_matches_profiles(volume, profiles)
        and volume not in active_state_volumes
    )
    print("State volume review")
    if not inactive_volumes:
        print("No inactive RunHaven state volumes found.")
        return
    print("Inactive RunHaven state volumes found:")
    for volume in inactive_volumes:
        print(f"- {volume}")
    agent_label = agent or "AGENT"
    print(
        "These can be normal reusable session state. Reset only when you want "
        "to discard that agent home state."
    )
    print(f"reset: runhaven state reset {agent_label} --workspace PATH --yes")


def print_preflight_recovery(agent: str | None) -> None:
    agent_label = agent or "AGENT"
    print("Preflight recovery")
    print(f"- Rebuild a missing or stale bundled image: runhaven image rebuild {agent_label}")
    print("- Inspect RunHaven-managed networks: runhaven network list")
    print("- Remove stale managed networks after review: runhaven network prune --yes")
    print(
        "- Reset interrupted isolated home state only when you want to discard it: "
        f"runhaven state reset {agent_label} --workspace PATH --yes"
    )
