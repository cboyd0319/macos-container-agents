from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from .active_records import (
    clear_active_run_kill_requested,
    clear_active_run_stop_requested,
    find_active_run_record,
    mark_active_run_kill_requested,
    mark_active_run_stop_requested,
    read_active_run_records,
    remove_active_run_record,
)
from .plans import uses_root_identity, validate_resource_options
from .validators import require_string, validate_runhaven_container_name

DEFAULT_ATTACH_COMMAND = ("/bin/bash",)
DEFAULT_LOG_FOLLOW_LINES = 200
ACTIVE_RUN_PUBLIC_FIELDS = (
    "timestamp",
    "run_id",
    "profile",
    "workspace",
    "network",
    "status",
    "container_name",
    "state_volume",
    "network_name",
    "host_pid",
    "stop_requested_at",
    "kill_requested_at",
)

ActiveRunRepairStatus = Literal["kept", "removed", "unverified"]
ContainerCaller = Callable[[tuple[str, ...]], int]
ContainerRunner = Callable[..., subprocess.CompletedProcess[Any]]
RequireContainer = Callable[[], None]
TTYCheck = Callable[[], bool]


@dataclass(frozen=True)
class ActiveRunRepairResult:
    run_id: str
    container_name: str
    status: ActiveRunRepairStatus
    inspect_return_code: int


def runs_active(*, json_output: bool) -> int:
    records = read_active_run_records()
    if json_output:
        print(json.dumps(records, indent=2, sort_keys=True))
        return 0
    if not records:
        print("No active RunHaven runs found.")
        return 0
    for record in records:
        print(
            f"{record.get('timestamp', '<unknown>')}  "
            f"{record.get('profile', 'unknown')}  "
            f"{record.get('network', 'unknown')}  "
            f"{record.get('status', 'unknown')}  "
            f"run={record.get('run_id', '-')}  "
            f"workspace={record.get('workspace', '-')}  "
            f"container={record.get('container_name', '-')}"
        )
    return 0


def runs_attach(
    run_id: str,
    *,
    user: str,
    workdir: str,
    tty_mode: str,
    allow_root_user: bool,
    command_args: tuple[str, ...],
    require_container: RequireContainer,
    call_container: ContainerCaller,
    stdin_is_tty: TTYCheck = sys.stdin.isatty,
    stdout_is_tty: TTYCheck = sys.stdout.isatty,
) -> int:
    record = find_active_run_record(run_id)
    container_name = require_string(
        record.get("container_name"),
        "active run record is missing container name",
    )
    validate_runhaven_container_name(container_name)
    validate_resource_options("1", "1g", user)
    if uses_root_identity(user) and not allow_root_user:
        raise ValueError("root user or group requires --allow-root-user")
    validate_attach_workdir(workdir)
    command = command_args or DEFAULT_ATTACH_COMMAND
    validate_attach_command(command)
    require_container()

    attach_command = ["container", "exec", "--interactive"]
    if tty_mode == "always" or (tty_mode == "auto" and stdin_is_tty() and stdout_is_tty()):
        attach_command.append("--tty")
    attach_command.extend(("--user", user, "--workdir", workdir, container_name))
    attach_command.extend(command)
    return call_container(tuple(attach_command))


def runs_logs_follow(
    run_id: str,
    *,
    lines: int,
    require_container: RequireContainer,
    call_container: ContainerCaller,
) -> int:
    if lines < 1:
        raise ValueError("--lines must be 1 or greater")
    record = find_active_run_record(run_id)
    container_name = require_string(
        record.get("container_name"),
        "active run record is missing container name",
    )
    validate_runhaven_container_name(container_name)
    require_container()
    return call_container(
        (
            "container",
            "logs",
            "--follow",
            "-n",
            str(lines),
            container_name,
        )
    )


def runs_status(
    run_id: str,
    *,
    json_output: bool,
    require_container: RequireContainer,
    run_container: ContainerRunner,
) -> int:
    record = find_active_run_record(run_id)
    container_name = require_string(
        record.get("container_name"),
        "active run record is missing container name",
    )
    validate_runhaven_container_name(container_name)
    require_container()
    result = run_container(
        ("container", "inspect", container_name),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"runhaven: container inspect failed for run {run_id} ({container_name})",
            file=sys.stderr,
        )
        return result.returncode

    container = summarize_container_inspect(load_container_inspect(result.stdout))
    payload = {
        "active_run": public_active_run_record(record),
        "container": container,
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print_runs_status(payload)
    return 0


def public_active_run_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ACTIVE_RUN_PUBLIC_FIELDS if key in record}


