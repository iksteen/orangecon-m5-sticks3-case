SCAD := m5sticks3_click_case_petg_pla.scad
BRAVE_SCRIPT := scripts/build_brave_hearted_svg.py
BRAVE_FONT := fonts/brave-hearted.ttf
BRAVE_RAW_PNG := brave_hearted_raw.png
BRAVE_FILLED_PNG := brave_hearted_filled.png
BRAVE_PBM := brave_hearted_filled.pbm
BRAVE_SVG := brave_hearted_filled.svg
STL_WITH_LOGO := m5sticks3_click_case_petg_pla_with_logo.stl
STL_NO_LOGO := m5sticks3_click_case_petg_pla_no_logo.stl
STLS := $(STL_WITH_LOGO) $(STL_NO_LOGO)
STL_ZIP := m5sticks3_click_case_petg_pla_stls.zip

.PHONY: all with-logo no-logo zip clean

all: $(STLS) $(STL_ZIP)

with-logo: $(STL_WITH_LOGO)

no-logo: $(STL_NO_LOGO)

zip: $(STL_ZIP)

$(STL_WITH_LOGO): $(SCAD) $(BRAVE_SVG)
	openscad -o $@ $<

$(BRAVE_SVG): $(BRAVE_SCRIPT) $(BRAVE_FONT)
	python3 $(BRAVE_SCRIPT)

$(STL_NO_LOGO): $(SCAD)
	openscad -D 'show_right_logo=false' -o $@ $<

$(STL_ZIP): $(STLS)
	rm -f $@
	zip -j $@ $(STLS)

clean:
	rm -f $(STLS) $(STL_ZIP) $(BRAVE_RAW_PNG) $(BRAVE_FILLED_PNG) $(BRAVE_PBM) $(BRAVE_SVG)
