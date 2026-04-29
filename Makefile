SCAD := m5sticks3_click_case.scad
LOGO_SCRIPT := scripts/build_orangecon_logo_svg.py
THREEMF_SCRIPT := scripts/build_3mf.py
THREEMF_TEMPLATE := m5sticks3_click_case_template.3mf
THREEMF_COLOR_TEMPLATE := m5sticks3_click_case_color_template.3mf
LOGO_FONT := fonts/brave-hearted.ttf
LOGO_RAW_PNG := orangecon_logo_raw.png
LOGO_FILLED_PNG := orangecon_logo_filled.png
LOGO_PBM := orangecon_logo_filled.pbm
LOGO_SVG := orangecon_logo_filled.svg
STL_WITH_LOGO := m5sticks3_click_case_with_logo.stl
STL_NO_LOGO := m5sticks3_click_case_no_logo.stl
STL_COLOR_BODY_EMBOSSED := m5sticks3_click_case_color_body_embossed.stl
STL_COLOR_LOGO_EMBOSSED := m5sticks3_click_case_color_logo_insert_embossed.stl
STL_COLOR_BODY_FLUSH := m5sticks3_click_case_color_body_flush.stl
STL_COLOR_LOGO_FLUSH := m5sticks3_click_case_color_logo_insert_flush.stl
STLS := $(STL_WITH_LOGO) $(STL_NO_LOGO)
STLS_COLOR := $(STL_COLOR_BODY_EMBOSSED) $(STL_COLOR_LOGO_EMBOSSED) $(STL_COLOR_BODY_FLUSH) $(STL_COLOR_LOGO_FLUSH)
THREEMF_WITH_LOGO := m5sticks3_click_case_with_logo.3mf
THREEMF_NO_LOGO := m5sticks3_click_case_no_logo.3mf
THREEMF_COLOR_LOGO_EMBOSSED := m5sticks3_click_case_color_logo_embossed.3mf
THREEMF_COLOR_LOGO_FLUSH := m5sticks3_click_case_color_logo_flush.3mf
THREEMFS := $(THREEMF_WITH_LOGO) $(THREEMF_NO_LOGO) $(THREEMF_COLOR_LOGO_EMBOSSED) $(THREEMF_COLOR_LOGO_FLUSH)
ZIP := m5sticks3_click_case.zip

.PHONY: all with-logo no-logo color-logo color-logo-embossed color-logo-flush 3mf zip clean

all: $(STLS) $(THREEMFS) $(ZIP)

with-logo: $(STL_WITH_LOGO)

no-logo: $(STL_NO_LOGO)

color-logo: $(THREEMF_COLOR_LOGO_EMBOSSED) $(THREEMF_COLOR_LOGO_FLUSH)

color-logo-embossed: $(THREEMF_COLOR_LOGO_EMBOSSED)

color-logo-flush: $(THREEMF_COLOR_LOGO_FLUSH)

3mf: $(THREEMFS)

zip: $(ZIP)

$(STL_WITH_LOGO): $(SCAD) $(LOGO_SVG)
	openscad -o $@ $<

$(LOGO_SVG): $(LOGO_SCRIPT) $(LOGO_FONT)
	python3 $(LOGO_SCRIPT)

$(STL_NO_LOGO): $(SCAD)
	openscad -D 'show_right_logo=false' -o $@ $<

$(THREEMF_WITH_LOGO): $(STL_WITH_LOGO) $(THREEMF_TEMPLATE) $(THREEMF_SCRIPT)
	python3 $(THREEMF_SCRIPT) --template $(THREEMF_TEMPLATE) --stl $(STL_WITH_LOGO) --output $@

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

$(ZIP): $(STLS) $(THREEMFS)
	rm -f $@
	zip -j $@ $(STLS) $(THREEMFS)

clean:
	rm -f $(STLS) $(STLS_COLOR) $(THREEMFS) $(ZIP) $(LOGO_RAW_PNG) $(LOGO_FILLED_PNG) $(LOGO_PBM) $(LOGO_SVG)
