SCAD := m5sticks3_click_case_petg_pla.scad
BASE := m5sticks3_click_case_petg_pla
MODES := 0 1 2 3
MODE_STLS := $(foreach mode,$(MODES),$(BASE)_mode$(mode).stl)

.PHONY: all clean mode0 mode1 mode2 mode3

all: $(MODE_STLS)

mode0: $(BASE)_mode0.stl

mode1: $(BASE)_mode1.stl

mode2: $(BASE)_mode2.stl

mode3: $(BASE)_mode3.stl

$(BASE)_mode%.stl: $(SCAD)
	openscad -D 'connector_cover_mode=$*' -o $@ $<

clean:
	rm -f $(MODE_STLS)
