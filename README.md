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

- `LOGO_FONT`: path to the font file passed to `build_logo_svg.py` (and to
  `build_3mf.py` for the per-text variants). Default:
  `fonts/brave-hearted.ttf`.
- `LOGO_OUTLINE_FLAG`: flag forwarded to the logo scripts. Default:
  `--outline`, which enables the outline-fill pass. To use a font that is
  already filled, override it with an empty value so no flag is forwarded:

  ```sh
  make all LOGO_FONT=fonts/my-filled-font.ttf LOGO_OUTLINE_FLAG=
  make named LOGO_FONT=fonts/my-filled-font.ttf LOGO_OUTLINE_FLAG= \
      NAME_TEXTS="ALICE,BOB"
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

Build a plate of named badges (each with a unique logo) and run it through
the PlateCycler post-processor:

```sh
make named VARIANT=color-logo-embossed NAME_TEXTS="ALICE,BOB,CAROL"
```

Build a bulk batch of identical cases (default 80 ORANGECONs) and run it
through PlateCycler:

```sh
make bulk
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

Variables:

- `LOGO_INNER_WALL_BACKING`: thickness in millimeters of body material kept
  behind the flush logo insert on the inner wall. Default `0.45`, which
  matches the `inner_wall_line_width` configured in the color 3MF template
  so the backing prints as a single inner wall line.

### `make named` and `make bulk`

Both targets call the same script (`scripts/build_3mf.py`) and share most
options. They only differ in how the badge list is sourced:

- `make named` reads a comma- or newline-separated list from `NAME_TEXTS`
  and produces one badge per entry. Intended for event/name-badge style
  runs where every case has a unique logo.
- `make bulk` repeats `LOGO_TEXT` across `BULK_COUNT` identical cases.
  Intended for bulk production runs.

Both targets always pipe the assembled project through the `platecycler`
post-processor (via the generic `%.platecycler.3mf: %.3mf` Make rule), so
the final output is `$(*_STEM).platecycler.3mf` (with the unsliced
intermediate `$(*_STEM).3mf` kept on disk as a Make dependency).
`platecycler` finds the Bambu Studio CLI itself (either `bambu-studio` on
`PATH` or the `com.bambulab.BambuStudio` flatpak).

Badges fill from the bottom-right corner of the first plate leftward along
-X, then up along +Y, and spill onto additional plates as needed. There is
no fixed cap on the badge count.

When every badge shares the same logo (always for `bulk`; for `named` only
when `NAME_TEXTS` resolves to a single unique entry) the project includes
the layer-height modifier so the logo prints at 0.16 mm layers. Mixed-text
named runs intentionally omit the modifier — priming behavior breaks for
varying logo sizes.

Default outputs:

- `make named` → `m5sticks3_click_case_named_badges.3mf` (intermediate)
  and `m5sticks3_click_case_named_badges.platecycler.3mf` (final).
- `make bulk` → `m5sticks3_click_case_orangecon_x80.3mf` (intermediate)
  and `m5sticks3_click_case_orangecon_x80.platecycler.3mf` (final).

Common examples:

```sh
make named NAME_TEXTS="ALICE,BOB,CAROL"
```

```sh
make named \
  VARIANT=color-logo-embossed \
  NAME_TEXTS="ALICE,BOB,CAROL,DAVE" \
  NAME_STEM=team_badges
```

```sh
make bulk BULK_COUNT=40 VARIANT=color-logo-flush-backed
```

Shared options (apply to both `make named` and `make bulk`, as well as the
single-badge 3MF targets):

- `VARIANT`: Case variant. Default: `with-logo`. (The single-badge targets
  `make with-logo` / `make no-logo` / `make color-logo-*` are hard-wired to
  their own variant and ignore `VARIANT`.)
- `GAP`: Spacing between badges in millimeters. Default: `2.5`.
- `X_OFFSET`: Non-negative inset from the right plate edge. Default: `10`.
- `Y_OFFSET`: Non-negative inset from the bottom plate edge. Default: `10`.
- `LOGO_TEXT`: Logo text used by `make bulk` and the single-badge targets.
  Default: `ORANGECON`. Also the default for `NAME_TEXTS`.

`make named`-only options:

- `NAME_TEXTS`: Comma-separated logo texts. Default: `$(LOGO_TEXT)`.
- `NAME_STEM`: Output filename stem. Default:
  `m5sticks3_click_case_named_badges`. Final output is
  `$(NAME_STEM).platecycler.3mf`.
- `NAME_BUILD_DIR`: Intermediate badge assets directory. Default:
  `build/named`.

`make bulk`-only options:

- `BULK_COUNT`: Total badge count. Default: `80`.
- `BULK_STEM`: Output filename stem. Default:
  `m5sticks3_click_case_orangecon_x$(BULK_COUNT)`. Final output is
  `$(BULK_STEM).platecycler.3mf`.
- `BULK_BUILD_DIR`: Intermediate badge assets directory. Default:
  `build/bulk`.

Supported `VARIANT` values:

- `with-logo`: Single-material case with embossed text.
- `no-logo`: Single-material case with no side logo.
- `color-logo-embossed`: Two-filament case with a raised logo insert.
- `color-logo-flush`: Two-filament case with a flush logo insert.
- `color-logo-flush-backed`: Two-filament flush logo with inner-wall backing.

Short logo texts are auto-sized with a height cap so one- or two-letter names
do not become oversized. Longer texts are width-limited to fit the side-logo
area.

### `make zip`

Builds `m5sticks3_click_case.zip` containing the standard STL and 3MF outputs.
Make will build any missing files needed for the zip.

### `make clean`

Removes generated STL, 3MF, SVG, zip, and badge work files.

## PlateCycler Post-Processing

`make named` and `make bulk` post-process the multi-plate 3MF using the standalone
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
