# M5StickS3 Click Case

This project builds a snap case for the M5StickS3 and packages it as STL, 3MF,
and zip outputs for printing. The Makefile default logo text is ORANGECON, and
the badge plate target can generate custom logo text per case.

## Requirements

- `make`
- `openscad`
- `uv` (manages the Python interpreter and dependencies declared in
  `pyproject.toml`; the Makefile invokes Python tools via `uv run`)
- `zip`

## Font Setup

The logo builder expects the Brave Hearted font at
`fonts/brave-hearted.ttf`. That font is licensed and is not included in this
repository. Buy/download it from Creative Market:

<https://creativemarket.com/Heroglyphs/2261491-Brave-Hearted>

Create the `fonts` directory and place the `.ttf` there before running targets
that generate logo SVGs, STLs, or 3MFs.

Brave Hearted is an *outline* font: its glyphs are drawn as strokes, not as
solid shapes. The Makefile fills those outlines by default so the wordmark
prints as a solid silhouette.

The font path and the outline-filling behavior are controlled by two Makefile
variables:

- `LOGO_FONT`: path to the font file passed to `build_logo_svg.py` (and, via
  `make badge-plate`, to `build_badge_plate.py`). Default:
  `fonts/brave-hearted.ttf`.
- `LOGO_OUTLINE_FLAG`: flag forwarded to the logo scripts. Default:
  `--outline`, which enables the outline-fill pass. To use a font that is
  already filled, override it with an empty value so no flag is forwarded:

  ```sh
  make all LOGO_FONT=fonts/my-filled-font.ttf LOGO_OUTLINE_FLAG=
  make badge-plate LOGO_FONT=fonts/my-filled-font.ttf LOGO_OUTLINE_FLAG= \
      BADGE_TEXTS="ALICE,BOB"
  ```

## Quick Start

Build everything:

```sh
make all
```

Build only the standard printable 3MF files:

```sh
make 3mf
```

Build a custom badge plate:

```sh
make badge-plate BADGE_VARIANT=color-logo-embossed BADGE_TEXTS="ALICE,BOB,CAROL"
```

Build the 8-plate PlateCycler batch from the with-logo case:

```sh
make platecycler
```

Generated STL, 3MF, SVG, zip, and badge work files are build artifacts and are
ignored by git.

## Make Targets

### `make all`

Builds the normal STL files, all standard 3MF files, and
`m5sticks3_click_case.zip`.

Outputs:

- `m5sticks3_click_case_with_logo.stl`
- `m5sticks3_click_case_no_logo.stl`
- `m5sticks3_click_case_with_logo.3mf`
- `m5sticks3_click_case_no_logo.3mf`
- `m5sticks3_click_case_color_logo_embossed.3mf`
- `m5sticks3_click_case_color_logo_flush.3mf`
- `m5sticks3_click_case_color_logo_flush_backed.3mf`
- `m5sticks3_click_case.zip`

### `make with-logo`

Builds the single-material STL with the embossed side logo from `LOGO_TEXT`.
Default: `ORANGECON`.

Logo variables:

- `LOGO_TEXT`: Standard side-logo text. Default: `ORANGECON`.
- `LOGO_FONT`: Font used for generated logo SVGs. Default:
  `fonts/brave-hearted.ttf`.

Output:

- `m5sticks3_click_case_with_logo.stl`

### `make no-logo`

Builds the single-material STL without the side logo.

Output:

- `m5sticks3_click_case_no_logo.stl`

### `make 3mf`

Builds all standard 3MF files. Make will also build any STL inputs needed for
those 3MF files.

Outputs:

- `m5sticks3_click_case_with_logo.3mf`
- `m5sticks3_click_case_no_logo.3mf`
- `m5sticks3_click_case_color_logo_embossed.3mf`
- `m5sticks3_click_case_color_logo_flush.3mf`
- `m5sticks3_click_case_color_logo_flush_backed.3mf`

### `make color-logo`

Builds all two-filament logo 3MF variants.

Outputs:

- `m5sticks3_click_case_color_logo_embossed.3mf`
- `m5sticks3_click_case_color_logo_flush.3mf`
- `m5sticks3_click_case_color_logo_flush_backed.3mf`

The body is assigned to filament 1. The logo insert is assigned to filament 2,
using orange (`#FF8000`) in the generated Bambu Studio project.

### `make color-logo-embossed`

Builds the two-filament 3MF where the orange logo insert reaches the raised
outer embossed face.

Output:

- `m5sticks3_click_case_color_logo_embossed.3mf`

### `make color-logo-flush`

Builds the two-filament 3MF where the orange logo insert ends flush with the
outer wall.

Output:

- `m5sticks3_click_case_color_logo_flush.3mf`

### `make color-logo-flush-backed`

Builds the two-filament flush 3MF with a thin body-material backing behind the
logo on the inner wall. This variant enables thin-wall detection in the
generated 3MF.

Output:

