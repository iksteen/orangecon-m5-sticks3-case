# ============================================================================
# User-configurable options
# ============================================================================
# Override these on the command line (e.g. `make all LOGO_TEXT=FOO`) or in the
# environment. All defaults are safe to change.

# Path to the font file passed to the logo script. The default is the
# licensed Brave Hearted font expected at fonts/brave-hearted.ttf -- see
# README for source and licensing.
LOGO_FONT ?= fonts/brave-hearted.ttf

# Flag forwarded to the logo script. Default `--outline` treats the font as
# outline-style and fills the silhouettes before generating the SVG. Set to
# empty (`LOGO_OUTLINE_FLAG=`) when using a font that is already filled and
# should not be re-filled.
LOGO_OUTLINE_FLAG ?= --outline

# Default single logo text. Used by the no-logo / with-logo / color-logo-*
# single-badge targets, by `make bulk`, and as the default for NAME_TEXTS.
LOGO_TEXT ?= ORANGECON

# Thickness in millimeters of body material kept behind the flush logo
# insert on the inner wall. Used only by the color-logo-flush-backed
# variant. Default 0.45 mm matches the `inner_wall_line_width` configured in
# the color 3MF template, so the backing prints as a single inner wall line.
LOGO_INNER_WALL_BACKING ?= 0.45

# Shared plate-layout options applied to every target that goes through
# scripts/build_3mf.py (no-logo, with-logo, color-logo-*, named, bulk).
# Offsets are non-negative edge insets from the bottom-right of each plate.
VARIANT ?= with-logo
GAP ?= 2.5
X_OFFSET ?= 10
Y_OFFSET ?= 10

# `make named` options: each badge gets its own logo text from NAME_TEXTS.
NAME_TEXTS ?= $(LOGO_TEXT)
NAME_STEM ?= m5sticks3_click_case_named_badges
NAME_BUILD_DIR ?= build/named

# `make bulk` options: BULK_COUNT identical copies of LOGO_TEXT.
BULK_COUNT ?= 80
BULK_STEM ?= m5sticks3_click_case_orangecon_x$(BULK_COUNT)
BULK_BUILD_DIR ?= build/bulk

# ============================================================================
# Internal: script paths, templates, derived names, intermediate file lists
# ============================================================================

SCAD := m5sticks3_click_case.scad
LOGO_SCRIPT := scripts/build_logo_svg.py
PLATE_SCRIPT := scripts/build_3mf.py
THREEMF_TEMPLATE := m5sticks3_click_case_template.3mf
THREEMF_COLOR_TEMPLATE := m5sticks3_click_case_color_template.3mf

# Bambu Studio CLI side effect: platecycler drives it during slicing and it
# drops a result.json next to the project. The clean rule removes it.
BAMBU_RESULT_JSON ?= result.json

# Derived from NAME_STEM / BULK_STEM; override directly only if you want
# non-standard filenames for the intermediate project / platecycler output.
NAME_PROJECT ?= $(NAME_STEM).3mf
NAME_OUTPUT ?= $(NAME_STEM).platecycler.3mf
BULK_PROJECT ?= $(BULK_STEM).3mf
BULK_OUTPUT ?= $(BULK_STEM).platecycler.3mf

STL_NO_LOGO := m5sticks3_click_case_no_logo.stl
STL_WITH_LOGO := m5sticks3_click_case_with_logo.stl

# Single-badge color-logo variants. The variant name appears verbatim in
# m5sticks3_click_case_color_logo_<variant>.3mf and in the build work-dir
# name. Underscores are converted to hyphens to form the script's --variant
# argument (color-logo-<variant>).
COLOR_VARIANTS := embossed flush flush_backed
COLOR_EXTRA_ARGS_flush_backed := --inner-wall-backing $(LOGO_INNER_WALL_BACKING)

STLS := $(STL_NO_LOGO) $(STL_WITH_LOGO)
THREEMF_NO_LOGO := m5sticks3_click_case_no_logo.3mf
THREEMF_WITH_LOGO := m5sticks3_click_case_with_logo.3mf
THREEMFS_COLOR := $(patsubst %,m5sticks3_click_case_color_logo_%.3mf,$(COLOR_VARIANTS))
THREEMFS := $(THREEMF_NO_LOGO) $(THREEMF_WITH_LOGO) $(THREEMFS_COLOR)
ZIP := m5sticks3_click_case.zip

# Work-dirs the unified script populates for each single-badge target.
SINGLE_BUILD_DIRS := build/no_logo build/with_logo $(foreach v,$(COLOR_VARIANTS),build/color_logo_$(v))

