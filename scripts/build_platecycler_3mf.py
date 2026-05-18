#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from build_3mf import build_repeated_plate_3mf
from threemf_utils import DEFAULT_BED_X, DEFAULT_BED_Y, cli_entry


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = ROOT / "m5sticks3_click_case_template.3mf"
DEFAULT_STL = ROOT / "m5sticks3_click_case_with_logo.stl"
DEFAULT_LOGO_HEIGHT_STL = ROOT / "m5sticks3_click_case_color_logo_insert_embossed.stl"
DEFAULT_OUTPUT = ROOT / "m5sticks3_click_case_orangecon_x80.3mf"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a repeated multi-plate Bambu 3MF from the single-material "
            "with-logo M5StickS3 case. The builder computes per-plate "
            "capacity and adds plates from the requested total badge count."
        )
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--badges", default=80, type=int)
    parser.add_argument("--bed-x", default=DEFAULT_BED_X, type=float)
    parser.add_argument("--bed-y", default=DEFAULT_BED_Y, type=float)
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
        default=None,
        type=int,
        help=(
            "Override the logical Bambu plates per row. By default this is "
            "derived from the plate count to match observed Bambu Studio "
            "multi-plate layouts."
        ),
    )
    parser.add_argument(
        "--plate-gap",
        default=36.0,
        type=float,
        help="Gap between logical Bambu plates in the project canvas.",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary = build_repeated_plate_3mf(
        template_path=DEFAULT_TEMPLATE,
        stl_path=DEFAULT_STL,
        output_path=args.output,
        badge_count=args.badges,
        bed_x=args.bed_x,
        bed_y=args.bed_y,
        gap=args.gap,
        x_offset=args.x_offset,
        y_offset=args.y_offset,
        plate_columns=args.plate_columns,
        plate_gap=args.plate_gap,
        logo_height_stl=DEFAULT_LOGO_HEIGHT_STL,
    )
    print(
        f"{args.output} "
        f"({summary.badge_count} badges, {summary.plate_count} plates, "
        f"{summary.badges_per_full_plate} badges/full plate)"
    )
    return 0


if __name__ == "__main__":
    cli_entry(main)
