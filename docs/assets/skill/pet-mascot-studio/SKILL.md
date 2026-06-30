---
name: pet-mascot-studio
description: Create, repair, validate, package, and QA complete Codex custom pets plus header/hero mascot assets from reference art, generated images, brand cues, or text concepts. Use when the user asks for Codex pets, animated pet spritesheets, pet.json packages, pixel/half-block terminal mascots, Terminal.app-safe 256-color assets, header mascot art, or a reusable pet/mascot workflow.
---

# Pet Mascot Studio

## Scope

Build two related asset families from one visual identity:

1. A complete Codex custom pet package:
   `${CODEX_HOME:-$HOME/.codex}/pets/<pet-id>/pet.json` and `spritesheet.webp`.
2. Optional terminal/header mascot assets:
   exact pixel-grid PNGs plus ANSI half-block text renderings that survive
   macOS Terminal.app 256-color quantization.

Use this skill's deterministic scripts for geometry, alpha cleanup, packaging,
and terminal quantization. Use `$imagegen` only for visual generation of base
art and animation rows; do not hand-draw or locally synthesize missing pet rows.

## Resource Map

Read only the references needed for the current task:

- `references/codex-pet-contract.md`: package shape and atlas dimensions.
- `references/animation-rows.md`: required row order, frame counts, and timing.
- `references/qa-rubric.md`: visual and deterministic acceptance criteria.
- `references/pet-workflow.md`: detailed full-pet generation and repair flow.
- `references/terminal-mascot-contract.md`: ANSI-256 half-block mascot rules.

Available scripts:

- `scripts/check_environment.py`: verify Python, Pillow, optional PyYAML, and
  helper CLI availability before a long visual run.
- `scripts/prepare_pet_run.py`: create run folder, prompts, layout guides, and
  `imagegen-jobs.json`.
- `scripts/complete_visual_job.py`: copy a selected generated image into
  `decoded/`, create `references/canonical-base.png` for the base job, and mark
  the job complete.
- `scripts/derive_running_left_from_running_right.py`: mirror `running-right`
  frame-by-frame only after visual approval.
- `scripts/process_pet_run.py`: extract frames, inspect, compose atlas, validate,
  make contact sheet, and render GIF previews.
- `scripts/package_pet.py`: install `pet.json` and `spritesheet.webp` under the
  Codex pets directory and write `qa/run-summary.json`.
- `scripts/terminal_mascot_assets.py`: generate and verify exact-size PNG and
  ANSI half-block mascot assets using xterm 256-color indices 16-255.

All script paths are relative to this skill directory. Requirement: Python 3
with Pillow installed for image scripts. PyYAML is needed only for the optional
skill validator. If plain `python3` lacks either package, install it into the
active user/runtime environment before continuing, or use a bundled Python that
already provides it. When dependencies are uncertain, run:

```bash
python scripts/check_environment.py --require-yaml
```

## Progress Checklist

Keep this visible for normal full-pet runs:

1. Getting `<Pet>` ready.
2. Imagining `<Pet>`'s main look.
3. Picturing `<Pet>`'s poses.
4. Hatching `<Pet>`.
5. Creating `<Pet>`'s terminal mascot assets. (Only when requested.)

Only mark a step complete after the corresponding file, decision, or validation
artifact exists.

## Full Pet Workflow

1. Prepare the run:

   ```bash
   python scripts/prepare_pet_run.py \
     --pet-name "<Display Name>" \
     --pet-id "<pet-id>" \
     --description "<one short sentence>" \
     --reference /absolute/path/to/reference.png \
     --output-dir /absolute/path/to/run \
     --pet-notes "<stable identity notes>" \
     --style-preset auto \
     --style-notes "<optional notes>" \
     --force
   ```

2. Read the ready jobs:

   ```bash
   jq '.jobs[] | {id, status, depends_on, prompt_file, retry_prompt_file, input_images, output_path, derivation_policy, mirror_policy}' /absolute/path/to/run/imagegen-jobs.json
   ```

