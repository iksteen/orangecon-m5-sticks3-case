# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` and `README.md` are the source of truth for project rules and target descriptions — read them. This file points at the parts most likely to bite you.

## What this repo is

OpenSCAD snap case for the M5StickS3 packaged as STL / 3MF / zip for FDM printing. One SCAD file (`m5sticks3_click_case.scad`) produces every variant via OpenSCAD `-D` overrides; Python scripts wrap those STLs into Bambu Studio 3MF projects.

## Build commands

The `Makefile` is the canonical entry point. Common targets:

- `make all` — STLs, all 3MFs, and the zip.
- `make 3mf` — every standard 3MF (single-material + color-logo variants).
- `make color-logo-{embossed,flush,flush-backed}` — single color-logo variants.
- `make badge-plate BADGE_TEXTS="ALICE,BOB,..."` — up to 10 cases with custom logo text on one plate. `BADGE_VARIANT` selects single-material vs color-logo variant.
- `make platecycler PLATECYCLER_BADGES=80` — multi-plate batch sliced via Bambu Studio CLI with PlateCycler swap gcode injected.
- `make clean` — removes generated STL/3MF/SVG/zip/badge work.

Python formatting: `uv run ruff format scripts/`. No test suite.

External tools required: `openscad`, `uv` (manages Python and the `pyproject.toml` dependencies — `fonttools`, `pillow`, `platecycler`), `zip`. The Makefile invokes every Python tool via `uv run` (e.g. `uv run python scripts/build_3mf.py …`, `uv run platecycler …`) so dependencies are resolved against the uv-managed env. `platecycler` invokes the Bambu Studio CLI itself — it finds `bambu-studio` on `PATH` or the `com.bambulab.BambuStudio` flatpak; the Makefile no longer calls Bambu Studio directly.

The Brave Hearted font (`fonts/brave-hearted.ttf`) is licensed and not committed — see README for source. Any logo-rendering target fails without it.

## Architecture

**SCAD output selection.** `m5sticks3_click_case.scad` switches on:
- `output_part`: `"full"` (single-material with embossed logo), `"body"` (case minus logo volume), `"logo"` (insert only).
- `color_logo_style`: `"embossed"` (insert reaches the raised outer face) or `"flush"` (insert ends flush with the outer wall).
- `color_logo_inner_wall_backing`: keeps that many mm of body material on the inner wall behind a flush logo (the `flush-backed` variant uses `0.45`).
- `show_right_logo=false`: omits the side logo entirely.

**3MF assembly.** `scripts/build_3mf.py` injects one or two ASCII STLs into a Bambu Studio template (`*_template.3mf`) and patches only model-specific metadata. The color template is the source of truth for the second filament and color-print slicer profile — don't reintroduce filament or layer-height logic in the script. The `--logo-height-stl` flag uses the supplied STL only as a Z-bounds reference for the layer-height modifier; it is not added as a part.

**Color-logo template.** Color-logo 3MFs are built from `m5sticks3_click_case_color_template.3mf`, single-material 3MFs from `m5sticks3_click_case_template.3mf`. Generated 3MF intentionally bakes in: `#FF8000` second filament, logo insert assigned to extruder 2, and (flush-backed only) `detect_thin_wall` plus `0.45 mm` inner-wall backing.

**Plate builders.** `scripts/build_badge_plate.py` lays out up to 10 cases with per-case custom logo SVGs on one plate. `scripts/build_platecycler_3mf.py` packs a requested badge count onto as many A1 mini plates as needed (starts bottom-right, fills along -X, then up along +Y). The `platecycler` CLI — an external tool declared as a git dependency in `pyproject.toml` (https://github.com/iksteen/platecycler) — takes the unsliced multi-plate 3MF, drives the Bambu Studio CLI to slice it, concatenates the per-plate gcode, inserts the Chitu PlateCycler swap gcode between plates, refreshes the md5, and collapses metadata to one printable plate.

## Hard constraints (do not relitigate without a user request)

- **Mechanical fit is physically validated:** clearances, window positions, snap-lip strength, and eyelet strength are correct. Do not "improve" these dimensions without new physical evidence or an explicit ask.
- **Embossed and flush logo inserts are through-wall by design.** The inner face being logo-colored is hidden by the M5StickS3. Only the `flush-backed` variant keeps body material behind the insert.
- **Do not reintroduce a boolean cut of the wall for the color-logo body.** The body STL is the intact wall; the insert overlaps it and Bambu Studio's part-priority (insert is part 2, extruder=2) colors the overlap. A boolean cut produced visible perimeter gaps because the two STLs' cut-surface triangulations did not align exactly.
- **Do not move the validated cavity or window coordinates** when adjusting `front_outer_edge_round` / `rear_outer_edge_round` bevels. Keep `top_gpio_cap_shell_bridge()` paired with the rear bevel so the lanyard eyelet stays joined at the open face.
- **Badge plates intentionally omit the per-logo layer-height modifier** — mixed text sizes break priming.
- **3MF edits use structured JSON/XML**, not string patching of `Metadata/project_settings.config` or `Metadata/model_settings.config`.

## Verification after touching `build_3mf.py` or the color-logo SCAD path

1. `uv run python -m py_compile scripts/build_3mf.py`
2. `make all`
3. `with-logo` and color-logo 3MFs contain the logo-height modifier; `no-logo` does not.
4. Color-logo slicer profile settings (layer height, support Z distance, etc.) come from the color template unchanged.
5. Part 2 is still assigned to extruder 2; second filament color is still `#FF8000`.

## Git hygiene

Generated STL/3MF/SVG/zip/build artifacts are gitignored — don't commit them. The `*_template.3mf` and `*_reference.3mf` files are checked-in source inputs (whitelisted in `.gitignore`); treat them as authoritative.
