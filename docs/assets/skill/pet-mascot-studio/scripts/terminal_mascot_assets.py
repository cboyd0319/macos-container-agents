#!/usr/bin/env python3
"""Create Terminal.app-safe PNG and ANSI half-block mascot assets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEFAULT_SIZES = "16x18,24x26,32x36,40x44,48x52"
BACKGROUND = (3, 5, 13)


def xterm_palette() -> dict[int, tuple[int, int, int]]:
    levels = [0, 95, 135, 175, 215, 255]
    palette: dict[int, tuple[int, int, int]] = {}
    for red_index, red in enumerate(levels):
        for green_index, green in enumerate(levels):
            for blue_index, blue in enumerate(levels):
                palette[16 + 36 * red_index + 6 * green_index + blue_index] = (
                    red,
                    green,
                    blue,
                )
    for index in range(24):
        value = 8 + index * 10
        palette[232 + index] = (value, value, value)
    return palette


PALETTE = xterm_palette()
PALETTE_ITEMS = sorted(PALETTE.items())


def manifest_reference(path: Path, repo_root: Path | None) -> str:
    if repo_root:
        try:
            return str(path.relative_to(repo_root))
        except ValueError:
            pass
    return str(path)


def resolve_manifest_asset(
    manifest_path: Path,
    raw_path: object,
    repo_root: Path | None,
) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path

    candidates: list[Path] = []
    if repo_root:
        candidates.append(repo_root / path)
    candidates.append(manifest_path.parent / path)
    candidates.append(manifest_path.parent / path.name)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else path


def read_pair(
    item: dict[str, object],
    key: str,
    manifest_path: Path,
    errors: list[str],
) -> tuple[int, int] | None:
    value = item.get(key)
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(part, int) for part in value)
    ):
        errors.append(f"{manifest_path}: {key} must be a two-integer array")
        return None
    return value[0], value[1]


def parse_sizes(raw: str) -> list[tuple[int, int]]:
    sizes: list[tuple[int, int]] = []
    for item in raw.split(","):
        item = item.strip().lower()
        if not item:
            continue
        match = re.fullmatch(r"(\d+)x(\d+)", item)
        if not match:
            raise SystemExit(f"invalid size {item!r}; expected WIDTHxHEIGHT")
        width = int(match.group(1))
        height = int(match.group(2))
        if width < 4 or height < 4:
            raise SystemExit(f"size too small: {item}")
        if height % 2:
            raise SystemExit(f"height must be even for half-block rendering: {item}")
        sizes.append((width, height))
    if not sizes:
        raise SystemExit("at least one --sizes entry is required")
    return sizes


def nearest_xterm(rgb: tuple[int, int, int]) -> tuple[int, tuple[int, int, int]]:
    red, green, blue = rgb
    best_index = 16
    best_distance = 10**12
    for index, (palette_red, palette_green, palette_blue) in PALETTE_ITEMS:
        distance = (
            (red - palette_red) ** 2
            + (green - palette_green) ** 2
            + (blue - palette_blue) ** 2
        )
        if index >= 232:
            distance += 400
        if distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index, PALETTE[best_index]


def isolate_edge_connected_background(
    source: Image.Image,
    dark_threshold: int,
    crop_margin: int,
) -> Image.Image:
    image = source.convert("RGB")
    width, height = image.size
    pixels = image.load()
    seen = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def is_background(x: int, y: int) -> bool:
        red, green, blue = pixels[x, y]
        return max(red, green, blue) <= dark_threshold and (
            red + green + blue
        ) <= dark_threshold * 2

    def add(x: int, y: int) -> None:
        offset = y * width + x
        if not seen[offset] and is_background(x, y):
            seen[offset] = 1
            queue.append((x, y))

    for x in range(width):
        add(x, 0)
        add(x, height - 1)
    for y in range(height):
        add(0, y)
        add(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if x:
            add(x - 1, y)
        if x + 1 < width:
            add(x + 1, y)
        if y:
            add(x, y - 1)
        if y + 1 < height:
            add(x, y + 1)

    rgba = image.convert("RGBA")
    output_pixels = rgba.load()
    for y in range(height):
        for x in range(width):
            if seen[y * width + x]:
                output_pixels[x, y] = (0, 0, 0, 0)
    bbox = rgba.getbbox()
    if not bbox:
        raise SystemExit("failed to isolate a mascot from the source image")
    left, top, right, bottom = bbox
    left = max(0, left - crop_margin)
    top = max(0, top - crop_margin)
    right = min(width, right + crop_margin)
    bottom = min(height, bottom + crop_margin)
    return rgba.crop((left, top, right, bottom))


def render_size(
    base: Image.Image,
    width: int,
    height: int,
    inset: int,
) -> tuple[Image.Image, list[list[int | None]]]:
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    base_width, base_height = base.size
    scale = min((width - inset * 2) / base_width, (height - inset * 2) / base_height)
    resized_width = max(1, round(base_width * scale))
    resized_height = max(1, round(base_height * scale))
    resized = base.resize((resized_width, resized_height), Image.Resampling.LANCZOS)

    resized_pixels = resized.load()
    for y in range(resized_height):
        for x in range(resized_width):
            red, green, blue, alpha = resized_pixels[x, y]
            if alpha < 46:
                resized_pixels[x, y] = (0, 0, 0, 0)
            elif alpha < 180:
                amount = alpha / 255
                resized_pixels[x, y] = (
                    round(red * amount + BACKGROUND[0] * (1 - amount)),
                    round(green * amount + BACKGROUND[1] * (1 - amount)),
                    round(blue * amount + BACKGROUND[2] * (1 - amount)),
                    255,
                )
            else:
                resized_pixels[x, y] = (red, green, blue, 255)

    left = (width - resized_width) // 2
    top = height - resized_height - inset
    canvas.alpha_composite(resized, (left, top))

    index_grid: list[list[int | None]] = [[None for _ in range(width)] for _ in range(height)]
    pixels = canvas.load()
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if not alpha:
                continue
            index, color = nearest_xterm((red, green, blue))
            pixels[x, y] = (*color, 255)
            index_grid[y][x] = index
    return canvas, index_grid


def ansi_halfblock(index_grid: list[list[int | None]], width: int, height: int) -> str:
    lines: list[str] = []
    for y in range(0, height, 2):
        parts: list[str] = []
        for x in range(width):
            top = index_grid[y][x]
            bottom = index_grid[y + 1][x] if y + 1 < height else None
            if top is None and bottom is None:
                parts.append("\x1b[0m ")
            elif top is not None and bottom is None:
                parts.append(f"\x1b[38;5;{top}m▀")
            elif top is None and bottom is not None:
                parts.append(f"\x1b[38;5;{bottom}m▄")
            else:
                parts.append(f"\x1b[38;5;{top};48;5;{bottom}m▀")
        lines.append("".join(parts) + "\x1b[0m")
    return "\n".join(lines) + "\n"


def make_contact_sheet(
    out_dir: Path,
    sizes: list[tuple[int, int]],
    name: str,
    filename: str,
) -> None:
    font = ImageFont.load_default()
    scale = 8
    padding = 18
    label_height = 13
    max_width = max(width for width, _height in sizes) * scale
    max_height = max(height for _width, height in sizes) * scale
    rows: list[Image.Image] = []

    for width, height in sizes:
        image = Image.open(out_dir / f"{name}-halfblock-{width}x{height}-ansi256.png").convert(
            "RGBA"
        )
        enlarged = image.resize((width * scale, height * scale), Image.Resampling.NEAREST)

        checker = Image.new("RGBA", (max_width, max_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(checker)
        tile = 8
        for y in range(0, max_height, tile):
            for x in range(0, max_width, tile):
                color = (
                    (235, 235, 235, 255)
                    if ((x // tile + y // tile) % 2 == 0)
                    else (205, 205, 205, 255)
                )
                draw.rectangle([x, y, x + tile - 1, y + tile - 1], fill=color)
        dark = Image.new("RGBA", (max_width, max_height), (*BACKGROUND, 255))

        position = ((max_width - enlarged.width) // 2, max_height - enlarged.height)
        checker.alpha_composite(enlarged, position)
        dark.alpha_composite(enlarged, position)

        row = Image.new(
            "RGBA",
            (max_width * 2 + padding * 3, max_height + label_height + padding),
            (255, 255, 255, 255),
        )
        row_draw = ImageDraw.Draw(row)
        row_draw.text(
            (padding, 4),
            f"{width}x{height}px  half-block {width}x{height // 2} cells",
            fill=(20, 24, 32),
            font=font,
        )
        row.alpha_composite(checker, (padding, label_height + padding // 2))
        row.alpha_composite(dark, (max_width + padding * 2, label_height + padding // 2))
        rows.append(row)

    contact = Image.new("RGBA", (rows[0].width, sum(row.height for row in rows)), (255, 255, 255, 255))
    y = 0
    for row in rows:
        contact.alpha_composite(row, (0, y))
        y += row.height
    contact.save(out_dir / filename)


def validate_manifest(manifest_path: Path, repo_root: Path | None = None) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    legal_colors = set(PALETTE.values())
    ansi_pattern = re.compile(
        r"\x1b\[(?:0|38;5;(?:1[6-9]|[2-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])"
        r"(?:;48;5;(?:1[6-9]|[2-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))?)m|[▀▄ \n]"
    )
    manifest_repo_root = manifest.get("repo_root")
    if repo_root is None and isinstance(manifest_repo_root, str) and manifest_repo_root:
        repo_root = Path(manifest_repo_root).expanduser().resolve()
    sizes = manifest.get("sizes")
    if not isinstance(sizes, list) or not sizes:
        errors.append(f"{manifest_path}: sizes must be a non-empty list")
        return {"ok": False, "errors": errors}
    for item in sizes:
        if not isinstance(item, dict):
            errors.append(f"{manifest_path}: size entry is not an object")
            continue
        pixels = read_pair(item, "pixels", manifest_path, errors)
        terminal_cells = read_pair(item, "terminal_cells_halfblock", manifest_path, errors)
        if pixels is None or terminal_cells is None:
            continue
        width, height = pixels
        columns, rows = terminal_cells
        png = resolve_manifest_asset(manifest_path, item.get("png"), repo_root)
        ansi = resolve_manifest_asset(manifest_path, item.get("ansi"), repo_root)
        if png is None:
            errors.append(f"{manifest_path}: size {width}x{height} has no png path")
            continue
        if ansi is None:
            errors.append(f"{manifest_path}: size {width}x{height} has no ansi path")
            continue
        if not png.exists():
            errors.append(f"{png}: missing PNG asset")
            continue
        if not ansi.exists():
            errors.append(f"{ansi}: missing ANSI asset")
            continue
        with Image.open(png) as image:
            rgba = image.convert("RGBA")
            if rgba.size != (width, height):
                errors.append(f"{png}: expected {width}x{height}, got {rgba.width}x{rgba.height}")
            data = (
                rgba.get_flattened_data()
                if hasattr(rgba, "get_flattened_data")
                else rgba.getdata()
            )
            for red, green, blue, alpha in data:
                if alpha and (red, green, blue) not in legal_colors:
                    errors.append(f"{png}: color {(red, green, blue)} is not in xterm 256 palette")
                    break
        ansi_text = ansi.read_text(encoding="utf-8")
        remainder = ansi_pattern.sub("", ansi_text)
        if remainder:
            errors.append(f"{ansi}: illegal ANSI/text payload {remainder[:20]!r}")
        plain_lines = re.sub(r"\x1b\[[0-9;]*m", "", ansi_text).splitlines()
        if len(plain_lines) != rows:
            errors.append(f"{ansi}: expected {rows} lines, got {len(plain_lines)}")
        if any(len(line) != columns for line in plain_lines):
            errors.append(f"{ansi}: expected every line to be {columns} cells")
        if any(index < 16 or index > 255 for index in item.get("ansi_256_indices", [])):
            errors.append(f"{ansi}: ANSI index outside 16-255")
    return {"ok": not errors, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source")
    parser.add_argument("--output-dir")
    parser.add_argument("--sizes", default=DEFAULT_SIZES)
    parser.add_argument("--name", default="cubby")
    parser.add_argument("--dark-threshold", type=int, default=40)
    parser.add_argument("--crop-margin", type=int, default=18)
    parser.add_argument("--inset", type=int, default=1)
    parser.add_argument("--repo-root", help="Use for repo-relative paths in manifest.")
    parser.add_argument(
        "--validate-only",
        metavar="MANIFEST",
        help="Validate an existing manifest without regenerating assets.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else None

    if args.validate_only:
        manifest_path = Path(args.validate_only).expanduser().resolve()
        if not manifest_path.is_file():
            raise SystemExit(f"manifest not found: {manifest_path}")
        validation = validate_manifest(manifest_path, repo_root=repo_root)
        print(json.dumps({**validation, "manifest": str(manifest_path)}, indent=2))
        if not validation["ok"]:
            sys.exit(1)
        return

    if not args.source:
        parser.error("--source is required unless --validate-only is used")
    if not args.output_dir:
        parser.error("--output-dir is required unless --validate-only is used")

    source = Path(args.source).expanduser().resolve()
    out_dir = Path(args.output_dir).expanduser().resolve()
    sizes = parse_sizes(args.sizes)
    if not source.is_file():
        raise SystemExit(f"source image not found: {source}")
    out_dir.mkdir(parents=True, exist_ok=True)

    base = isolate_edge_connected_background(
        Image.open(source),
        dark_threshold=args.dark_threshold,
        crop_margin=args.crop_margin,
    )
    base.save(out_dir / f"{args.name}-terminal-source-transparent.png")

    manifest = {
        "source": str(source),
        "method": "edge-connected dark background removal, aspect-fit resize with safety inset, hard alpha, nearest stable xterm-256 quantization, half-block ANSI export",
        "terminal_palette": "xterm 256-color indices 16-255 only; base indices 0-15 intentionally avoided for macOS Terminal.app profile stability",
        "sizes": [],
    }
    if repo_root:
        manifest["repo_root"] = str(repo_root)
    for width, height in sizes:
        image, grid = render_size(base, width, height, inset=args.inset)
        stem = f"{args.name}-halfblock-{width}x{height}-ansi256"
        png = out_dir / f"{stem}.png"
        ansi = out_dir / f"{stem}.ansi"
        image.save(png)
        ansi.write_text(ansi_halfblock(grid, width, height), encoding="utf-8")
        used = sorted({index for row in grid for index in row if index is not None})
        manifest["sizes"].append(
            {
                "pixels": [width, height],
                "terminal_cells_halfblock": [width, height // 2],
                "png": manifest_reference(png, repo_root),
                "ansi": manifest_reference(ansi, repo_root),
                "ansi_256_indices": used,
                "unique_colors": len(used),
            }
        )

    make_contact_sheet(out_dir, sizes, args.name, f"{args.name}-halfblock-ansi256-contact-sheet.png")
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    validation = validate_manifest(manifest_path, repo_root=repo_root)
    print(
        json.dumps(
            {
                **validation,
                "output_dir": str(out_dir),
                "manifest": str(manifest_path),
                "contact_sheet": str(out_dir / f"{args.name}-halfblock-ansi256-contact-sheet.png"),
            },
            indent=2,
        )
    )
    if not validation["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
