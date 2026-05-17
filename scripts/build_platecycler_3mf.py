#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from build_3mf import build_repeated_plate_3mf


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = ROOT / "m5sticks3_click_case_template.3mf"
DEFAULT_STL = ROOT / "m5sticks3_click_case_with_logo.stl"
DEFAULT_LOGO_HEIGHT_STL = ROOT / "m5sticks3_click_case_color_logo_insert_embossed.stl"
DEFAULT_OUTPUT = ROOT / "m5sticks3_click_case_orangecon_x10_x8.3mf"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a repeated multi-plate Bambu 3MF from the single-material "
            "with-logo M5StickS3 case. Plate count and per-plate case count "
            "are configurable."
        )
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--plates", default=8, type=int)
    parser.add_argument("--cases-per-plate", default=10, type=int)
    parser.add_argument("--bed-x", default=90.0, type=float)
    parser.add_argument("--bed-y", default=90.0, type=float)
    parser.add_argument("--gap", default=2.5, type=float)
    parser.add_argument(
        "--x-offset",
        default=0.0,
        type=float,
        help="Non-negative inset from the right edge for the bottom-right layout.",
    )
    parser.add_argument(
        "--y-offset",
        default=0.0,
        type=float,
        help="Non-negative inset from the bottom edge for the bottom-right layout.",
    )
    parser.add_argument(
        "--plate-columns",
        default=3,
        type=int,
        help="Number of logical Bambu plates per row in the project canvas.",
    )
    parser.add_argument(
        "--plate-gap",
        default=36.0,
        type=float,
        help="Gap between logical Bambu plates in the project canvas.",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_repeated_plate_3mf(
        template_path=DEFAULT_TEMPLATE,
        stl_path=DEFAULT_STL,
        output_path=args.output,
        plate_count=args.plates,
        cases_per_plate=args.cases_per_plate,
        bed_x=args.bed_x,
        bed_y=args.bed_y,
        gap=args.gap,
        x_offset=args.x_offset,
        y_offset=args.y_offset,
        plate_columns=args.plate_columns,
        plate_gap=args.plate_gap,
        logo_height_stl=DEFAULT_LOGO_HEIGHT_STL,
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
