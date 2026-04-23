SCAD := m5sticks3_click_case_petg_pla.scad
STL := m5sticks3_click_case_petg_pla.stl

.PHONY: all clean

all: $(STL)

$(STL): $(SCAD)
	openscad -o $@ $<

clean:
	rm -f $(STL)
