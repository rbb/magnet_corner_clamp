"""Generate a corner clamp FreeCAD model with configurable dimensions."""

import sys

import corner_util as cu

OUTPUT = "Corner_Clamp.FCStd"

_PARSER = cu.build_parser("Generate corner clamp geometry (mm).")
_SCRIPT_TAG = "corner-clamp-generator"


def main(argv=None):
    """Build the corner clamp document and save OUTPUT."""
    script_argv = cu.script_argv(argv)
    try:
        cu.import_freecad()
    except ModuleNotFoundError:
        cu.run_under_freecad(__file__, script_argv)
    args = cu.parse_args(_PARSER, script_argv)

    arm_length = args.arm_length
    height = args.height
    wall_thickness = args.wall_thickness
    base_thickness = args.base_thickness
    clearance = args.clearance
    magnet_diameter = args.magnet_diameter
    membrane_thickness = args.membrane_thickness
    rib_thickness = args.rib_thickness
    base_arm_width = height - base_thickness
    inner_start = wall_thickness + clearance
    inner_arm_length = arm_length - inner_start
    inner_z = base_thickness + clearance
    inner_height = height - inner_z - clearance
    magnet_depth = wall_thickness - membrane_thickness
    magnet_pocket_start = wall_thickness - magnet_depth - membrane_thickness
    outer_corner_chamfer = wall_thickness
    inner_corner_chamfer = wall_thickness * arm_length / 100.0
    magnet_center = wall_thickness + (arm_length - wall_thickness) * 5 / 8
    magnet_z = (height + base_thickness) / 2

    doc = cu.App.newDocument("Corner_Clamp")
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
        "Press one 10 x 3 mm disc magnet into each straight pocket. "
        "Check polarity before insertion. Each magnet is covered by a "
        f"{membrane_thickness:g} mm membrane."
    )

    # OUTER PIECE
    # L-shaped floor plus two perpendicular outside walls.
    outer_floor = cu.Part.makeBox(arm_length, arm_length, base_thickness)
    outer_floor = outer_floor.fuse(
        cu.Part.makeBox(base_arm_width, arm_length, base_thickness)
    )
    outer_floor = outer_floor.cut(
        cu.exterior_corner_chamfer_cut(
            outer_corner_chamfer, base_thickness, arm_length
        )
    )
    outer_x_wall = cu.Part.makeBox(wall_thickness, arm_length, height)
    outer_y_wall = cu.Part.makeBox(arm_length, wall_thickness, height)
    outer_shape = outer_floor.fuse(outer_x_wall).fuse(outer_y_wall)

    # Straight magnet pockets in each leg, inserted from outside.
    outer_x_magnet = cu.magnet_pocket(
        (magnet_pocket_start, magnet_center, magnet_z),
        (1.0, 0.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    outer_y_magnet = cu.magnet_pocket(
        (magnet_center, magnet_pocket_start, magnet_z),
        (0.0, 1.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    outer_shape = outer_shape.cut(outer_x_magnet.fuse(outer_y_magnet))

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

    # INNER PIECE
    # Upright L-shaped pusher, nested inside the outer walls.
    inner_x_leg = cu.Part.makeBox(
        wall_thickness,
        inner_arm_length,
        inner_height,
        cu.App.Vector(inner_start, inner_start, inner_z),
    )
    inner_y_leg = cu.Part.makeBox(
        inner_arm_length,
        wall_thickness,
        inner_height,
        cu.App.Vector(inner_start, inner_start, inner_z),
    )
    inner_shape = inner_x_leg.fuse(inner_y_leg)

    inner_far_x = inner_start + wall_thickness
    inner_far_y = inner_start + wall_thickness
    inner_shape = inner_shape.fuse(
        cu.interior_chamfer_brace(
            inner_corner_chamfer,
            inner_height,
            inner_far_x,
            inner_far_y,
            inner_z,
            "z",
        )
    )
    inner_magnet_z = inner_z + inner_height / 2.0

    inner_x_magnet = cu.magnet_pocket(
        (
            inner_far_x - magnet_pocket_start,
            magnet_center,
            inner_magnet_z,
        ),
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
    inner_shape = inner_shape.cut(inner_x_magnet.fuse(inner_y_magnet))

    inner = doc.addObject("PartDesign::Feature", "InnerPiece")
    inner.Label = "Inner Piece - Filled L Corner"
    inner.Shape = inner_shape.removeSplitter()
    inner.addProperty(
        "App::PropertyString",
        "PrintOrientation",
        "Manufacturing",
        "Suggested printing orientation",
    )
    inner.PrintOrientation = (
        "Print with the broad L-shaped end face on the build plate."
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
    """Console entry point (``uv run corner-clamp-generator``, etc.)."""
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
