SCAD := m5sticks3_click_case_petg_pla.scad
BRAVE_SCRIPT := scripts/build_brave_hearted_svg.py
THREEMF_SCRIPT := scripts/build_3mf.py
THREEMF_TEMPLATE := m5sticks3_click_case_petg_pla_template.3mf
BRAVE_FONT := fonts/brave-hearted.ttf
BRAVE_RAW_PNG := brave_hearted_raw.png
BRAVE_FILLED_PNG := brave_hearted_filled.png
BRAVE_PBM := brave_hearted_filled.pbm
BRAVE_SVG := brave_hearted_filled.svg
STL_WITH_LOGO := m5sticks3_click_case_petg_pla_with_logo.stl
STL_NO_LOGO := m5sticks3_click_case_petg_pla_no_logo.stl
STLS := $(STL_WITH_LOGO) $(STL_NO_LOGO)
THREEMF_WITH_LOGO := m5sticks3_click_case_petg_pla_with_logo.3mf
THREEMF_NO_LOGO := m5sticks3_click_case_petg_pla_no_logo.3mf
THREEMFS := $(THREEMF_WITH_LOGO) $(THREEMF_NO_LOGO)
ZIP := m5sticks3_click_case_petg_pla.zip

.PHONY: all with-logo no-logo 3mf zip clean

all: $(STLS) $(THREEMFS) $(ZIP)

with-logo: $(STL_WITH_LOGO)

no-logo: $(STL_NO_LOGO)

3mf: $(THREEMFS)

zip: $(ZIP)

$(STL_WITH_LOGO): $(SCAD) $(BRAVE_SVG)
	openscad -o $@ $<

$(BRAVE_SVG): $(BRAVE_SCRIPT) $(BRAVE_FONT)
	python3 $(BRAVE_SCRIPT)

$(STL_NO_LOGO): $(SCAD)
	openscad -D 'show_right_logo=false' -o $@ $<

$(THREEMF_WITH_LOGO): $(STL_WITH_LOGO) $(THREEMF_TEMPLATE) $(THREEMF_SCRIPT)
	python3 $(THREEMF_SCRIPT) --template $(THREEMF_TEMPLATE) --stl $(STL_WITH_LOGO) --output $@

$(THREEMF_NO_LOGO): $(STL_NO_LOGO) $(THREEMF_TEMPLATE) $(THREEMF_SCRIPT)
	python3 $(THREEMF_SCRIPT) --template $(THREEMF_TEMPLATE) --stl $(STL_NO_LOGO) --output $@

$(ZIP): $(STLS) $(THREEMFS)
	rm -f $@
	zip -j $@ $(STLS) $(THREEMFS)

clean:
	rm -f $(STLS) $(THREEMFS) $(ZIP) $(BRAVE_RAW_PNG) $(BRAVE_FILLED_PNG) $(BRAVE_PBM) $(BRAVE_SVG)
