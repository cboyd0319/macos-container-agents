from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .auth_broker import BrokerDecision
from .cache_paths import runs_log_path
from .egress import ProxyDecision
from .plans import AgentRunPlan
from .validators import require_string

GIT_STATUS_PATH_LIMIT = 100

LogReader = Callable[[], Sequence[dict[str, Any]]]


@dataclass(frozen=True)
class GitStatusEntry:
    path: str
    status: str


def capture_git_snapshot(workspace: Path) -> dict[str, object]:
    repo_root, unavailable_reason = git_repo_root(workspace)
    if repo_root is None:
        return {"available": False, "reason": unavailable_reason}

    head = git_head(repo_root)
    entries = read_git_status_entries(repo_root, workspace)
    if entries is None:
        return {
            "available": False,
            "reason": "git-status-failed",
            "repo_root": repo_root,
        }

    paths = tuple(entry.path for entry in entries)
    shown_paths = list(paths[:GIT_STATUS_PATH_LIMIT])
    return {
        "available": True,
        "repo_root": repo_root,
        "head": head,
        "dirty": bool(paths),
        "changed_count": len(paths),
        "paths": shown_paths,
        "truncated": len(paths) > GIT_STATUS_PATH_LIMIT,
    }


def read_git_status_entries(repo_root: str, workspace: Path) -> tuple[GitStatusEntry, ...] | None:
    resolved_workspace = str(workspace.resolve())
    status_result = run_git_for_metadata(
        ("git", "-C", repo_root, "status", "--porcelain=v1", "-z", "--", resolved_workspace),
    )
    if status_result is None or status_result.returncode != 0:
        return None
    return parse_git_status_entries(status_result.stdout)


def git_repo_root(workspace: Path) -> tuple[str | None, str]:
    result = run_git_for_metadata(
        ("git", "-C", str(workspace), "rev-parse", "--show-toplevel"),
        text=True,
    )
    if result is None:
        return None, "git-not-found"
    if result.returncode != 0:
        return None, "not-a-git-worktree"
    repo_root = result.stdout.strip()
    if not repo_root:
        return None, "not-a-git-worktree"
    return str(Path(repo_root).resolve()), ""


def git_head(repo_root: str) -> str | None:
    result = run_git_for_metadata(
        ("git", "-C", repo_root, "rev-parse", "HEAD"),
        text=True,
    )
    if result is None or result.returncode != 0:
        return None
    head = result.stdout.strip()
    return head or None


def run_git_for_metadata(
    command: tuple[str, ...],
    *,
    text: bool = False,
) -> subprocess.CompletedProcess[Any] | None:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=text,
        )
    except (FileNotFoundError, OSError):
        return None


def parse_git_status_paths(output: bytes) -> tuple[str, ...]:
    return tuple(entry.path for entry in parse_git_status_entries(output))


def parse_git_status_entries(output: bytes) -> tuple[GitStatusEntry, ...]:
    entries = [entry for entry in output.split(b"\0") if entry]
    parsed: dict[str, GitStatusEntry] = {}
    index = 0
    while index < len(entries):
        entry = entries[index]
        if len(entry) >= 4:
            status = entry[:2]
            path = os.fsdecode(entry[3:])
            parsed[path] = GitStatusEntry(path=path, status=os.fsdecode(status))
            if b"R" in status or b"C" in status:
                index += 1
        index += 1
    return tuple(parsed[path] for path in sorted(parsed))


def summarize_git_change(
    before: dict[str, object],
    after: dict[str, object],
) -> dict[str, object]:
    before_available = before.get("available") is True
    after_available = after.get("available") is True
    if not before_available or not after_available:
        reason = after.get("reason") if not after_available else before.get("reason")
        metadata: dict[str, object] = {
            "available": False,
            "reason": reason if isinstance(reason, str) else "git-unavailable",
        }
        repo_root = after.get("repo_root") or before.get("repo_root")
        if isinstance(repo_root, str):
            metadata["repo_root"] = repo_root
        return metadata

    before_summary = git_snapshot_for_record(before)
    after_summary = git_snapshot_for_record(after)
    return {
        "available": True,
        "repo_root": after["repo_root"],
        "changed": before_summary != after_summary,
        "before": before_summary,
        "after": after_summary,
    }


def git_snapshot_for_record(snapshot: dict[str, object]) -> dict[str, object]:
    return {
        "head": snapshot.get("head"),
        "dirty": snapshot.get("dirty") is True,
        "changed_count": snapshot.get("changed_count", 0),
        "paths": snapshot.get("paths", []),
        "truncated": snapshot.get("truncated") is True,
    }


