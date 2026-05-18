#!/usr/bin/env python3

from __future__ import annotations

import argparse
import functools
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zipfile import ZipFile

from threemf_utils import (
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

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
MODEL_NAME = "M5StickS3 Click Case Color Logo"
BODY_PART_NAME = "Case body"
LOGO_PART_NAME = "ORANGECON logo insert"
LOGO_FILAMENT_COLOR = "#FF8000"
LOGO_LAYER_HEIGHT = "0.16"
# Bambu stores the height range on the assembled print object, while the logo
# bounds come from the second input STL.
LOGO_MESH_INDEX = 1
LAYER_CONFIG_OBJECT_ID = "1"
LAYER_CONFIG_RANGES_PATH = "Metadata/layer_config_ranges.xml"
IDENTITY_MATRIX = "1 0 0 0 1 0 0 0 1"
# Bambu Studio allocates low instance IDs internally while slicing. Dense
# generated IDs 1..80 fail on 80-object repeated-plate jobs, while Bambu-authored
# projects use high sparse IDs.
REPEATED_PLATE_IDENTIFY_ID_START = 20000
REPEATED_PLATE_IDENTIFY_ID_STEP = 11
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


def bed_center_transform(meshes: list[Mesh], bed_x: float, bed_y: float) -> str:
    return center_transform_for_bounds(combined_bounds(meshes), bed_x, bed_y)


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


def append_assembly_object(
    resources: ET.Element,
    assembly_id: int,
    component_count: int,
    transform: str,
) -> None:
    obj = ET.SubElement(
        resources,
        "object",
        {"id": str(assembly_id), "type": "model", "name": MODEL_NAME},
    )
    components = ET.SubElement(obj, "components")
    for obj_id in range(1, component_count + 1):
        ET.SubElement(
            components,
            "component",
            {"objectid": str(obj_id), "transform": transform},
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


def build_model_xml(meshes: list[Mesh], bed_x: float, bed_y: float) -> bytes:
    if not meshes:
        raise ValueError("at least one STL path is required")

    transform = bed_center_transform(meshes, bed_x, bed_y)
    model, resources, build = build_model_document()
    for obj_id, mesh in enumerate(meshes, start=1):
        append_mesh_object(resources, obj_id, mesh)

    if len(meshes) > 1:
        assembly_id = len(meshes) + 1
        append_assembly_object(resources, assembly_id, len(meshes), transform)
        # Only the assembly is placed in the build. The transform is applied to
        # components so Bambu Studio keeps the body/logo as selectable parts.
        append_build_item(build, assembly_id)
    else:
        append_build_item(build, 1, transform)

    return ET.tostring(model, encoding="utf-8", xml_declaration=True)


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


def side_column_plate_layout_positions(
    item_count: int,
    item_width: float,
    item_depth: float,
    bed_x: float,
    bed_y: float,
    gap: float,
    x_offset: float,
    y_offset: float,
) -> list[tuple[float, float]]:
    main_columns = 4
    main_rows = 2
    main_count = min(main_columns * main_rows, item_count)
    main_width = main_columns * item_width + (main_columns - 1) * gap
    total_depth = main_rows * item_depth + (main_rows - 1) * gap
    main_left = bed_x - main_width / 2 + x_offset
    left_column_x = main_left - gap - item_width / 2
    positions: list[tuple[float, float]] = []

    for index in range(main_count):
        row = index // main_columns
        column = index % main_columns
        x = main_left + item_width / 2 + column * (item_width + gap)
        y = (
            bed_y
            + total_depth / 2
            - item_depth / 2
            - row * (item_depth + gap)
            + y_offset
        )
        positions.append((x, y))

    for extra_index in range(item_count - main_count):
        row = extra_index % main_rows
        y = (
            bed_y
            + total_depth / 2
            - item_depth / 2
            - row * (item_depth + gap)
            + y_offset
        )
        positions.append((left_column_x, y))

    return positions


def plate_layout_positions(
    items: list[PlateModelItem],
    bed_x: float,
    bed_y: float,
    columns: int = 4,
    gap: float = 5.0,
    x_offset: float = 0,
    y_offset: float = 0,
) -> list[tuple[float, float]]:
    if not items:
        raise ValueError("at least one plate item is required")
    if columns < 1:
        raise ValueError("columns must be at least 1")

    columns = min(columns, len(items))
    rows = (len(items) + columns - 1) // columns
    item_width = max(item_xy_size(item)[0] for item in items)
    item_depth = max(item_xy_size(item)[1] for item in items)
    total_depth = rows * item_depth + (rows - 1) * gap
    bed_width = bed_x * 2
    bed_depth = bed_y * 2

    if len(items) > 8 and columns == 4:
        positions = side_column_plate_layout_positions(
            len(items),
            item_width,
            item_depth,
            bed_x,
            bed_y,
            gap,
            x_offset,
            y_offset,
        )
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

    positions = []
    for row in range(rows):
        row_start = row * columns
        row_count = min(columns, len(items) - row_start)
        row_width = row_count * item_width + (row_count - 1) * gap
        y = (
            bed_y
            + total_depth / 2
            - item_depth / 2
            - row * (item_depth + gap)
            + y_offset
        )

        for column in range(row_count):
            x = (
                bed_x
                - row_width / 2
                + item_width / 2
                + column * (item_width + gap)
                + x_offset
            )
            positions.append((x, y))

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


def bottom_right_plate_layout_positions(
    items: list[PlateModelItem],
    bed_x: float,
    bed_y: float,
    gap: float = 5.0,
    x_offset: float = 0,
    y_offset: float = 0,
) -> list[tuple[float, float]]:
    if not items:
        raise ValueError("at least one plate item is required")
    if x_offset < 0 or y_offset < 0:
        raise ValueError("bottom-right plate offsets must be non-negative edge insets")

    item_width = max(item_xy_size(item)[0] for item in items)
    item_depth = max(item_xy_size(item)[1] for item in items)
    bed_width = bed_x * 2
    bed_depth = bed_y * 2
    right_x = bed_width - item_width / 2 - x_offset
    x = right_x
    y = item_depth / 2 + y_offset
    positions = []

    for index, _ in enumerate(items):
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
    item: PlateModelItem,
    bed_x: float,
    bed_y: float,
    gap: float = 5.0,
    x_offset: float = 0,
    y_offset: float = 0,
) -> tuple[int, list[tuple[float, float]]]:
    if x_offset < 0 or y_offset < 0:
        raise ValueError("bottom-right plate offsets must be non-negative edge insets")

    item_width, item_depth = item_xy_size(item)
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
        [item] * capacity,
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
    columns: int = 4,
    gap: float = 5.0,
    x_offset: float = 0,
    y_offset: float = 0,
) -> tuple[bytes, list[AssemblySettings]]:
    if not items:
        raise ValueError("at least one plate item is required")

    positions = plate_layout_positions(
        items, bed_x, bed_y, columns, gap, x_offset, y_offset
    )
    model, resources, build = build_model_document()
    next_id = 1
    assembly_settings: list[AssemblySettings] = []

    for item, (x, y) in zip(items, positions, strict=True):
        next_id, _, _, settings = append_plate_item(
            resources, build, next_id, item, x, y
        )
        if settings is not None:
            assembly_settings.append(settings)

    return ET.tostring(model, encoding="utf-8", xml_declaration=True), assembly_settings