3. Load `$imagegen` before any visual generation. Generate `base` first, then
   record the selected output:

   ```bash
   python scripts/complete_visual_job.py \
     --run-dir /absolute/path/to/run \
     --job-id base \
     --source /absolute/path/to/selected-generated-output.png
   ```

4. Generate row jobs through `$imagegen` using the job prompt and every listed
   input image. Start with `idle` and `running-right`. After selecting a row
   image, record it with `complete_visual_job.py`.

5. Derive `running-left` only when mirroring is visually safe:

   ```bash
   python scripts/derive_running_left_from_running_right.py \
     --run-dir /absolute/path/to/run \
     --confirm-appropriate-mirror \
     --decision-note "<why the pet remains correct when mirrored>"
   ```

   If mirroring changes identity, prop meaning, markings, lighting, or direction
   semantics, generate `running-left` as a normal `$imagegen` row.

6. Process the completed run:

   ```bash
   python scripts/process_pet_run.py --run-dir /absolute/path/to/run
   ```

   If preview GIFs show extraction-induced baseline jumps or lost vertical
   motion while the source strip itself is stable, rerun only those rows with:

   ```bash
   python scripts/process_pet_run.py \
     --run-dir /absolute/path/to/run \
     --stable-slots jumping
   ```

7. Inspect `qa/contact-sheet.png` and `qa/previews/*.gif`. Deterministic
   validation is necessary but not sufficient. Repair the smallest failing row,
   then rerun `process_pet_run.py`.

8. Package only after `final/validation.json` is ok, `qa/review.json` has no
   errors, and visual QA passes:

   ```bash
   python scripts/package_pet.py --run-dir /absolute/path/to/run
   ```

## Terminal Mascot Workflow

Use this for header/hero mascot assets, half-block sprites, or Terminal.app-safe
assets. It does not require `$imagegen` when an acceptable reference image
already exists.

```bash
python scripts/terminal_mascot_assets.py \
  --source /absolute/path/to/reference.png \
  --output-dir /absolute/path/to/output \
  --repo-root /absolute/path/to/repo \
  --name cubby \
  --sizes 16x18,24x26,32x36,40x44,48x52
```

To re-validate existing generated mascot assets without rewriting them:

```bash
python scripts/terminal_mascot_assets.py \
  --validate-only /absolute/path/to/output/manifest.json \
  --repo-root /absolute/path/to/repo
```

The script writes:

- `<name>-halfblock-<WxH>-ansi256.png`
- `<name>-halfblock-<WxH>-ansi256.ansi`
- `<name>-halfblock-ansi256-contact-sheet.png`
- `<name>-terminal-source-transparent.png`
- `manifest.json`

Always inspect the contact sheet. For macOS Terminal.app survivability, verify
that the manifest reports xterm 256-color indices 16-255 only and that each PNG
has exact requested dimensions.

## Visual Generation Rules

- Keep one stable identity: silhouette, face, palette, material, props, and
  style must remain consistent across every row and mascot size.
- Do not use local scripts to invent missing pet rows. Scripts may only process
  already selected/generated visuals.
- Do not accept guide marks, text, logos, UI panels, white backgrounds, shadows,
  glows, detached effects, speed lines, dust, or chroma-key artifacts.
- Only the base pet may be prompt-only. Row jobs must attach the listed
  reference/canonical/layout images when the active generation path supports
  references.
- Keep generated originals unless the user explicitly asks for cleanup. Copy
  selected outputs into the run folder.
- For brand-only requests, do lightweight official-source discovery first and
  pass only compact mascot-safe cues into `prepare_pet_run.py`; do not copy
  logos, slogans, UI screenshots, or readable marks.

## Completion Report

Report:

- pet package paths: `pet.json` and `spritesheet.webp`
- run QA paths: `qa/contact-sheet.png`, `qa/previews/`, `final/validation.json`,
  `qa/review.json`, and `qa/run-summary.json`
- terminal mascot output directory and contact sheet, if created
- verification commands and any accepted warnings, such as deliberate
  `stable-slots` extraction for a specific row
