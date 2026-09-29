"""Generate a corner clamp with a stacked inner base plate (FreeCAD)."""

import sys

import corner_util as cu

OUTPUT = "Corner_Clamp_With_Base.FCStd"

_PARSER = cu.build_parser(
    "Generate corner clamp geometry with inner base plate (mm)."
)
_SCRIPT_TAG = "corner-clamp-base-gen"


def main(argv=None):
    """Build the corner clamp document and save OUTPUT."""
    script_argv = cu.script_argv(argv)
    try:
        cu.import_freecad()
    except ModuleNotFoundError:
        cu.run_under_freecad(__file__, script_argv)
    print("Starting...")
    args = cu.parse_args(_PARSER, script_argv)

    arm_length = args.arm_length
    height = args.height
    clearance = args.clearance
    wall_thickness = args.wall_thickness
    base_thickness = args.base_thickness
    magnet_diameter = args.magnet_diameter
    membrane_thickness = args.membrane_thickness
    rib_thickness = args.rib_thickness
    print(f"{height=}")
    print(f"{wall_thickness=}")
    print(f"{base_thickness=}")
    print(f"{clearance=}")
    base_arm_width = height - base_thickness
    inner_start_xy = wall_thickness + clearance
    inner_start_z = 2 * base_thickness + clearance
    inner_arm_length = arm_length - inner_start_xy
    # Bottom +Z lift is only in inner_base_floor (z_offset=clearance).
    inner_base_top_z = 2.0 * base_thickness + clearance
    inner_wall_z = 2.0 * base_thickness
    inner_height = height - inner_wall_z - clearance
    print(f"{inner_start_xy=}")
    print(f"{inner_wall_z=}")
    print(f"{inner_height=}")
    print(f"{inner_start_z=}")
    magnet_depth = wall_thickness - membrane_thickness
    magnet_pocket_start = wall_thickness - magnet_depth - membrane_thickness
    outer_corner_chamfer = wall_thickness
    inner_corner_chamfer = wall_thickness * arm_length / 100.0
    magnet_center = wall_thickness + (arm_length - wall_thickness) * 5 / 8
    inner_magnet_z = inner_start_z + inner_height / 2.0
    inner_far_x = inner_start_xy + wall_thickness
    inner_far_y = inner_start_xy + wall_thickness
    base_magnet_center = (inner_start_xy + arm_length) / 2.0
    base_magnet_depth = base_thickness - membrane_thickness

    print("Setting up doc...")
    doc = cu.App.newDocument("Corner_Clamp_With_Base")
    doc.Comment = cu.cli_comment(args, _PARSER, _SCRIPT_TAG)

    params = doc.addObject("App::FeaturePython", "Parameters")
    params.Label = "Design Parameters (mm)"
    cu.add_properties(
        params,
        arm_length,
        height,
        wall_thickness,
        base_thickness,
        clearance,
        magnet_diameter,
        magnet_depth,
        membrane_thickness,
        rib_thickness,
        outer_corner_chamfer,
    )
    params.addProperty(
        "App::PropertyString",
        "Instructions",
        "Magnets",
        "Magnet installation note",
    )
    params.Instructions = (
        "Press one 10 x 3 mm disc magnet into each straight pocket and "
        "one into the center base pocket on each piece (inner from +Z, "
        "outer from -Z). Check polarity before insertion. Each magnet is "
        f"covered by a {membrane_thickness:g} mm membrane."
    )

    # ----------------------------------------
    # OUTER PIECE
    # ----------------------------------------
    # L-shaped floor plus two perpendicular outside walls.
    outer_floor = cu.outer_base_floor(
        arm_length,
        base_arm_width,
        base_thickness,
        outer_corner_chamfer,
    )
    outer_x_wall = cu.Part.makeBox(wall_thickness, arm_length, height)
    outer_y_wall = cu.Part.makeBox(arm_length, wall_thickness, height)
    outer_shape = outer_floor.fuse(outer_x_wall).fuse(outer_y_wall)

    # Straight magnet pockets in each leg, inserted from outside.
    outer_x_magnet = cu.magnet_pocket(
        (magnet_pocket_start, magnet_center, inner_magnet_z),
        (1.0, 0.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    outer_y_magnet = cu.magnet_pocket(
        (magnet_center, magnet_pocket_start, inner_magnet_z),
        (0.0, 1.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    outer_base_magnet = cu.magnet_pocket(
        (base_magnet_center, base_magnet_center, 0.0),
        (0.0, 0.0, 1.0),
        magnet_diameter,
        base_magnet_depth,
        rib_thickness,
    )
    outer_shape = outer_shape.cut(
        outer_x_magnet.fuse(outer_y_magnet).fuse(outer_base_magnet)
    )

    outer = doc.addObject("PartDesign::Feature", "OuterPiece")
    outer.Label = "Outer Piece - L Base and Side Walls"
    outer.Shape = outer_shape.removeSplitter()
    outer.addProperty(
        "App::PropertyString",
        "PrintOrientation",
        "Manufacturing",
        "Suggested printing orientation",
    )
    outer.PrintOrientation = "Print flat on the L-shaped base."
    outer_color = (1.0, 0.72, 0.05)
    if outer.ViewObject:
        outer.ViewObject.Visibility = True
        outer.ViewObject.ShapeColor = outer_color

    print("Outer shape done")

    # ----------------------------------------
    # INNER PIECE
    # ----------------------------------------
    # Floor plate on the outer base, then upright L nested inside walls.
    inner_shape = cu.inner_base_floor(
        arm_length,
        base_arm_width,
        base_thickness,
        outer_corner_chamfer,
        inner_start_xy,
        clearance,
    )
    inner_x_leg = cu.Part.makeBox(
        wall_thickness,
        inner_arm_length,
        inner_height,
        cu.App.Vector(inner_start_xy, inner_start_xy, inner_start_z),
    )
    inner_y_leg = cu.Part.makeBox(
        inner_arm_length,
        wall_thickness,
        inner_height,
        cu.App.Vector(inner_start_xy, inner_start_xy, inner_start_z),
    )
    inner_shape = inner_shape.fuse(inner_x_leg)
    inner_shape = inner_shape.fuse(inner_y_leg)

    inner_chamfer_corner = cu.interior_chamfer_brace(
        inner_corner_chamfer,
        inner_height,
        inner_far_x,
        inner_far_y,
        inner_start_z,
        "z",
    )
    # X leg foot: long dimension along +Y; Y leg foot: long dimension
    # along +X. Each brace begins on the inner face of its respective leg.
    inner_chamfer_x_base = cu.interior_chamfer_brace(
        inner_corner_chamfer,
        inner_arm_length,
        inner_far_x,
        inner_start_xy,
        inner_start_z,
        "y",
    )
    inner_chamfer_y_base = cu.interior_chamfer_brace(
        inner_corner_chamfer,
        inner_arm_length,
        inner_start_xy,
        inner_far_y,
        inner_start_z,
        "x",
    )
    inner_shape = inner_shape.fuse(inner_chamfer_corner)
    inner_shape = inner_shape.fuse(inner_chamfer_x_base)
    inner_shape = inner_shape.fuse(inner_chamfer_y_base)

    inner_x_magnet = cu.magnet_pocket(
        (inner_far_x - magnet_pocket_start, magnet_center, inner_magnet_z),
        (-1.0, 0.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    inner_y_magnet = cu.magnet_pocket(
        (magnet_center, inner_far_y - magnet_pocket_start, inner_magnet_z),
        (0.0, -1.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    inner_base_magnet = cu.magnet_pocket(
        (base_magnet_center, base_magnet_center, inner_base_top_z),
        (0.0, 0.0, -1.0),
        magnet_diameter,
        base_magnet_depth,
        rib_thickness,
    )
    inner_shape = inner_shape.cut(inner_x_magnet)
    inner_shape = inner_shape.cut(inner_y_magnet)
    inner_shape = inner_shape.cut(inner_base_magnet)

    print("Inner shape done")

    inner = doc.addObject("PartDesign::Feature", "InnerPiece")
    inner.Label = "Inner Piece - L Corner with Base Plate"
    inner.Shape = inner_shape.removeSplitter()
    inner.addProperty(
        "App::PropertyString",
        "PrintOrientation",
        "Manufacturing",
        "Suggested printing orientation",
    )
    inner.PrintOrientation = (
        "Print with the inner base plate flat on the build plate."
    )
    inner_color = (1.0, 0.88, 0.10)
    if inner.ViewObject:
        inner.ViewObject.Visibility = True
        inner.ViewObject.ShapeColor = inner_color

    parts = doc.addObject("App::DocumentObjectGroup", "ClampParts")
    parts.Label = "Printable Parts"
    parts.addObject(outer)
    parts.addObject(inner)

    doc.recompute()
    gui_colors = {
        outer.Name: outer_color,
        inner.Name: inner_color,
    }
    output = cu.output_filename(
        OUTPUT, arm_length, height, magnet_diameter
    )
    cu.save_with_gui_view(doc, output, [outer, inner], gui_colors)
    print("Saved:", output)
    print("Outer volume (mm^3):", round(outer.Shape.Volume, 2))
    print("Inner volume (mm^3):", round(inner.Shape.Volume, 2))
    print("Outer valid:", outer.Shape.isValid())
    print("Inner valid:", inner.Shape.isValid())


_CLI_INVOKED = False


def cli():
    """Console entry point for the with-base generator script."""
    global _CLI_INVOKED
    if _CLI_INVOKED:
        return
    _CLI_INVOKED = True
    _cli_argv = cu.script_argv(sys.argv[1:])
    if "-h" in _cli_argv or "--help" in _cli_argv:
        _PARSER.parse_args(_cli_argv)
    else:
        main()


if cu.freecad_script_entry(__file__, __name__):
    cli()