def logo_height_modifier_bounds(
    meshes: list[Mesh],
    logo_height_stl: Path | None,
) -> Bounds | None:
    if logo_height_stl is not None:
        _, _, bounds = parse_ascii_stl(logo_height_stl)
        return bounds

    if len(meshes) > LOGO_MESH_INDEX:
        return meshes[LOGO_MESH_INDEX][3]

    return None


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


def build_layer_config_ranges_xml(logo_bounds: Bounds) -> bytes:
    return build_layer_config_ranges_xml_for_objects(
        [(LAYER_CONFIG_OBJECT_ID, logo_bounds)]
    )


def build_repeated_plate_model_xml(
    mesh: Mesh,
    badge_count: int,
    bed_x: float,
    bed_y: float,
    gap: float,
    x_offset: float,
    y_offset: float,
    plate_columns: int | None,
    plate_gap: float,
) -> tuple[bytes, list[PlacedPlateItem], RepeatedPlateSummary]:
    if badge_count < 1:
        raise ValueError("badge count must be at least 1")

    capacity_item = PlateModelItem(meshes=[mesh], name="M5StickS3 Click Case")
    badges_per_full_plate, base_positions = bottom_right_plate_capacity(
        capacity_item, bed_x, bed_y, gap, x_offset, y_offset
    )
    plate_count = math.ceil(badge_count / badges_per_full_plate)
    if plate_columns is None:
        plate_columns = math.ceil(math.sqrt(plate_count))
    if plate_columns < 1:
        raise ValueError("plate columns must be at least 1")
    plate_columns = min(plate_columns, plate_count)
    plate_step_x = bed_x * 2 + plate_gap
    plate_step_y = bed_y * 2 + plate_gap

    model, resources, build = build_model_document()
    placed_items: list[PlacedPlateItem] = []
    next_id = 1

    for plate_index in range(plate_count):
        plate_column = plate_index % plate_columns
        plate_row = plate_index // plate_columns
        plate_offset_x = plate_column * plate_step_x
        plate_offset_y = -plate_row * plate_step_y
        plate_badge_count = min(
            badges_per_full_plate,
            badge_count - plate_index * badges_per_full_plate,
        )

        for slot_index, (base_x, base_y) in enumerate(
            base_positions[:plate_badge_count], start=1
        ):
            badge_number = plate_index * badges_per_full_plate + slot_index
            item = PlateModelItem(
                meshes=[mesh], name=f"M5StickS3 Click Case {badge_number:02d}"
            )
            next_id, object_id, transform, _ = append_plate_item(
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

    return (
        ET.tostring(model, encoding="utf-8", xml_declaration=True),
        placed_items,
        RepeatedPlateSummary(
            badge_count=badge_count,
            plate_count=plate_count,
            badges_per_full_plate=badges_per_full_plate,
        ),
    )


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

    identify_id = REPEATED_PLATE_IDENTIFY_ID_START
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
            identify_id += REPEATED_PLATE_IDENTIFY_ID_STEP
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


def build_repeated_plate_3mf(
    template_path: Path,
    stl_path: Path,
    output_path: Path,
    badge_count: int,
    bed_x: float,
    bed_y: float,
    gap: float,
    x_offset: float,
    y_offset: float,
    plate_columns: int | None,
    plate_gap: float,
    logo_height_stl: Path | None,
) -> RepeatedPlateSummary:
    mesh = load_meshes([stl_path])[0]
    model_xml, placed_items, summary = build_repeated_plate_model_xml(
        mesh,
        badge_count,
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
            build_plate_instance_model_settings,
            placed_items=placed_items,
            plate_count=summary.plate_count,
        ),
    }

    rewrite_zip(template_path, output_path, patches=patches, overrides=overrides)
    return summary


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


