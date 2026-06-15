from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from .active_records import (
    find_active_run_record,
    read_active_run_records,
    remove_active_run_record,
)
from .validators import require_string, validate_runhaven_container_name

ActiveRunRepairStatus = Literal["kept", "removed", "unverified"]
ContainerRunner = Callable[..., subprocess.CompletedProcess[Any]]
RequireContainer = Callable[[], None]


@dataclass(frozen=True)
class ActiveRunRepairResult:
    run_id: str
    container_name: str
    status: ActiveRunRepairStatus
    inspect_return_code: int


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
            f"runhaven: active marker kept because container still exists: {result.container_name}",
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
