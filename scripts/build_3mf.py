#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

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

    model_date = date.today().isoformat()
    transform = bed_center_transform(meshes, bed_x, bed_y)
    model = ET.Element(
        "model",
        {
            "unit": "millimeter",
            "{http://www.w3.org/XML/1998/namespace}lang": "en-US",
            "xmlns": CORE_NS,
        },
    )
    for name, value in (
        ("Application", "BambuStudio-02.06.00.51"),
        ("BambuStudio:3mfVersion", "1"),
        ("Copyright", ""),
        ("CreationDate", model_date),
        ("Description", ""),
        ("Designer", ""),
        ("DesignerCover", ""),
        ("DesignerUserId", "2683275966"),
        ("License", ""),
        ("ModificationDate", model_date),
        ("Origin", ""),
        ("ProfileCover", ""),
        ("ProfileDescription", ""),
        ("ProfileTitle", ""),
        ("Title", ""),
    ):
        metadata = ET.SubElement(model, "metadata", {"name": name})
        metadata.text = value

    resources = ET.SubElement(model, "resources")
    for obj_id, mesh in enumerate(meshes, start=1):
        append_mesh_object(resources, obj_id, mesh)

    build = ET.SubElement(model, "build")

    if len(meshes) > 1:
        assembly_id = len(meshes) + 1
        append_assembly_object(resources, assembly_id, len(meshes), transform)
        # Only the assembly is placed in the build. The transform is applied to
        # components so Bambu Studio keeps the body/logo as selectable parts.
        ET.SubElement(build, "item", {"objectid": str(assembly_id)})
    else:
        ET.SubElement(build, "item", {"objectid": "1", "transform": transform})

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
            f"({layout_width:.1f} x {layout_depth:.1f} mm needed "
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

    model_date = date.today().isoformat()
    positions = plate_layout_positions(
        items, bed_x, bed_y, columns, gap, x_offset, y_offset
    )
    model = ET.Element(
        "model",
        {
            "unit": "millimeter",
            "{http://www.w3.org/XML/1998/namespace}lang": "en-US",
            "xmlns": CORE_NS,
        },
    )
    for name, value in (
        ("Application", "BambuStudio-02.06.00.51"),
        ("BambuStudio:3mfVersion", "1"),
        ("Copyright", ""),
        ("CreationDate", model_date),
        ("Description", ""),
        ("Designer", ""),
        ("DesignerCover", ""),
        ("DesignerUserId", "2683275966"),
        ("License", ""),
        ("ModificationDate", model_date),
        ("Origin", ""),
        ("ProfileCover", ""),
        ("ProfileDescription", ""),
        ("ProfileTitle", ""),
        ("Title", ""),
    ):
        metadata = ET.SubElement(model, "metadata", {"name": name})
        metadata.text = value

    resources = ET.SubElement(model, "resources")
    build = ET.SubElement(model, "build")
    next_id = 1
    assembly_settings: list[AssemblySettings] = []

    for item, (x, y) in zip(items, positions, strict=True):
        mesh_ids = []
        for mesh in item.meshes:
            mesh_name = item.name if len(item.meshes) == 1 else None
            append_mesh_object(resources, next_id, mesh, mesh_name)
            mesh_ids.append(next_id)
            next_id += 1

        if len(mesh_ids) == 1:
            build_object_id = mesh_ids[0]
        else:
            assembly_id = next_id
            append_plate_assembly_object(resources, assembly_id, mesh_ids, item.name)
            assembly_settings.append(
                AssemblySettings(
                    assembly_id=assembly_id,
                    name=item.name,
                    # Bambu part settings address the assembly component
                    # object IDs, not the part's ordinal position.
                    body_part_id=str(mesh_ids[0]),
                    logo_part_id=str(mesh_ids[1]),
                    body_part_name=item.body_part_name,
                    logo_part_name=item.logo_part_name,
                )
            )
            build_object_id = assembly_id
            next_id += 1

        ET.SubElement(
            build,
            "item",
            {
                "objectid": str(build_object_id),
                "transform": center_transform_for_bounds(
                    combined_bounds(item.meshes), x, y
                ),
            },
        )

    return ET.tostring(model, encoding="utf-8", xml_declaration=True), assembly_settings


def format_float(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


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


def set_metadata(element: ET.Element, key: str, value: str) -> None:
    for metadata in element.findall("metadata"):
        if metadata.get("key") == key:
            metadata.set("value", value)
            return

    ET.SubElement(element, "metadata", {"key": key, "value": value})


def find_child_by_attr(
    element: ET.Element,
    tag: str,
    attr: str,
    value: str,
) -> ET.Element | None:
    for child in element.findall(tag):
        if child.get(attr) == value:
            return child
    return None


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
    wrote_layer_config_ranges = False

    with (
        ZipFile(template_path, "r") as template,
        ZipFile(output_path, "w", ZIP_DEFLATED) as output,
    ):
        for info in template.infolist():
            if info.filename == "3D/3dmodel.model":
                continue

            content = template.read(info.filename)

            if is_multi:
                if info.filename == "Metadata/project_settings.config":
                    content = patch_color_project_settings(content, detect_thin_wall)
                elif info.filename == "Metadata/model_settings.config":
                    content = patch_model_settings(content, assembly_id)

            if (
                layer_config_ranges_xml is not None
                and info.filename == LAYER_CONFIG_RANGES_PATH
            ):
                content = layer_config_ranges_xml
                wrote_layer_config_ranges = True

            output.writestr(info, content)

        if layer_config_ranges_xml is not None and not wrote_layer_config_ranges:
            output.writestr(LAYER_CONFIG_RANGES_PATH, layer_config_ranges_xml)

        output.writestr("3D/3dmodel.model", model_xml)


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
    wrote_layer_config_ranges = False

    with (
        ZipFile(template_path, "r") as template,
        ZipFile(output_path, "w", ZIP_DEFLATED) as output,
    ):
        for info in template.infolist():
            if info.filename == "3D/3dmodel.model":
                continue

            content = template.read(info.filename)

            if patch_color_metadata:
                if info.filename == "Metadata/project_settings.config":
                    content = patch_color_project_settings(content, detect_thin_wall)
                elif (
                    info.filename == "Metadata/model_settings.config"
                    and assembly_settings
                ):
                    content = patch_assembly_model_settings(content, assembly_settings)

            if (
                layer_config_ranges_xml is not None
                and info.filename == LAYER_CONFIG_RANGES_PATH
            ):
                content = layer_config_ranges_xml
                wrote_layer_config_ranges = True

            output.writestr(info, content)

        if layer_config_ranges_xml is not None and not wrote_layer_config_ranges:
            output.writestr(LAYER_CONFIG_RANGES_PATH, layer_config_ranges_xml)

        output.writestr("3D/3dmodel.model", model_xml)


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
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
