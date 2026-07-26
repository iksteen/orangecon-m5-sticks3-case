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
- `scripts/build_3mf.py`: the single unified plate builder. It renders the
  per-text SVG via `build_logo_svg.py`, runs OpenSCAD per variant to produce
  body/logo STLs in a work-dir, and assembles them into a (multi-)plate
  Bambu 3MF using the variant's template (`m5sticks3_click_case_template.3mf`
  or `m5sticks3_click_case_color_template.3mf`). Drives every 3MF target:
  `make no-logo`, `make with-logo`, `make color-logo-*` (each invoked with
  `--badges 1` and a hard-wired `--variant`); `make named` (unique
  per-badge texts via `--texts`); and `make bulk` (one text repeated via
  `--text TEXT --badges N`; mutually exclusive with `--texts`). Five
  variants are supported (no-logo, with-logo, color-logo-embossed,
  color-logo-flush, color-logo-flush-backed); the `no-logo` variant skips
  the SVG/logo pipeline entirely and passes `show_right_logo=false` to
  OpenSCAD. The `--inner-wall-backing` CLI flag overrides the variant's
  built-in backing thickness (only meaningful for color-logo-flush-backed).
  The `--stl-output PART:PATH` flag copies a rendered STL out to PATH after
  building, so `m5sticks3_click_case_{with,no}_logo.stl` come from the same
  OpenSCAD run as their matching `.3mf` (the Makefile uses a grouped target
  `&:` to declare that one recipe execution produces both files).
  The `named` and `bulk` Make targets pipe the assembled project through
  the `platecycler` CLI via the generic `%.platecycler.3mf: %.3mf` pattern
  rule; with the Makefile defaults, the badge count for `make bulk` spreads
  across as many A1 mini plates as needed, packing roughly 10 ORANGECON
  cases per plate.
  `--logo-svg PATH` swaps the text/font logo for a user-supplied SVG, which
  drives `make svg-logo` (single badge) and `make svg-bulk` (`SVG_COUNT`
  copies through `platecycler`). The SVG's bounds are measured by extruding
  `import()` in a throwaway probe `.scad` and reading the resulting STL
  bounds, so the fit matches whatever OpenSCAD actually imports; the SCAD
  then centers and scales it like a text logo. `--logo-svg` is incompatible
  with `--texts` and with the `no-logo` variant, and defaults `--text`
  (naming only) to the SVG's filename stem.
- `platecycler` (external CLI, declared in `pyproject.toml` as a git
  dependency on https://github.com/iksteen/platecycler): merges sliced
  per-plate Bambu gcode and injects the Chitu PlateCycler plate-swap gcode.
  The Makefile invokes the installed `platecycler` console script directly.
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
- `make named` / `make bulk`: build a per-text or repeated-text multi-plate
  project and run it through the `platecycler` CLI, which slices with the
  Bambu Studio CLI and injects the PlateCycler plate-swap gcode in a single
  step. See README for the variable list.
- `make svg-logo LOGO_SVG=x.svg` / `make svg-bulk LOGO_SVG=x.svg`: same as
  the text targets, but the logo comes from `LOGO_SVG`. Both require it.
- `make all`: build STL, 3MF, and zip outputs.
- `make clean`: remove generated artifacts.
- `uv run ruff format scripts/build_3mf.py`: format the 3MF builder.

Build dependencies include `openscad`, `uv` (which manages Python and the
`pyproject.toml` dependencies — `fontTools`, `pillow`, `platecycler`, and the
`ruff` dev dependency), and `zip`. The Makefile invokes every Python tool via
`uv run`.

## Color Logo 3MF Rules

For each color-logo 3MF, `scripts/build_3mf.py` runs OpenSCAD twice per
unique badge text to render `<slug>_body.stl` and `<slug>_logo.stl` into the
target's work-dir (e.g. `build/color_logo_embossed/ORANGECON_body.stl`).
The two STLs are then assembled into a Bambu part with these model settings:

- assembly/object name: `M5StickS3 Click Case - <text>` for single-badge
  3MFs, `M5StickS3 Click Case Badge NN - <text>` for multi-badge plates.
- part 1: `Case body`
- part 2: `<text> logo insert`
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

The color-logo body STL is the intact side wall. The logo insert overlaps
it, and Bambu Studio's part priority (insert is part 2, extruder 2) colors
the overlap in the second filament. Do not reintroduce a boolean cut of the
wall for the color-logo body — a previous attempt produced visible
perimeter gaps because the two STLs' cut-surface triangulations did not
align exactly.

`logo_footprint_2d()` runs the imported SVG through `offset(delta = 0.001)`
before extruding. Exported logo art (Illustrator in particular) routinely has
overlapping subpaths, which extrude into a self-intersecting solid that CGAL
refuses to boolean against the shell; the Clipper pass in `offset()` resolves
them. Keep it — without it, arbitrary `--logo-svg` input fails with "The given
mesh is not closed". It leaves the ORANGECON case bounds unchanged.

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

1. Run `uv run python -m py_compile scripts/build_3mf.py`.
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
