# Complete Pet Workflow

## Visual Job Order

Use up to ten visual jobs:

1. `base`
2. `idle`
3. `running-right`
4. `running-left` (generated or derived from `running-right`)
5. `waving`
6. `jumping`
7. `failed`
8. `waiting`
9. `running`
10. `review`

The base job establishes identity. Every row must preserve that identity.

## Row Semantics

- `idle`: calm reduced-motion baseline; subtle breathing or blink only.
- `running-right`: directional drag movement to the right.
- `running-left`: directional drag movement to the left.
- `waving`: limb gesture only; no wave marks.
- `jumping`: pose or vertical movement only; no floor cues.
- `failed`: slumped or sad reaction; no red X or floating symbols.
- `waiting`: expectant input-needed pose, distinct from idle and review.
- `running`: active task work, not foot-running.
- `review`: focused inspection without new props.

## Repair Policy

Repair the smallest failing scope:

1. One row.
2. The base only when identity is wrong everywhere.
3. The whole run only when multiple generated rows are unusable for the same
   root cause.

Use `--stable-slots <state>` only when component extraction has destroyed
source-strip motion or baseline stability. Do not use stable-slots to hide
clipping, identity drift, missing frames, or bad row semantics.

## Acceptance

Accept only when:

- `final/spritesheet.webp` is `1536x1872`.
- `final/validation.json` is `ok: true` with no errors.
- `qa/review.json` is `ok: true`; warnings are explicitly visually reviewed.
- `qa/contact-sheet.png` shows all rows with stable identity.
- `qa/previews/*.gif` show correct row semantics and no unintended popping.
- `${CODEX_HOME:-$HOME/.codex}/pets/<pet-id>/pet.json` and
  `spritesheet.webp` are written together.