# Args shared by every invocation of $(PLATE_SCRIPT).
PLATE_ARGS = --font "$(LOGO_FONT)" --gap "$(GAP)" --x-offset "$(X_OFFSET)" --y-offset "$(Y_OFFSET)" $(LOGO_OUTLINE_FLAG)

# ============================================================================
# Targets
# ============================================================================

.PHONY: all no-logo with-logo color-logo color-logo-embossed color-logo-flush color-logo-flush-backed named bulk 3mf zip clean

all: $(STLS) $(THREEMFS) $(ZIP)

no-logo: $(STL_NO_LOGO)

with-logo: $(STL_WITH_LOGO)

color-logo: $(THREEMFS_COLOR)

color-logo-embossed: m5sticks3_click_case_color_logo_embossed.3mf

color-logo-flush: m5sticks3_click_case_color_logo_flush.3mf

color-logo-flush-backed: m5sticks3_click_case_color_logo_flush_backed.3mf

named: $(NAME_OUTPUT)

bulk: $(BULK_OUTPUT)

3mf: $(THREEMFS)

zip: $(ZIP)

# Single-badge 3MFs go through the unified plate script with --badges 1. The
# no-logo and with-logo runs also pull out the rendered STL to its canonical
# filename via --stl-output, so non-Bambu slicers can use it directly. The
# grouped target (`&:`, GNU Make 4.3+) declares that one recipe execution
# produces both files.
$(STL_NO_LOGO) $(THREEMF_NO_LOGO) &: $(SCAD) $(PLATE_SCRIPT) $(THREEMF_TEMPLATE) $(LOGO_FONT)
	uv run python $(PLATE_SCRIPT) --variant no-logo --text "$(LOGO_TEXT)" --badges 1 --work-dir build/no_logo --output $(THREEMF_NO_LOGO) --stl-output full:$(STL_NO_LOGO) $(PLATE_ARGS)

$(STL_WITH_LOGO) $(THREEMF_WITH_LOGO) &: $(SCAD) $(LOGO_SCRIPT) $(PLATE_SCRIPT) $(THREEMF_TEMPLATE) $(LOGO_FONT)
	uv run python $(PLATE_SCRIPT) --variant with-logo --text "$(LOGO_TEXT)" --badges 1 --work-dir build/with_logo --output $(THREEMF_WITH_LOGO) --stl-output full:$(STL_WITH_LOGO) $(PLATE_ARGS)

m5sticks3_click_case_color_logo_%.3mf: $(SCAD) $(LOGO_SCRIPT) $(PLATE_SCRIPT) $(THREEMF_COLOR_TEMPLATE) $(LOGO_FONT)
	uv run python $(PLATE_SCRIPT) --variant "color-logo-$(subst _,-,$*)" --text "$(LOGO_TEXT)" --badges 1 --work-dir "build/color_logo_$*" --output "$@" $(COLOR_EXTRA_ARGS_$*) $(PLATE_ARGS)

# Named/bulk plate projects.
$(NAME_PROJECT): $(SCAD) $(LOGO_SCRIPT) $(PLATE_SCRIPT) $(THREEMF_TEMPLATE) $(THREEMF_COLOR_TEMPLATE) $(LOGO_FONT)
	uv run python $(PLATE_SCRIPT) --variant "$(VARIANT)" --texts "$(NAME_TEXTS)" --work-dir "$(NAME_BUILD_DIR)" --output "$@" $(PLATE_ARGS)

$(BULK_PROJECT): $(SCAD) $(LOGO_SCRIPT) $(PLATE_SCRIPT) $(THREEMF_TEMPLATE) $(THREEMF_COLOR_TEMPLATE) $(LOGO_FONT)
	uv run python $(PLATE_SCRIPT) --variant "$(VARIANT)" --text "$(LOGO_TEXT)" --badges "$(BULK_COUNT)" --work-dir "$(BULK_BUILD_DIR)" --output "$@" $(PLATE_ARGS)

# Generic: any .3mf can be piped through the platecycler tool to produce a
# matching .platecycler.3mf. `make named` and `make bulk` chain through here
# automatically; users can also run it on arbitrary plate 3MFs.
%.platecycler.3mf: %.3mf
	uv run platecycler --force -o "$@" "$<"

$(ZIP): $(STLS) $(THREEMFS)
	rm -f $@
	zip -j $@ $(STLS) $(THREEMFS)

clean:
	rm -f $(STLS) $(THREEMFS) $(ZIP) $(NAME_PROJECT) $(NAME_OUTPUT) $(BULK_PROJECT) $(BULK_OUTPUT) $(BAMBU_RESULT_JSON)
	rm -rf $(NAME_BUILD_DIR) $(BULK_BUILD_DIR) $(SINGLE_BUILD_DIRS)
