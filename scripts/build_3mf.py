#!/usr/bin/env python3

from __future__ import annotations

import argparse
import functools
import json
import math
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from zipfile import ZipFile

from threemf_utils import (
    DEFAULT_BED_X,
    DEFAULT_BED_Y,
    cli_entry,
    find_child_by_attr,
    format_float,
    rewrite_zip,
    set_metadata,
)

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]
Bounds = tuple[list[float], list[float]]
Mesh = tuple[Path, list[Point3], list[Triangle], Bounds]
LogoMetrics = dict[str, float]

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
BODY_PART_NAME = "Case body"
LOGO_PART_NAME = "ORANGECON logo insert"
LOGO_FILAMENT_COLOR = "#FF8000"
LOGO_LAYER_HEIGHT = "0.16"
LAYER_CONFIG_RANGES_PATH = "Metadata/layer_config_ranges.xml"
IDENTITY_MATRIX = "1 0 0 0 1 0 0 0 1"
# Bambu Studio allocates low instance IDs internally while slicing, so dense
# generated IDs (1..80) collide on large repeated-plate jobs. Match
# Bambu-authored projects by starting high and stepping with a coprime gap.
SPARSE_INSTANCE_ID_START = 20000
SPARSE_INSTANCE_ID_STEP = 11
MODEL_METADATA = (
    ("Application", "BambuStudio-02.06.00.51"),
    ("BambuStudio:3mfVersion", "1"),
    ("Copyright", ""),
    ("CreationDate", None),
    ("Description", ""),
    ("Designer", ""),
    ("DesignerCover", ""),
    ("DesignerUserId", "2683275966"),
    ("License", ""),
    ("ModificationDate", None),
    ("Origin", ""),
    ("ProfileCover", ""),
    ("ProfileDescription", ""),
    ("ProfileTitle", ""),
    ("Title", ""),
)

ET.register_namespace("", CORE_NS)

ROOT = Path(__file__).resolve().parent.parent
SCAD = ROOT / "m5sticks3_click_case.scad"
LOGO_SCRIPT = ROOT / "scripts" / "build_logo_svg.py"
SINGLE_TEMPLATE = ROOT / "m5sticks3_click_case_template.3mf"
COLOR_TEMPLATE = ROOT / "m5sticks3_click_case_color_template.3mf"
DEFAULT_OUTPUT = ROOT / "m5sticks3_click_case_named_badges.3mf"
DEFAULT_WORK_DIR = ROOT / "build" / "named"
FLUSH_BACKING = 0.45
DEFAULT_GAP = 2.5
DEFAULT_X_OFFSET = 10.0
DEFAULT_Y_OFFSET = 10.0
DEFAULT_PLATE_GAP = 36.0
# SVG uses 96 dpi; OpenSCAD's SVG import treats lengths as PostScript points
# (72 dpi). Scale logo metrics by 96/72 = 4/3 before passing them as defines.
SVG_TO_OPENSCAD = 4.0 / 3.0


@dataclass
class AssemblySettings:
    assembly_id: int
    name: str
    body_part_id: str = "1"
    logo_part_id: str = "2"
    body_part_name: str = BODY_PART_NAME
    logo_part_name: str = LOGO_PART_NAME


@dataclass
class PlateModelItem:
    meshes: list[Mesh]
    name: str
    body_part_name: str = BODY_PART_NAME
    logo_part_name: str = LOGO_PART_NAME


@dataclass(frozen=True)
class PlacedPlateItem:
    object_id: int
    plate_number: int
    transform: str


@dataclass(frozen=True)
class RepeatedPlateSummary:
    badge_count: int
    plate_count: int
    badges_per_full_plate: int


@dataclass(frozen=True)
class Variant:
    template: Path
    color_logo_style: str
    output_parts: tuple[str, ...]
    patch_color_metadata: bool = False
    detect_thin_wall: bool = False
    inner_wall_backing: float = 0
    # When False, the SCAD is invoked with `show_right_logo=false` and the
    # SVG/logo-metrics steps are skipped.
    show_logo: bool = True
    # OpenSCAD output part whose Z bounds define the optional layer-height
    # modifier. For color variants this is typically already one of the
    # printable output_parts; for with-logo single-material it isn't, so a
    # one-off STL is rendered just for its Z bounds. None disables the
    # modifier (used by no-logo).
    height_reference_part: str | None = "logo"


