SCAD := m5sticks3_click_case.scad
LOGO_SCRIPT := scripts/build_logo_svg.py
THREEMF_SCRIPT := scripts/build_3mf.py
BADGE_SCRIPT := scripts/build_badge_plate.py
PLATECYCLER_BUILD_SCRIPT := scripts/build_platecycler_3mf.py
THREEMF_TEMPLATE := m5sticks3_click_case_template.3mf
THREEMF_COLOR_TEMPLATE := m5sticks3_click_case_color_template.3mf
LOGO_INNER_WALL_BACKING := 0.45
LOGO_TEXT ?= ORANGECON
BADGE_VARIANT ?= with-logo
BADGE_TEXTS ?= ORANGECON
BADGE_OUTPUT ?= m5sticks3_click_case_badge_plate.3mf
BADGE_BUILD_DIR ?= build/badge_plate
BADGE_X_OFFSET ?= 20
BADGE_Y_OFFSET ?= -20
BAMBU_RESULT_JSON ?= result.json
PLATECYCLER_BADGES ?= 80
PLATECYCLER_STEM ?= m5sticks3_click_case_orangecon_x$(PLATECYCLER_BADGES)
PLATECYCLER_PROJECT ?= $(PLATECYCLER_STEM).3mf
PLATECYCLER_OUTPUT ?= $(PLATECYCLER_STEM).platecycler.3mf
PLATECYCLER_GAP ?= 2.5
PLATECYCLER_X_OFFSET ?= 10
PLATECYCLER_Y_OFFSET ?= 10
LOGO_FONT := fonts/brave-hearted.ttf
# By default the logo SVG fills outline-style fonts (like Brave Hearted) so the
# wordmark prints as a solid silhouette. Override with `LOGO_OUTLINE_FLAG=` for
# fonts that are already filled and should not be re-filled.
LOGO_OUTLINE_FLAG ?= --outline
LOGO_SVG := orangecon_logo_filled.svg
STL_WITH_LOGO := m5sticks3_click_case_with_logo.stl
STL_NO_LOGO := m5sticks3_click_case_no_logo.stl

# Color-logo variants. The variant name appears verbatim in
# m5sticks3_click_case_color_body_<variant>.stl,
# m5sticks3_click_case_color_logo_insert_<variant>.stl, and
# m5sticks3_click_case_color_logo_<variant>.3mf.
COLOR_VARIANTS := embossed flush flush_backed
COLOR_STYLE_embossed := embossed
COLOR_STYLE_flush := flush
COLOR_STYLE_flush_backed := flush
COLOR_EXTRA_SCAD_DEFS_flush_backed := -D 'color_logo_inner_wall_backing=$(LOGO_INNER_WALL_BACKING)'
COLOR_EXTRA_3MF_ARGS_flush_backed := --detect-thin-wall

# The embossed logo insert is the canonical reference for the with-logo
# layer-height modifier bounds.
LOGO_HEIGHT_REF_STL := m5sticks3_click_case_color_logo_insert_embossed.stl

STLS := $(STL_WITH_LOGO) $(STL_NO_LOGO)
STLS_COLOR := $(foreach v,$(COLOR_VARIANTS),m5sticks3_click_case_color_body_$(v).stl m5sticks3_click_case_color_logo_insert_$(v).stl)
THREEMF_WITH_LOGO := m5sticks3_click_case_with_logo.3mf
THREEMF_NO_LOGO := m5sticks3_click_case_no_logo.3mf
THREEMFS_COLOR := $(patsubst %,m5sticks3_click_case_color_logo_%.3mf,$(COLOR_VARIANTS))
THREEMFS := $(THREEMF_WITH_LOGO) $(THREEMF_NO_LOGO) $(THREEMFS_COLOR)
ZIP := m5sticks3_click_case.zip

.PHONY: all with-logo no-logo color-logo color-logo-embossed color-logo-flush color-logo-flush-backed badge-plate platecycler platecycler-project 3mf zip clean

# Pattern-built color STLs would otherwise be deleted as intermediates after a
# downstream .3mf is built. Keep them so subsequent builds and clean can find
# them.
.SECONDARY: $(STLS_COLOR)

all: $(STLS) $(THREEMFS) $(ZIP)

with-logo: $(STL_WITH_LOGO)

no-logo: $(STL_NO_LOGO)

color-logo: $(THREEMFS_COLOR)

color-logo-embossed: m5sticks3_click_case_color_logo_embossed.3mf