def write_run_record(
    plan: AgentRunPlan,
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    return_code: int,
    status: str | None = None,
    provider_decisions: Sequence[ProxyDecision],
    auth_decisions: Sequence[BrokerDecision] | None,
    cleanup: dict[str, object],
    git: dict[str, object],
) -> None:
    log_path = runs_log_path()
    log_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "timestamp": finished_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "run_id": run_id,
        "profile": plan.profile_name,
        "workspace": str(plan.workspace),
        "network": plan.network_mode,
        "status": status or ("succeeded" if return_code == 0 else "failed"),
        "return_code": return_code,
        "provider_policy": summarize_provider_policy(provider_decisions),
        "auth_broker": summarize_auth_broker(auth_decisions),
        "cleanup": cleanup,
        "git": git,
    }
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(payload, sort_keys=True) + "\n")


def summarize_provider_policy(decisions: Sequence[ProxyDecision]) -> dict[str, int]:
    return {
        "entries": len(decisions),
        "allowed": sum(decision.count for decision in decisions if decision.decision == "allowed"),
        "denied": sum(decision.count for decision in decisions if decision.decision == "denied"),
    }


def summarize_auth_broker(decisions: Sequence[BrokerDecision] | None) -> dict[str, object]:
    if decisions is None:
        return {
            "broker": None,
            "entries": 0,
            "allowed": 0,
            "denied": 0,
            "no_requests": False,
        }
    return {
        "broker": "codex-api-key",
        "entries": len(decisions),
        "allowed": sum(decision.count for decision in decisions if decision.decision == "allowed"),
        "denied": sum(decision.count for decision in decisions if decision.decision == "denied"),
        "no_requests": not decisions,
    }


def runs_list(*, limit: int, json_output: bool) -> int:
    if limit < 0:
        raise ValueError("--limit must be 0 or greater")
    records = read_run_records(limit=limit)
    if json_output:
        print(json.dumps(records, indent=2, sort_keys=True))
        return 0
    if not records:
        print("No RunHaven run records found.")
        return 0
    for record in records:
        provider_policy = record.get("provider_policy")
        auth_broker = record.get("auth_broker")
        cleanup = record.get("cleanup")
        provider_denied = (
            provider_policy.get("denied", 0) if isinstance(provider_policy, dict) else 0
        )
        auth_denied = auth_broker.get("denied", 0) if isinstance(auth_broker, dict) else 0
        cleanup_status = (
            cleanup.get("provider_network", "-") if isinstance(cleanup, dict) else "-"
        )
        print(
            f"{record.get('timestamp', '<unknown>')}  "
            f"{record.get('profile', 'unknown')}  "
            f"{record.get('network', 'unknown')}  "
            f"{record.get('status', 'unknown')}  "
            f"return={record.get('return_code', '-')}  "
            f"provider_denied={provider_denied}  "
            f"auth_denied={auth_denied}  "
            f"cleanup={cleanup_status}  "
            f"run={record.get('run_id', '-')}"
        )
    return 0


def runs_show(run_id: str, *, json_output: bool) -> int:
    record = find_run_record(run_id)
    if json_output:
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0

    provider_policy = record.get("provider_policy")
    auth_broker = record.get("auth_broker")
    cleanup = record.get("cleanup")
    print(f"Run id: {record.get('run_id', '-')}")
    print(f"Started: {record.get('started_at', '-')}")
    print(f"Finished: {record.get('finished_at', '-')}")
    print(f"Profile: {record.get('profile', 'unknown')}")
    print(f"Workspace: {record.get('workspace', 'unknown')}")
    print(f"Network: {record.get('network', 'unknown')}")
    print(f"Status: {record.get('status', 'unknown')}")
    print(f"Return code: {record.get('return_code', '-')}")
    git = record.get("git")
    if isinstance(git, dict):
        print(format_git_summary(git))
    if isinstance(provider_policy, dict):
        print(
            "Provider policy: "
            f"entries={provider_policy.get('entries', 0)} "
            f"allowed={provider_policy.get('allowed', 0)} "
            f"denied={provider_policy.get('denied', 0)}"
        )
    if isinstance(auth_broker, dict):
        no_requests = str(auth_broker.get("no_requests", False)).lower()
        print(
            "Auth broker: "
            f"broker={auth_broker.get('broker') or '-'} "
            f"entries={auth_broker.get('entries', 0)} "
            f"allowed={auth_broker.get('allowed', 0)} "
            f"denied={auth_broker.get('denied', 0)} "
            f"no_requests={no_requests}"
        )
    if isinstance(cleanup, dict):
        print(f"Cleanup provider network: {cleanup.get('provider_network', '-')}")
    return 0


