#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def parse_ascii_stl(path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[float], list[float]]:
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    index: dict[tuple[float, float, float], int] = {}
    current: list[int] = []
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3

    for line in path.read_text(errors="strict").splitlines():
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


def build_model_xml(stl_path: Path, bed_x: float, bed_y: float) -> bytes:
    vertices, triangles, mins, maxs = parse_ascii_stl(stl_path)
    center_x = (mins[0] + maxs[0]) / 2
    center_y = (mins[1] + maxs[1]) / 2
    tx = bed_x - center_x
    ty = bed_y - center_y

    vertex_xml = "\n".join(
        f'      <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>'
        for x, y, z in vertices
    )
    triangle_xml = "\n".join(
        f'      <triangle v1="{v1}" v2="{v2}" v3="{v3}"/>'
        for v1, v2, v3 in triangles
    )

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">
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
  <object id="1" type="model" name="{escape(stl_path.name)}">
   <mesh>
    <vertices>
{vertex_xml}
    </vertices>
    <triangles>
{triangle_xml}
    </triangles>
   </mesh>
  </object>
 </resources>
 <build>
  <item objectid="1" transform="1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} 0"/>
 </build>
</model>
'''.encode("utf-8")


def build_3mf(template_path: Path, stl_path: Path, output_path: Path, bed_x: float, bed_y: float) -> None:
    model_xml = build_model_xml(stl_path, bed_x, bed_y)

    with ZipFile(template_path, "r") as template, ZipFile(output_path, "w", ZIP_DEFLATED) as output:
        for info in template.infolist():
            if info.filename == "3D/3dmodel.model":
                continue
            output.writestr(info, template.read(info.filename))

        output.writestr("3D/3dmodel.model", model_xml)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject one ASCII STL into a Bambu Studio 3MF template.")
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--stl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bed-x", default=90.0, type=float)
    parser.add_argument("--bed-y", default=90.0, type=float)
    args = parser.parse_args()

    build_3mf(args.template, args.stl, args.output, args.bed_x, args.bed_y)
    print(args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
