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
clearance_xy = 0.15;
clearance_z = 0.325;
wall = 1.40;
front_wall = 1.20;
join = 0.08;

// Top/bottom retention geometry.
corner_span = 6.0;

// Rear clips.
clip_depth = 1.2;
clip_span = 8.0;
clip_lip = 0.90;
clip_ramp = 0.75;
clip_y1 = 13.0;
clip_y2 = -13.0;
clip_y_center = 0.0;

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

// Connector openings.
top_open_w = 21.2;
connector_cover_mode = 3;  // 0 = no cover, 1 = cover above Grove only, 2 = cover above GPIO only, 3 = cover above GPIO and Grove
bottom_open_w = 14.0;
edge_open_h = wall;
edge_open_overcut = 0.30;
top_divider_from_device_front = 5.3;
gpio_row_start_from_device_front = 10.2;  // adjusted to fully clear the IR LED/receiver while still covering the GPIO header row
usb_c_bottom_from_front = 3.6;
grove_top_from_rear = 3.1;

// Taper for all openings to reduce unsupported edges.
front_window_taper = 3.00;
side_window_taper = 3.00;
edge_window_taper = 3.00;

inner_w = device_w + 2 * clearance_xy;
inner_h = device_h + 2 * clearance_xy;
inner_d = device_d + clearance_z;

outer_w = inner_w + 2 * wall;
outer_h = inner_h + 2 * wall;
outer_d = front_wall + inner_d;
outer_r = device_r + clearance_xy + wall;
inner_r = outer_r - wall;
cover_grove = connector_cover_mode == 1 || connector_cover_mode == 3;
cover_gpio = connector_cover_mode == 2 || connector_cover_mode == 3;
use_center_clips = connector_cover_mode == 3;
top_fill_from_front = front_wall + top_divider_from_device_front;
top_open_rear_z = cover_gpio ? front_wall + gpio_row_start_from_device_front : outer_d + 0.2;
bottom_fill_from_front = (front_wall + usb_c_bottom_from_front) / 2;

rear_z = outer_d;
inner_rear_z = front_wall + inner_d;
bottom_open_rear_z = cover_grove ? inner_rear_z - grove_top_from_rear : outer_d + 0.2;

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

module top_left_rail() {
    intersection() {
        shell_band();

        translate([-outer_w / 2 - 0.1, inner_h / 2 - 0.1, front_wall - join])
            cube([corner_span + 0.2, wall + 0.2, outer_d]);
    }
}

module top_right_rail() {
    intersection() {
        shell_band();

        translate([outer_w / 2 - corner_span - 0.1, inner_h / 2 - 0.1, front_wall - join])
            cube([corner_span + 0.2, wall + 0.2, outer_d]);
    }
}

module bottom_left_rail() {
    intersection() {
        shell_band();

        translate([-outer_w / 2 - 0.1, -outer_h / 2 - 0.1, front_wall - join])
            cube([corner_span + 0.2, wall + 0.2, outer_d]);
    }
}

module bottom_right_rail() {
    intersection() {
        shell_band();

        translate([outer_w / 2 - corner_span - 0.1, -outer_h / 2 - 0.1, front_wall - join])
            cube([corner_span + 0.2, wall + 0.2, outer_d]);
    }
}

module left_wall() {
    intersection() {
        shell_band();

        translate([-outer_w / 2 - 0.1, -outer_h / 2 - 0.1, front_wall - join])
            cube([wall + 0.2, outer_h + 0.2, outer_d]);
    }
}

module right_wall() {
    intersection() {
        shell_band();

        translate([outer_w / 2 - wall - 0.1, -outer_h / 2 - 0.1, front_wall - join])
            cube([wall + 0.2, outer_h + 0.2, outer_d]);
    }
}

module left_clip(y_pos) {
    hull() {
        translate([-inner_w / 2 - join, y_pos - clip_span / 2, inner_rear_z - clip_ramp])
            cube([clip_lip + join, clip_span, clip_ramp]);

        translate([-inner_w / 2 - join, y_pos - clip_span / 2, inner_rear_z - clip_depth])
            cube([clip_lip + join - clip_ramp, clip_span, clip_depth - clip_ramp]);
    }
}

module right_clip(y_pos) {
    hull() {
        translate([inner_w / 2 - clip_lip, y_pos - clip_span / 2, inner_rear_z - clip_ramp])
            cube([clip_lip + join, clip_span, clip_ramp]);

        translate([inner_w / 2 - clip_lip + clip_ramp, y_pos - clip_span / 2, inner_rear_z - clip_depth])
            cube([clip_lip + join - clip_ramp, clip_span, clip_depth - clip_ramp]);
    }
}

module body() {
    union() {
        front_plate();
        shell_band();
        if (use_center_clips) {
            left_clip(clip_y_center);
            right_clip(clip_y_center);
        } else {
            left_clip(clip_y1);
            left_clip(clip_y2);
            right_clip(clip_y1);
            right_clip(clip_y2);
        }
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

module tapered_cutout_y(x, y, z, w, h, d, taper) {
    hull() {
        // Keep the exterior flare constant even if the wall is thinner.
        translate([x - taper / 2, y, z - taper / 2])
            cube([w + taper, 0.01, d + taper]);

        translate([x, y + h - 0.01, z])
            cube([w, 0.01, d]);
    }
}

module cutouts() {
    // Front/build-plate access to the display area.
    tapered_cutout_z(
        -screen_w / 2,
        screen_y - screen_h / 2,
        -0.1,
        screen_w,
        screen_h,
        front_wall + 0.2,
        front_window_taper
    );

    // Front/build-plate access to the control button area.
    tapered_cutout_z(
        -control_w / 2,
        control_y - control_h / 2,
        -0.1,
        control_w,
        control_h,
        front_wall + 0.2,
        front_window_taper
    );

    // Left side access for the device's right-side center button.
    tapered_cutout_x(
        -outer_w / 2 - 0.1,
        left_btn_y - left_btn_h / 2,
        front_wall + left_btn_z0,
        wall + 0.3,
        left_btn_h,
        left_btn_d,
        side_window_taper
    );

    // Right side button access.
    mirror([1, 0, 0])
        tapered_cutout_x(
            -outer_w / 2 - 0.1,
            right_btn_y - right_btn_h / 2,
            front_wall + right_btn_z0,
            wall + 0.4,
            right_btn_h,
            right_btn_d,
            side_window_taper
        );

    // Open the top center. Optionally stop at the IR band so the GPIO row stays covered.
    translate(
        [
            -top_open_w / 2,
            outer_h / 2 - edge_open_h - edge_open_overcut / 2,
            top_fill_from_front
        ]
    )
        cube([top_open_w, edge_open_h + edge_open_overcut, top_open_rear_z - top_fill_from_front]);

    // Open the bottom center for the USB-C/Grove side.
    mirror([0, 1, 0])
        translate(
            [
                -bottom_open_w / 2,
                outer_h / 2 - edge_open_h - edge_open_overcut / 2,
                bottom_fill_from_front
            ]
        )
            cube([
                bottom_open_w,
                edge_open_h + edge_open_overcut,
                bottom_open_rear_z - bottom_fill_from_front
            ]);
}

difference() {
    body();
    cutouts();
}