def load_container_inspect(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("container inspect returned invalid JSON") from exc
    if isinstance(payload, list):
        if not payload:
            raise ValueError("container inspect returned no records")
        record = payload[0]
    else:
        record = payload
    if not isinstance(record, dict):
        raise ValueError("container inspect returned an invalid record")
    return record


def summarize_container_inspect(record: dict[str, Any]) -> dict[str, Any]:
    configuration = record.get("configuration")
    status = record.get("status")
    container: dict[str, Any] = {"id": optional_string(record.get("id"))}
    if isinstance(configuration, dict):
        image = configuration.get("image")
        resources = configuration.get("resources")
        if isinstance(image, dict):
            container["image"] = optional_string(image.get("reference"))
        if isinstance(resources, dict):
            container["resources"] = summarize_container_resources(resources)
    if isinstance(status, dict):
        container["state"] = optional_string(status.get("state"))
        container["started_at"] = optional_string(status.get("startedDate"))
        container["networks"] = summarize_container_networks(status.get("networks"))
    return {
        key: value
        for key, value in container.items()
        if value is not None and value != [] and value != {}
    }


def summarize_container_resources(resources: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    cpus = resources.get("cpus")
    memory = resources.get("memoryInBytes")
    if isinstance(cpus, int | float):
        summary["cpus"] = cpus
    if isinstance(memory, int):
        summary["memory_in_bytes"] = memory
    return summary


def summarize_container_networks(networks: Any) -> list[dict[str, str]]:
    if not isinstance(networks, list):
        return []
    summaries: list[dict[str, str]] = []
    for network in networks:
        if not isinstance(network, dict):
            continue
        summary = {
            output_key: value
            for source_key, output_key in (
                ("network", "network"),
                ("hostname", "hostname"),
                ("ipv4Address", "ipv4_address"),
                ("ipv4Gateway", "ipv4_gateway"),
                ("ipv6Address", "ipv6_address"),
            )
            if isinstance(value := network.get(source_key), str)
        }
        if summary:
            summaries.append(summary)
    return summaries


def optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def print_runs_status(payload: dict[str, Any]) -> None:
    active_run = payload["active_run"]
    container = payload["container"]
    print(f"Run id: {active_run.get('run_id', '-')}")
    print(f"Profile: {active_run.get('profile', 'unknown')}")
    print(f"Workspace: {active_run.get('workspace', 'unknown')}")
    print(f"Network: {active_run.get('network', 'unknown')}")
    print(f"Marker status: {active_run.get('status', 'unknown')}")
    print(f"Container: {active_run.get('container_name', '-')}")
    print(f"Container state: {container.get('state', 'unknown')}")
    print(f"Container started: {container.get('started_at', '-')}")
    image = container.get("image")
    if isinstance(image, str):
        print(f"Container image: {image}")
    networks = container.get("networks")
    if isinstance(networks, list):
        for network in networks:
            if isinstance(network, dict):
                print(f"Container network: {format_container_network(network)}")


def format_container_network(network: dict[str, Any]) -> str:
    parts = [str(network.get("network", "unknown"))]
    for key, label in (
        ("ipv4_address", "ipv4"),
        ("ipv6_address", "ipv6"),
        ("hostname", "hostname"),
    ):
        value = network.get(key)
        if isinstance(value, str):
            parts.append(f"{label}={value}")
    return " ".join(parts)


def validate_attach_workdir(workdir: str) -> None:
    if not workdir or not workdir.startswith("/"):
        raise ValueError(f"invalid attach workdir: {workdir!r}")
    if any(character in "\x00\r\n" for character in workdir):
        raise ValueError(f"invalid attach workdir: {workdir!r}")


def validate_attach_command(command: tuple[str, ...]) -> None:
    if not command:
        raise ValueError("attach command is empty")
    if any(argument == "" or "\x00" in argument for argument in command):
        raise ValueError("attach command arguments cannot be empty")


def runs_stop(
    run_id: str,
    *,
    require_container: RequireContainer,
    run_container: ContainerRunner,
) -> int:
    record = find_active_run_record(run_id)
    container_name = require_string(
        record.get("container_name"),
        "active run record is missing container name",
    )
    validate_runhaven_container_name(container_name)
    require_container()
    mark_active_run_stop_requested(run_id, record)
    result = run_container(("container", "stop", container_name), check=False)
    if result.returncode != 0:
        try:
            clear_active_run_stop_requested(run_id, record)
        except ValueError:
            pass
        return result.returncode
    print(f"Stop requested for run {run_id} ({container_name}).")
    return 0


def runs_kill(
    run_id: str,
    *,
    require_container: RequireContainer,
    run_container: ContainerRunner,
) -> int:
    record = find_active_run_record(run_id)
    container_name = require_string(
        record.get("container_name"),
        "active run record is missing container name",
    )
    validate_runhaven_container_name(container_name)
    require_container()
    mark_active_run_kill_requested(run_id, record)
    result = run_container(("container", "kill", container_name), check=False)
    if result.returncode != 0:
        try:
            clear_active_run_kill_requested(run_id, record)
        except ValueError:
            pass
        return result.returncode
    print(f"Kill requested for run {run_id} ({container_name}).")
    return 0


def runs_repair(
    run_id: str | None,
    *,
    repair_all: bool,
    json_output: bool,
    require_container: RequireContainer,
    run_container: ContainerRunner,
) -> int:
    if run_id is not None and repair_all:
        raise ValueError("--all cannot be used with RUN_ID")
    if repair_all:
        return runs_repair_all(
            json_output=json_output,
            require_container=require_container,
            run_container=run_container,
        )
    if run_id is None:
        raise ValueError("repair requires RUN_ID or --all")
    return runs_repair_one(
        run_id,
        json_output=json_output,
        require_container=require_container,
        run_container=run_container,
    )


def runs_repair_one(
    run_id: str,
    *,
    json_output: bool,
    require_container: RequireContainer,
    run_container: ContainerRunner,
) -> int:
    record = find_active_run_record(run_id)
    active_run_repair_container_name(record)
    require_container()
    result = repair_active_run_record(run_id, record, run_container=run_container)
    exit_code = active_run_repair_single_exit_code(result)
    if json_output:
        print(
            json.dumps(
                active_run_repair_payload("single", [result], exit_code),
                indent=2,
                sort_keys=True,
            )
        )
        return exit_code
    if result.status == "kept":
        print(
            f"runhaven: active marker kept because container still exists: "
            f"{result.container_name}",
            file=sys.stderr,
        )
        return exit_code
    if result.status == "unverified":
        print(
            f"runhaven: could not confirm missing container for run "
            f"{result.run_id} ({result.container_name})",
            file=sys.stderr,
        )
        return exit_code
    print(f"Removed stale active marker for run {result.run_id} ({result.container_name}).")
    return exit_code


def runs_repair_all(
    *,
    json_output: bool,
    require_container: RequireContainer,
    run_container: ContainerRunner,
) -> int:
    records = read_active_run_records()
    if not records:
        if json_output:
            print(
                json.dumps(
                    active_run_repair_payload("all", [], 0),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        print("No active RunHaven runs found.")
        return 0
    require_container()
    results: list[ActiveRunRepairResult] = []
    for record in records:
        run_id = require_string(record.get("run_id"), "active run record is missing run id")
        result = repair_active_run_record(run_id, record, run_container=run_container)
        results.append(result)
    counts = active_run_repair_summary(results)
    exit_code = 1 if counts["unverified"] else 0
    if json_output:
        print(
            json.dumps(
                active_run_repair_payload("all", results, exit_code),
                indent=2,
                sort_keys=True,
            )
        )
        return exit_code
    for result in results:
        run_id = result.run_id
        if result.status == "removed":
            print(f"Removed stale active marker for run {run_id} ({result.container_name}).")
        elif result.status == "kept":
            print(
                f"Kept active marker for run {run_id} "
                f"({result.container_name}): container still exists."
            )
        else:
            print(
                f"Could not verify active marker for run {run_id} "
                f"({result.container_name}); marker kept."
            )
    print(
        "Repair summary: "
        f"removed={counts['removed']} kept={counts['kept']} unverified={counts['unverified']}"
    )
    return exit_code


def active_run_repair_single_exit_code(result: ActiveRunRepairResult) -> int:
    if result.status == "removed":
        return 0
    if result.status == "kept":
        return 1
    return result.inspect_return_code


def active_run_repair_payload(
    mode: str,
    results: list[ActiveRunRepairResult],
    exit_code: int,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "mode": mode,
        "results": [active_run_repair_result_payload(result) for result in results],
        "summary": active_run_repair_summary(results),
    }


def active_run_repair_summary(results: list[ActiveRunRepairResult]) -> dict[str, int]:
    summary: dict[ActiveRunRepairStatus, int] = {"kept": 0, "removed": 0, "unverified": 0}
    for result in results:
        summary[result.status] += 1
    return {
        "kept": summary["kept"],
        "removed": summary["removed"],
        "unverified": summary["unverified"],
    }


def active_run_repair_result_payload(result: ActiveRunRepairResult) -> dict[str, object]:
    return {
        "container_name": result.container_name,
        "inspect_return_code": result.inspect_return_code,
        "marker_removed": result.status == "removed",
        "run_id": result.run_id,
        "status": result.status,
    }


def repair_active_run_record(
    run_id: str,
    record: dict[str, Any],
    *,
    run_container: ContainerRunner,
) -> ActiveRunRepairResult:
    container_name = active_run_repair_container_name(record)
    result = run_container(
        ("container", "inspect", container_name),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return ActiveRunRepairResult(
            run_id=run_id,
            container_name=container_name,
            status="kept",
            inspect_return_code=result.returncode,
        )
    if not container_inspect_reports_missing(result, container_name):
        return ActiveRunRepairResult(
            run_id=run_id,
            container_name=container_name,
            status="unverified",
            inspect_return_code=result.returncode,
        )
    remove_active_run_record(run_id)
    return ActiveRunRepairResult(
        run_id=run_id,
        container_name=container_name,
        status="removed",
        inspect_return_code=result.returncode,
    )


def active_run_repair_container_name(record: dict[str, Any]) -> str:
    container_name = require_string(
        record.get("container_name"),
        "active run record is missing container name",
    )
    validate_runhaven_container_name(container_name)
    return container_name


def container_inspect_reports_missing(
    result: subprocess.CompletedProcess[Any],
    container_name: str,
) -> bool:
    output = f"{result.stdout}\n{result.stderr}".lower()
    return f"container not found: {container_name.lower()}" in output
