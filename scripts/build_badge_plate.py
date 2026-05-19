#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from build_3mf import build_plate_3mf
from threemf_utils import DEFAULT_BED_X, DEFAULT_BED_Y, cli_entry


ROOT = Path(__file__).resolve().parent.parent
SCAD = ROOT / "m5sticks3_click_case.scad"
LOGO_SCRIPT = ROOT / "scripts" / "build_logo_svg.py"
SINGLE_TEMPLATE = ROOT / "m5sticks3_click_case_template.3mf"
COLOR_TEMPLATE = ROOT / "m5sticks3_click_case_color_template.3mf"
DEFAULT_OUTPUT = ROOT / "m5sticks3_click_case_badge_plate.3mf"
DEFAULT_WORK_DIR = ROOT / "build" / "badge_plate"
FLUSH_BACKING = 0.45
MAX_BADGES = 10
DEFAULT_X_OFFSET = 20.0
DEFAULT_Y_OFFSET = -20.0
# SVG uses 96 dpi; OpenSCAD's SVG import treats lengths as PostScript points
# (72 dpi). Scale logo metrics by 96/72 = 4/3 before passing them as defines.
SVG_TO_OPENSCAD = 4.0 / 3.0

LogoMetrics = dict[str, float]


@dataclass(frozen=True)
class Variant:
    template: Path
    color_logo_style: str
    output_parts: tuple[str, ...]
    patch_color_metadata: bool = False
    detect_thin_wall: bool = False
    inner_wall_backing: float = 0


VARIANTS = {
    "with-logo": Variant(
        template=SINGLE_TEMPLATE,
        color_logo_style="embossed",
        output_parts=("full",),
    ),
    "color-logo-embossed": Variant(
        template=COLOR_TEMPLATE,
        color_logo_style="embossed",
        output_parts=("body", "logo"),
        patch_color_metadata=True,
    ),
    "color-logo-flush": Variant(
        template=COLOR_TEMPLATE,
        color_logo_style="flush",
        output_parts=("body", "logo"),
        patch_color_metadata=True,
    ),
    "color-logo-flush-backed": Variant(
        template=COLOR_TEMPLATE,
        color_logo_style="flush",
        output_parts=("body", "logo"),
        patch_color_metadata=True,
        detect_thin_wall=True,
        inner_wall_backing=FLUSH_BACKING,
    ),
}


def parse_texts(args: argparse.Namespace) -> list[str]:
    texts: list[str] = []

    if args.texts:
        texts.extend(
            text.strip() for text in re.split(r"[\n,]", args.texts) if text.strip()
        )

    if args.text:
        texts.extend(text.strip() for text in args.text if text.strip())

    if args.texts_file:
        texts.extend(
            line.strip()
            for line in args.texts_file.read_text().splitlines()
            if line.strip()
        )

    if not texts:
        raise ValueError("provide at least one logo text")
    if len(texts) > MAX_BADGES:
        raise ValueError(f"a badge plate can contain at most {MAX_BADGES} cases")

    return texts


def slugify(text: str, index: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip()).strip("_")
    if not slug:
        slug = f"badge_{index:02d}"
    return slug[:40]


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=ROOT)


def openscad_define(name: str, value: str | float) -> str:
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{name}="{escaped}"'
    return f"{name}={value}"


def render_logo_svg(
    text: str,
    output_path: Path,
    font_path: Path,
    fill_outline: bool,
) -> LogoMetrics:
    metrics_path = output_path.with_suffix(".json")
    command = [
        sys.executable,
        str(LOGO_SCRIPT),
        "--text",
        text,
        "--font",
        str(font_path),
        "--output",
        str(output_path),
        "--preserve-aspect",
        "--metrics-output",
        str(metrics_path),
    ]
    if fill_outline:
        command.append("--outline")
    run(command)
    return json.loads(metrics_path.read_text())


