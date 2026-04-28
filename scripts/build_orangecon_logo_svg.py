#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = ROOT / "fonts" / "brave-hearted.ttf"
RAW_PNG_PATH = ROOT / "orangecon_logo_raw.png"
FILLED_PNG_PATH = ROOT / "orangecon_logo_filled.png"
PBM_PATH = ROOT / "orangecon_logo_filled.pbm"
SVG_PATH = ROOT / "orangecon_logo_filled.svg"

TEXT = "ORANGECON"
FONT_SIZE = 100
THRESHOLD = 200
# Keep only small enclosed white regions as counters (e.g. O, A, R).
COUNTER_MAX_AREA = 1000


def render_raw_wordmark() -> Image.Image:
    font = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)
    image = Image.new("L", (3000, 600), 255)
    draw = ImageDraw.Draw(image)
    draw.text((0, 0), TEXT, font=font, fill=0)

    pixels = image.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(image.size[1]):
        for x in range(image.size[0]):
            if pixels[x, y] < 128:
                xs.append(x)
                ys.append(y)

    if not xs or not ys:
        raise RuntimeError("failed to rasterize Brave Hearted wordmark")

    bbox = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    cropped = image.crop(bbox)
    cropped.save(RAW_PNG_PATH)
    return cropped


def build_filled_bitmap(raw: Image.Image) -> None:
    image = raw.point(lambda p: 0 if p < THRESHOLD else 255, mode="L")
    width, height = image.size
    src = image.load()

    out = Image.new("L", (width, height), 255)
    dst = out.load()

    # Keep the original black outlines.
    for y in range(height):
        for x in range(width):
            if src[x, y] == 0:
                dst[x, y] = 0

    visited = bytearray(width * height)

    def index(x: int, y: int) -> int:
        return y * width + x

    for start_y in range(height):
        for start_x in range(width):
            if src[start_x, start_y] != 255 or visited[index(start_x, start_y)]:
                continue

            queue = deque([(start_x, start_y)])
            visited[index(start_x, start_y)] = 1
            component: list[tuple[int, int]] = []
            touches_border = (
                start_x == 0
                or start_y == 0
                or start_x == width - 1
                or start_y == height - 1
            )

            while queue:
                x, y = queue.popleft()
                component.append((x, y))

                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        idx = index(nx, ny)
                        if src[nx, ny] == 255 and not visited[idx]:
                            visited[idx] = 1
                            if nx in (0, width - 1) or ny in (0, height - 1):
                                touches_border = True
                            queue.append((nx, ny))

            keep_white = touches_border or len(component) <= COUNTER_MAX_AREA
            fill = 255 if keep_white else 0
            for x, y in component:
                dst[x, y] = fill

    out = out.convert("1")
    out.save(FILLED_PNG_PATH)
    out.save(PBM_PATH)


def trace_svg() -> None:
    try:
        subprocess.run(
            ["potrace", "-s", "-o", str(SVG_PATH), str(PBM_PATH)],
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("potrace is required to generate orangecon_logo_filled.svg") from exc


def main() -> int:
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"missing font: {FONT_PATH}")

    raw = render_raw_wordmark()
    build_filled_bitmap(raw)
    trace_svg()
    print(SVG_PATH)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
