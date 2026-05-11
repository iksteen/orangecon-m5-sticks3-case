#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo


PLATE_GCODE_RE = re.compile(r"^Metadata/plate_(\d+)\.gcode$")
PLATE_GCODE_MD5_RE = re.compile(r"^Metadata/plate_(\d+)\.gcode\.md5$")

# Captured from the Chitu PlateCycler web tool output. It ejects the completed
# plate and returns the toolhead/bed to a state where the next sliced plate gcode
# can run its normal startup sequence.
DEFAULT_SWAP_GCODE = (
    "G0 X-10 F5000; \n"
    " G0 Z175; \n"
    " G0 Y-5 F2000;  \n"
    "  G0 Y186.5 F2000;  \n"
    "  G0 Y182 F10000;  \n"
    "  G0 Z186 ;\n"
    "  G0 X180 F5000;\n"
    " G0 Y120 F500; \n"
    " G0 Y-4 Z175 X-15 F3000; \n"
    " G0 Y145; \n"
    "  G0 Y115 F1000; \n"
    " G0 Y25 F500; \n"
    " G0 Y85 F1000; \n"
    " G0 Y180 F1000; \n"
    " G0 X-10 F5000;\n"
    " G4 P500; wait  \n"
    " G0 Y186.5 F200; \n"
    " G4 P500; wait  \n"
    " G0 Y3 F3000; \n"
    " G0 Y-5 F200; \n"
    "G4 P500; wait  \n"
    " G0 Y10 F1000; \n"
    " G0 Z100 Y186 F2000; \n"
    " G0 Y150; \n"
    " G4 P1000; wait;"
)