def format_git_summary(git: dict[str, Any]) -> str:
    if git.get("available") is not True:
        reason = git.get("reason")
        reason_text = reason if isinstance(reason, str) else "unknown"
        return f"Git: unavailable ({reason_text})"

    before = git.get("before")
    after = git.get("after")
    before_head = short_git_head(before.get("head") if isinstance(before, dict) else None)
    after_head = short_git_head(after.get("head") if isinstance(after, dict) else None)
    changed = str(git.get("changed") is True).lower()
    files = after.get("changed_count", 0) if isinstance(after, dict) else 0
    return f"Git: changed={changed} before={before_head} after={after_head} files={files}"


def short_git_head(head: object) -> str:
    if not isinstance(head, str) or not head:
        return "-"
    return head[:7]


def runs_diff(run_id: str) -> int:
    record = find_run_record(run_id)
    git = require_available_git_metadata(record, run_id)
    before = require_git_snapshot(git.get("before"), "before")
    after = require_git_snapshot(git.get("after"), "after")
    repo_root = require_string(git.get("repo_root"), "run git metadata is missing repo root")
    workspace = require_string(record.get("workspace"), "run record is missing workspace")
    before_head = require_string(
        before.get("head"),
        "run git metadata is missing a base HEAD; refusing live diff",
    )
    after_head = require_string(
        after.get("head"),
        "run git metadata is missing recorded HEAD; refusing live diff",
    )
    after_dirty = after.get("dirty") is True
    after_paths = git_snapshot_paths(after)

    if after.get("truncated") is True:
        raise ValueError("run git path list is truncated; refusing live diff")
    if not Path(repo_root).is_dir():
        raise ValueError("recorded git repo no longer exists; refusing live diff")
    if not Path(workspace).exists():
        raise ValueError("recorded workspace no longer exists; refusing live diff")

    current = capture_git_snapshot(Path(workspace))
    if current.get("available") is not True:
        raise ValueError("recorded workspace is no longer a git worktree; refusing live diff")
    if current.get("repo_root") != repo_root:
        raise ValueError(
            "workspace git repo no longer matches the recorded run; refusing live diff"
        )
    if current.get("head") != after_head:
        raise ValueError("git HEAD changed since the recorded run; refusing live diff")
    if not git_snapshot_matches(after, current):
        raise ValueError("git working tree changed since the recorded run; refusing live diff")

    if not after_dirty and before_head == after_head:
        print("No git changes recorded for this run.")
        return 0

    if after_dirty:
        print(
            "runhaven: showing a live working tree diff; RunHaven verified "
            "the recorded HEAD and path set, not file contents since the run.",
            file=sys.stderr,
        )

    diff_parts: list[str] = []
    if after_dirty:
        if before_head != after_head:
            diff_parts.append(
                run_git_diff(
                    (
                        "git",
                        "-C",
                        repo_root,
                        "diff",
                        "--no-ext-diff",
                        "--no-color",
                        before_head,
                        after_head,
                    ),
                )
            )
        entries = read_git_status_entries(repo_root, Path(workspace))
        if entries is None:
            raise ValueError("could not read current git status; refusing live diff")
        untracked_paths = {
            entry.path for entry in entries if entry.status == "??" and entry.path in after_paths
        }
        tracked_paths = [path for path in after_paths if path not in untracked_paths]
        if tracked_paths:
            diff_parts.append(
                run_git_diff(
                    (
                        "git",
                        "-C",
                        repo_root,
                        "diff",
                        "--no-ext-diff",
                        "--no-color",
                        after_head,
                        "--",
                        *tracked_paths,
                    ),
                )
            )
        for path in sorted(untracked_paths):
            diff_parts.append(run_untracked_git_diff(repo_root, path))
    else:
        diff_parts.append(
            run_git_diff(
                (
                    "git",
                    "-C",
                    repo_root,
                    "diff",
                    "--no-ext-diff",
                    "--no-color",
                    before_head,
                    after_head,
                ),
            )
        )

    printed = False
    for diff in diff_parts:
        if not diff:
            continue
        print(diff, end="" if diff.endswith("\n") else "\n")
        printed = True
    if not printed:
        print("No git diff output for recorded changes.")
    return 0


def require_available_git_metadata(record: dict[str, Any], run_id: str) -> dict[str, Any]:
    git = record.get("git")
    if not isinstance(git, dict):
        raise ValueError(f"git metadata is unavailable for run {run_id}")
    if git.get("available") is not True:
        reason = git.get("reason")
        reason_text = f": {reason}" if isinstance(reason, str) and reason else ""
        raise ValueError(f"git metadata is unavailable for run {run_id}{reason_text}")
    return git


