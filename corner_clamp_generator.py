"""Generate a corner clamp FreeCAD model with configurable dimensions."""

import argparse
import math
import os
import tempfile

import FreeCAD as App
import OfflineRenderingUtils
import Part
from pivy import coin


OUTPUT = "Corner_Clamp.FCStd"

# Magnet placement (mm); not exposed on the CLI
MAGNET_CENTER = 67.0
MAGNET_Z = 36.0


def parse_args(argv=None):
    """Return CLI overrides for overall and magnet-pocket dimensions."""
    parser = argparse.ArgumentParser(
        description="Generate corner clamp geometry (mm).",
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
        help="Gap between the two pieces (mm)",
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
    parser.add_argument(
        "--z-clearance",
        type=float,
        default=1.0,
        help=(
            "Vertical gap at the top of the inner piece; also lowers "
            "inner magnet pockets by this amount (mm)"
        ),
    )
    args, _unknown = parser.parse_known_args(argv)
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


def interior_corner_chamfer_brace(size, height, corner_x, corner_y, z_base):
    """45 deg triangular brace; wedge opens toward +X and +Y in plan."""
    wire = Part.makePolygon(
        [
            App.Vector(corner_x, corner_y, z_base),
            App.Vector(corner_x + size, corner_y, z_base),
            App.Vector(corner_x, corner_y + size, z_base),
            App.Vector(corner_x, corner_y, z_base),
        ]
    )
    face = Part.Face(wire)
    return face.extrude(App.Vector(0, 0, height))


def exterior_corner_chamfer_cut(size, height, arm_length):
    """Remove a 45 deg chamfer on the floor corner opposite the origin."""
    return corner_chamfer_cut(size, height, arm_length, arm_length, 0.0)


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
        ("Clearance", clearance, "Gap between the two pieces"),
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
    args = parse_args(argv)

    arm_length = args.arm_length
    height = args.height
    wall_thickness = args.wall_thickness
    base_thickness = args.base_thickness
    clearance = args.clearance
    magnet_diameter = args.magnet_diameter
    membrane_thickness = args.membrane_thickness
    rib_thickness = args.rib_thickness
    z_clearance = args.z_clearance

    base_arm_width = height - base_thickness
    inner_start = wall_thickness + clearance
    inner_arm_length = arm_length - inner_start
    inner_height = height - base_thickness - z_clearance
    magnet_depth = wall_thickness - membrane_thickness
    magnet_pocket_start = wall_thickness - magnet_depth - membrane_thickness
    outer_corner_chamfer = wall_thickness
    inner_corner_chamfer = wall_thickness

    doc = App.newDocument("Corner_Clamp")

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
        "Press one 10 x 3 mm disc magnet into each straight pocket. "
        "Check polarity before insertion. Each magnet is covered by a "
        f"{membrane_thickness:g} mm membrane."
    )

    # OUTER PIECE
    # L-shaped floor plus two perpendicular outside walls.
    outer_floor = Part.makeBox(arm_length, arm_length, base_thickness)
    outer_floor = outer_floor.fuse(
        Part.makeBox(base_arm_width, arm_length, base_thickness)
    )
    outer_floor = outer_floor.cut(
        exterior_corner_chamfer_cut(
            outer_corner_chamfer, base_thickness, arm_length
        )
    )
    outer_x_wall = Part.makeBox(wall_thickness, arm_length, height)
    outer_y_wall = Part.makeBox(arm_length, wall_thickness, height)
    outer_shape = outer_floor.fuse(outer_x_wall).fuse(outer_y_wall)

    # Straight magnet pockets in each leg, inserted from outside.
    outer_x_magnet = magnet_pocket(
        (magnet_pocket_start, MAGNET_CENTER, MAGNET_Z),
        (1.0, 0.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    outer_y_magnet = magnet_pocket(
        (MAGNET_CENTER, magnet_pocket_start, MAGNET_Z),
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
    inner_x_leg = Part.makeBox(
        wall_thickness,
        inner_arm_length,
        inner_height,
        App.Vector(inner_start, inner_start, base_thickness),
    )
    inner_y_leg = Part.makeBox(
        inner_arm_length,
        wall_thickness,
        inner_height,
        App.Vector(inner_start, inner_start, base_thickness),
    )
    inner_shape = inner_x_leg.fuse(inner_y_leg)

    inner_far_x = inner_start + wall_thickness
    inner_far_y = inner_start + wall_thickness
    inner_shape = inner_shape.fuse(
        interior_corner_chamfer_brace(
            inner_corner_chamfer,
            inner_height,
            inner_far_x,
            inner_far_y,
            base_thickness,
        )
    )
    inner_magnet_z = MAGNET_Z - z_clearance

    inner_x_magnet = magnet_pocket(
        (
            inner_far_x - magnet_pocket_start,
            MAGNET_CENTER,
            inner_magnet_z,
        ),
        (-1.0, 0.0, 0.0),
        magnet_diameter,
        magnet_depth,
        rib_thickness,
    )
    inner_y_magnet = magnet_pocket(
        (MAGNET_CENTER, inner_far_y - magnet_pocket_start, inner_magnet_z),
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
    save_with_gui_view(doc, OUTPUT, [outer, inner], gui_colors)
    print("Saved:", OUTPUT)
    print("Outer volume (mm^3):", round(outer.Shape.Volume, 2))
    print("Inner volume (mm^3):", round(inner.Shape.Volume, 2))
    print("Outer valid:", outer.Shape.isValid())
    print("Inner valid:", inner.Shape.isValid())


if __name__ in ("__main__", "corner_clamp_generator"):
    main()