@dataclass
class FilamentUsage:
    attrs: dict[str, str]
    used_g: Decimal = field(default_factory=lambda: Decimal("0"))
    used_m: Decimal = field(default_factory=lambda: Decimal("0"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inject Chitu PlateCycler plate-swap gcode into a sliced "
            "multi-plate Bambu Studio 3MF."
        )
    )
    parser.add_argument("input", type=Path, help="Sliced multi-plate .gcode.3mf")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .3mf path. Defaults to INPUT with .platecycler before the extension.",
    )
    parser.add_argument(
        "--swap-gcode",
        type=Path,
        help="Optional text file with replacement plate-swap gcode.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args()


def default_output_path(input_path: Path) -> Path:
    name = input_path.name
    if name.endswith(".gcode.3mf"):
        return input_path.with_name(
            f"{name.removesuffix('.gcode.3mf')}.platecycler.3mf"
        )
    if input_path.suffix:
        return input_path.with_name(f"{input_path.stem}.platecycler{input_path.suffix}")
    return input_path.with_name(f"{input_path.name}.platecycler")


def plate_numbers(zip_file: ZipFile) -> list[int]:
    numbers = []
    for name in zip_file.namelist():
        match = PLATE_GCODE_RE.match(name)
        if match:
            numbers.append(int(match.group(1)))

    numbers = sorted(numbers)
    if not numbers:
        raise ValueError("input 3MF does not contain Metadata/plate_N.gcode files")
    expected = list(range(1, numbers[-1] + 1))
    if numbers != expected:
        raise ValueError(
            f"plate gcode files must be numbered contiguously from 1 (found {numbers})"
        )
    return numbers


def merged_gcode(zip_file: ZipFile, numbers: list[int], swap_gcode: bytes) -> bytes:
    chunks = []
    for number in numbers:
        chunks.append(zip_file.read(f"Metadata/plate_{number}.gcode"))
        chunks.append(swap_gcode)
    return b"".join(chunks)


def decimal_attr(element: ET.Element, key: str) -> Decimal:
    value = element.get(key, "0")
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal("0")


def format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def collect_filament_usage(root: ET.Element) -> list[FilamentUsage]:
    usages: dict[str, FilamentUsage] = {}

    for filament in root.findall(".//filament"):
        filament_id = filament.get("id")
        if filament_id is None:
            continue

        if filament_id not in usages:
            usages[filament_id] = FilamentUsage(
                attrs={
                    key: value
                    for key, value in filament.attrib.items()
                    if key in {"id", "type", "color"}
                }
            )

        usages[filament_id].used_g += decimal_attr(filament, "used_g")
        usages[filament_id].used_m += decimal_attr(filament, "used_m")

    return list(usages.values())


def compact_model_settings(content: bytes) -> bytes:
    root = ET.fromstring(content)
    plates = root.findall("plate")
    if not plates:
        return content

    first_plate = plates[0]
    for plate in plates[1:]:
        root.remove(plate)

    removed_metadata = {
        "plater_name",
        "filament_map_mode",
        "filament_maps",
        "filament_volume_maps",
        "thumbnail_no_light_file",
    }
    for metadata in list(first_plate.findall("metadata")):
        if metadata.get("key") in removed_metadata:
            first_plate.remove(metadata)

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def compact_slice_info(content: bytes) -> bytes:
    root = ET.fromstring(content)
    plates = root.findall("plate")
    if not plates:
        return content

    filament_usages = collect_filament_usage(root)
    first_plate = plates[0]
    for plate in plates[1:]:
        root.remove(plate)

    for filament in list(first_plate.findall("filament")):
        first_plate.remove(filament)

    for usage in filament_usages:
        attrs = dict(usage.attrs)
        attrs["used_g"] = format_decimal(usage.used_g)
        attrs["used_m"] = format_decimal(usage.used_m)
        ET.SubElement(first_plate, "filament", attrs)

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def should_skip(name: str) -> bool:
    gcode_match = PLATE_GCODE_RE.match(name)
    if gcode_match and int(gcode_match.group(1)) > 1:
        return True

    md5_match = PLATE_GCODE_MD5_RE.match(name)
    return bool(md5_match and int(md5_match.group(1)) > 1)


def write_metadata_dir(output: ZipFile) -> None:
    info = ZipInfo("Metadata/")
    info.compress_type = ZIP_STORED
    output.writestr(info, b"")


def inject_platecycler_gcode(
    input_path: Path,
    output_path: Path,
    swap_gcode: bytes,
) -> tuple[int, str]:
    with ZipFile(input_path, "r") as source:
        numbers = plate_numbers(source)
        gcode = merged_gcode(source, numbers, swap_gcode)
        gcode_md5 = hashlib.md5(gcode).hexdigest()
        wrote_metadata_dir = "Metadata/" in source.namelist()

        with ZipFile(output_path, "w", ZIP_DEFLATED) as output:
            for info in source.infolist():
                name = info.filename
                if should_skip(name):
                    continue

                if name == "Metadata/plate_1.gcode":
                    content = gcode
                elif name == "Metadata/plate_1.gcode.md5":
                    content = gcode_md5.encode("ascii")
                elif name == "Metadata/model_settings.config":
                    content = compact_model_settings(source.read(name))
                elif name == "Metadata/slice_info.config":
                    content = compact_slice_info(source.read(name))
                else:
                    content = source.read(name)

                if name == "Metadata/":
                    wrote_metadata_dir = True
                output.writestr(info, content)

            if not wrote_metadata_dir:
                write_metadata_dir(output)

    return len(numbers), gcode_md5


def read_swap_gcode(path: Path | None) -> bytes:
    if path is None:
        return DEFAULT_SWAP_GCODE.encode("utf-8")
    return path.read_bytes()


def main() -> int:
    args = parse_args()
    input_path = args.input
    output_path = args.output or default_output_path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"missing input file: {input_path}")
    if output_path == input_path:
        raise ValueError("output path must be different from input path")
    if output_path.exists() and not args.force:
        raise FileExistsError(f"output already exists: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plate_count, gcode_md5 = inject_platecycler_gcode(
        input_path,
        output_path,
        read_swap_gcode(args.swap_gcode),
    )
    print(f"{output_path} ({plate_count} plates, gcode md5 {gcode_md5})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