- `m5sticks3_click_case_color_logo_flush_backed.3mf`

### `make badge-plate`

Builds one 3MF plate containing up to 10 badge cases, each with custom logo
text. This target is intended for event/name-badge style batches.

Default output:

- `m5sticks3_click_case_badge_plate.3mf`

Default work directory:

- `build/badge_plate`

Common examples:

```sh
make badge-plate BADGE_TEXTS="ALICE,BOB,CAROL"
```

```sh
make badge-plate \
  BADGE_VARIANT=color-logo-embossed \
  BADGE_TEXTS="ALICE,BOB,CAROL,DAVE" \
  BADGE_OUTPUT=team_badges.3mf
```

```sh
make badge-plate \
  BADGE_VARIANT=color-logo-flush-backed \
  BADGE_TEXTS="OPS,INFO,CREW,VOLUNTEER" \
  BADGE_X_OFFSET=20 \
  BADGE_Y_OFFSET=-20
```

Badge plate variables:

- `BADGE_TEXTS`: Comma-separated logo texts. Default: `ORANGECON`.
- `LOGO_FONT`: Font used for generated badge logo SVGs. Default:
  `fonts/brave-hearted.ttf`.
- `BADGE_VARIANT`: Case variant to place on the plate. Default: `with-logo`.
- `BADGE_OUTPUT`: Output 3MF path. Default:
  `m5sticks3_click_case_badge_plate.3mf`.
- `BADGE_BUILD_DIR`: Intermediate badge assets directory. Default:
  `build/badge_plate`.
- `BADGE_X_OFFSET`: Plate layout X shift in millimeters. Default: `20`.
- `BADGE_Y_OFFSET`: Plate layout Y shift in millimeters. Default: `-20`.

Supported `BADGE_VARIANT` values:

- `with-logo`: Single-material case with custom embossed text.
- `color-logo-embossed`: Two-filament case with a raised logo insert.
- `color-logo-flush`: Two-filament case with a flush logo insert.
- `color-logo-flush-backed`: Two-filament flush logo with inner-wall backing.

Short logo texts are auto-sized with a height cap so one- or two-letter names do
not become oversized. Longer texts are width-limited to fit the side-logo area.

### `make platecycler`

Builds a with-logo batch for a Chitu PlateCycler and runs it through the
`platecycler` tool, which slices the project with the Bambu Studio CLI and
injects the PlateCycler swap gcode. The requested total badge count is packed
onto as many logical plates as needed.

Default outputs:

- `m5sticks3_click_case_orangecon_x80.3mf`
- `m5sticks3_click_case_orangecon_x80.platecycler.3mf`

The generated project repeats the single-material `with-logo` case, using the
same logo-height modifier as `m5sticks3_click_case_with_logo.3mf`. Case
placement starts at the bottom-right of each A1 mini plate, fills left along X
until the next case would cross the plate edge, then moves up along Y and resets
to the right edge. The per-plate capacity is computed from the case bounds, bed
size, spacing, and offsets.

`platecycler` finds the Bambu Studio CLI itself (either `bambu-studio` on
`PATH` or the `com.bambulab.BambuStudio` flatpak); the Makefile no longer
shells out to it directly.

PlateCycler variables:

- `PLATECYCLER_STEM`: Output filename stem. Default:
  `m5sticks3_click_case_orangecon_x$(PLATECYCLER_BADGES)`.
- `PLATECYCLER_BADGES`: Total badge count. Default: `80`.
- `PLATECYCLER_GAP`: Case spacing in millimeters. Default: `2.5`.
- `PLATECYCLER_X_OFFSET`: Non-negative inset from the right plate edge.
  Default: `10`.
- `PLATECYCLER_Y_OFFSET`: Non-negative inset from the bottom plate edge.
  Default: `10`.

### `make zip`

Builds `m5sticks3_click_case.zip` containing the standard STL and 3MF outputs.
Make will build any missing files needed for the zip.

### `make clean`

Removes generated STL, 3MF, SVG, zip, and badge work files.

## PlateCycler Post-Processing

`make platecycler` post-processes the multi-plate 3MF using the standalone
[`platecycler`](https://github.com/iksteen/platecycler) tool, which is declared
as a project dependency in `pyproject.toml`. `platecycler` accepts either an
unsliced `.3mf` (it invokes the Bambu Studio CLI internally to slice) or an
already-sliced `.gcode.3mf`. To run it manually:

```sh
platecycler --force -o output.3mf input.3mf
```

See the platecycler README for the full set of flags (`--swap-gcode`,
`--plate`, `--repeat`, etc.) and default output-filename behavior.

## Notes For Printing

- Standard `with-logo` and `no-logo` outputs are single-material.
- `color-logo-*` outputs are intended for two-filament printing in Bambu Studio.
- The generated 3MF files inherit slicer settings from the checked-in template
  3MF files.
- Badge plates intentionally do not include the per-logo layer-height modifier,
  because mixed custom text sizes are not compatible with priming behavior.
