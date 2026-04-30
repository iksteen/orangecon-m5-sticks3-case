#!/usr/bin/env python3

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = ROOT / "fonts" / "brave-hearted.ttf"
SVG_PATH = ROOT / "orangecon_logo_filled.svg"

TEXT = "ORANGECON"
# Preserve the traced SVG footprint so the existing OpenSCAD placement remains stable.
TARGET_WIDTH = 643.0
TARGET_HEIGHT = 74.0
CUBIC_APPROX_ERROR = 1.0
COUNTER_GLYPHS = {"O", "R", "A"}

Point = tuple[float, float]
Command = tuple[str, tuple[object, ...]]
Contour = list[Command]
PlacedContours = list[tuple[float, list[Contour]]]
Bounds = tuple[float, float, float, float]

SVG_NS = "http://www.w3.org/2000/svg"

ET.register_namespace("", SVG_NS)


def format_number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def split_contours(commands: list[Command]) -> list[Contour]:
    contours: list[Contour] = []
    contour: Contour = []

    for command in commands:
        name, _ = command
        if name == "moveTo":
            contour = []

        contour.append(command)

        if name in {"closePath", "endPath"}:
            contours.append(contour)
            contour = []

    if contour:
        contours.append(contour)

    return contours


def selected_contours(char: str, contours: list[Contour]) -> list[Contour]:
    if not contours:
        return []

    keep = [0]
    # Brave Hearted is an outline font: contour 0 is the exterior, intermediate
    # contours are the hollow outline interior, and the final contour is the
    # visible counter for glyphs that need one.
    if char in COUNTER_GLYPHS and len(contours) > 1:
        keep.append(len(contours) - 1)

    return [contours[index] for index in keep]


def iter_points(contours: list[Contour], x_offset: float = 0) -> list[Point]:
    points: list[Point] = []
    for contour in contours:
        for _, args in contour:
            for arg in args:
                if isinstance(arg, tuple) and len(arg) == 2:
                    x, y = arg
                    points.append((x_offset + float(x), float(y)))
    return points


def glyph_kerning(font: TTFont, left: str, right: str) -> int:
    if "kern" not in font:
        return 0

    return sum(
        subtable.kernTable.get((left, right), 0) for subtable in font["kern"].kernTables
    )


def collect_wordmark(font: TTFont) -> tuple[PlacedContours, Bounds]:
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]

    x_offset = 0
    placed_contours: PlacedContours = []
    all_points: list[Point] = []

    for index, char in enumerate(TEXT):
        glyph_name = cmap[ord(char)]
        pen = RecordingPen()
        glyph_set[glyph_name].draw(pen)
        contours = selected_contours(char, split_contours(pen.value))

        placed_contours.append((x_offset, contours))
        all_points.extend(iter_points(contours, x_offset))

        x_offset += hmtx[glyph_name][0]
        if index + 1 < len(TEXT):
            next_glyph_name = cmap[ord(TEXT[index + 1])]
            x_offset += glyph_kerning(font, glyph_name, next_glyph_name)

    if not all_points:
        raise RuntimeError("failed to extract Brave Hearted wordmark contours")

    xs = [x for x, _ in all_points]
    ys = [y for _, y in all_points]
    return placed_contours, (min(xs), min(ys), max(xs), max(ys))


def replay_contour(contour: Contour, pen) -> None:
    for command, args in contour:
        getattr(pen, command)(*args)


def build_path(placed_contours: PlacedContours, bounds: Bounds) -> str:
    min_x, min_y, max_x, max_y = bounds
    scale_x = TARGET_WIDTH / (max_x - min_x)
    scale_y = TARGET_HEIGHT / (max_y - min_y)

    svg_pen = SVGPathPen(None, ntos=format_number)
    for x_offset, contours in placed_contours:
        transform = (
            scale_x,
            0,
            0,
            -scale_y,
            (x_offset - min_x) * scale_x,
            max_y * scale_y,
        )
        pen = Qu2CuPen(
            TransformPen(svg_pen, transform),
            max_err=CUBIC_APPROX_ERROR,
            all_cubic=True,
        )
        for contour in contours:
            replay_contour(contour, pen)

    return svg_pen.getCommands()


def write_svg(path_data: str) -> None:
    svg = ET.Element(
        "svg",
        {
            "version": "1.1",
            "xmlns": SVG_NS,
            "width": f"{TARGET_WIDTH:.6f}pt",
            "height": f"{TARGET_HEIGHT:.6f}pt",
            "viewBox": f"0 0 {TARGET_WIDTH:.6f} {TARGET_HEIGHT:.6f}",
            "preserveAspectRatio": "xMidYMid meet",
        },
    )
    ET.SubElement(
        svg,
        "path",
        {"fill": "#000000", "stroke": "none", "d": path_data},
    )

    SVG_PATH.write_bytes(ET.tostring(svg, encoding="utf-8", xml_declaration=True))


def main() -> int:
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"missing font: {FONT_PATH}")

    font = TTFont(FONT_PATH)
    placed_contours, bounds = collect_wordmark(font)
    write_svg(build_path(placed_contours, bounds))
    print(SVG_PATH)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
