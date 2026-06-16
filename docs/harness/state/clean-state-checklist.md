# Clean State Checklist

Use this before ending a non-trivial session.

## Required Checks

- [ ] Startup path still works, or the breakage is recorded with risk.
- [ ] Verification path ran, or the skipped command and reason are recorded.
- [ ] `feature_list.json` reflects actual state. No item is `passing` without
  evidence.
- [ ] `current-state.md` records the current objective, trusted verification,
  touched files, blockers, and next step.
- [ ] No temporary debug files, stale generated reports, or undocumented partial
  work are left behind.

## Next Session

The next session should be able to read `AGENTS.md`, `feature_list.json`, and
`current-state.md`, then continue without reconstructing state from chat
history.
