#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo


CORE_3MF_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
BAMBU_3MF_NS = "http://schemas.bambulab.com/package/2021"
PRODUCTION_3MF_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
PLATE_GCODE_RE = re.compile(r"^Metadata/plate_(\d+)\.gcode$")
PLATE_GCODE_MD5_RE = re.compile(r"^Metadata/plate_(\d+)\.gcode\.md5$")
GCODE_PARAM_RE = re.compile(r"([A-Z])([-+]?(?:\d+(?:\.\d*)?|\.\d+))")
COLLAGE_IMAGE_PATTERNS = {
    "Metadata/plate_1.png": "Metadata/plate_{number}.png",
    "Metadata/plate_1_small.png": "Metadata/plate_{number}_small.png",
    "Metadata/plate_no_light_1.png": "Metadata/plate_no_light_{number}.png",
    "Metadata/top_1.png": "Metadata/top_{number}.png",
    "Metadata/pick_1.png": "Metadata/pick_{number}.png",
}

ET.register_namespace("", CORE_3MF_NS)
ET.register_namespace("BambuStudio", BAMBU_3MF_NS)
ET.register_namespace("p", PRODUCTION_3MF_NS)

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


def png_bytes(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def image_is_blank(image) -> bool:
    return image.getbbox() is None


def plate_json_bbox(
    zip_file: ZipFile, number: int
) -> tuple[float, float, float, float]:
    data = json.loads(zip_file.read(f"Metadata/plate_{number}.json"))
    bbox = data.get("bbox_all")
    if (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or bbox[0] >= bbox[2]
        or bbox[1] >= bbox[3]
    ):
        raise ValueError(f"invalid bbox_all in Metadata/plate_{number}.json")

    return tuple(float(value) for value in bbox)


def gcode_params(line: str) -> dict[str, float]:
    return {key: float(value) for key, value in GCODE_PARAM_RE.findall(line)}


def bbox_intersects(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def plate_extrusion_segments(
    zip_file: ZipFile,
    number: int,
    bbox: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    gcode = zip_file.read(f"Metadata/plate_{number}.gcode").decode(
        "utf-8", errors="ignore"
    )
    margin = max(bbox[2] - bbox[0], bbox[3] - bbox[1]) * 0.05
    expanded_bbox = (
        bbox[0] - margin,
        bbox[1] - margin,
        bbox[2] + margin,
        bbox[3] + margin,
    )
    segments = []
    current_x: float | None = None
    current_y: float | None = None

    for raw_line in gcode.splitlines():
        line = raw_line.split(";", 1)[0].strip().upper()
        if not line:
            continue

        command = line.split(None, 1)[0]
        if command not in {"G0", "G1", "G2", "G3"}:
            continue

        params = gcode_params(line)
        next_x = params.get("X", current_x)
        next_y = params.get("Y", current_y)
        extrusion = params.get("E")

        if (
            command in {"G1", "G2", "G3"}
            and extrusion is not None
            and extrusion > 0
            and current_x is not None
            and current_y is not None
            and next_x is not None
            and next_y is not None
        ):
            segment_bbox = (
                min(current_x, next_x),
                min(current_y, next_y),
                max(current_x, next_x),
                max(current_y, next_y),
            )
            if bbox_intersects(segment_bbox, expanded_bbox):
                segments.append((current_x, current_y, next_x, next_y))

        current_x = next_x
        current_y = next_y

    return segments


def rendered_plate_thumbnail(zip_file: ZipFile, number: int, size: tuple[int, int]):
    from PIL import Image, ImageDraw

    bbox = plate_json_bbox(zip_file, number)
    segments = plate_extrusion_segments(zip_file, number, bbox)
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    if not segments:
        return image

    bbox_width = bbox[2] - bbox[0]
    bbox_height = bbox[3] - bbox[1]
    padding = max(2, round(min(width, height) * 0.08))
    scale = min(
        (width - 2 * padding) / bbox_width,
        (height - 2 * padding) / bbox_height,
    )
    center_x = (bbox[0] + bbox[2]) / 2
    center_y = (bbox[1] + bbox[3]) / 2

    def point(x: float, y: float) -> tuple[int, int]:
        return (
            round(width / 2 + (x - center_x) * scale),
            round(height / 2 - (y - center_y) * scale),
        )

    draw = ImageDraw.Draw(image, "RGBA")
    line_width = max(1, round(min(width, height) / 160))
    for x1, y1, x2, y2 in segments:
        draw.line(
            (point(x1, y1), point(x2, y2)), fill=(45, 45, 45, 230), width=line_width
        )

    return image


def thumbnail_image(
    zip_file: ZipFile,
    number: int,
    name: str,
    render_cache: dict[tuple[int, tuple[int, int]], object],
):
    from PIL import Image

    image = Image.open(BytesIO(zip_file.read(name))).convert("RGBA")
    image.load()
    if not image_is_blank(image):
        return image

    key = (number, image.size)
    if key not in render_cache:
        render_cache[key] = rendered_plate_thumbnail(zip_file, number, image.size)

    return render_cache[key].copy()


def contained_resize(image, max_size: tuple[int, int], resample):
    max_width, max_height = max_size
    width, height = image.size
    scale = min(max_width / width, max_height / height)
    resized_size = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    return image.resize(resized_size, resample)


def collage_image(
    zip_file: ZipFile,
    numbers: list[int],
    pattern: str,
    render_cache: dict[tuple[int, tuple[int, int]], object],
) -> bytes | None:
    from PIL import Image

    images = []
    for number in numbers:
        name = pattern.format(number=number)
        try:
            image = thumbnail_image(zip_file, number, name, render_cache)
        except KeyError:
            return None

        images.append(image)

    if not images:
        return None

    target_width, target_height = images[0].size
    columns = min(len(images), math.ceil(math.sqrt(len(images))))
    rows = math.ceil(len(images) / columns)
    grid_width = max(1, round(min(target_width, target_height) * 0.012))
    tile_width = max(1, (target_width - grid_width * (columns - 1)) // columns)
    tile_height = max(1, (target_height - grid_width * (rows - 1)) // rows)
    used_width = tile_width * columns + grid_width * (columns - 1)
    used_height = tile_height * rows + grid_width * (rows - 1)
    origin_x = (target_width - used_width) // 2
    origin_y = (target_height - used_height) // 2

    canvas = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    grid_color = (95, 100, 95, 190)
    resample = Image.Resampling.LANCZOS
    for index, image in enumerate(images):
        row = index // columns
        column = index % columns
        x = origin_x + column * (tile_width + grid_width)
        y = origin_y + row * (tile_height + grid_width)
        tile = contained_resize(image, (tile_width, tile_height), resample)
        tile_x = x + (tile_width - tile.width) // 2
        tile_y = y + (tile_height - tile.height) // 2
        canvas.alpha_composite(tile, (tile_x, tile_y))

    for column in range(1, columns):
        x = origin_x + column * tile_width + (column - 1) * grid_width
        canvas.alpha_composite(
            Image.new("RGBA", (grid_width, used_height), grid_color), (x, origin_y)
        )
    for row in range(1, rows):
        y = origin_y + row * tile_height + (row - 1) * grid_width
        canvas.alpha_composite(
            Image.new("RGBA", (used_width, grid_width), grid_color), (origin_x, y)
        )

    return png_bytes(canvas)


def collage_images(zip_file: ZipFile, numbers: list[int]) -> dict[str, bytes]:
    collages = {}
    render_cache = {}
    for output_name, pattern in COLLAGE_IMAGE_PATTERNS.items():
        collage = collage_image(zip_file, numbers, pattern, render_cache)
        if collage is not None:
            collages[output_name] = collage

    return collages


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

    for object_element in root.findall("object"):
        root.remove(object_element)
    for assemble in root.findall("assemble"):
        root.remove(assemble)

    first_plate = plates[0]
    for plate in plates[1:]:
        root.remove(plate)

    for model_instance in first_plate.findall("model_instance"):
        first_plate.remove(model_instance)

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

    set_metadata_value(first_plate, "pattern_bbox_file", "Metadata/plate_1.json")

    return serialize_xml(root)


def ensure_model_namespace_declarations(content: bytes) -> bytes:
    model_start = content.find(b"<model")
    if model_start < 0:
        return content

    tag_end = content.find(b">", model_start)
    if tag_end < 0:
        return content

    tag = content[model_start:tag_end]
    declarations = []
    if b"xmlns:BambuStudio=" not in tag:
        declarations.append(f'xmlns:BambuStudio="{BAMBU_3MF_NS}"'.encode("ascii"))
    if b"xmlns:p=" not in tag:
        declarations.append(f'xmlns:p="{PRODUCTION_3MF_NS}"'.encode("ascii"))

    if not declarations:
        return content

    return content[:tag_end] + b" " + b" ".join(declarations) + content[tag_end:]


def strip_3mf_model_geometry(content: bytes) -> bytes:
    root = ET.fromstring(content)
    changed = False

    resources = root.find(f"{{{CORE_3MF_NS}}}resources")
    if resources is None:
        resources = ET.SubElement(root, f"{{{CORE_3MF_NS}}}resources")
        changed = True
    elif list(resources):
        changed = True
    for child in list(resources):
        resources.remove(child)

    build = root.find(f"{{{CORE_3MF_NS}}}build")
    if build is None:
        build = ET.SubElement(root, f"{{{CORE_3MF_NS}}}build")
        changed = True
    elif build.attrib or list(build):
        changed = True
    build.attrib.clear()
    for child in list(build):
        build.remove(child)

    if not changed:
        return content

    return ensure_model_namespace_declarations(serialize_xml(root))


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
        source_names = set(source.namelist())
        collages = collage_images(source, numbers)
        gcode = merged_gcode(source, numbers, swap_gcode)
        gcode_md5 = hashlib.md5(gcode).hexdigest()

        with ZipFile(output_path, "w", ZIP_DEFLATED) as output:
            for info in source.infolist():
                name = info.filename
                if (
                    name == "Metadata/"
                    or PLATE_GCODE_RE.match(name)
                    or PLATE_GCODE_MD5_RE.match(name)
                    or name == "3D/_rels/3dmodel.model.rels"
                    or name.startswith("3D/Objects/")
                ):
                    continue

                if name == "Metadata/model_settings.config":
                    content = compact_model_settings(source.read(name))
                elif name == "Metadata/slice_info.config":
                    content = compact_slice_info(source.read(name))
                elif name == "3D/3dmodel.model":
                    content = strip_3mf_model_geometry(source.read(name))
                elif name in collages:
                    content = collages[name]
                else:
                    content = source.read(name)

                write_file(output, info, content)

            for name, content in collages.items():
                if name not in source_names:
                    write_generated_file(output, source, name, content)

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
