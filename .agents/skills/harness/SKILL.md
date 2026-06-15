---
name: harness
description: Use when maintaining, reviewing, or improving this repository's agent harness without requiring HarnessForge to be installed.
---

# Harness Skill

Status: REVIEW REQUIRED

Use when changing or reviewing instructions, generated harness docs, state,
verification routing, agent tools, CI/workflows, release controls, or evidence.

## Zero-Install Rule

Maintain the harness from repo files alone. HarnessForge CLI and the HarnessForge GitHub Action are optional owner tools, not contributor prerequisites or project source of truth. Use repo-owned commands, docs, tests, and maintainer decisions first.

## Startup

1. Read `references/repo-harness.md`.
2. Load only the repo-root files that match the task surface.
3. Keep detailed repo facts in repo-owned harness docs, not in this skill.

## Operating Rules

- Keep root instructions short; route durable detail into focused docs.
- Update the authoritative owner first, then only surfaces that need to change.
- Do not require HarnessForge for ordinary contributor verification.
- Do not promote HarnessForge report suggestions into project requirements
  until repo-owned docs, tests, policy, or a maintainer accepts them.
- Do not add machine-local paths, user-specific tool mandates, personal
  preferences, autonomous repair workflows, credential rotation, pushes, or PRs.
- Preserve project-owned instruction files unless enhancement or force behavior
  is explicit.
- Treat structural scores as harness-health signals, not real-agent
  effectiveness evidence.

## Improvement Loop

1. Confirm objective and changed surfaces.
2. Inspect the real repo before editing generated placeholders.
3. Prefer deleting stale guidance, merging duplicates, or tightening checks.
4. Make the smallest harness change that prevents the miss.
5. Run repo-owned commands from the verification matrix.
6. Record pass/fail, skipped checks, risk, and next step in evidence or handoff.
7. Retire first-agent or review placeholders after accepted guidance moves into
   durable docs, tests, policy, or state.

## Optional Owner Tools

Use these only when available and relevant:

```bash
harnessforge report --target .
harnessforge plan --target . --since HEAD
harnessforge audit --target . --min-score 85
harnessforge update --target . --drift-report
```

Treat the output as advisory unless the repo owner has adopted HarnessForge or
the HarnessForge Action as an explicit maintenance gate.
