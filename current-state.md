# Current State

Last Updated: 2026-06-16 UTC

## Current Objective

RunHaven's repo harness has been refreshed onto the current operating contract:
one compact state file, organized harness docs, repo-owned verification, and
advisory HarnessForge checks.

## State Contract

- `feature_list.json`: machine-readable feature state and durable product
  evidence.
- `docs/harness/evidence/evidence-log.md`: meaningful verification, source
  review, release, or harness evidence.
- `current-state.md`: current objective, trusted verification, touched
  surfaces, blockers, and next step.
- Do not recreate separate root `progress.md` or `session-handoff.md` files.

## Product State

- RunHaven is a Python 3.13+ CLI for running AI coding agents inside Apple
  `container` on macOS 26+ on Apple silicon.
- Windows and Linux are not supported runtime or contributor-verification
  targets.
- Default product safety boundaries remain: no host home mount, no cloud
  credential folder mount, no raw SSH key mount, no arbitrary environment
  passthrough, explicit workspace scope, non-root bundled images, and
  provider egress allowlisting only through reviewed provider mode.
- HarnessForge output is advisory unless a maintainer promotes a recommendation
  into repo-owned docs, tests, policy, code, or release checks.

## Latest Verified Work

- Root startup and harness docs now route to `current-state.md`.
- The obsolete `progress.md` and `session-handoff.md` split has been retired.
- The first-agent harness review is recorded at
  `docs/harness/evidence/first-agent-review.json`.
- The local harness skill at `.agents/skills/harness/` is active and wired to
  repo-owned guidance without requiring HarnessForge for ordinary contributors.
- `docs/harness/manifest.json` now requires `current-state.md` and the
  first-agent review evidence file.

## Trusted Verification

- `python3 scripts/check_pins.py`: passed.
- JSON validation for `feature_list.json`, `docs/harness/manifest.json`,
  `docs/harness/evidence/first-agent-review.json`, harness privacy labels, and
  research source records: passed.
- Local Markdown link check across tracked Markdown files: passed.
- Platform wording scan: passed. Matches were intentional macOS-only,
  unsupported-platform, or Linux-container implementation references.
- `git diff --check`: passed.
- Advisory HarnessForge audit from the sibling development checkout:
  `100/100`.
- Advisory HarnessForge report from the sibling development checkout: audit
  `100/100`, generated drift actionable `0`, docs fanout warnings `0`,
  first-agent lifecycle `retired`. Remaining readiness warnings are high-risk
  workflow/governance inventory reminders and stay advisory unless maintainers
  promote them into RunHaven-owned policy.
- Harness maturity remains at `generated` with next level `reviewed` until the
  advisory high-risk workflow/governance inventory is explicitly accepted or
  promoted into repo-owned requirements.
- RunHaven-side acceptance evidence for the instruction routers, CI workflow,
  and image Containerfiles is recorded in
  `docs/harness/evidence/first-agent-review.json`; current HarnessForge report
  logic does not yet consume that evidence.
- `PYTHON=<temporary-venv-python> ./init.sh`: passed. The full local harness
  ran compileall, 195 unit tests, pin policy, ruff, mypy, and build.

## Touched Surfaces

- `AGENTS.md`
- `.agents/skills/harness/`
- `current-state.md`
- `docs/ROADMAP.md`
- `docs/HARNESS_EVALUATION.md`
- `docs/harness/`
- `docs/harness/evidence/first-agent-review.json`
- `feature_list.json`
- `tests/test_repo_policy.py`

## Blockers

- None known.

## Next Step

Review and commit the RunHaven harness cleanup, then continue normal feature
work from `docs/ROADMAP.md` and `docs/harness/state/roadmap.md`.
