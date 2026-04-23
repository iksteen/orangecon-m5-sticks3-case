/*
Minimal snap case for M5StickS3, intended for PLA/PETG.

User-defined orientation:
- front  = screen side
- rear   = table side
- bottom = USB-C side
- top    = GPIO/Hat2 side
- left/right as viewed from the front

Insertion:
- device is inserted rear-first into the case from the front
- clips snap over the front face

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
device_d = 15.0;   // rear-front
device_r = 3.0;

// General fit for rigid plastics.
clearance_xy = 0.20;
clearance_z = 0.30;
wall = 1.40;
rear_wall = 1.20;
join = 0.08;

// Top/bottom retention geometry.
corner_span = 6.0;

// Front clips.
clip_depth = 1.2;
clip_span = 8.0;
clip_lip = 0.90;
clip_ramp = 0.75;
clip_y1 = 13.0;
clip_y2 = -13.0;

// Rear openings.
// Measured from the official front-view drawing in K150-sticks3.pdf,
// scaled against the dimensioned 24 x 48 mm body outline.
screen_w = 16.4;
screen_h = 26.4;
screen_y = 6.9;
control_w = 12.2;
control_h = 2.7;
control_y = -13.5;

// Side button windows, measured from the official side-view drawing.
// Device right maps to model left in this rear-plate/front-facing layout.
left_btn_h = 10.2;
left_btn_y = 0.0;
left_btn_z0 = 2.8;
left_btn_d = 8.2;
right_btn_h = 5.3;
right_btn_y = -15.4;
right_btn_z0 = 3.1;
right_btn_d = 8.2;

// Connector openings.
top_open_w = 14.0;
bottom_open_w = 14.0;
edge_open_h = wall;
edge_open_overcut = 0.30;

// Taper for all openings to reduce unsupported edges.
rear_window_taper = 3.00;
side_window_taper = 3.00;
edge_window_taper = 3.00;

inner_w = device_w + 2 * clearance_xy;
inner_h = device_h + 2 * clearance_xy;
inner_d = device_d + clearance_z;

outer_w = inner_w + 2 * wall;
outer_h = inner_h + 2 * wall;
outer_d = rear_wall + inner_d;
outer_r = device_r + clearance_xy + wall;
inner_r = outer_r - wall;

front_z = outer_d;
inner_front_z = rear_wall + inner_d;

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

module rear_plate() {
    rounded_prism(outer_w, outer_h, rear_wall, outer_r);
}

module shell_band() {
    difference() {
        rounded_prism(outer_w, outer_h, outer_d, outer_r);

        translate([0, 0, rear_wall])
            rounded_prism(inner_w, inner_h, outer_d - rear_wall + 0.2, inner_r);
    }
}

module top_left_rail() {
    intersection() {
        shell_band();

        translate([-outer_w / 2 - 0.1, inner_h / 2 - 0.1, rear_wall - join])
            cube([corner_span + 0.2, wall + 0.2, outer_d]);
    }
}

module top_right_rail() {
    intersection() {
        shell_band();

        translate([outer_w / 2 - corner_span - 0.1, inner_h / 2 - 0.1, rear_wall - join])
            cube([corner_span + 0.2, wall + 0.2, outer_d]);
    }
}

module bottom_left_rail() {
    intersection() {
        shell_band();

        translate([-outer_w / 2 - 0.1, -outer_h / 2 - 0.1, rear_wall - join])
            cube([corner_span + 0.2, wall + 0.2, outer_d]);
    }
}

module bottom_right_rail() {
    intersection() {
        shell_band();

        translate([outer_w / 2 - corner_span - 0.1, -outer_h / 2 - 0.1, rear_wall - join])
            cube([corner_span + 0.2, wall + 0.2, outer_d]);
    }
}

module left_wall() {
    intersection() {
        shell_band();

        translate([-outer_w / 2 - 0.1, -outer_h / 2 - 0.1, rear_wall - join])
            cube([wall + 0.2, outer_h + 0.2, outer_d]);
    }
}

module right_wall() {
    intersection() {
        shell_band();

        translate([outer_w / 2 - wall - 0.1, -outer_h / 2 - 0.1, rear_wall - join])
            cube([wall + 0.2, outer_h + 0.2, outer_d]);
    }
}

module left_clip(y_pos) {
    hull() {
        translate([-inner_w / 2 - join, y_pos - clip_span / 2, inner_front_z - clip_ramp])
            cube([clip_lip + join, clip_span, clip_ramp]);

        translate([-inner_w / 2 - join, y_pos - clip_span / 2, inner_front_z - clip_depth])
            cube([clip_lip + join - clip_ramp, clip_span, clip_depth - clip_ramp]);
    }
}

module right_clip(y_pos) {
    hull() {
        translate([inner_w / 2 - clip_lip, y_pos - clip_span / 2, inner_front_z - clip_ramp])
            cube([clip_lip + join, clip_span, clip_ramp]);

        translate([inner_w / 2 - clip_lip + clip_ramp, y_pos - clip_span / 2, inner_front_z - clip_depth])
            cube([clip_lip + join - clip_ramp, clip_span, clip_depth - clip_ramp]);
    }
}

module body() {
    union() {
        rear_plate();
        shell_band();
        left_clip(clip_y1);
        left_clip(clip_y2);
        right_clip(clip_y1);
        right_clip(clip_y2);
    }
}

module tapered_cutout_z(x, y, z, w, h, d, taper) {
    hull() {
        // Larger opening at the outer rear face, shrinking inward.
        translate([x - taper / 2, y - taper / 2, z])
            cube([w + taper, h + taper, 0.01]);

        translate([x, y, z + min(taper, d - 0.01)])
            cube([w, h, max(d - min(taper, d - 0.01), 0.01)]);
    }
}

module tapered_cutout_x(x, y, z, w, h, d, taper) {
    hull() {
        // Larger opening at the outside side wall, shrinking inward.
        translate([x, y - taper / 2, z - taper / 2])
            cube([0.01, h + taper, d + taper]);

        translate([x + min(taper, w - 0.01), y, z])
            cube([max(w - min(taper, w - 0.01), 0.01), h, d]);
    }
}

module tapered_cutout_y(x, y, z, w, h, d, taper) {
    hull() {
        // Larger opening at the outside top/bottom face, shrinking inward.
        translate([x - taper / 2, y, z - taper / 2])
            cube([w + taper, 0.01, d + taper]);

        translate([x, y + min(taper, h - 0.01), z])
            cube([w, max(h - min(taper, h - 0.01), 0.01), d]);
    }
}

module cutouts() {
    // Rear access to the front display area.
    tapered_cutout_z(
        -screen_w / 2,
        screen_y - screen_h / 2,
        -0.1,
        screen_w,
        screen_h,
        rear_wall + 0.2,
        rear_window_taper
    );

    // Rear access to the front control button area.
    tapered_cutout_z(
        -control_w / 2,
        control_y - control_h / 2,
        -0.1,
        control_w,
        control_h,
        rear_wall + 0.2,
        rear_window_taper
    );

    // Left side access for the device's right-side center button.
    tapered_cutout_x(
        -outer_w / 2 - 0.1,
        left_btn_y - left_btn_h / 2,
        rear_wall + left_btn_z0,
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
            rear_wall + right_btn_z0,
            wall + 0.4,
            right_btn_h,
            right_btn_d,
            side_window_taper
        );

    // Open the top center for the GPIO/Hat2 connector.
    translate(
        [-top_open_w / 2, outer_h / 2 - edge_open_h - edge_open_overcut / 2, rear_wall - 0.1]
    )
        cube([top_open_w, edge_open_h + edge_open_overcut, inner_d + 0.2]);

    // Open the bottom center for the USB-C side.
    mirror([0, 1, 0])
        translate(
            [-bottom_open_w / 2, outer_h / 2 - edge_open_h - edge_open_overcut / 2, rear_wall - 0.1]
        )
            cube([bottom_open_w, edge_open_h + edge_open_overcut, inner_d + 0.2]);
}

difference() {
    body();
    cutouts();
}
