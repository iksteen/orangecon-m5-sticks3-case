SCAD := m5sticks3_click_case.scad
LOGO_SCRIPT := scripts/build_orangecon_logo_svg.py
THREEMF_SCRIPT := scripts/build_3mf.py
BADGE_SCRIPT := scripts/build_badge_plate.py
THREEMF_TEMPLATE := m5sticks3_click_case_template.3mf
THREEMF_COLOR_TEMPLATE := m5sticks3_click_case_color_template.3mf
LOGO_INNER_WALL_BACKING := 0.45
BADGE_VARIANT ?= with-logo
BADGE_TEXTS ?= ORANGECON
BADGE_OUTPUT ?= m5sticks3_click_case_badge_plate.3mf
BADGE_BUILD_DIR ?= build/badge_plate
BADGE_X_OFFSET ?= 20
BADGE_Y_OFFSET ?= -20
LOGO_FONT := fonts/brave-hearted.ttf
LOGO_SVG := orangecon_logo_filled.svg
STL_WITH_LOGO := m5sticks3_click_case_with_logo.stl
STL_NO_LOGO := m5sticks3_click_case_no_logo.stl
STL_COLOR_BODY_EMBOSSED := m5sticks3_click_case_color_body_embossed.stl
STL_COLOR_LOGO_EMBOSSED := m5sticks3_click_case_color_logo_insert_embossed.stl
STL_COLOR_BODY_FLUSH := m5sticks3_click_case_color_body_flush.stl
STL_COLOR_LOGO_FLUSH := m5sticks3_click_case_color_logo_insert_flush.stl
STL_COLOR_BODY_FLUSH_BACKED := m5sticks3_click_case_color_body_flush_backed.stl
STL_COLOR_LOGO_FLUSH_BACKED := m5sticks3_click_case_color_logo_insert_flush_backed.stl
STLS := $(STL_WITH_LOGO) $(STL_NO_LOGO)
STLS_COLOR := $(STL_COLOR_BODY_EMBOSSED) $(STL_COLOR_LOGO_EMBOSSED) $(STL_COLOR_BODY_FLUSH) $(STL_COLOR_LOGO_FLUSH) $(STL_COLOR_BODY_FLUSH_BACKED) $(STL_COLOR_LOGO_FLUSH_BACKED)
THREEMF_WITH_LOGO := m5sticks3_click_case_with_logo.3mf
THREEMF_NO_LOGO := m5sticks3_click_case_no_logo.3mf
THREEMF_COLOR_LOGO_EMBOSSED := m5sticks3_click_case_color_logo_embossed.3mf
THREEMF_COLOR_LOGO_FLUSH := m5sticks3_click_case_color_logo_flush.3mf
THREEMF_COLOR_LOGO_FLUSH_BACKED := m5sticks3_click_case_color_logo_flush_backed.3mf
THREEMFS := $(THREEMF_WITH_LOGO) $(THREEMF_NO_LOGO) $(THREEMF_COLOR_LOGO_EMBOSSED) $(THREEMF_COLOR_LOGO_FLUSH) $(THREEMF_COLOR_LOGO_FLUSH_BACKED)
ZIP := m5sticks3_click_case.zip

.PHONY: all with-logo no-logo color-logo color-logo-embossed color-logo-flush color-logo-flush-backed badge-plate 3mf zip clean

all: $(STLS) $(THREEMFS) $(ZIP)

with-logo: $(STL_WITH_LOGO)

no-logo: $(STL_NO_LOGO)

color-logo: $(THREEMF_COLOR_LOGO_EMBOSSED) $(THREEMF_COLOR_LOGO_FLUSH) $(THREEMF_COLOR_LOGO_FLUSH_BACKED)

color-logo-embossed: $(THREEMF_COLOR_LOGO_EMBOSSED)

color-logo-flush: $(THREEMF_COLOR_LOGO_FLUSH)

color-logo-flush-backed: $(THREEMF_COLOR_LOGO_FLUSH_BACKED)

badge-plate: $(SCAD) $(LOGO_SCRIPT) $(THREEMF_SCRIPT) $(BADGE_SCRIPT) $(THREEMF_TEMPLATE) $(THREEMF_COLOR_TEMPLATE) $(LOGO_FONT)
	python3 $(BADGE_SCRIPT) --variant "$(BADGE_VARIANT)" --texts "$(BADGE_TEXTS)" --work-dir "$(BADGE_BUILD_DIR)" --output "$(BADGE_OUTPUT)" --x-offset "$(BADGE_X_OFFSET)" --y-offset "$(BADGE_Y_OFFSET)"

