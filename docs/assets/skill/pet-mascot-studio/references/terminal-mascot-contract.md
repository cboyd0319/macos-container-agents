# Terminal Mascot Contract

Use this reference for header/hero mascot assets intended to render in terminal
UIs without graphics protocols.

## Required Outputs

For each requested pixel size, produce:

- exact-size PNG with transparency
- `.ansi` file using Unicode half-block glyphs (`▀` and `▄`)
- manifest entry with pixel size, terminal cell size, and used ANSI indices
- manifest `repo_root` when paths are written repo-relative

For a `WIDTH x HEIGHT` pixel asset, half-block output is `WIDTH x HEIGHT/2`
terminal cells. Require even heights.

## macOS Terminal.app Constraint

macOS Terminal.app does not support Kitty, iTerm inline images, or Sixel, and its
truecolor handling can be profile-dependent. Use xterm 256-color output as the
portable floor:

- Use only SGR `38;5;<n>` and `48;5;<n>`.
- Prefer indices `16-255`.
- Avoid indices `0-15`; Terminal profiles can remap those base colors.
- Verify the PNG pixels are exactly in the xterm 256-color palette.

## Visual Rules

- Preserve the mascot identity: face, outline, core palette, and readable prop.
- Keep a one-pixel safety inset for tiny sizes unless the user explicitly asks
  for edge-to-edge crops.
- At the smallest size, prioritize silhouette and eyes over glass detail.
- Always inspect a contact sheet on both transparent/checkerboard and dark
  terminal-like backgrounds.

## Repeatable Validation

After generation, or when checking assets made earlier, run:

```bash
python scripts/terminal_mascot_assets.py \
  --validate-only /absolute/path/to/output/manifest.json \
  --repo-root /absolute/path/to/repo
```

If the manifest includes `repo_root`, `--repo-root` can be omitted unless the
assets moved to a different checkout.

## Default Sizes

Use these when the user asks for the RunHaven/Cubby header set:

```text
16x18,24x26,32x36,40x44,48x52
```