def patch_model_settings(content: bytes, assembly_id: int) -> bytes:
    return patch_assembly_model_settings(
        content,
        [AssemblySettings(assembly_id=assembly_id, name=MODEL_NAME)],
    )


def build_3mf(
    template_path: Path,
    stl_paths: list[Path],
    output_path: Path,
    bed_x: float,
    bed_y: float,
    logo_height_stl: Path | None,
    detect_thin_wall: bool,
) -> None:
    meshes = load_meshes(stl_paths)
    model_xml = build_model_xml(meshes, bed_x, bed_y)
    is_multi = len(stl_paths) > 1
    assembly_id = len(stl_paths) + 1 if is_multi else 1
    logo_bounds = logo_height_modifier_bounds(meshes, logo_height_stl)
    layer_config_ranges_xml = (
        build_layer_config_ranges_xml(logo_bounds) if logo_bounds is not None else None
    )

    overrides: dict[str, bytes] = {"3D/3dmodel.model": model_xml}
    if layer_config_ranges_xml is not None:
        overrides[LAYER_CONFIG_RANGES_PATH] = layer_config_ranges_xml

    patches = {}
    if is_multi:
        patches["Metadata/project_settings.config"] = functools.partial(
            patch_color_project_settings, detect_thin_wall=detect_thin_wall
        )
        patches["Metadata/model_settings.config"] = functools.partial(
            patch_model_settings, assembly_id=assembly_id
        )

    rewrite_zip(template_path, output_path, patches=patches, overrides=overrides)


