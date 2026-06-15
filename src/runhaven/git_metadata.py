from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GIT_STATUS_PATH_LIMIT = 100


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
