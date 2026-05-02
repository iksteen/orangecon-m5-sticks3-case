#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
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


def bed_center_transform(meshes: list[Mesh], bed_x: float, bed_y: float) -> str:
    mins, maxs = combined_bounds(meshes)
    center_x = (mins[0] + maxs[0]) / 2
    center_y = (mins[1] + maxs[1]) / 2
    tx = bed_x - center_x
    ty = bed_y - center_y
    return f"{IDENTITY_MATRIX} {tx:.6f} {ty:.6f} 0"


def append_mesh_object(resources: ET.Element, obj_id: int, mesh: Mesh) -> None:
    stl_path, vertices, triangles, _ = mesh
    obj = ET.SubElement(
        resources,
        "object",
        {"id": str(obj_id), "type": "model", "name": stl_path.name},
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


def build_layer_config_ranges_xml(logo_bounds: Bounds) -> bytes:
    logo_mins, logo_maxs = logo_bounds
    root = ET.Element("objects")
    obj = ET.SubElement(root, "object", {"id": LAYER_CONFIG_OBJECT_ID})
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

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def patch_color_project_settings(content: bytes) -> bytes:
    data = json.loads(content.decode("utf-8"))

    for key in ("filament_colour", "filament_multi_colour"):
        value = data.get(key)
        if not isinstance(value, list) or len(value) < 2:
            raise ValueError("multi-part color builds require a two-filament template")
        value[1] = LOGO_FILAMENT_COLOR

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


def patch_model_settings(content: bytes, assembly_id: int) -> bytes:
    root = ET.fromstring(content.decode("utf-8"))

    obj_entry = find_child_by_attr(root, "object", "id", str(assembly_id))
    if obj_entry is None:
        obj_entry = ET.SubElement(root, "object", {"id": str(assembly_id)})

    set_metadata(obj_entry, "name", MODEL_NAME)
    set_metadata(obj_entry, "extruder", "1")

    part1 = ensure_part(obj_entry, "1")
    set_metadata(part1, "name", BODY_PART_NAME)

    part2 = ensure_part(obj_entry, "2")
    set_metadata(part2, "name", LOGO_PART_NAME)
    set_metadata(part2, "extruder", "2")

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_3mf(
    template_path: Path,
    stl_paths: list[Path],
    output_path: Path,
    bed_x: float,
    bed_y: float,
    logo_height_stl: Path | None,
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
                    content = patch_color_project_settings(content)
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
    args = parser.parse_args()

    build_3mf(
        args.template,
        args.stls,
        args.output,
        args.bed_x,
        args.bed_y,
        args.logo_height_stl,
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