VARIANTS = {
    "with-logo": Variant(
        template=SINGLE_TEMPLATE,
        color_logo_style="embossed",
        output_parts=("full",),
    ),
    "no-logo": Variant(
        template=SINGLE_TEMPLATE,
        color_logo_style="embossed",
        output_parts=("full",),
        show_logo=False,
        height_reference_part=None,
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


def parse_ascii_stl(
    path: Path,
) -> tuple[list[Point3], list[Triangle], Bounds]:
    vertices: list[Point3] = []
    triangles: list[Triangle] = []
    index: dict[Point3, int] = {}
    current: list[int] = []
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3

    text = path.read_text(errors="strict")
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) != 4 or parts[0] != "vertex":
            continue

        coord = tuple(round(float(value), 6) for value in parts[1:])
        if coord not in index:
            index[coord] = len(vertices)
            vertices.append(coord)

        current.append(index[coord])
        for axis, value in enumerate(coord):
            mins[axis] = min(mins[axis], value)
            maxs[axis] = max(maxs[axis], value)

        if len(current) == 3:
            triangles.append((current[0], current[1], current[2]))
            current = []

    if current:
        raise ValueError(f"dangling triangle data in {path}")
    if not vertices or not triangles:
        raise ValueError(f"no ASCII STL mesh data found in {path}")

    return vertices, triangles, (mins, maxs)


def load_meshes(stl_paths: list[Path]) -> list[Mesh]:
    meshes = []
    for stl_path in stl_paths:
        vertices, triangles, bounds = parse_ascii_stl(stl_path)
        meshes.append((stl_path, vertices, triangles, bounds))
    return meshes


def combined_bounds(meshes: list[Mesh]) -> Bounds:
    all_mins = [float("inf")] * 3
    all_maxs = [float("-inf")] * 3

    for _, _, _, (mins, maxs) in meshes:
        for axis in range(3):
            all_mins[axis] = min(all_mins[axis], mins[axis])
            all_maxs[axis] = max(all_maxs[axis], maxs[axis])

    return all_mins, all_maxs


def transform_string(tx: float, ty: float, tz: float = 0) -> str:
    return f"{IDENTITY_MATRIX} {tx:.6f} {ty:.6f} {tz:.6f}"


def center_transform_for_bounds(
    bounds: Bounds, center_x: float, center_y: float
) -> str:
    mins, maxs = bounds
    mesh_center_x = (mins[0] + maxs[0]) / 2
    mesh_center_y = (mins[1] + maxs[1]) / 2
    return transform_string(center_x - mesh_center_x, center_y - mesh_center_y)


def build_model_document() -> tuple[ET.Element, ET.Element, ET.Element]:
    model_date = date.today().isoformat()
    model = ET.Element(
        "model",
        {
            "unit": "millimeter",
            "{http://www.w3.org/XML/1998/namespace}lang": "en-US",
            "xmlns": CORE_NS,
        },
    )
    for name, value in MODEL_METADATA:
        metadata = ET.SubElement(model, "metadata", {"name": name})
        metadata.text = model_date if value is None else value

    resources = ET.SubElement(model, "resources")
    build = ET.SubElement(model, "build")
    return model, resources, build


def build_item_attrs(
    object_id: int, transform: str | None = None, printable: bool = False
) -> dict[str, str]:
    attrs = {"objectid": str(object_id)}
    if transform is not None:
        attrs["transform"] = transform
    if printable:
        attrs["printable"] = "1"
    return attrs


def append_build_item(
    build: ET.Element,
    object_id: int,
    transform: str | None = None,
    printable: bool = False,
) -> None:
    ET.SubElement(build, "item", build_item_attrs(object_id, transform, printable))


def append_mesh_object(
    resources: ET.Element,
    obj_id: int,
    mesh: Mesh,
    name: str | None = None,
) -> None:
    stl_path, vertices, triangles, _ = mesh
    obj = ET.SubElement(
        resources,
        "object",
        {"id": str(obj_id), "type": "model", "name": name or stl_path.name},
    )
    mesh_el = ET.SubElement(obj, "mesh")
    vertices_el = ET.SubElement(mesh_el, "vertices")
    for x, y, z in vertices:
        ET.SubElement(
            vertices_el,
            "vertex",
            {"x": f"{x:.6f}", "y": f"{y:.6f}", "z": f"{z:.6f}"},
        )

    triangles_el = ET.SubElement(mesh_el, "triangles")
    for v1, v2, v3 in triangles:
        ET.SubElement(
            triangles_el,
            "triangle",
            {"v1": str(v1), "v2": str(v2), "v3": str(v3)},
        )


def append_plate_assembly_object(
    resources: ET.Element,
    assembly_id: int,
    mesh_ids: list[int],
    name: str,
) -> None:
    obj = ET.SubElement(
        resources,
        "object",
        {"id": str(assembly_id), "type": "model", "name": name},
    )
    components = ET.SubElement(obj, "components")
    for mesh_id in mesh_ids:
        ET.SubElement(
            components,
            "component",
            {
                "objectid": str(mesh_id),
                "transform": transform_string(0, 0),
            },
        )


def item_xy_size(item: PlateModelItem) -> tuple[float, float]:
    mins, maxs = combined_bounds(item.meshes)
    return maxs[0] - mins[0], maxs[1] - mins[1]


def validate_plate_positions(
    positions: list[tuple[float, float]],
    item_width: float,
    item_depth: float,
    bed_width: float,
    bed_depth: float,
    x_offset: float,
    y_offset: float,
) -> None:
    min_layout_x = min(x - item_width / 2 for x, _ in positions)
    max_layout_x = max(x + item_width / 2 for x, _ in positions)
    min_layout_y = min(y - item_depth / 2 for _, y in positions)
    max_layout_y = max(y + item_depth / 2 for _, y in positions)

    if (
        min_layout_x < 0
        or max_layout_x > bed_width
        or min_layout_y < 0
        or max_layout_y > bed_depth
    ):
        layout_width = max_layout_x - min_layout_x
        layout_depth = max_layout_y - min_layout_y
        raise ValueError(
            "plate layout exceeds the configured bed size "
            f"(layout spans {layout_width:.1f} x {layout_depth:.1f} mm, "
            f"X {min_layout_x:.1f}..{max_layout_x:.1f}, "
            f"Y {min_layout_y:.1f}..{max_layout_y:.1f}, "
            f"at offset {x_offset:.1f}, {y_offset:.1f}, "
            f"{bed_width:.1f} x {bed_depth:.1f} mm available)"
        )


def bottom_right_plate_layout_positions(
    item_width: float,
    item_depth: float,
    item_count: int,
    bed_x: float,
    bed_y: float,
    gap: float = 5.0,
    x_offset: float = 0,
    y_offset: float = 0,
) -> list[tuple[float, float]]:
    if item_count < 1:
        raise ValueError("at least one plate item is required")
    if x_offset < 0 or y_offset < 0:
        raise ValueError("bottom-right plate offsets must be non-negative edge insets")

    bed_width = bed_x * 2
    bed_depth = bed_y * 2
    right_x = bed_width - item_width / 2 - x_offset
    x = right_x
    y = item_depth / 2 + y_offset
    positions = []

    for index in range(item_count):
        if index > 0 and x - item_width / 2 < 0:
            x = right_x
            y += item_depth + gap

        positions.append((x, y))
        x -= item_width + gap

    validate_plate_positions(
        positions,
        item_width,
        item_depth,
        bed_width,
        bed_depth,
        x_offset,
        y_offset,
    )

    return positions


def bottom_right_plate_capacity(
    item_width: float,
    item_depth: float,
    bed_x: float,
    bed_y: float,
    gap: float = 5.0,
    x_offset: float = 0,
    y_offset: float = 0,
) -> tuple[int, list[tuple[float, float]]]:
    if x_offset < 0 or y_offset < 0:
        raise ValueError("bottom-right plate offsets must be non-negative edge insets")

    bed_width = bed_x * 2
    bed_depth = bed_y * 2
    usable_width = bed_width - item_width - x_offset
    usable_depth = bed_depth - item_depth - y_offset
    if usable_width < 0 or usable_depth < 0:
        raise ValueError(
            "one badge does not fit the configured bed size "
            f"(badge spans {item_width:.1f} x {item_depth:.1f} mm, "
            f"at offset {x_offset:.1f}, {y_offset:.1f}, "
            f"{bed_width:.1f} x {bed_depth:.1f} mm available)"
        )

    columns = math.floor((usable_width + 1e-9) / (item_width + gap)) + 1
    rows = math.floor((usable_depth + 1e-9) / (item_depth + gap)) + 1
    capacity = columns * rows
    if capacity < 1:
        raise ValueError("one badge does not fit the configured bed size")

    positions = bottom_right_plate_layout_positions(
        item_width,
        item_depth,
        capacity,
        bed_x,
        bed_y,
        gap,
        x_offset,
        y_offset,
    )
    return capacity, positions


def append_plate_item(
    resources: ET.Element,
    build: ET.Element,
    next_id: int,
    item: PlateModelItem,
    center_x: float,
    center_y: float,
    printable: bool = False,
) -> tuple[int, int, str, AssemblySettings | None]:
    mesh_ids = []
    for mesh in item.meshes:
        mesh_name = item.name if len(item.meshes) == 1 else None
        append_mesh_object(resources, next_id, mesh, mesh_name)
        mesh_ids.append(next_id)
        next_id += 1

    assembly_settings = None
    if len(mesh_ids) == 1:
        build_object_id = mesh_ids[0]
    else:
        assembly_id = next_id
        append_plate_assembly_object(resources, assembly_id, mesh_ids, item.name)
        assembly_settings = AssemblySettings(
            assembly_id=assembly_id,
            name=item.name,
            # Bambu part settings address the assembly component object IDs, not
            # the part's ordinal position.
            body_part_id=str(mesh_ids[0]),
            logo_part_id=str(mesh_ids[1]),
            body_part_name=item.body_part_name,
            logo_part_name=item.logo_part_name,
        )
        build_object_id = assembly_id
        next_id += 1

    transform = center_transform_for_bounds(
        combined_bounds(item.meshes), center_x, center_y
    )
    append_build_item(build, build_object_id, transform, printable)
    return next_id, build_object_id, transform, assembly_settings


def build_plate_model_xml(
    items: list[PlateModelItem],
    bed_x: float,
    bed_y: float,
    gap: float,
    x_offset: float,
    y_offset: float,
    plate_columns: int | None,
    plate_gap: float,
) -> tuple[
    bytes,
    list[PlacedPlateItem],
    list[AssemblySettings],
    RepeatedPlateSummary,
]:
    if not items:
        raise ValueError("at least one plate item is required")

    # Heterogeneous items share a single slot grid sized to the largest item so
    # plate layout is stable regardless of the order they're placed in.
    item_width = max(item_xy_size(item)[0] for item in items)
    item_depth = max(item_xy_size(item)[1] for item in items)
    badges_per_full_plate, base_positions = bottom_right_plate_capacity(
        item_width, item_depth, bed_x, bed_y, gap, x_offset, y_offset
    )
    plate_count = math.ceil(len(items) / badges_per_full_plate)
    if plate_columns is None:
        plate_columns = math.ceil(math.sqrt(plate_count))
    if plate_columns < 1:
        raise ValueError("plate columns must be at least 1")
    plate_columns = min(plate_columns, plate_count)
    plate_step_x = bed_x * 2 + plate_gap
    plate_step_y = bed_y * 2 + plate_gap

    model, resources, build = build_model_document()
    placed_items: list[PlacedPlateItem] = []
    assembly_settings: list[AssemblySettings] = []
    next_id = 1

    for index, item in enumerate(items):
        plate_index = index // badges_per_full_plate
        slot_index = index % badges_per_full_plate
        plate_column = plate_index % plate_columns
        plate_row = plate_index // plate_columns
        plate_offset_x = plate_column * plate_step_x
        plate_offset_y = -plate_row * plate_step_y
        base_x, base_y = base_positions[slot_index]

        next_id, object_id, transform, settings = append_plate_item(
            resources,
            build,
            next_id,
            item,
            base_x + plate_offset_x,
            base_y + plate_offset_y,
            printable=True,
        )
        placed_items.append(
            PlacedPlateItem(
                object_id=object_id,
                plate_number=plate_index + 1,
                transform=transform,
            )
        )
        if settings is not None:
            assembly_settings.append(settings)

    return (
        ET.tostring(model, encoding="utf-8", xml_declaration=True),
        placed_items,
        assembly_settings,
        RepeatedPlateSummary(
            badge_count=len(items),
            plate_count=plate_count,
            badges_per_full_plate=badges_per_full_plate,
        ),
    )


def append_layer_config_range(
    parent: ET.Element, object_id: str, logo_bounds: Bounds
) -> None:
    logo_mins, logo_maxs = logo_bounds
    obj = ET.SubElement(parent, "object", {"id": object_id})
    height_range = ET.SubElement(
        obj,
        "range",
        {
            "min_z": format_float(logo_mins[2]),
            "max_z": format_float(logo_maxs[2]),
        },
    )
    ET.SubElement(height_range, "option", {"opt_key": "extruder"}).text = "0"
    ET.SubElement(
        height_range, "option", {"opt_key": "layer_height"}
    ).text = LOGO_LAYER_HEIGHT


def build_layer_config_ranges_xml_for_objects(
    logo_bounds_by_object_id: list[tuple[str, Bounds]],
) -> bytes:
    root = ET.Element("objects")
    for object_id, logo_bounds in logo_bounds_by_object_id:
        append_layer_config_range(root, object_id, logo_bounds)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def plate_metadata_from_template(
    template_plate: ET.Element | None, plate_number: int
) -> ET.Element:
    plate = ET.Element("plate")
    template_values = {}
    if template_plate is not None:
        template_values = {
            metadata.get("key"): metadata.get("value", "")
            for metadata in template_plate.findall("metadata")
            if metadata.get("key") is not None
        }

    values = {
        "plater_id": str(plate_number),
        "plater_name": template_values.get("plater_name", ""),
        "locked": template_values.get("locked", "false"),
        "filament_map_mode": template_values.get("filament_map_mode", "Auto For Flush"),
        "filament_maps": template_values.get("filament_maps", "1"),
        "filament_volume_maps": template_values.get("filament_volume_maps", "0"),
        "thumbnail_file": f"Metadata/plate_{plate_number}.png",
        "thumbnail_no_light_file": f"Metadata/plate_no_light_{plate_number}.png",
        "top_file": f"Metadata/top_{plate_number}.png",
        "pick_file": f"Metadata/pick_{plate_number}.png",
    }

    for key, value in values.items():
        ET.SubElement(plate, "metadata", {"key": key, "value": value})

    return plate


def build_plate_instance_model_settings(
    content: bytes,
    placed_items: list[PlacedPlateItem],
    plate_count: int,
) -> bytes:
    root = ET.fromstring(content.decode("utf-8"))
    template_plate = root.find("plate")

    for plate in list(root.findall("plate")):
        root.remove(plate)

    assemble = root.find("assemble")
    if assemble is not None:
        root.remove(assemble)

    items_by_plate: dict[int, list[PlacedPlateItem]] = {
        plate_number: [] for plate_number in range(1, plate_count + 1)
    }
    for item in placed_items:
        items_by_plate[item.plate_number].append(item)

    identify_id = SPARSE_INSTANCE_ID_START
    for plate_number in range(1, plate_count + 1):
        plate = plate_metadata_from_template(template_plate, plate_number)
        for item in items_by_plate[plate_number]:
            model_instance = ET.SubElement(plate, "model_instance")
            ET.SubElement(
                model_instance,
                "metadata",
                {"key": "object_id", "value": str(item.object_id)},
            )
            ET.SubElement(
                model_instance,
                "metadata",
                {"key": "instance_id", "value": "0"},
            )
            ET.SubElement(
                model_instance,
                "metadata",
                {"key": "identify_id", "value": str(identify_id)},
            )
            identify_id += SPARSE_INSTANCE_ID_STEP
        root.append(plate)

    assemble = ET.SubElement(root, "assemble")
    for item in placed_items:
        ET.SubElement(
            assemble,
            "assemble_item",
            {
                "object_id": str(item.object_id),
                "instance_id": "0",
                "transform": item.transform,
                "offset": "0 0 0",
            },
        )

    ET.indent(root, space="  ")
    content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return content.replace(
        b"<?xml version='1.0' encoding='utf-8'?>",
        b'<?xml version="1.0" encoding="UTF-8"?>',
        1,
    )


PREVIEW_PATTERNS = (
    "Metadata/plate_{}.png",
    "Metadata/plate_{}_small.png",
    "Metadata/plate_no_light_{}.png",
    "Metadata/top_{}.png",
    "Metadata/pick_{}.png",
)


def plate_preview_overrides(template_path: Path, plate_count: int) -> dict[str, bytes]:
    """Replicate the template's plate-1 preview images as plate-2..N overrides."""
    overrides: dict[str, bytes] = {}
    with ZipFile(template_path, "r") as template:
        for pattern in PREVIEW_PATTERNS:
            try:
                content = template.read(pattern.format(1))
            except KeyError:
                continue
            for plate_number in range(2, plate_count + 1):
                overrides[pattern.format(plate_number)] = content
    return overrides


def patch_color_project_settings(content: bytes, detect_thin_wall: bool) -> bytes:
    data = json.loads(content.decode("utf-8"))

    for key in ("filament_colour", "filament_multi_colour"):
        value = data.get(key)
        if not isinstance(value, list) or len(value) < 2:
            raise ValueError("multi-part color builds require a two-filament template")
        value[1] = LOGO_FILAMENT_COLOR

    if detect_thin_wall:
        data["detect_thin_wall"] = "1"

    return json.dumps(data, indent=4).encode("utf-8")


def ensure_part(obj_entry: ET.Element, part_id: str) -> ET.Element:
    part = find_child_by_attr(obj_entry, "part", "id", part_id)
    if part is not None:
        return part
    return ET.SubElement(obj_entry, "part", {"id": part_id, "subtype": "normal_part"})


def patch_assembly_model_settings(
    content: bytes,
    assembly_settings: list[AssemblySettings],
) -> bytes:
    root = ET.fromstring(content.decode("utf-8"))

    for settings in assembly_settings:
        obj_entry = find_child_by_attr(root, "object", "id", str(settings.assembly_id))
        if obj_entry is None:
            obj_entry = ET.SubElement(root, "object", {"id": str(settings.assembly_id)})

        set_metadata(obj_entry, "name", settings.name)
        set_metadata(obj_entry, "extruder", "1")

        part1 = ensure_part(obj_entry, settings.body_part_id)
        set_metadata(part1, "name", settings.body_part_name)

        part2 = ensure_part(obj_entry, settings.logo_part_id)
        set_metadata(part2, "name", settings.logo_part_name)
        set_metadata(part2, "extruder", "2")

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _patch_plate_model_settings(
    content: bytes,
    assembly_settings: list[AssemblySettings],
    placed_items: list[PlacedPlateItem],
    plate_count: int,
) -> bytes:
    # Run the assembly-metadata patch (object/part naming and extruder
    # assignment) before rewriting the <plate>/<assemble> entries; the two
    # operate on disjoint subtrees of model_settings.config.
    if assembly_settings:
        content = patch_assembly_model_settings(content, assembly_settings)
    return build_plate_instance_model_settings(content, placed_items, plate_count)


def build_plate_3mf(
    template_path: Path,
    item_stl_paths: list[list[Path]],
    output_path: Path,
    bed_x: float,
    bed_y: float,
    gap: float,
    x_offset: float,
    y_offset: float,
    plate_columns: int | None = None,
    plate_gap: float = DEFAULT_PLATE_GAP,
    logo_height_stl: Path | None = None,
    detect_thin_wall: bool = False,
    patch_color_metadata: bool = False,
    item_names: list[str] | None = None,
    body_part_names: list[str] | None = None,
    logo_part_names: list[str] | None = None,
) -> RepeatedPlateSummary:
    if not item_stl_paths:
        raise ValueError("at least one plate item is required")

    if item_names is None:
        item_names = [
            f"M5StickS3 Click Case {index:02d}"
            for index in range(1, len(item_stl_paths) + 1)
        ]
    if body_part_names is None:
        body_part_names = [BODY_PART_NAME for _ in item_stl_paths]
    if logo_part_names is None:
        logo_part_names = [LOGO_PART_NAME for _ in item_stl_paths]

    expected = len(item_stl_paths)
    if not (
        len(item_names) == len(body_part_names) == len(logo_part_names) == expected
    ):
        raise ValueError("plate item names and part names must match STL item count")

    mesh_cache: dict[Path, Mesh] = {}

    def load_cached(stl_paths: list[Path]) -> list[Mesh]:
        meshes = []
        for stl_path in stl_paths:
            cached = mesh_cache.get(stl_path)
            if cached is None:
                cached = load_meshes([stl_path])[0]
                mesh_cache[stl_path] = cached
            meshes.append(cached)
        return meshes

    items = [
        PlateModelItem(
            meshes=load_cached(stl_paths),
            name=item_names[index],
            body_part_name=body_part_names[index],
            logo_part_name=logo_part_names[index],
        )
        for index, stl_paths in enumerate(item_stl_paths)
    ]
    model_xml, placed_items, assembly_settings, summary = build_plate_model_xml(
        items,
        bed_x,
        bed_y,
        gap,
        x_offset,
        y_offset,
        plate_columns,
        plate_gap,
    )
    layer_config_ranges_xml = None
    if logo_height_stl is not None:
        _, _, logo_bounds = parse_ascii_stl(logo_height_stl)
        layer_config_ranges_xml = build_layer_config_ranges_xml_for_objects(
            [(str(item.object_id), logo_bounds) for item in placed_items]
        )

    overrides: dict[str, bytes] = {
        "3D/3dmodel.model": model_xml,
        **plate_preview_overrides(template_path, summary.plate_count),
    }
    if layer_config_ranges_xml is not None:
        overrides[LAYER_CONFIG_RANGES_PATH] = layer_config_ranges_xml

    patches = {
        "Metadata/model_settings.config": functools.partial(
            _patch_plate_model_settings,
            assembly_settings=assembly_settings,
            placed_items=placed_items,
            plate_count=summary.plate_count,
        ),
    }
    if patch_color_metadata:
        patches["Metadata/project_settings.config"] = functools.partial(
            patch_color_project_settings, detect_thin_wall=detect_thin_wall
        )

    rewrite_zip(template_path, output_path, patches=patches, overrides=overrides)
    return summary


def slugify(text: str, fallback_index: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip()).strip("_")
    if not slug:
        slug = f"badge_{fallback_index:02d}"
    return slug[:40]


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=ROOT)


