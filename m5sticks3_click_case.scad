/*
Minimal snap case for M5StickS3, intended for PLA/PETG.

Orientation used in this file:
- front  = build-plate side of the case
- rear   = clip/open side of the case
- bottom = USB-C side
- top    = GPIO/Hat2 side
- left/right as viewed from the front/build-plate side

Insertion:
- device is inserted front-first into the case from the rear
- clips snap over the rear face

Official dimensions used from M5Stack docs / model-size PDF:
- 48.0 x 24.0 x 15.0 mm
- body corner radius R3

Notes:
- Only the overall envelope is official here.
- Button window positions are intentionally generous and should be tuned after first print.
*/

$fn = 64;

// Official overall envelope.
device_w = 24.0;   // left-right
device_h = 48.0;   // bottom-top
device_d = 15.0;   // front-rear
device_r = 3.0;

// General fit for rigid plastics.
clearance_xy = 0.25;
clearance_z = 0.425;
wall = 1.40;
front_wall = 1.20;
join = 0.08;

// Rear clips.
// One clip per side.
clip_depth = 1.2;
clip_span = 7.4;
clip_lip = 0.90;
clip_ramp = 0.75;
clip_y_left = 8.9;
clip_y_right = -8.9;

// Front/build-plate openings.
// Measured from the official front-view drawing in K150-sticks3.pdf,
// scaled against the dimensioned 24 x 48 mm body outline.
screen_w = 16.4;
screen_h = 26.4;
screen_y = 6.9;
control_w = 12.2;
control_h = 2.7;
control_y = -13.5;

// Side button windows, measured from the official side-view drawing.
// Device right maps to model left in this front-plate/front-facing layout.
left_btn_h = 10.2;
left_btn_y = 0.0;
left_btn_z0 = 2.8;
left_btn_d = 8.2;
right_btn_h = 5.3;
right_btn_y = -15.4;
right_btn_z0 = 3.1;
right_btn_d = 8.2;
left_btn_cut_w = wall + 0.3;
right_btn_cut_w = wall + 0.4;

// Microphone port window on the device-right/model-left side.
// Center measured from model_size_marked.png: 7.1 mm above the bottom edge,
// 5.2 mm from the build-plate side in the side view.
mic_h = 1.1;
mic_y = -17.0;
mic_z0 = 2.5;
mic_d = 3.0;
mic_cut_w = wall + 0.3;
mic_r = 0.35;

// Connector openings.
top_open_w = 21.2;
bottom_open_w = 14.0;
edge_open_h = wall;
edge_open_overcut = 0.30;
top_divider_from_device_front = 5.3;
gpio_row_start_from_device_front = 10.2;  // adjusted to fully clear the IR LED/receiver while still covering the GPIO header row
usb_c_bottom_from_front = 3.6;
grove_top_from_rear = 3.1;
top_gpio_cap_h = 9.6;
top_gpio_cap_w = 3 * top_open_w / 4;
top_gpio_cap_round_r = 0.8;
top_gpio_hole_margin_x = 1.2;
top_gpio_hole_margin_y = 3 * top_gpio_hole_margin_x / 2;

// Model-right engraving.
show_right_logo = true;

// Output selector for color builds: "full", "body", or "logo"
output_part = "full";

// Color logo style for split two-filament builds: "embossed" or "flush".
color_logo_style = "embossed";

// Model-right embossed text, generated from brave-hearted.ttf by
// scripts/build_orangecon_logo_svg.py and imported as a filled SVG.
right_logo_src_x0 = 0.666667;
right_logo_src_y0 = 0.0323331;
right_logo_text_w = 856.667;
right_logo_text_h = 97.9677;
right_logo_margin_y = 2.5;
right_logo_depth = 0.8;  // embossed height from the wall

// Taper for all openings to reduce unsupported edges.
front_window_taper = 3.00;
side_window_taper = 3.00;

// Derived dimensions.
inner_w = device_w + 2 * clearance_xy;
inner_h = device_h + 2 * clearance_xy;
inner_d = device_d + clearance_z;

outer_w = inner_w + 2 * wall;
outer_h = inner_h + 2 * wall;
outer_d = front_wall + inner_d;
outer_r = device_r + clearance_xy + wall;
inner_r = outer_r - wall;
right_btn_top_y = right_btn_y + right_btn_h / 2;
right_logo_x = outer_w / 2 - join;
side_logo_top_curve_start_y = outer_h / 2 - outer_r;
right_logo_y1 = side_logo_top_curve_start_y;
right_logo_available_y = right_logo_y1 - (right_btn_top_y + right_logo_margin_y);
right_logo_scale = min(right_logo_available_y / right_logo_text_w, outer_d / right_logo_text_h);
right_logo_draw_w = right_logo_text_w * right_logo_scale;
right_logo_draw_h = right_logo_text_h * right_logo_scale;
right_logo_y0 = right_logo_y1 - right_logo_draw_w;
right_logo_z0 = (outer_d - right_logo_draw_h) / 2;
top_fill_from_front = front_wall + top_divider_from_device_front;
top_open_rear_z = front_wall + gpio_row_start_from_device_front;
top_open_d = top_open_rear_z - top_fill_from_front;
bottom_fill_from_front = (front_wall + usb_c_bottom_from_front) / 2;