color-logo-flush: m5sticks3_click_case_color_logo_flush.3mf

color-logo-flush-backed: m5sticks3_click_case_color_logo_flush_backed.3mf

badge-plate: $(SCAD) $(LOGO_SCRIPT) $(THREEMF_SCRIPT) $(BADGE_SCRIPT) $(THREEMF_TEMPLATE) $(THREEMF_COLOR_TEMPLATE) $(LOGO_FONT)
	uv run python $(BADGE_SCRIPT) --variant "$(BADGE_VARIANT)" --texts "$(BADGE_TEXTS)" --font "$(LOGO_FONT)" --work-dir "$(BADGE_BUILD_DIR)" --output "$(BADGE_OUTPUT)" --x-offset "$(BADGE_X_OFFSET)" --y-offset "$(BADGE_Y_OFFSET)" $(LOGO_OUTLINE_FLAG)

platecycler: $(PLATECYCLER_OUTPUT)

platecycler-project: $(PLATECYCLER_PROJECT)

3mf: $(THREEMFS)

zip: $(ZIP)

$(STL_WITH_LOGO): $(SCAD) $(LOGO_SVG)
	openscad -o $@ $<

$(LOGO_SVG): $(LOGO_SCRIPT) $(LOGO_FONT)
	uv run python $(LOGO_SCRIPT) --text "$(LOGO_TEXT)" --font "$(LOGO_FONT)" $(LOGO_OUTLINE_FLAG)

$(STL_NO_LOGO): $(SCAD)
	openscad -D 'show_right_logo=false' -o $@ $<

$(THREEMF_WITH_LOGO): $(STL_WITH_LOGO) $(LOGO_HEIGHT_REF_STL) $(THREEMF_TEMPLATE) $(THREEMF_SCRIPT)
	uv run python $(THREEMF_SCRIPT) --template $(THREEMF_TEMPLATE) --stl $(STL_WITH_LOGO) --logo-height-stl $(LOGO_HEIGHT_REF_STL) --output $@

$(THREEMF_NO_LOGO): $(STL_NO_LOGO) $(THREEMF_TEMPLATE) $(THREEMF_SCRIPT)
	uv run python $(THREEMF_SCRIPT) --template $(THREEMF_TEMPLATE) --stl $(STL_NO_LOGO) --output $@

m5sticks3_click_case_color_body_%.stl: $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="body"' -D 'color_logo_style="$(COLOR_STYLE_$*)"' $(COLOR_EXTRA_SCAD_DEFS_$*) -o $@ $<

m5sticks3_click_case_color_logo_insert_%.stl: $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="logo"' -D 'color_logo_style="$(COLOR_STYLE_$*)"' $(COLOR_EXTRA_SCAD_DEFS_$*) -o $@ $<

m5sticks3_click_case_color_logo_%.3mf: m5sticks3_click_case_color_body_%.stl m5sticks3_click_case_color_logo_insert_%.stl $(THREEMF_COLOR_TEMPLATE) $(THREEMF_SCRIPT)
	uv run python $(THREEMF_SCRIPT) --template $(THREEMF_COLOR_TEMPLATE) --stl $< --stl $(word 2,$^) $(COLOR_EXTRA_3MF_ARGS_$*) --output $@

$(PLATECYCLER_PROJECT): $(STL_WITH_LOGO) $(LOGO_HEIGHT_REF_STL) $(THREEMF_TEMPLATE) $(THREEMF_SCRIPT) $(PLATECYCLER_BUILD_SCRIPT)
	uv run python $(PLATECYCLER_BUILD_SCRIPT) --output "$@" --badges "$(PLATECYCLER_BADGES)" --gap "$(PLATECYCLER_GAP)" --x-offset "$(PLATECYCLER_X_OFFSET)" --y-offset "$(PLATECYCLER_Y_OFFSET)"

$(PLATECYCLER_OUTPUT): $(PLATECYCLER_PROJECT)
	uv run platecycler --force -o "$@" "$<"

$(ZIP): $(STLS) $(THREEMFS)
	rm -f $@
	zip -j $@ $(STLS) $(THREEMFS)

clean:
	rm -f $(STLS) $(STLS_COLOR) $(THREEMFS) $(ZIP) $(LOGO_SVG) $(BADGE_OUTPUT) $(PLATECYCLER_PROJECT) $(PLATECYCLER_OUTPUT) $(BAMBU_RESULT_JSON)
	rm -rf $(BADGE_BUILD_DIR)
