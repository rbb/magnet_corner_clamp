"""Generate a corner clamp with a stacked inner base plate (FreeCAD)."""

import argparse
import math
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

OUTPUT = "Corner_Clamp_With_Base.FCStd"

App = None
Part = None
OfflineRenderingUtils = None
coin = None


def _import_freecad():
    """Load FreeCAD bindings (not available in a normal system Python)."""
    global App, Part, OfflineRenderingUtils, coin
    if App is not None:
        return
    import FreeCAD as App
    import OfflineRenderingUtils
    import Part
    from pivy import coin


def _find_freecad_cmd():
    """Return a FreeCAD headless launcher on PATH, if any."""
    for name in ("freecad.cmd", "FreeCADCmd", "freecadcmd"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _run_under_freecad(script_argv):
    """Re-run this script under FreeCAD's Python (e.g. from a venv CLI)."""
    freecad = _find_freecad_cmd()
    if freecad is None:
        print(
            "FreeCAD is not available in this Python environment and "
            "freecad.cmd was not found on PATH.",
            file=sys.stderr,
        )
        print(
            "Install FreeCAD or run: freecad.cmd "
            f"{os.path.abspath(__file__)} ...",
            file=sys.stderr,
        )
        sys.exit(1)
    script_path = os.path.abspath(__file__)
    cmd = [freecad, script_path]
    if script_argv:
        cmd.extend(["--pass", shlex.join(script_argv)])
    completed = subprocess.run(cmd, check=False)
    sys.exit(completed.returncode)


def _freecad_running_this_file():
    """True when FreeCADCmd is executing this file (not a plain import)."""
    this_path = os.path.abspath(__file__)
    this_name = os.path.basename(this_path)
    for arg in sys.argv[1:]:
        if arg in ("--pass",):
            continue
        if os.path.abspath(arg) == this_path:
            return True
        if os.path.basename(arg) == this_name:
            return True
    return False


def _freecad_script_entry():
    """True when this file is the FreeCADCmd script target.

    FreeCADCmd sets ``__name__`` to the script stem (not ``__main__``).
    """
    if __name__ == "__main__":
        return True
    if not _freecad_running_this_file():
        return False
    stem = os.path.splitext(os.path.basename(__file__))[0]
    return __name__ == stem


def _script_argv(argv):
    """Expand FreeCADCmd ``--pass`` (one token) into normal argparse argv."""
    if argv is None:
        argv = sys.argv[1:]
    out = []
    idx = 0
    while idx < len(argv):
        token = argv[idx]
        if token == "--pass":
            idx += 1
            if idx >= len(argv):
                break
            bundled = argv[idx]
            idx += 1
            if " " in bundled.strip():
                out.extend(shlex.split(bundled))
            else:
                out.append(bundled)
            continue
        out.append(token)
        idx += 1
    return out


def _build_parser():
    """Return the corner-clamp CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate corner clamp geometry with inner base plate (mm)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--arm-length",
        type=float,
        default=100.0,
        help="Overall arm length (mm)",
    )
    parser.add_argument(
        "--height",
        type=float,
        default=60.0,
        help="Overall clamp height (mm)",
    )
    parser.add_argument(
        "--wall-thickness",
        type=float,
        default=12.0,
        help="Main structural wall thickness (mm)",
    )
    parser.add_argument(
        "--base-thickness",
        type=float,
        default=12.0,
        help="Outer-piece base thickness (mm)",
    )
    parser.add_argument(
        "--clearance",
        type=float,
        default=0.4,
        help=(
            "Gap between inner and outer pieces in plan; lifts the inner "
            "piece on +Z and leaves the same gap at the top (mm)"
        ),
    )
    parser.add_argument(
        "--magnet-diameter",
        type=float,
        default=10.0,
        help="Press-fit magnet pocket diameter (mm)",
    )
    parser.add_argument(
        "--membrane-thickness",
        type=float,
        default=1.0,
        help="Material left at each magnet mating face (mm)",
    )
    parser.add_argument(
        "--rib-thickness",
        type=float,
        default=0.1,
        help="Press-fit rib depth into bore from wall (mm)",
    )
    return parser


def parse_args(argv=None):
    """Return CLI overrides for overall and magnet-pocket dimensions."""
    args, _unknown = _build_parser().parse_known_args(_script_argv(argv))
    return args


def _pocket_axis_frame(direction):
    """Unit axis and perpendicular basis vectors for a pocket bore."""
    axis = App.Vector(*direction)
    if axis.Length == 0:
        raise ValueError("direction must be non-zero")
    axis.normalize()
    ref = App.Vector(0, 0, 1)
    if abs(axis.dot(ref)) > 0.9:
        ref = App.Vector(0, 1, 0)
    e1 = ref.cross(axis)
    e1.normalize()
    e2 = axis.cross(e1)
    e2.normalize()
    return axis, e1, e2


def magnet_pocket(
    base,
    direction,
    magnet_diameter,
    magnet_depth,
    rib_thickness,
):
    """Press-fit bore cut; shallow ribs on the wall reduce effective diameter."""
    radius = magnet_diameter / 2.0
    origin = App.Vector(*base)
    axis, e1, e2 = _pocket_axis_frame(direction)
    cutter = Part.makeCylinder(radius, magnet_depth, origin, axis)
    if rib_thickness <= 0:
        return cutter

    ribs = []
    for index in range(4):
        angle = index * math.pi / 2.0
        radial = e1 * math.cos(angle) + e2 * math.sin(angle)
        tangent = axis.cross(radial)
        tangent.normalize()
        rib = Part.makeBox(magnet_depth, rib_thickness, rib_thickness)
        orient = App.Matrix(
            axis.x,
            radial.x,
            tangent.x,
            0,
            axis.y,
            radial.y,
            tangent.y,
            0,
            axis.z,
            radial.z,
            tangent.z,
            0,
            0,
            0,
            0,
            1,
        )
        rib_origin = (
            origin
            + radial * (radius - rib_thickness)
            - tangent * (rib_thickness / 2.0)
        )
        rib.Placement = App.Placement(rib_origin, App.Rotation(orient))
        ribs.append(rib)

    rib_solid = ribs[0]
    for rib in ribs[1:]:
        rib_solid = rib_solid.fuse(rib)
    return cutter.cut(rib_solid)


def corner_chamfer_cut(size, height, corner_x, corner_y, z_base):
    """Remove a 45 deg chamfer; wedge opens toward -X and -Y in plan."""
    wire = Part.makePolygon(
        [
            App.Vector(corner_x, corner_y, z_base),
            App.Vector(corner_x - size, corner_y, z_base),
            App.Vector(corner_x, corner_y - size, z_base),
            App.Vector(corner_x, corner_y, z_base),
        ]
    )
    face = Part.Face(wire)
    return face.extrude(App.Vector(0, 0, height))


def interior_chamfer_brace(
    size,
    along_length,
    corner_x,
    corner_y,
    z_base,
    along_axis,
):
    """Fill an inside corner with a 45-degree triangular brace.

    ``along_axis`` is the positive direction to extrude. The triangle lies in
    the plane normal to that axis and extends positively along its two axes.
    Place ``corner_*`` at the junction shared by the touching solids.
    """
    if along_axis == "y":
        wire = Part.makePolygon(
            [
                App.Vector(corner_x, corner_y, z_base),
                App.Vector(corner_x + size, corner_y, z_base),
                App.Vector(corner_x, corner_y, z_base + size),
                App.Vector(corner_x, corner_y, z_base),
            ]
        )
        extrude = App.Vector(0, along_length, 0)
    elif along_axis == "x":
        wire = Part.makePolygon(
            [
                App.Vector(corner_x, corner_y, z_base),
                App.Vector(corner_x, corner_y + size, z_base),
                App.Vector(corner_x, corner_y, z_base + size),
                App.Vector(corner_x, corner_y, z_base),
            ]
        )
        extrude = App.Vector(along_length, 0, 0)
    elif along_axis == "z":
        wire = Part.makePolygon(
            [
                App.Vector(corner_x, corner_y, z_base),
                App.Vector(corner_x + size, corner_y, z_base),
                App.Vector(corner_x, corner_y + size, z_base),
                App.Vector(corner_x, corner_y, z_base),
            ]
        )
        extrude = App.Vector(0, 0, along_length)
    else:
        raise ValueError('along_axis must be "x", "y", or "z"')
    face = Part.Face(wire)
    return face.extrude(extrude)


def exterior_corner_chamfer_cut(size, height, arm_length):
    """Remove a 45 deg chamfer on the floor corner opposite the origin."""
    return corner_chamfer_cut(size, height, arm_length, arm_length, 0.0)


def outer_base_floor(
    arm_length,
    base_arm_width,
    base_thickness,
    outer_corner_chamfer,
):
    """Floor plate in +X/+Y with a 45 deg chamfer at the far corner."""
    floor = Part.makeBox(arm_length, arm_length, base_thickness)
    floor = floor.fuse(
        Part.makeBox(base_arm_width, arm_length, base_thickness)
    )
    floor = floor.cut(
        exterior_corner_chamfer_cut(
            outer_corner_chamfer, base_thickness, arm_length
        )
    )
    return floor


def inner_base_floor(
    arm_length,
    base_arm_width,
    base_thickness,
    outer_corner_chamfer,
    inner_start_xy,
    z_offset,
):
    """Floor plate above the outer base (+Z), flush with inner wall outsides."""
    floor_z = base_thickness + z_offset
    outer = outer_base_floor(
        arm_length,
        base_arm_width,
        base_thickness,
        outer_corner_chamfer,
    )
    outer.translate(App.Vector(0, 0, floor_z))
    clip_x = arm_length - inner_start_xy
    clip_y = arm_length - inner_start_xy
    clip = Part.makeBox(
        clip_x,
        clip_y,
        base_thickness,
        App.Vector(inner_start_xy, inner_start_xy, floor_z),
    )
    return outer.common(clip)


def top_right_camera(objects):
    """Orthographic camera from the +X,+Y,+Z octant, fitted to the parts."""
    scene = OfflineRenderingUtils.buildScene(objects)
    camera = coin.SoOrthographicCamera()
    view_dir = coin.SbVec3f(1, 1, 1)
    view_dir.normalize()
    camera.orientation = coin.SbRotation(coin.SbVec3f(0, 0, 1), view_dir)
    camera.viewAll(scene, coin.SbViewportRegion(800, 600))

    cam_path = tempfile.mkstemp(suffix=".iv")[1]
    out = coin.SoOutput()
    out.openFile(cam_path)
    wa = coin.SoWriteAction(out)
    wa.apply(camera)
    out.closeFile()
    with open(cam_path, encoding="utf-8") as cam_file:
        camera_text = " ".join(
            line.strip()
            for line in cam_file
            if line.strip() and not line.startswith("#")
        )
    os.remove(cam_path)
    return camera_text


def save_with_gui_view(doc, filename, parts, colors):
    """Save geometry plus GuiDocument (visible parts, camera)."""
    camera = top_right_camera(parts)
    OfflineRenderingUtils.save(doc, filename=filename, colors=colors, camera=camera)


def add_properties(
    obj,
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
):
    dimensions = [
        ("ArmLength", arm_length, "Overall arm length"),
        ("Height", height, "Overall clamp height"),
        ("WallThickness", wall_thickness, "Main structural wall thickness"),
        ("BaseThickness", base_thickness, "Outer-piece base thickness"),
        (
            "Clearance",
            clearance,
            "Plan gap; inner piece +Z offset and matching top gap",
        ),
    ]
    magnets = [
        ("NominalMagnetDiameter", 10.0, "Nominal disc magnet diameter"),
        ("NominalMagnetThickness", 3.0, "Nominal disc magnet thickness"),
        ("PocketDiameter", magnet_diameter, "Press-fit magnet pocket diameter"),
        ("PocketDepth", magnet_depth, "Magnet pocket depth"),
        ("MembraneThickness", membrane_thickness, "Material left at each mating face"),
        (
            "RibThickness",
            rib_thickness,
            "Press-fit rib depth into bore from wall",
        ),
        (
            "OuterCornerChamfer",
            outer_corner_chamfer,
            "45 deg chamfer on outer floor far corner",
        ),
    ]
    for name, value, description in dimensions:
        obj.addProperty("App::PropertyLength", name, "Dimensions", description)
        setattr(obj, name, value)
    for name, value, description in magnets:
        obj.addProperty("App::PropertyLength", name, "Magnets", description)
        setattr(obj, name, value)


def main(argv=None):
    """Build the corner clamp document and save OUTPUT."""
    script_argv = _script_argv(argv)
    try:
        _import_freecad()
    except ModuleNotFoundError:
        _run_under_freecad(script_argv)
    print("Starting...")
    args = parse_args(script_argv)

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
    inner_start_z = 2* base_thickness + clearance
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
    doc = App.newDocument("Corner_Clamp_With_Base")

    params = doc.addObject("App::FeaturePython", "Parameters")
    params.Label = "Design Parameters (mm)"
    add_properties(
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
    outer_floor = outer_base_floor(
        arm_length,
        base_arm_width,
        base_thickness,
        outer_corner_chamfer,
    )
    outer_x_wall = Part.makeBox(wall_thickness, arm_length, height)
    outer_y_wall = Part.makeBox(arm_length, wall_thickness, height)
    outer_shape = outer_floor.fuse(outer_x_wall).fuse(outer_y_wall)

    # Straight magnet pockets in each leg, inserted from outside.
    outer_x_magnet = magnet_pocket(
        (magnet_pocket_start, magnet_center, inner_magnet_z),
        (1.0, 0.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    outer_y_magnet = magnet_pocket(
        (magnet_center, magnet_pocket_start, inner_magnet_z),
        (0.0, 1.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    outer_base_magnet = magnet_pocket(
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
    inner_shape = inner_base_floor(
        arm_length,
        base_arm_width,
        base_thickness,
        outer_corner_chamfer,
        inner_start_xy,
        clearance,
    )
    inner_x_leg = Part.makeBox(
        wall_thickness,
        inner_arm_length,
        inner_height,
        App.Vector(inner_start_xy, inner_start_xy, inner_start_z),
    )
    inner_y_leg = Part.makeBox(
        inner_arm_length,
        wall_thickness,
        inner_height,
        App.Vector(inner_start_xy, inner_start_xy, inner_start_z),
    )
    inner_shape = inner_shape.fuse(inner_x_leg)
    inner_shape = inner_shape.fuse(inner_y_leg)

    inner_chamfer_corner = interior_chamfer_brace(
        inner_corner_chamfer,
        inner_height,
        inner_far_x,
        inner_far_y,
        inner_start_z,
        "z",
    )
    # X leg foot: long dimension along +Y; Y leg foot: long dimension
    # along +X. Each brace begins on the inner face of its respective leg.
    inner_chamfer_x_base = interior_chamfer_brace(
        inner_corner_chamfer,
        inner_arm_length,
        inner_far_x,
        inner_start_xy,
        inner_start_z,
        "y",
    )
    inner_chamfer_y_base = interior_chamfer_brace(
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

    inner_x_magnet = magnet_pocket(
        (inner_far_x - magnet_pocket_start, magnet_center, inner_magnet_z),
        (-1.0, 0.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    inner_y_magnet = magnet_pocket(
        (magnet_center, inner_far_y - magnet_pocket_start, inner_magnet_z),
        (0.0, -1.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    inner_base_magnet = magnet_pocket(
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
    save_with_gui_view(doc, OUTPUT, [outer, inner], gui_colors)
    print("Saved:", OUTPUT)
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
    _cli_argv = _script_argv(sys.argv[1:])
    if "-h" in _cli_argv or "--help" in _cli_argv:
        _build_parser().parse_args(_cli_argv)
    else:
        main()


if _freecad_script_entry():
    cli()
