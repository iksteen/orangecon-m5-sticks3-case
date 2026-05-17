# AGENTS.md

## Project Overview

This repo builds an OpenSCAD snap case for the M5StickS3 and packages it as STL,
3MF, and zip outputs for PLA/PETG printing.

The main model is `m5sticks3_click_case.scad`. It supports normal
single-material output and a color-logo split output via the `output_part`
OpenSCAD variable:

- `output_part="full"`: normal case with embossed ORANGECON logo.
- `output_part="body"`: case body with the through-wall logo volume removed.
- `output_part="logo"`: the ORANGECON logo insert only.

For two-color builds, `color_logo_style` selects the side-wall finish:

- `color_logo_style="embossed"`: logo insert reaches the outer embossed face.
- `color_logo_style="flush"`: logo insert ends flush with the outer wall.

The optional `color_logo_inner_wall_backing` value keeps that much body
material on the inner wall behind the split logo insert. The
`color-logo-flush-backed` Make target uses `0.45` mm, matching the configured
`inner_wall_line_width` in the color 3MF template, and enables
`detect_thin_wall` for that generated 3MF so the single-line backing survives
slicing.

The standard embossed and flush logo inserts intentionally run through the side
wall. The flush-backed variant keeps one line width of body material on the
inner wall while preserving the exterior flush logo face.

The mechanical fit has been physically validated: current clearances fit well,
all windows are correctly positioned, the snap lips are strong enough, and the
eyelet is strong enough. Do not reopen those assumptions without new physical
evidence or an explicit user request.

## Important Files

- `Makefile`: canonical build entry points.
- `m5sticks3_click_case.scad`: case geometry and output-part selection.
- `scripts/build_logo_svg.py`: renders logo text from a font directly to SVG
  paths. The Makefile supplies the current default `ORANGECON` text and
  `fonts/brave-hearted.ttf` font path, and uses `--outline` to fill the outline
  font while preserving the intended counters.
- `scripts/build_3mf.py`: injects ASCII STL meshes into a Bambu Studio 3MF
  template and patches only model-specific Bambu metadata. Its optional
  `--logo-height-stl` argument uses that STL only as a height-modifier bounds
  reference, not as an added model part.
- `scripts/build_platecycler_3mf.py`: builds repeated multi-plate Bambu
  projects from the single-material with-logo case for PlateCycler automation.
  The Makefile defaults use 8 plates with 10 ORANGECON cases per plate.
- `scripts/inject_platecycler_gcode.py`: merges sliced per-plate Bambu gcode
  and injects the Chitu PlateCycler plate-swap gcode.
- `m5sticks3_click_case_template.3mf`: source Bambu Studio template.
- `m5sticks3_click_case_color_template.3mf`: source Bambu Studio
  template for the two-color logo output only. It already contains the second
  filament definition and color-print profile settings.
- `m5sticks3_click_case_color_logo_reference.3mf`: known-good
  reference for color-logo filament/extruder metadata.

## Build Commands

- `make color-logo`: build all color-logo variants.
- `make color-logo-embossed`: build `m5sticks3_click_case_color_logo_embossed.3mf`.
- `make color-logo-flush`: build `m5sticks3_click_case_color_logo_flush.3mf`.
- `make color-logo-flush-backed`: build
  `m5sticks3_click_case_color_logo_flush_backed.3mf`.
- `make 3mf`: build all 3MF outputs.
- `make platecycler`: build the 8-plate with-logo project, slice it with the
  Bambu Studio CLI, and inject PlateCycler gcode into the sliced `.gcode.3mf`.
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
- `m5sticks3_click_case_color_body_flush_backed.stl`
- `m5sticks3_click_case_color_logo_insert_flush_backed.stl`

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
- flush-backed logo inner-wall body-material thickness: `0.45` mm
- flush-backed thin-wall detection: enabled for
  `m5sticks3_click_case_color_logo_flush_backed.3mf`
- logo-height modifier: `Metadata/layer_config_ranges.xml` sets the logo's
  Z span to `0.16` mm layers, with the min/max Z values derived from the logo
  insert STL bounds. The same modifier is also applied to
  `m5sticks3_click_case_with_logo.3mf`, using the embossed logo insert STL as a
  bounds reference.

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

The standard embossed and flush logo inserts should remain through-wall. The
inside face being logo-colored is intentional and will be hidden by the
inserted M5StickS3. The flush-backed variant is the exception: it deliberately
keeps `color_logo_inner_wall_backing` of body material on the inside.

The front/build-plate and rear/open-side outer perimeters are intentionally
softened by visible `front_outer_edge_round` and `rear_outer_edge_round` bevels
in the outer shell. They should not move the validated internal cavity or
window coordinates. Keep `top_gpio_cap_shell_bridge()` with the rear bevel so
the lanyard eyelet remains joined to the main shell at the open face.

## Verification Checklist

After changing `scripts/build_3mf.py` or the color-logo SCAD path:

1. Run `python3 -m py_compile scripts/build_3mf.py`.
2. Run `make all`.
3. Verify `m5sticks3_click_case_with_logo.3mf` and the color-logo 3MFs contain
   the logo-height modifier, while `m5sticks3_click_case_no_logo.3mf` does not.
4. Verify color-logo profile settings such as layer height and support Z
   distance are preserved from `m5sticks3_click_case_color_template.3mf`.
5. Verify the Bambu model settings still assign part 2 to extruder `2`.
6. Verify the second filament display color is `#FF8000`.

## Editing Guidance

Generated outputs are ignored by git. Avoid committing generated STL/3MF/zip
artifacts unless explicitly requested. The template and reference 3MF files are
intentional source/reference inputs.

Prefer narrow changes that preserve the existing OpenSCAD coordinate system and
Makefile targets. Use structured JSON/XML handling for 3MF metadata; avoid
string patching inside `Metadata/project_settings.config` or
`Metadata/model_settings.config`.
