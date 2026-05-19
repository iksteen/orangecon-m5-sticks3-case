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


def format_float(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SVG_PATH = ROOT / "orangecon_logo_filled.svg"

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


def contour_bounds(contour: Contour) -> Bounds | None:
    points = iter_points([contour])
    if not points:
        return None

    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return (min(xs), min(ys), max(xs), max(ys))


def bounds_contains(outer: Bounds | None, inner: Bounds | None) -> bool:
    if outer is None or inner is None:
        return False

    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    if len(polygon) < 3:
        return False

    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) == (y2 > y):
            continue
        x_intersection = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        if x < x_intersection:
            inside = not inside

    return inside


def contour_nesting_depths(contours: list[Contour]) -> list[int]:
    polygons = [iter_points([contour]) for contour in contours]
    bounds = [contour_bounds(contour) for contour in contours]
    areas = [abs(contour_signed_area(contour)) for contour in contours]
    depths: list[int] = []

    for index, polygon in enumerate(polygons):
        if not polygon:
            depths.append(0)
            continue

        depth = 0
        point = polygon[0]
        for candidate_index, candidate_polygon in enumerate(polygons):
            if candidate_index == index or areas[candidate_index] <= areas[index]:
                continue
            if not bounds_contains(bounds[candidate_index], bounds[index]):
                continue
            if point_in_polygon(point, candidate_polygon):
                depth += 1
        depths.append(depth)

    return depths


def outline_filled_contours_by_area(contours: list[Contour]) -> list[Contour]:
    if not contours:
        return []

    signed_areas = [contour_signed_area(contour) for contour in contours]
    exterior_candidates = [
        (index, area) for index, area in enumerate(signed_areas) if area != 0
    ]
    if not exterior_candidates:
        return contours

    exterior_index, exterior_area = max(
        exterior_candidates, key=lambda item: abs(item[1])
    )
    exterior_sign = 1 if exterior_area > 0 else -1
    interior_candidates = [
        (index, abs(area))
        for index, area in enumerate(signed_areas)
        if area * exterior_sign < 0
    ]
    outline_interior_index = None
    if interior_candidates:
        outline_interior_index, _ = max(interior_candidates, key=lambda item: item[1])

    keep = [exterior_index]
    keep.extend(
        index
        for index, area in enumerate(signed_areas)
        if area * exterior_sign < 0 and index != outline_interior_index
    )

    return [contours[index] for index in keep]


def outline_filled_contours(contours: list[Contour]) -> list[Contour]:
    if not contours:
        return []

    # Outline fonts model the visible stroke as nested contour pairs. To convert
    # that into a filled glyph, keep the contours that correspond to the original
    # filled-font boundaries: outer silhouettes and real counters.
    depths = contour_nesting_depths(contours)
    keep = [index for index, depth in enumerate(depths) if depth % 4 in {0, 3}]
    if len(contours) > 1 and max(depths) == 0:
        return outline_filled_contours_by_area(contours)
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


def collect_wordmark(
    font: TTFont, text: str, fill_outline: bool = False
) -> tuple[PlacedContours, Bounds]:
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
        contours = split_contours(pen.value)
        if fill_outline:
            contours = outline_filled_contours(contours)

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

    svg_pen = SVGPathPen(None, ntos=format_float)
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
        description="Render logo text to filled SVG paths."
    )
    parser.add_argument("--text", required=True)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--output", default=DEFAULT_SVG_PATH, type=Path)
    parser.add_argument(
        "--outline",
        action="store_true",
        help=(
            "Treat the font as an outline font and fill the outer silhouettes "
            "while preserving counters."
        ),
    )
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
    placed_contours, bounds = collect_wordmark(font, args.text, args.outline)
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
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