3mf: $(THREEMFS)

zip: $(ZIP)

$(STL_WITH_LOGO): $(SCAD) $(LOGO_SVG)
	openscad -o $@ $<

$(LOGO_SVG): $(LOGO_SCRIPT) $(LOGO_FONT)
	python3 $(LOGO_SCRIPT)

$(STL_NO_LOGO): $(SCAD)
	openscad -D 'show_right_logo=false' -o $@ $<

$(THREEMF_WITH_LOGO): $(STL_WITH_LOGO) $(STL_COLOR_LOGO_EMBOSSED) $(THREEMF_TEMPLATE) $(THREEMF_SCRIPT)
	python3 $(THREEMF_SCRIPT) --template $(THREEMF_TEMPLATE) --stl $(STL_WITH_LOGO) --logo-height-stl $(STL_COLOR_LOGO_EMBOSSED) --output $@

$(THREEMF_NO_LOGO): $(STL_NO_LOGO) $(THREEMF_TEMPLATE) $(THREEMF_SCRIPT)
	python3 $(THREEMF_SCRIPT) --template $(THREEMF_TEMPLATE) --stl $(STL_NO_LOGO) --output $@

$(STL_COLOR_BODY_EMBOSSED): $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="body"' -D 'color_logo_style="embossed"' -o $@ $<

$(STL_COLOR_LOGO_EMBOSSED): $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="logo"' -D 'color_logo_style="embossed"' -o $@ $<

$(THREEMF_COLOR_LOGO_EMBOSSED): $(STL_COLOR_BODY_EMBOSSED) $(STL_COLOR_LOGO_EMBOSSED) $(THREEMF_COLOR_TEMPLATE) $(THREEMF_SCRIPT)
	python3 $(THREEMF_SCRIPT) --template $(THREEMF_COLOR_TEMPLATE) --stl $(STL_COLOR_BODY_EMBOSSED) --stl $(STL_COLOR_LOGO_EMBOSSED) --output $@

$(STL_COLOR_BODY_FLUSH): $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="body"' -D 'color_logo_style="flush"' -o $@ $<

$(STL_COLOR_LOGO_FLUSH): $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="logo"' -D 'color_logo_style="flush"' -o $@ $<

$(THREEMF_COLOR_LOGO_FLUSH): $(STL_COLOR_BODY_FLUSH) $(STL_COLOR_LOGO_FLUSH) $(THREEMF_COLOR_TEMPLATE) $(THREEMF_SCRIPT)
	python3 $(THREEMF_SCRIPT) --template $(THREEMF_COLOR_TEMPLATE) --stl $(STL_COLOR_BODY_FLUSH) --stl $(STL_COLOR_LOGO_FLUSH) --output $@

$(STL_COLOR_BODY_FLUSH_BACKED): $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="body"' -D 'color_logo_style="flush"' -D 'color_logo_inner_wall_backing=$(LOGO_INNER_WALL_BACKING)' -o $@ $<

$(STL_COLOR_LOGO_FLUSH_BACKED): $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="logo"' -D 'color_logo_style="flush"' -D 'color_logo_inner_wall_backing=$(LOGO_INNER_WALL_BACKING)' -o $@ $<

$(THREEMF_COLOR_LOGO_FLUSH_BACKED): $(STL_COLOR_BODY_FLUSH_BACKED) $(STL_COLOR_LOGO_FLUSH_BACKED) $(THREEMF_COLOR_TEMPLATE) $(THREEMF_SCRIPT)
	python3 $(THREEMF_SCRIPT) --template $(THREEMF_COLOR_TEMPLATE) --stl $(STL_COLOR_BODY_FLUSH_BACKED) --stl $(STL_COLOR_LOGO_FLUSH_BACKED) --detect-thin-wall --output $@

$(ZIP): $(STLS) $(THREEMFS)
	rm -f $@
	zip -j $@ $(STLS) $(THREEMFS)

clean:
	rm -f $(STLS) $(STLS_COLOR) $(THREEMFS) $(ZIP) $(LOGO_SVG) $(BADGE_OUTPUT)
	rm -rf $(BADGE_BUILD_DIR)
