#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
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
DEFAULT_SVG_PATH = ROOT / "orangecon_logo_filled.svg"

DEFAULT_TEXT = "ORANGECON"
# Preserve the traced SVG footprint so the existing OpenSCAD placement remains stable.
TARGET_WIDTH = 643.0
TARGET_HEIGHT = 74.0
CUBIC_APPROX_ERROR = 1.0

Point = tuple[float, float]
Command = tuple[str, tuple[object, ...]]
Contour = list[Command]
PlacedContours = list[tuple[float, list[Contour]]]
Bounds = tuple[float, float, float, float]
SvgMetrics = dict[str, float]

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


def selected_contours(contours: list[Contour]) -> list[Contour]:
    if not contours:
        return []

    signed_areas = [contour_signed_area(contour) for contour in contours]
    exterior_candidates = [
        (index, abs(area)) for index, area in enumerate(signed_areas) if area < 0
    ]
    if not exterior_candidates:
        return [contours[0]]

    exterior_index, _ = max(exterior_candidates, key=lambda item: item[1])
    interior_candidates = [
        (index, area) for index, area in enumerate(signed_areas) if area > 0
    ]
    outline_interior_index = None
    if interior_candidates:
        outline_interior_index, _ = max(interior_candidates, key=lambda item: item[1])

    # Brave Hearted is an outline font. For a filled wordmark, keep the largest
    # clockwise contour as the glyph silhouette, discard the largest opposite
    # contour that forms the hollow outline-font stroke, and keep smaller
    # opposite contours as real counters.
    keep = [exterior_index]
    keep.extend(
        index
        for index, area in enumerate(signed_areas)
        if area > 0 and index != outline_interior_index
    )

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


def contour_signed_area(contour: Contour) -> float:
    points = iter_points([contour])
    if len(points) < 3:
        return 0

    return (
        sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
        )
        / 2
    )


def glyph_kerning(font: TTFont, left: str, right: str) -> int:
    if "kern" not in font:
        return 0

    return sum(
        subtable.kernTable.get((left, right), 0) for subtable in font["kern"].kernTables
    )


def collect_wordmark(font: TTFont, text: str) -> tuple[PlacedContours, Bounds]:
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    missing = sorted({char for char in text if ord(char) not in cmap})
    if missing:
        raise ValueError(f"font does not contain glyphs for: {''.join(missing)!r}")

    x_offset = 0
    placed_contours: PlacedContours = []
    all_points: list[Point] = []

    for index, char in enumerate(text):
        glyph_name = cmap[ord(char)]
        pen = RecordingPen()
        glyph_set[glyph_name].draw(pen)
        contours = selected_contours(split_contours(pen.value))

        placed_contours.append((x_offset, contours))
        all_points.extend(iter_points(contours, x_offset))

        x_offset += hmtx[glyph_name][0]
        if index + 1 < len(text):
            next_glyph_name = cmap[ord(text[index + 1])]
            x_offset += glyph_kerning(font, glyph_name, next_glyph_name)

    if not all_points:
        raise RuntimeError("text must contain at least one drawable glyph")

    xs = [x for x, _ in all_points]
    ys = [y for _, y in all_points]
    return placed_contours, (min(xs), min(ys), max(xs), max(ys))


def replay_contour(contour: Contour, pen) -> None:
    for command, args in contour:
        getattr(pen, command)(*args)


def build_path(
    placed_contours: PlacedContours,
    bounds: Bounds,
    preserve_aspect: bool = False,
) -> tuple[str, SvgMetrics]:
    min_x, min_y, max_x, max_y = bounds
    source_w = max_x - min_x
    source_h = max_y - min_y
    scale_x = TARGET_WIDTH / source_w
    scale_y = TARGET_HEIGHT / source_h
    path_x0 = 0.0
    path_y0 = 0.0

    if preserve_aspect:
        scale_x = scale_y = min(scale_x, scale_y)

    svg_pen = SVGPathPen(None, ntos=format_number)
    for x_offset, contours in placed_contours:
        transform = (
            scale_x,
            0,
            0,
            -scale_y,
            (x_offset - min_x) * scale_x + path_x0,
            max_y * scale_y + path_y0,
        )
        pen = Qu2CuPen(
            TransformPen(svg_pen, transform),
            max_err=CUBIC_APPROX_ERROR,
            all_cubic=True,
        )
        for contour in contours:
            replay_contour(contour, pen)

    return svg_pen.getCommands(), {
        "x0": path_x0,
        "y0": path_y0,
        "width": source_w * scale_x,
        "height": source_h * scale_y,
    }


def write_svg(path_data: str, output_path: Path) -> None:
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(ET.tostring(svg, encoding="utf-8", xml_declaration=True))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render Brave Hearted logo text to filled SVG paths."
    )
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--font", default=FONT_PATH, type=Path)
    parser.add_argument("--output", default=DEFAULT_SVG_PATH, type=Path)
    parser.add_argument(
        "--preserve-aspect",
        action="store_true",
        help="Use uniform X/Y scaling and center the text in the SVG canvas.",
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        help="Optional JSON file with the scaled path bounds inside the SVG.",
    )
    args = parser.parse_args()

    if not args.text:
        raise ValueError("logo text must not be empty")
    if not args.font.exists():
        raise FileNotFoundError(f"missing font: {args.font}")

    font = TTFont(args.font)
    placed_contours, bounds = collect_wordmark(font, args.text)
    path_data, metrics = build_path(placed_contours, bounds, args.preserve_aspect)
    write_svg(path_data, args.output)
    if args.metrics_output:
        args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_output.write_text(json.dumps(metrics, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