def require_git_snapshot(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"run git metadata is missing {name} snapshot")
    return value


def git_snapshot_paths(snapshot: dict[str, Any]) -> tuple[str, ...]:
    paths = snapshot.get("paths")
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError("run git metadata has invalid path list")
    return tuple(sorted(paths))


def git_snapshot_matches(recorded: dict[str, Any], current: dict[str, object]) -> bool:
    current_paths = current.get("paths")
    if not isinstance(current_paths, list) or not all(
        isinstance(path, str) for path in current_paths
    ):
        return False
    return (
        recorded.get("dirty") is (current.get("dirty") is True)
        and recorded.get("changed_count", 0) == current.get("changed_count", 0)
        and git_snapshot_paths(recorded) == tuple(sorted(current_paths))
        and recorded.get("truncated") is (current.get("truncated") is True)
    )


def run_git_diff(command: tuple[str, ...]) -> str:
    result = run_git_for_metadata(command, text=True)
    if result is None:
        raise ValueError("git diff is unavailable")
    if result.returncode != 0:
        detail = result.stderr.strip() if isinstance(result.stderr, str) else ""
        raise ValueError(f"git diff failed: {detail or result.returncode}")
    return result.stdout if isinstance(result.stdout, str) else ""


def run_untracked_git_diff(repo_root: str, path: str) -> str:
    full_path = safe_repo_path(repo_root, path)
    result = run_git_for_metadata(
        (
            "git",
            "-C",
            repo_root,
            "diff",
            "--no-ext-diff",
            "--no-color",
            "--no-index",
            "--",
            "/dev/null",
            str(full_path),
        ),
        text=True,
    )
    if result is None:
        raise ValueError("git diff is unavailable")
    if result.returncode not in (0, 1):
        detail = result.stderr.strip() if isinstance(result.stderr, str) else ""
        raise ValueError(f"git diff failed: {detail or result.returncode}")
    return result.stdout if isinstance(result.stdout, str) else ""


def safe_repo_path(repo_root: str, path: str) -> Path:
    root = Path(repo_root).resolve()
    full_path = (root / path).resolve()
    try:
        full_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("git path escapes the recorded repository; refusing live diff") from exc
    return full_path


def runs_log(
    run_id: str,
    *,
    json_output: bool,
    read_provider_log: LogReader,
    read_auth_log: LogReader,
) -> int:
    record = find_run_record(run_id)
    provider_entries = log_entries_for_run(read_provider_log(), run_id)
    auth_entries = log_entries_for_run(read_auth_log(), run_id)
    payload = {
        "run": record,
        "provider_policy": provider_entries,
        "auth_broker": auth_entries,
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    runs_show(run_id, json_output=False)
    print("Provider policy decisions:")
    if provider_entries:
        for entry in provider_entries:
            host = entry.get("host", "<unknown>")
            port = entry.get("port", "?")
            matched_rule = entry.get("matched_rule") or "-"
            print(
                f"  - {entry.get('timestamp', '<unknown>')}  "
                f"{entry.get('decision', 'unknown')}  {host}:{port}  "
                f"count={entry.get('count', 1)}  "
                f"reason={entry.get('reason', 'unknown')}  rule={matched_rule}"
            )
    else:
        print("  none")

    print("Auth broker decisions:")
    if auth_entries:
        for entry in auth_entries:
            upstream_status = entry.get("upstream_status")
            status = upstream_status if upstream_status is not None else "-"
            print(
                f"  - {entry.get('timestamp', '<unknown>')}  "
                f"{entry.get('broker', 'unknown')}  "
                f"{entry.get('decision', 'unknown')}  "
                f"{entry.get('method', '-')} {entry.get('path', '-')}  "
                f"status={status}  count={entry.get('count', 1)}  "
                f"reason={entry.get('reason', 'unknown')}"
            )
    else:
        print("  none")
    return 0


def find_run_record(run_id: str) -> dict[str, Any]:
    for record in reversed(read_run_records(limit=0)):
        if record.get("run_id") == run_id:
            return record
    raise ValueError(f"run record not found: {run_id}")


def log_entries_for_run(entries: Sequence[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    return [entry for entry in entries if entry.get("run_id") == run_id]


def read_run_records(*, limit: int) -> list[dict[str, Any]]:
    log_path = runs_log_path()
    if not log_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    if limit == 0:
        return records
    return records[-limit:]