rear_z = outer_d;
inner_rear_z = front_wall + inner_d;
bottom_open_rear_z = inner_rear_z - grove_top_from_rear;
bottom_open_d = bottom_open_rear_z - bottom_fill_from_front;

function top_gpio_cap_depth() = 3 * (rear_z - top_open_rear_z) / 8;
function top_gpio_ramp_depth() = rear_z - top_gpio_cap_depth() - top_open_rear_z;
function top_gpio_total_depth() = rear_z - top_open_rear_z;
function top_edge_open_y0() = outer_h / 2 - edge_open_h - edge_open_overcut / 2;
function top_gpio_cap_y0() = outer_h / 2 - join;
function top_gpio_cap_z0() = rear_z - top_gpio_cap_depth();
function color_logo_insert_depth() =
    wall + (color_logo_style == "flush" ? 0 : right_logo_depth);

module rounded_rect_2d(w, h, r) {
    hull() {
        for (x = [-1, 1], y = [-1, 1]) {
            translate([x * (w / 2 - r), y * (h / 2 - r)])
                circle(r = r);
        }
    }
}

module rounded_prism(w, h, d, r) {
    linear_extrude(height = d)
        rounded_rect_2d(w, h, r);
}

module front_plate() {
    rounded_prism(outer_w, outer_h, front_wall, outer_r);
}

module shell_band() {
    difference() {
        rounded_prism(outer_w, outer_h, outer_d, outer_r);

        translate([0, 0, front_wall])
            rounded_prism(inner_w, inner_h, outer_d - front_wall + 0.2, inner_r);
    }
}

module clip_at_left(y_pos) {
    hull() {
        translate([-inner_w / 2 - join, y_pos - clip_span / 2, inner_rear_z - clip_ramp])
            cube([clip_lip + join, clip_span, clip_ramp]);

        translate([-inner_w / 2 - join, y_pos - clip_span / 2, inner_rear_z - clip_depth])
            cube([clip_lip + join - clip_ramp, clip_span, clip_depth - clip_ramp]);
    }
}

module clip_pair(y_pos) {
    clip_at_left(y_pos);
    mirror([1, 0, 0])
        clip_at_left(y_pos);
}

module top_gpio_cap_footprint_2d() {
    w = top_gpio_cap_w;
    h = top_gpio_cap_h;
    r = min(top_gpio_cap_round_r, w / 2 - 0.01, h - 0.01);

    union() {
        translate([-w / 2, 0])
            square([w, h - r]);

        hull() {
            translate([-w / 2 + r, h - r])
                circle(r = r);

            translate([w / 2 - r, h - r])
                circle(r = r);
        }
    }
}

module top_gpio_cap_raw() {
    cap_d = top_gpio_cap_depth();
    ramp_d = top_gpio_ramp_depth();

    union() {
        translate([0, top_gpio_cap_y0(), top_gpio_cap_z0()])
            rotate([0, 90, 0])
                linear_extrude(height = top_gpio_cap_w, center = true)
                    polygon(
                        [
                            [0, 0],
                            [0, top_gpio_cap_h],
                            [ramp_d, 0]
                        ]
                    );

        translate(
            [
                -top_gpio_cap_w / 2,
                top_gpio_cap_y0(),
                top_gpio_cap_z0()
            ]
        )
            cube([
                top_gpio_cap_w,
                top_gpio_cap_h,
                cap_d
            ]);
    }
}

module top_gpio_cap() {
    combo_z0 = top_open_rear_z;
    combo_h = top_gpio_total_depth();
    combo_y_center = top_gpio_cap_y0() + top_gpio_cap_h / 2;
    combo_hole_h = top_gpio_cap_h / 2 - top_gpio_hole_margin_y;

    difference() {
        intersection() {
            top_gpio_cap_raw();

            translate([0, top_gpio_cap_y0(), -1])
                linear_extrude(height = outer_d + 2)
                    top_gpio_cap_footprint_2d();
        }

        translate([0, combo_y_center, combo_z0 - 1])
            scale(
                [
                    top_gpio_cap_w / 2 - top_gpio_hole_margin_x,
                    combo_hole_h,
                    1
                ]
            )
                cylinder(h = combo_h + 2, r = 1);
    }
}

module logo_footprint_2d() {
    translate([right_logo_draw_w, right_logo_draw_h])
        rotate(180)
            resize([right_logo_draw_w, 0], auto = true)
                translate([-right_logo_src_x0, -right_logo_src_y0])
                    import("orangecon_logo_filled.svg");
}

