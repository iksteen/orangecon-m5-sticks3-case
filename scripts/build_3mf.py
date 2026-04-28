#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]
Bounds = tuple[list[float], list[float]]
Mesh = tuple[Path, list[Point3], list[Triangle], Bounds]

MODEL_NAME = "M5StickS3 Click Case Color Logo"
BODY_PART_NAME = "Case body"
LOGO_PART_NAME = "ORANGECON logo insert"
LOGO_FILAMENT_COLOR = "#FF8000"

TWO_FILAMENT_KEYS = (
    "default_filament_colour",
    "nozzle_temperature",
    "nozzle_temperature_initial_layer",
    "nozzle_temperature_range_high",
    "nozzle_temperature_range_low",
    "required_nozzle_HRC",
)

REPEATED_FILAMENT_KEYS = {
    "filament_dev_ams_drying_ams_limitations": 4,
    "filament_dev_ams_drying_temperature": 8,
    "filament_dev_ams_drying_time": 8,
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


def bed_center_transform(meshes: list[Mesh], bed_x: float, bed_y: float) -> str:
    mins, maxs = combined_bounds(meshes)
    center_x = (mins[0] + maxs[0]) / 2
    center_y = (mins[1] + maxs[1]) / 2
    tx = bed_x - center_x
    ty = bed_y - center_y
    return f"1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} 0"


def mesh_object_xml(obj_id: int, mesh: Mesh) -> str:
    stl_path, vertices, triangles, _ = mesh
    vertex_xml = "\n".join(
        f'      <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in vertices
    )
    triangle_xml = "\n".join(
        f'      <triangle v1="{v1}" v2="{v2}" v3="{v3}"/>' for v1, v2, v3 in triangles
    )

    return f'''  <object id="{obj_id}" type="model" name="{escape(stl_path.name)}">
   <mesh>
    <vertices>
{vertex_xml}
    </vertices>
    <triangles>
{triangle_xml}
    </triangles>
   </mesh>
  </object>'''


def assembly_object_xml(assembly_id: int, component_count: int, transform: str) -> str:
    component_xml = "\n".join(
        f'    <component objectid="{obj_id}" transform="{transform}"/>'
        for obj_id in range(1, component_count + 1)
    )
    return f'''  <object id="{assembly_id}" type="model" name="{MODEL_NAME}">
   <components>
{component_xml}
   </components>
  </object>'''


def build_model_xml(stl_paths: list[Path], bed_x: float, bed_y: float) -> bytes:
    meshes = load_meshes(stl_paths)
    if not meshes:
        raise ValueError("at least one STL path is required")

    transform = bed_center_transform(meshes, bed_x, bed_y)
    resource_xml = [mesh_object_xml(i, mesh) for i, mesh in enumerate(meshes, start=1)]

    if len(meshes) > 1:
        assembly_id = len(meshes) + 1
        resource_xml.append(assembly_object_xml(assembly_id, len(meshes), transform))
        # Only the assembly is placed in the build. The transform is applied to
        # components so Bambu Studio keeps the body/logo as selectable parts.
        build_items = f'  <item objectid="{assembly_id}"/>'
    else:
        build_items = f'  <item objectid="1" transform="{transform}"/>'

    resources = "\n".join(resource_xml)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
 <metadata name="Application">BambuStudio-02.06.00.51</metadata>
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <metadata name="Copyright"></metadata>
 <metadata name="CreationDate">2026-04-26</metadata>
 <metadata name="Description"></metadata>
 <metadata name="Designer"></metadata>
 <metadata name="DesignerCover"></metadata>
 <metadata name="DesignerUserId">2683275966</metadata>
 <metadata name="License"></metadata>
 <metadata name="ModificationDate">2026-04-26</metadata>
 <metadata name="Origin"></metadata>
 <metadata name="ProfileCover"></metadata>
 <metadata name="ProfileDescription"></metadata>
 <metadata name="ProfileTitle"></metadata>
 <metadata name="Title"></metadata>
 <resources>
{resources}
 </resources>
 <build>
{build_items}
 </build>
</model>
""".encode("utf-8")


def ensure_repeated_list(data: dict[str, object], key: str, length: int) -> None:
    value = data.get(key)
    if not isinstance(value, list) or not value:
        return

    repeated = []
    while len(repeated) < length:
        repeated.extend(value)
    data[key] = repeated[:length]


def patch_project_settings(content: bytes) -> bytes:
    data = json.loads(content.decode("utf-8"))

    for key, value in list(data.items()):
        if isinstance(value, list) and len(value) == 1 and key.startswith("filament_"):
            data[key] = [value[0], value[0]]

    for key in TWO_FILAMENT_KEYS:
        ensure_repeated_list(data, key, 2)

    for key, length in REPEATED_FILAMENT_KEYS.items():
        ensure_repeated_list(data, key, length)

    if isinstance(data.get("extruder_ams_count"), list) and data["extruder_ams_count"]:
        data["extruder_ams_count"] = [
            data["extruder_ams_count"][0],
            data["extruder_ams_count"][0],
        ]

    if (
        isinstance(data.get("filament_colour_type"), list)
        and len(data["filament_colour_type"]) >= 2
    ):
        data["filament_colour_type"][1] = "1"

    if (
        isinstance(data.get("filament_self_index"), list)
        and len(data["filament_self_index"]) >= 2
    ):
        data["filament_self_index"][1] = "2"

    for key in ("filament_colour", "filament_multi_colour"):
        if isinstance(data.get(key), list) and len(data[key]) >= 2:
            data[key][1] = LOGO_FILAMENT_COLOR

    data["enable_prime_tower"] = "1"

    if "wipe_tower_x" not in data or not data["wipe_tower_x"]:
        data["wipe_tower_x"] = ["15"]
    if "wipe_tower_y" not in data or not data["wipe_tower_y"]:
        data["wipe_tower_y"] = ["140"]

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
    ET.register_namespace("", "")
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
) -> None:
    model_xml = build_model_xml(stl_paths, bed_x, bed_y)
    is_multi = len(stl_paths) > 1
    assembly_id = len(stl_paths) + 1 if is_multi else 1

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
                    content = patch_project_settings(content)
                elif info.filename == "Metadata/model_settings.config":
                    content = patch_model_settings(content, assembly_id)

            output.writestr(info, content)

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
    args = parser.parse_args()

    build_3mf(args.template, args.stls, args.output, args.bed_x, args.bed_y)
    print(args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
