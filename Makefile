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
STL_COLOR_BODY := m5sticks3_click_case_color_body.stl
STL_COLOR_LOGO := m5sticks3_click_case_color_logo_insert.stl
STLS := $(STL_WITH_LOGO) $(STL_NO_LOGO)
STLS_COLOR := $(STL_COLOR_BODY) $(STL_COLOR_LOGO)
THREEMF_WITH_LOGO := m5sticks3_click_case_with_logo.3mf
THREEMF_NO_LOGO := m5sticks3_click_case_no_logo.3mf
THREEMF_COLOR_LOGO := m5sticks3_click_case_color_logo.3mf
THREEMFS := $(THREEMF_WITH_LOGO) $(THREEMF_NO_LOGO) $(THREEMF_COLOR_LOGO)
ZIP := m5sticks3_click_case.zip

.PHONY: all with-logo no-logo color-logo 3mf zip clean

all: $(STLS) $(THREEMFS) $(ZIP)

with-logo: $(STL_WITH_LOGO)

no-logo: $(STL_NO_LOGO)

color-logo: $(THREEMF_COLOR_LOGO)

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

$(STL_COLOR_BODY): $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="body"' -o $@ $<

$(STL_COLOR_LOGO): $(SCAD) $(LOGO_SVG)
	openscad -D 'output_part="logo"' -o $@ $<

$(THREEMF_COLOR_LOGO): $(STL_COLOR_BODY) $(STL_COLOR_LOGO) $(THREEMF_COLOR_TEMPLATE) $(THREEMF_SCRIPT)
	python3 $(THREEMF_SCRIPT) --template $(THREEMF_COLOR_TEMPLATE) --stl $(STL_COLOR_BODY) --stl $(STL_COLOR_LOGO) --output $@

$(ZIP): $(STLS) $(THREEMFS)
	rm -f $@
	zip -j $@ $(STLS) $(THREEMFS)

clean:
	rm -f $(STLS) $(STLS_COLOR) $(THREEMFS) $(ZIP) $(LOGO_RAW_PNG) $(LOGO_FILLED_PNG) $(LOGO_PBM) $(LOGO_SVG)
