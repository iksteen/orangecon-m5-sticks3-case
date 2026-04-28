#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def parse_ascii_stl(
    path: Path,
) -> tuple[
    list[tuple[float, float, float]],
    list[tuple[int, int, int]],
    list[float],
    list[float],
]:
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    index: dict[tuple[float, float, float], int] = {}
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

    return vertices, triangles, mins, maxs


def build_model_xml(stl_paths: list[Path], bed_x: float, bed_y: float) -> bytes:
    all_mins = [float("inf")] * 3
    all_maxs = [float("-inf")] * 3

    meshes = []
    for stl_path in stl_paths:
        vertices, triangles, mins, maxs = parse_ascii_stl(stl_path)
        meshes.append((stl_path, vertices, triangles, mins, maxs))
        for axis in range(3):
            all_mins[axis] = min(all_mins[axis], mins[axis])
            all_maxs[axis] = max(all_maxs[axis], maxs[axis])

    center_x = (all_mins[0] + all_maxs[0]) / 2
    center_y = (all_mins[1] + all_maxs[1]) / 2
    tx = bed_x - center_x
    ty = bed_y - center_y

    resource_xml = []
    item_xml = []

    # If we have multiple meshes, we create a single assembly object using components.
    if len(meshes) > 1:
        # First, define individual meshes as objects.
        # These will not be placed directly in the build.
        for i, (stl_path, vertices, triangles, mins, maxs) in enumerate(meshes):
            obj_id = i + 1

            vertex_xml = "\n".join(
                f'      <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>'
                for x, y, z in vertices
            )
            triangle_xml = "\n".join(
                f'      <triangle v1="{v1}" v2="{v2}" v3="{v3}"/>'
                for v1, v2, v3 in triangles
            )

            resource_xml.append(f'''  <object id="{obj_id}" type="model" name="{escape(stl_path.name)}">
   <mesh>
    <vertices>
{vertex_xml}
    </vertices>
    <triangles>
{triangle_xml}
    </triangles>
   </mesh>
  </object>''')

        # Now create the assembly object.
        assembly_id = len(meshes) + 1
        component_xml = "\n".join(
            f'    <component objectid="{i + 1}" transform="1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} 0"/>'
            for i in range(len(meshes))
        )
        resource_xml.append(f'''  <object id="{assembly_id}" type="model" name="Assembly">
   <components>
{component_xml}
   </components>
  </object>''')
        # Only the assembly is placed in the build.
        # Note: the transform is applied to components, so the assembly itself has identity transform.
        item_xml.append(f'  <item objectid="{assembly_id}"/>')
    else:
        # Single object case: original behavior but with tx, ty applied to the item.
        stl_path, vertices, triangles, mins, maxs = meshes[0]
        obj_id = 1
        vertex_xml = "\n".join(
            f'      <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>'
            for x, y, z in vertices
        )
        triangle_xml = "\n".join(
            f'      <triangle v1="{v1}" v2="{v2}" v3="{v3}"/>'
            for v1, v2, v3 in triangles
        )

        resource_xml.append(f'''  <object id="{obj_id}" type="model" name="{escape(stl_path.name)}">
   <mesh>
    <vertices>
{vertex_xml}
    </vertices>
    <triangles>
{triangle_xml}
    </triangles>
   </mesh>
  </object>''')
        item_xml.append(
            f'  <item objectid="{obj_id}" transform="1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} 0"/>'
        )

    resources = "\n".join(resource_xml)
    build_items = "\n".join(item_xml)

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


def patch_project_settings(content: bytes) -> bytes:
    data = json.loads(content.decode("utf-8"))

    # Duplicate settings that Bambu Studio stores per filament/nozzle.
    for key, value in list(data.items()):
        if isinstance(value, list) and len(value) == 1 and key.startswith("filament_"):
            data[key] = [value[0], value[0]]

    duplicate_single_value_keys = (
        "default_filament_colour",
        "nozzle_temperature",
        "nozzle_temperature_initial_layer",
        "nozzle_temperature_range_high",
        "nozzle_temperature_range_low",
        "required_nozzle_HRC",
    )
    for key in duplicate_single_value_keys:
        value = data.get(key)
        if isinstance(value, list) and len(value) == 1:
            data[key] = [value[0], value[0]]

    for key in (
        "filament_dev_ams_drying_ams_limitations",
        "filament_dev_ams_drying_temperature",
        "filament_dev_ams_drying_time",
    ):
        value = data.get(key)
        if isinstance(value, list) and value:
            data[key] = value + value

    if isinstance(data.get("extruder_ams_count"), list) and data["extruder_ams_count"]:
        data["extruder_ams_count"] = [data["extruder_ams_count"][0], data["extruder_ams_count"][0]]

    if isinstance(data.get("filament_colour_type"), list) and len(data["filament_colour_type"]) >= 2:
        data["filament_colour_type"][1] = "1"

    if isinstance(data.get("filament_self_index"), list) and len(data["filament_self_index"]) >= 2:
        data["filament_self_index"][1] = "2"

    # Specific color for the second filament (ORANGECON Orange).
    for key in ("filament_colour", "filament_multi_colour"):
        if isinstance(data.get(key), list) and len(data[key]) >= 2:
            data[key][1] = "#FF8000"

    # Enable prime tower
    data["enable_prime_tower"] = "1"
    # Ensure wipe tower coordinates are reasonable if not present (Bambu Studio usually has them)
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


def patch_model_settings(content: bytes, assembly_id: int) -> bytes:
    ET.register_namespace("", "")
    root = ET.fromstring(content.decode("utf-8"))

    # Find or create object entry for our assembly
    obj_entry = None
    for obj in root.findall("object"):
        if obj.get("id") == str(assembly_id):
            obj_entry = obj
            break

    if obj_entry is None:
        obj_entry = ET.SubElement(root, "object", {"id": str(assembly_id)})

    # Metadata for the assembly object.
    set_metadata(obj_entry, "name", "Assembly")
    set_metadata(obj_entry, "extruder", "1")

    # We want at least two parts if it's a multi-part build.
    # build_3mf will only call this for multi-part builds.

    # Part 1 (Body)
    part1 = None
    for p in obj_entry.findall("part"):
        if p.get("id") == "1":
            part1 = p
            break
    if part1 is None:
        part1 = ET.SubElement(obj_entry, "part", {"id": "1", "subtype": "normal_part"})
    set_metadata(part1, "name", "Assembly")

    # Part 2 (Logo)
    part2 = None
    for p in obj_entry.findall("part"):
        if p.get("id") == "2":
            part2 = p
            break
    if part2 is None:
        part2 = ET.SubElement(obj_entry, "part", {"id": "2", "subtype": "normal_part"})
    set_metadata(part2, "name", "Assembly_2")
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