def build_plate_3mf(
    template_path: Path,
    item_stl_paths: list[list[Path]],
    output_path: Path,
    bed_x: float,
    bed_y: float,
    logo_bounds_by_item: list[Bounds | None] | None = None,
    detect_thin_wall: bool = False,
    patch_color_metadata: bool = False,
    item_names: list[str] | None = None,
    body_part_names: list[str] | None = None,
    logo_part_names: list[str] | None = None,
    columns: int = 4,
    gap: float = 5.0,
    x_offset: float = 0,
    y_offset: float = 0,
) -> None:
    if not item_stl_paths:
        raise ValueError("at least one plate item is required")

    if item_names is None:
        item_names = [
            f"M5StickS3 Click Case Badge {index}"
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

    items = [
        PlateModelItem(
            meshes=load_meshes(stl_paths),
            name=item_names[index],
            body_part_name=body_part_names[index],
            logo_part_name=logo_part_names[index],
        )
        for index, stl_paths in enumerate(item_stl_paths)
    ]
    model_xml, assembly_settings = build_plate_model_xml(
        items,
        bed_x,
        bed_y,
        columns,
        gap,
        x_offset,
        y_offset,
    )
    layer_config_ranges_xml = None
    if logo_bounds_by_item is not None:
        if len(logo_bounds_by_item) != len(items):
            raise ValueError("logo bounds count must match plate item count")
        object_logo_bounds = [
            (str(index), logo_bounds)
            for index, logo_bounds in enumerate(logo_bounds_by_item, start=1)
            if logo_bounds is not None
        ]
        if object_logo_bounds:
            layer_config_ranges_xml = build_layer_config_ranges_xml_for_objects(
                object_logo_bounds
            )

    overrides: dict[str, bytes] = {"3D/3dmodel.model": model_xml}
    if layer_config_ranges_xml is not None:
        overrides[LAYER_CONFIG_RANGES_PATH] = layer_config_ranges_xml

    patches = {}
    if patch_color_metadata:
        patches["Metadata/project_settings.config"] = functools.partial(
            patch_color_project_settings, detect_thin_wall=detect_thin_wall
        )
        if assembly_settings:
            patches["Metadata/model_settings.config"] = functools.partial(
                patch_assembly_model_settings, assembly_settings=assembly_settings
            )

    rewrite_zip(template_path, output_path, patches=patches, overrides=overrides)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inject one or more ASCII STLs into a Bambu Studio 3MF template."
    )
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--stl", required=True, type=Path, action="append", dest="stls")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bed-x", default=90.0, type=float)
    parser.add_argument("--bed-y", default=90.0, type=float)
    parser.add_argument(
        "--logo-height-stl",
        type=Path,
        help=(
            "Optional STL whose Z bounds define the logo height modifier "
            "without adding it as a printable model part."
        ),
    )
    parser.add_argument(
        "--detect-thin-wall",
        action="store_true",
        help="Enable slicer thin-wall detection for this generated 3MF.",
    )
    args = parser.parse_args()

    build_3mf(
        args.template,
        args.stls,
        args.output,
        args.bed_x,
        args.bed_y,
        args.logo_height_stl,
        args.detect_thin_wall,
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    cli_entry(main)
