# AGENTS.md

## Project Overview

This repo builds an OpenSCAD snap case for the M5StickS3 and packages it as STL,
3MF, and zip outputs for PLA/PETG printing.

The main model is `m5sticks3_click_case.scad`. It supports normal
single-material output and a color-logo split output via the `output_part`
OpenSCAD variable:

- `output_part="full"`: normal case with embossed ORANGECON logo.
- `output_part="body"`: case body with the through-wall logo volume removed.
- `output_part="logo"`: the through-wall ORANGECON logo insert only.

For two-color builds, `color_logo_style` selects the side-wall finish:

- `color_logo_style="embossed"`: logo insert reaches the outer embossed face.
- `color_logo_style="flush"`: logo insert ends flush with the outer wall.

The logo insert intentionally runs through the side wall. It is meant for a
semi-transparent glow-in-the-dark filament, so preserving logo volume is more
important than keeping the color on the exterior surface only.

The mechanical fit has been physically validated: current clearances fit well,
all windows are correctly positioned, the snap lips are strong enough, and the
eyelet is strong enough. Do not reopen those assumptions without new physical
evidence or an explicit user request.

## Important Files

- `Makefile`: canonical build entry points.
- `m5sticks3_click_case.scad`: case geometry and output-part selection.
- `scripts/build_orangecon_logo_svg.py`: renders the ORANGECON wordmark from
  `fonts/brave-hearted.ttf` directly to SVG paths, filling the outline font
  while preserving the intended counters.
- `scripts/build_3mf.py`: injects ASCII STL meshes into a Bambu Studio 3MF
  template and patches only model-specific Bambu metadata.
- `m5sticks3_click_case_template.3mf`: source Bambu Studio template.
- `m5sticks3_click_case_color_template.3mf`: source Bambu Studio
  template for the two-color logo output only. It already contains the second
  filament definition and color-print profile settings.
- `m5sticks3_click_case_color_logo_reference.3mf`: known-good
  reference for color-logo filament/extruder metadata.

## Build Commands

- `make color-logo`: build both color-logo variants.
- `make color-logo-embossed`: build `m5sticks3_click_case_color_logo_embossed.3mf`.
- `make color-logo-flush`: build `m5sticks3_click_case_color_logo_flush.3mf`.
- `make 3mf`: build all 3MF outputs.
- `make all`: build STL, 3MF, and zip outputs.
- `make clean`: remove generated artifacts.
- `ruff format scripts/build_3mf.py`: format the 3MF builder.

Build dependencies include `openscad`, `python3`, `fontTools`, `zip`, and `ruff`
for formatting.

## Color Logo 3MF Rules

Each color-logo 3MF is built from two variant-specific STLs:

- `m5sticks3_click_case_color_body_embossed.stl`
- `m5sticks3_click_case_color_logo_insert_embossed.stl`
- `m5sticks3_click_case_color_body_flush.stl`
- `m5sticks3_click_case_color_logo_insert_flush.stl`

`scripts/build_3mf.py` creates an assembly object named
`M5StickS3 Click Case Color Logo`, with Bambu model settings:

- part 1: `Case body`
- part 2: `ORANGECON logo insert`
- assembly/object extruder: `1`
- logo insert extruder: `2`

The color-logo build uses `m5sticks3_click_case_color_template.3mf`,
not the single-material template. The color template is the source of truth for
second-filament definitions, layer-height-dependent settings, support settings,
prime tower settings, and other slicer profile choices. Do not reintroduce
second-filament duplication or layer-height-derived setting logic in
`scripts/build_3mf.py`.

The intentionally baked-in model-specific overrides are:

- second filament color: `#FF8000`
- logo-height modifier: `Metadata/layer_config_ranges.xml` sets the logo's
  Z span to `0.16` mm layers, with the min/max Z values derived from the logo
  insert STL bounds.

The script also patches object/part names and assigns the logo insert to
extruder `2`.

## Geometry Notes

The current fit, window locations, snap lip strength, and eyelet strength are
validated. Preserve those dimensions unless the user explicitly asks for a
mechanical change.

For the split color-logo build, the body subtraction must use the same Y/Z logo
footprint as the actual logo insert. Do not add `offset()` or lateral slop to
the logo footprint, because that creates a visible perimeter gap. If the body
boolean needs help, overcut only along the wall/extrusion axis.

The logo insert should remain through-wall in both color variants. The inside
face being logo-colored is intentional and will be hidden by the inserted
M5StickS3.

The front/build-plate and rear/open-side outer perimeters are intentionally
softened by small `front_outer_edge_round` and `rear_outer_edge_round` bevels
in the outer shell. They should not move the validated internal cavity or
window coordinates.

## Verification Checklist

After changing `scripts/build_3mf.py` or the color-logo SCAD path:

1. Run `python3 -m py_compile scripts/build_3mf.py`.
2. Run `make color-logo`.
3. Verify color-logo profile settings such as layer height and support Z
   distance are preserved from `m5sticks3_click_case_color_template.3mf`.
4. Verify the Bambu model settings still assign part 2 to extruder `2`.
5. Verify the second filament display color is `#FF8000`.

## Editing Guidance

Generated outputs are ignored by git. Avoid committing generated STL/3MF/zip
artifacts unless explicitly requested. The template and reference 3MF files are
intentional source/reference inputs.

Prefer narrow changes that preserve the existing OpenSCAD coordinate system and
Makefile targets. Use structured JSON/XML handling for 3MF metadata; avoid
string patching inside `Metadata/project_settings.config` or
`Metadata/model_settings.config`.
