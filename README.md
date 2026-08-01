# M5StickS3 Click Case

This project builds a snap-fit case for the M5StickS3 — a pocket-sized
ESP32-S3 dev kit from M5Stack — and packages it as STL, 3MF, and zip
outputs for FDM printing. The case was originally designed as a wearable
badge for [ORANGECON](https://orangecon.nl/), a Dutch hacker conference,
hence the `ORANGECON` default side-logo text and orange (`#FF8000`) accent
filament. Override `LOGO_TEXT` for a different one-off logo, or use `make
named` / `make bulk` to generate custom-text batches for any event or
production run.

Licensed under the [MIT License](LICENSE).

## Requirements

- `make`
- `openscad`
- `uv` (manages the Python interpreter and dependencies declared in
  `pyproject.toml`; the Makefile invokes Python tools via `uv run`)
- `zip`

## Font Setup

The logo builder expects the Brave Hearted font at
`fonts/brave-hearted.ttf`. That font is licensed and is not included in
this repository. Buy/download it from Creative Market:

<https://creativemarket.com/Heroglyphs/2261491-Brave-Hearted>

Create the `fonts` directory and place the `.ttf` there before running any
logo-rendering target.

Brave Hearted is an *outline* font — its glyphs are drawn as strokes, not
as solid shapes. The Makefile fills those outlines by default
(`LOGO_OUTLINE_FLAG=--outline`) so the wordmark prints as a solid
silhouette. To use a font that's already filled, override `LOGO_FONT` and
clear `LOGO_OUTLINE_FLAG`:

```sh
make all LOGO_FONT=fonts/my-filled-font.ttf LOGO_OUTLINE_FLAG=
```

## Build Parameters

Override any of these on the command line (e.g. `make all LOGO_TEXT=FOO`)
or in the environment. Defaults are safe.

### Logo

- `LOGO_TEXT`: the logo text used by `make all` and `make bulk` (and the
  default for `NAME_TEXTS`). Default: `ORANGECON`.
- `LOGO_FONT`: path to the font file. Default: `fonts/brave-hearted.ttf`.
- `LOGO_OUTLINE_FLAG`: flag forwarded to the logo renderer. Default:
  `--outline`. Set to empty for already-filled fonts.
- `LOGO_INNER_WALL_BACKING`: thickness in millimeters of body material
  kept behind the flush logo insert on the inner wall (only used by
  `color-logo-flush-backed`). Default: `0.45`, matching the
  `inner_wall_line_width` in the color 3MF template so the backing prints
  as a single inner wall line.

### `make svg-logo` and `make svg-bulk` only

- `LOGO_SVG`: path to an SVG used as the badge logo instead of text
  rendered from `LOGO_FONT`. Required by both targets; no default. The
  artwork is centered and scaled to the side wall exactly like a text
  logo, so it should be a filled, cropped SVG (no stray whitespace in the
  drawing — its geometry bounds are what gets fit).
- `SVG_COUNT`: Badge count for `make svg-bulk`. Default: `10`, roughly one
  full A1 mini plate; higher counts spill onto more plates.
- `SVG_STEM`: Output filename stem. Default:
  `m5sticks3_click_case_<svg filename without extension>`. `make svg-logo`
  writes `$(SVG_STEM).3mf`; `make svg-bulk` writes
  `$(SVG_STEM)_x$(SVG_COUNT).platecycler.3mf`; the two-filament targets
  write `$(SVG_STEM)_color_logo_<variant>.3mf`.
- `SVG_BUILD_DIR` / `SVG_BULK_BUILD_DIR`: Intermediate assets
  directories. Defaults: `build/svg`, `build/svg_bulk`.

### Plate layout (`make named`, `make bulk`, `make svg-*`)

Offsets are non-negative edge insets from the bottom-right of each plate;
badges fill leftward along -X, then up along +Y, and spill onto
additional plates as needed.

- `VARIANT`: Case variant (see below). Default: `with-logo`. The
  single-badge 3MF targets hard-wire their own variant and ignore this.
- `GAP`: Spacing between badges in millimeters. Default: `2.5`.
- `X_OFFSET`: Inset from the right plate edge. Default: `10`.
- `Y_OFFSET`: Inset from the bottom plate edge. Default: `10`.

### `make named` only

- `NAME_TEXTS`: Comma- or newline-separated logo texts (one badge per
  entry). Default: `$(LOGO_TEXT)`.
- `NAME_STEM`: Output filename stem. Default:
  `m5sticks3_click_case_named_badges`. Final output is
  `$(NAME_STEM).platecycler.3mf`.
- `NAME_BUILD_DIR`: Intermediate assets directory. Default: `build/named`.

### `make bulk` only

- `BULK_COUNT`: Total badge count. Default: `80`.
- `BULK_STEM`: Output filename stem. Default:
  `m5sticks3_click_case_orangecon_x$(BULK_COUNT)`. Final output is
  `$(BULK_STEM).platecycler.3mf`.
- `BULK_BUILD_DIR`: Intermediate assets directory. Default: `build/bulk`.

### Variants

- `no-logo`: Single-material case with no side logo.
- `with-logo`: Single-material case with embossed text.
- `color-logo-embossed`: Two-filament case with a raised logo insert.
- `color-logo-flush`: Two-filament case with a flush logo insert.
- `color-logo-flush-backed`: Two-filament flush logo with inner-wall
  backing.

Color-logo variants assign the body to filament 1 and the logo insert to
filament 2 (orange `#FF8000` in the generated project). Slicer settings
(layer height, supports, prime tower, etc.) come from the checked-in
3MF templates.

## Quick Start

Build the standard deliverable (STLs, all 3MFs, and zip):

```sh
make all
```

Build a plate of named badges and run it through PlateCycler:

```sh
make named NAME_TEXTS="ALICE,BOB,CAROL"
```

Build 80 identical cases for a PlateCycler bulk run:

```sh
make bulk
```

## Make Targets

### `make all`

Builds the canonical deliverable: STLs and 3MFs for the single-material
variants, 3MFs for the three color-logo variants, and a zip of all of
those.

Outputs:

- `m5sticks3_click_case_no_logo.stl` / `.3mf`
- `m5sticks3_click_case_with_logo.stl` / `.3mf`
- `m5sticks3_click_case_color_logo_embossed.3mf`
- `m5sticks3_click_case_color_logo_flush.3mf`
- `m5sticks3_click_case_color_logo_flush_backed.3mf`
- `m5sticks3_click_case.zip`

### `make named` and `make bulk`

Both targets call the same script and use the same plate-layout pipeline;
they only differ in how the badge list is sourced:

- `make named` reads a comma- or newline-separated list from `NAME_TEXTS`
  and produces one badge per entry. Intended for event/name-badge runs.
- `make bulk` repeats `LOGO_TEXT` across `BULK_COUNT` identical cases for
  bulk production.

Both always pipe the assembled project through the `platecycler`
post-processor (via the generic `%.platecycler.3mf: %.3mf` Make rule), so
the final output is `$(*_STEM).platecycler.3mf`. The unsliced intermediate
`$(*_STEM).3mf` is kept on disk as a Make dependency.

`platecycler` finds the Bambu Studio CLI itself (either `bambu-studio`
on `PATH` or the `com.bambulab.BambuStudio` flatpak).

When every badge shares the same logo (always for `bulk`; for `named`
only when `NAME_TEXTS` resolves to a single unique entry) the project
includes a layer-height modifier so the logo prints at 0.16 mm layers.
Mixed-text `named` runs omit the modifier — priming behavior breaks for
varying logo sizes.

Examples:

```sh
make named NAME_TEXTS="ALICE,BOB,CAROL"

make named \
  VARIANT=color-logo-embossed \
  NAME_TEXTS="ALICE,BOB,CAROL,DAVE" \
  NAME_STEM=team_badges

make bulk BULK_COUNT=40 VARIANT=color-logo-flush-backed
```

### `make svg-logo` and `make svg-bulk`

Same pipeline as the text targets, with the logo coming from `LOGO_SVG`
instead of a font render:

- `make svg-logo` builds a single-badge project.
- `make svg-bulk` builds `SVG_COUNT` copies and pipes them through
  `platecycler`, like `make bulk`.

`VARIANT` selects single-material or color-logo output here too (`no-logo`
is rejected — there is nowhere to put the artwork).

For two-filament single badges, use the dedicated targets instead of
`VARIANT`; they mirror `make color-logo` and give each variant its own
filename so all three can coexist:

- `make svg-color-logo` builds all three.
- `make svg-color-logo-embossed` / `-flush` / `-flush-backed` build one.

```sh
make svg-logo LOGO_SVG=logos/cat.svg

make svg-color-logo LOGO_SVG=logos/cat.svg

make svg-bulk LOGO_SVG=logos/cat.svg SVG_COUNT=20 VARIANT=color-logo-flush
```

### `make clean`

Removes generated STL, 3MF, SVG, zip, and intermediate assets.

### Other targets

Any specific output is a valid Make target — e.g. `make
m5sticks3_click_case_color_logo_flush.3mf` for a single 3MF. Aggregate
aliases exist for subsets (`make 3mf`, `make color-logo`, `make
no-logo`, etc.); see the Makefile for the full list.

## PlateCycler Post-Processing

`make named` and `make bulk` post-process the multi-plate 3MF using the
standalone [`platecycler`](https://github.com/iksteen/platecycler) tool,
which is declared as a project dependency in `pyproject.toml`.
`platecycler` accepts either an unsliced `.3mf` (it invokes the Bambu
Studio CLI internally to slice) or an already-sliced `.gcode.3mf`. To run
it manually:

```sh
platecycler --force -o output.3mf input.3mf
```

See the platecycler README for the full set of flags (`--swap-gcode`,
`--plate`, `--repeat`, etc.) and default output-filename behavior.