def render_stl(
    variant: Variant,
    svg_path: Path,
    logo_metrics: LogoMetrics,
    output_part: str,
    output_path: Path,
) -> None:
    defines = [
        openscad_define("right_logo_svg", str(svg_path)),
        openscad_define("right_logo_src_x0", logo_metrics["x0"] * SVG_TO_OPENSCAD),
        openscad_define("right_logo_src_y0", logo_metrics["y0"] * SVG_TO_OPENSCAD),
        openscad_define("right_logo_text_w", logo_metrics["width"] * SVG_TO_OPENSCAD),
        openscad_define("right_logo_text_h", logo_metrics["height"] * SVG_TO_OPENSCAD),
        openscad_define("output_part", output_part),
        openscad_define("color_logo_style", variant.color_logo_style),
    ]
    if variant.inner_wall_backing:
        defines.append(
            openscad_define(
                "color_logo_inner_wall_backing",
                variant.inner_wall_backing,
            )
        )

    command = ["openscad"]
    for define in defines:
        command.extend(["-D", define])
    command.extend(["-o", str(output_path), str(SCAD)])
    run(command)


def build_badge_assets(
    texts: list[str],
    variant: Variant,
    work_dir: Path,
    font_path: Path,
    fill_outline: bool,
) -> list[list[Path]]:
    item_stl_paths: list[list[Path]] = []
    work_dir.mkdir(parents=True, exist_ok=True)

    for index, text in enumerate(texts, start=1):
        slug = slugify(text, index)
        stem = f"{index:02d}_{slug}"
        svg_path = work_dir / f"{stem}.svg"
        logo_metrics = render_logo_svg(text, svg_path, font_path, fill_outline)

        item_paths = []
        for output_part in variant.output_parts:
            stl_path = work_dir / f"{stem}_{output_part}.stl"
            render_stl(variant, svg_path, logo_metrics, output_part, stl_path)
            item_paths.append(stl_path)

        item_stl_paths.append(item_paths)

    return item_stl_paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            f"Build a Bambu 3MF plate with up to {MAX_BADGES} "
            "M5StickS3 badge cases, "
            "each using custom side-logo text."
        )
    )
    parser.add_argument(
        "--variant",
        default="with-logo",
        choices=sorted(VARIANTS),
        help="Case/print variant to put on the plate.",
    )
    parser.add_argument(
        "--texts",
        help="Comma- or newline-separated logo texts.",
    )
    parser.add_argument(
        "--text",
        action="append",
        help="One logo text. May be repeated.",
    )
    parser.add_argument(
        "--texts-file",
        type=Path,
        help="File with one logo text per line.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--work-dir", default=DEFAULT_WORK_DIR, type=Path)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--bed-x", default=DEFAULT_BED_X, type=float)
    parser.add_argument("--bed-y", default=DEFAULT_BED_Y, type=float)
    parser.add_argument("--columns", default=4, type=int)
    parser.add_argument("--gap", default=5.0, type=float)
    parser.add_argument(
        "--x-offset",
        default=DEFAULT_X_OFFSET,
        type=float,
        help="Shift the whole badge grid on the plate in millimeters.",
    )
    parser.add_argument(
        "--y-offset",
        default=DEFAULT_Y_OFFSET,
        type=float,
        help="Shift the whole badge grid on the plate in millimeters.",
    )
    parser.add_argument(
        "--outline",
        action="store_true",
        help=(
            "Treat the font as an outline font and fill the outer silhouettes "
            "before generating each badge SVG."
        ),
    )
    args = parser.parse_args()

    texts = parse_texts(args)
    variant = VARIANTS[args.variant]
    item_stl_paths = build_badge_assets(
        texts, variant, args.work_dir, args.font, args.outline
    )
    item_names = [
        f"M5StickS3 Click Case Badge {index:02d} - {text}"
        for index, text in enumerate(texts, start=1)
    ]
    logo_part_names = [f"{text} logo insert" for text in texts]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_plate_3mf(
        template_path=variant.template,
        item_stl_paths=item_stl_paths,
        output_path=args.output,
        bed_x=args.bed_x,
        bed_y=args.bed_y,
        detect_thin_wall=variant.detect_thin_wall,
        patch_color_metadata=variant.patch_color_metadata,
        item_names=item_names,
        logo_part_names=logo_part_names,
        columns=args.columns,
        gap=args.gap,
        x_offset=args.x_offset,
        y_offset=args.y_offset,
    )
    print(f"{args.output} ({len(texts)} badges, variant {args.variant})")
    return 0


if __name__ == "__main__":
    cli_entry(main)