module right_side_logo_embossed() {
    // Local axes:
    // - text X runs along model Y
    // - text Y runs along model Z
    // - extrusion runs outward along model X, starting slightly inside the wall so it unions cleanly
    multmatrix([
        [0, 0, 1, right_logo_x],
        [1, 0, 0, right_logo_y0],
        [0, 1, 0, right_logo_z0],
        [0, 0, 0, 1]
    ])
        linear_extrude(height = right_logo_depth + join)
            logo_footprint_2d();
}

module right_side_logo_insert(extra_start = 0, extra_end = 0) {
    // Extends from inner wall surface to either the outer wall surface
    // ("flush") or the outer face of the embossed logo ("embossed").
    // Inner wall is at x = outer_w/2 - wall
    // Outer wall is at x = outer_w/2
    // Embossed outer face is at x = outer_w/2 + right_logo_depth
    insert_depth = color_logo_insert_depth() + extra_start + extra_end;
    multmatrix([
        [0, 0, 1, outer_w / 2 - wall - extra_start],
        [1, 0, 0, right_logo_y0],
        [0, 1, 0, right_logo_z0],
        [0, 0, 0, 1]
    ])
        linear_extrude(height = insert_depth)
            logo_footprint_2d();
}

module body() {
    union() {
        front_plate();
        shell_band();
        top_gpio_cap();
        clip_pair(clip_y_left);
        clip_pair(clip_y_right);
        if (show_right_logo && output_part == "full")
            right_side_logo_embossed();
    }
}

module tapered_cutout_z(x, y, z, w, h, d, taper) {
    hull() {
        // Keep the exterior flare constant even if the wall is thinner.
        translate([x - taper / 2, y - taper / 2, z])
            cube([w + taper, h + taper, 0.01]);

        translate([x, y, z + d - 0.01])
            cube([w, h, 0.01]);
    }
}

module tapered_cutout_x(x, y, z, w, h, d, taper) {
    hull() {
        // Keep the exterior flare constant even if the wall is thinner.
        translate([x, y - taper / 2, z - taper / 2])
            cube([0.01, h + taper, d + taper]);

        translate([x + w - 0.01, y, z])
            cube([0.01, h, d]);
    }
}

module front_access_window(w, h, y_center) {
    tapered_cutout_z(
        -w / 2,
        y_center - h / 2,
        -0.1,
        w,
        h,
        front_wall + 0.2,
        front_window_taper
    );
}

module side_button_window(y_center, z0, d, h, cut_w) {
    tapered_cutout_x(
        -outer_w / 2 - 0.1,
        y_center - h / 2,
        front_wall + z0,
        cut_w,
        h,
        d,
        side_window_taper
    );
}

module mic_window() {
    translate([-outer_w / 2 - 0.1, mic_y, front_wall + mic_z0 + mic_d / 2])
        rotate([0, 90, 0])
            linear_extrude(height = mic_cut_w)
                rounded_rect_2d(mic_d, mic_h, mic_r);
}

module top_open_window(x0, w) {
    translate(
        [
            x0,
            top_edge_open_y0(),
            top_fill_from_front
        ]
    )
        cube([w, edge_open_h + edge_open_overcut, top_open_d]);
}

module bottom_open_window() {
    mirror([0, 1, 0])
        translate(
            [
                -bottom_open_w / 2,
                top_edge_open_y0(),
                bottom_fill_from_front
            ]
        )
            cube([
                bottom_open_w,
                edge_open_h + edge_open_overcut,
                bottom_open_d
            ]);
}

module cutouts() {
    // Front/build-plate access to the display area.
    front_access_window(screen_w, screen_h, screen_y);

    // Front/build-plate access to the control button area.
    front_access_window(control_w, control_h, control_y);

    // Left side access for the device's right-side center button.
    side_button_window(left_btn_y, left_btn_z0, left_btn_d, left_btn_h, left_btn_cut_w);

    // Left side access for the microphone port.
    mic_window();

    // Right side button access.
    mirror([1, 0, 0])
        side_button_window(right_btn_y, right_btn_z0, right_btn_d, right_btn_h, right_btn_cut_w);

    // Keep one continuous top opening.
    top_open_window(-top_open_w / 2, top_open_w);

    // Open the bottom center for the USB-C/Grove side.
    bottom_open_window();

}

if (output_part == "logo") {
    right_side_logo_insert();
} else if (output_part == "body") {
    difference() {
        difference() {
            body();
            cutouts();
        }
        // Overcut only through the wall thickness. The logo footprint stays
        // identical to the insert so there is no visible perimeter gap.
        right_side_logo_insert(extra_start = 0.1, extra_end = 0.1);
    }
} else {
    difference() {
        body();
        cutouts();
    }
}
