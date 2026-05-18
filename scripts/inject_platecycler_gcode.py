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


def filament_decimal_attr(
    element: ET.Element, lower_key: str, upper_key: str
) -> Decimal:
    if lower_key in element.attrib:
        return decimal_attr(element, lower_key)
    return decimal_attr(element, upper_key)


def chitu_filament_attrs(element: ET.Element) -> dict[str, str]:
    attrs = {}

    for key in ("color", "type", "id", "group_id"):
        value = element.get(key)
        if value is not None:
            attrs[key] = value

    tray_info_idx = element.get("trayInfoIdx", element.get("tray_info_idx"))
    if tray_info_idx is not None:
        attrs["trayInfoIdx"] = tray_info_idx

    return attrs


def ordered_chitu_filament_attrs(usage: FilamentUsage) -> dict[str, str]:
    used_g = format_decimal(usage.used_g)
    used_m = format_decimal(usage.used_m)
    attrs = {}

    for key in ("color", "trayInfoIdx", "type", "id"):
        value = usage.attrs.get(key)
        if value is not None:
            attrs[key] = value

    attrs["usedG"] = used_g
    attrs["usedM"] = used_m

    group_id = usage.attrs.get("group_id")
    if group_id is not None:
        attrs["group_id"] = group_id

    attrs["used_g"] = used_g
    attrs["used_m"] = used_m
    return attrs


def collect_filament_usage(root: ET.Element) -> list[FilamentUsage]:
    usages: dict[str, FilamentUsage] = {}

    for filament in root.findall(".//filament"):
        filament_id = filament.get("id")
        if filament_id is None:
            continue

        if filament_id not in usages:
            usages[filament_id] = FilamentUsage(attrs=chitu_filament_attrs(filament))

        usages[filament_id].used_g += filament_decimal_attr(filament, "used_g", "usedG")
        usages[filament_id].used_m += filament_decimal_attr(filament, "used_m", "usedM")

    return list(usages.values())


def metadata_decimal_value(element: ET.Element, key: str) -> Decimal | None:
    for metadata in element.findall("metadata"):
        if metadata.get("key") == key:
            try:
                return Decimal(metadata.get("value", "0"))
            except InvalidOperation:
                return None

    return None


def set_metadata_value(element: ET.Element, key: str, value: str) -> None:
    for metadata in element.findall("metadata"):
        if metadata.get("key") == key:
            metadata.set("value", value)
            return

    ET.SubElement(element, "metadata", {"key": key, "value": value})


def sum_plate_prediction(plates: list[ET.Element]) -> Decimal | None:
    prediction = Decimal("0")
    for plate in plates:
        value = metadata_decimal_value(plate, "prediction")
        if value is None:
            return None
        prediction += value

    return prediction


def serialize_xml(root: ET.Element) -> bytes:
    ET.indent(root, space="  ")
    content = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    content = content.replace(
        b"<?xml version='1.0' encoding='UTF-8'?>",
        b'<?xml version="1.0" encoding="UTF-8"?>',
        1,
    )
    return content.replace(b" />", b"/>")


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

    return serialize_xml(root)


def compact_slice_info(content: bytes) -> bytes:
    root = ET.fromstring(content)
    plates = root.findall("plate")
    if not plates:
        return content

    filament_usages = collect_filament_usage(root)
    prediction = sum_plate_prediction(plates)
    first_plate = plates[0]
    for plate in plates[1:]:
        root.remove(plate)

    if prediction is not None:
        set_metadata_value(first_plate, "prediction", format_decimal(prediction))

    for filament in list(first_plate.findall("filament")):
        first_plate.remove(filament)

    for usage in filament_usages:
        ET.SubElement(first_plate, "filament", ordered_chitu_filament_attrs(usage))

    return serialize_xml(root)


def write_metadata_dir(output: ZipFile) -> None:
    info = ZipInfo("Metadata/")
    info.compress_type = ZIP_STORED
    info.create_system = 0
    info.external_attr = 0
    output.writestr(info, b"")


def output_zip_info(source_info: ZipInfo, compress_type: int = ZIP_DEFLATED) -> ZipInfo:
    info = ZipInfo(source_info.filename, source_info.date_time)
    info.compress_type = compress_type
    info.create_system = 0
    info.external_attr = 0
    return info


def write_file(output: ZipFile, source_info: ZipInfo, content: bytes) -> None:
    output.writestr(output_zip_info(source_info), content)


def write_generated_file(
    output: ZipFile,
    source: ZipFile,
    name: str,
    content: bytes,
) -> None:
    try:
        source_info = source.getinfo(name)
    except KeyError:
        source_info = ZipInfo(name)

    output.writestr(output_zip_info(source_info), content)


def inject_platecycler_gcode(
    input_path: Path,
    output_path: Path,
    swap_gcode: bytes,
) -> tuple[int, str]:
    with ZipFile(input_path, "r") as source:
        numbers = plate_numbers(source)
        gcode = merged_gcode(source, numbers, swap_gcode)
        gcode_md5 = hashlib.md5(gcode).hexdigest()

        with ZipFile(output_path, "w", ZIP_DEFLATED) as output:
            for info in source.infolist():
                name = info.filename
                if (
                    name == "Metadata/"
                    or PLATE_GCODE_RE.match(name)
                    or PLATE_GCODE_MD5_RE.match(name)
                ):
                    continue

                if name == "Metadata/model_settings.config":
                    content = compact_model_settings(source.read(name))
                elif name == "Metadata/slice_info.config":
                    content = compact_slice_info(source.read(name))
                else:
                    content = source.read(name)

                write_file(output, info, content)

            write_metadata_dir(output)
            write_generated_file(output, source, "Metadata/plate_1.gcode", gcode)
            write_generated_file(
                output,
                source,
                "Metadata/plate_1.gcode.md5",
                gcode_md5.encode("ascii"),
            )

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