def openscad_define(name: str, value: bool | str | float) -> str:
    if isinstance(value, bool):
        return f"{name}={'true' if value else 'false'}"
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
    svg_path: Path | None,
    logo_metrics: LogoMetrics | None,
    output_part: str,
    output_path: Path,
) -> None:
    defines: list[str] = []
    if variant.show_logo:
        assert svg_path is not None and logo_metrics is not None
        defines.extend(
            [
                openscad_define("right_logo_svg", str(svg_path)),
                openscad_define(
                    "right_logo_src_x0", logo_metrics["x0"] * SVG_TO_OPENSCAD
                ),
                openscad_define(
                    "right_logo_src_y0", logo_metrics["y0"] * SVG_TO_OPENSCAD
                ),
                openscad_define(
                    "right_logo_text_w", logo_metrics["width"] * SVG_TO_OPENSCAD
                ),
                openscad_define(
                    "right_logo_text_h", logo_metrics["height"] * SVG_TO_OPENSCAD
                ),
            ]
        )
    else:
        defines.append(openscad_define("show_right_logo", False))

    defines.extend(
        [
            openscad_define("output_part", output_part),
            openscad_define("color_logo_style", variant.color_logo_style),
        ]
    )
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
) -> tuple[list[list[Path]], list[Path | None]]:
    """Render the SVG + STL assets for each badge.

    Returns `(item_stl_paths, reference_stl_paths)` aligned with `texts`.
    Assets are deduplicated by text (or once total for `show_logo=False`
    variants, where the text doesn't influence geometry).
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    cache: dict[str, tuple[list[Path], Path | None]] = {}
    item_stl_paths: list[list[Path]] = []
    reference_stl_paths: list[Path | None] = []

    for index, text in enumerate(texts, start=1):
        cache_key = text if variant.show_logo else "<no-logo>"
        cached = cache.get(cache_key)
        if cached is None:
            if variant.show_logo:
                slug = slugify(text, index)
                svg_path: Path | None = work_dir / f"{slug}.svg"
                logo_metrics: LogoMetrics | None = render_logo_svg(
                    text, svg_path, font_path, fill_outline
                )
            else:
                slug = "no_logo"
                svg_path = None
                logo_metrics = None

            printable_paths: list[Path] = []
            for part in variant.output_parts:
                stl_path = work_dir / f"{slug}_{part}.stl"
                render_stl(variant, svg_path, logo_metrics, part, stl_path)
                printable_paths.append(stl_path)

            ref_part = variant.height_reference_part
            ref_path: Path | None
            if ref_part is None:
                ref_path = None
            elif ref_part in variant.output_parts:
                ref_path = printable_paths[variant.output_parts.index(ref_part)]
            else:
                ref_path = work_dir / f"{slug}_{ref_part}_reference.stl"
                render_stl(variant, svg_path, logo_metrics, ref_part, ref_path)

            cached = (printable_paths, ref_path)
            cache[cache_key] = cached

        printable_paths, ref_path = cached
        item_stl_paths.append(printable_paths)
        reference_stl_paths.append(ref_path)

    return item_stl_paths, reference_stl_paths


def collect_texts(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> list[str]:
    if args.badges is not None:
        if not args.text:
            parser.error("--badges requires --text")
        if args.badges < 1:
            parser.error("--badges must be at least 1")
        return [args.text] * args.badges

    texts = [text.strip() for text in re.split(r"[\n,]", args.texts) if text.strip()]
    if not texts:
        parser.error("--texts must contain at least one entry")
    return texts


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a (multi-)plate Bambu 3MF of M5StickS3 cases. Either pass "
            "a list of unique per-badge texts with --texts, or repeat a "
            "single text across N identical badges with --text + --badges."
        )
    )
    parser.add_argument(
        "--variant",
        default="with-logo",
        choices=sorted(VARIANTS),
        help="Case/print variant to put on the plate.",
    )

    text_mode = parser.add_mutually_exclusive_group(required=True)
    text_mode.add_argument(
        "--texts",
        help="Comma- or newline-separated unique logo texts (one badge per text).",
    )
    text_mode.add_argument(
        "--badges",
        type=int,
        help="Number of identical badges to place. Requires --text.",
    )

    parser.add_argument(
        "--text",
        default=None,
        help="Logo text used for every badge when --badges is set.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, type=Path)
    parser.add_argument("--work-dir", default=DEFAULT_WORK_DIR, type=Path)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--bed-x", default=DEFAULT_BED_X, type=float)
    parser.add_argument("--bed-y", default=DEFAULT_BED_Y, type=float)
    parser.add_argument("--gap", default=DEFAULT_GAP, type=float)
    parser.add_argument(
        "--x-offset",
        default=DEFAULT_X_OFFSET,
        type=float,
        help="Non-negative inset from the right edge for the bottom-right layout.",
    )
    parser.add_argument(
        "--y-offset",
        default=DEFAULT_Y_OFFSET,
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
        default=DEFAULT_PLATE_GAP,
        type=float,
        help="Gap between logical Bambu plates in the project canvas.",
    )
    parser.add_argument(
        "--inner-wall-backing",
        type=float,
        default=None,
        help=(
            "Override the variant's color-logo inner-wall backing thickness "
            "in millimeters. Default keeps the variant's built-in value."
        ),
    )
    parser.add_argument(
        "--outline",
        action="store_true",
        help=(
            "Treat the font as an outline font and fill the outer silhouettes "
            "before generating each badge SVG."
        ),
    )
    parser.add_argument(
        "--stl-output",
        action="append",
        default=[],
        metavar="PART:PATH",
        help=(
            "Copy a rendered STL to PATH after building. PART must be one of "
            "the variant's output parts (e.g. 'full', 'body', 'logo'). May be "
            "repeated. Only valid with a single-badge invocation."
        ),
    )
    args = parser.parse_args()

    texts = collect_texts(args, parser)
    variant = VARIANTS[args.variant]
    if args.inner_wall_backing is not None:
        variant = replace(variant, inner_wall_backing=args.inner_wall_backing)

    stl_outputs: list[tuple[str, Path]] = []
    for spec in args.stl_output:
        part, sep, path_str = spec.partition(":")
        if not sep or not part or not path_str:
            parser.error(f"--stl-output must be PART:PATH (got {spec!r})")
        if part not in variant.output_parts:
            parser.error(
                f"--stl-output part {part!r} is not in variant "
                f"{args.variant!r} output parts {variant.output_parts}"
            )
        stl_outputs.append((part, Path(path_str)))
    if stl_outputs and len(texts) != 1:
        parser.error("--stl-output requires a single-badge invocation")

    item_stl_paths, reference_stl_paths = build_badge_assets(
        texts, variant, args.work_dir, args.font, args.outline
    )

    for part, dst in stl_outputs:
        src = item_stl_paths[0][variant.output_parts.index(part)]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    # Include the layer-height modifier only when every badge shares the same
    # logo geometry (and the variant has a reference part). Mixed-text plates
    # intentionally omit it because priming behavior breaks for varying logo
    # sizes.
    logo_height_stl: Path | None = None
    if reference_stl_paths and reference_stl_paths[0] is not None:
        if len(set(reference_stl_paths)) == 1:
            logo_height_stl = reference_stl_paths[0]

    # Use a clean name for single-badge outputs; fall back to numbered "Badge"
    # names for multi-item plates.
    if len(texts) == 1:
        if variant.show_logo:
            item_names = [f"M5StickS3 Click Case - {texts[0]}"]
            logo_part_names = [f"{texts[0]} logo insert"]
        else:
            item_names = ["M5StickS3 Click Case"]
            logo_part_names = [LOGO_PART_NAME]
    else:
        item_names = [
            f"M5StickS3 Click Case Badge {index:02d} - {text}"
            for index, text in enumerate(texts, start=1)
        ]
        logo_part_names = [f"{text} logo insert" for text in texts]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary = build_plate_3mf(
        template_path=variant.template,
        item_stl_paths=item_stl_paths,
        output_path=args.output,
        bed_x=args.bed_x,
        bed_y=args.bed_y,
        gap=args.gap,
        x_offset=args.x_offset,
        y_offset=args.y_offset,
        plate_columns=args.plate_columns,
        plate_gap=args.plate_gap,
        logo_height_stl=logo_height_stl,
        detect_thin_wall=variant.detect_thin_wall,
        patch_color_metadata=variant.patch_color_metadata,
        item_names=item_names,
        logo_part_names=logo_part_names,
    )
    print(
        f"{args.output} "
        f"({summary.badge_count} badges, {summary.plate_count} plates, "
        f"{summary.badges_per_full_plate} badges/full plate, "
        f"variant {args.variant})"
    )
    return 0


if __name__ == "__main__":
    cli_entry(main)
