import os
import tempfile

import FreeCAD as App
import OfflineRenderingUtils
import Part
from pivy import coin


OUTPUT = "Corner_Clamp.FCStd"

# Overall dimensions (mm)
ARM_LENGTH = 100.0
HEIGHT = 60.0
WALL_THICKNESS = 12.0
BASE_THICKNESS = 12.0
BASE_ARM_WIDTH = 42.0

# Nested inner part
CLEARANCE = 0.4
INNER_START = WALL_THICKNESS + CLEARANCE
INNER_ARM_LENGTH = ARM_LENGTH - INNER_START
INNER_HEIGHT = HEIGHT - BASE_THICKNESS

# Magnet pockets for nominal 10 x 3 mm disc magnets
MAGNET_DIAMETER = 9.8
MEMBRANE = 1.0
#MAGNET_DEPTH = 3.1
MAGNET_DEPTH = WALL_THICKNESS - MEMBRANE
MAGNET_POCKET_START = WALL_THICKNESS - MAGNET_DEPTH - MEMBRANE
MAGNET_CENTER = 67.0
MAGNET_Z = 36.0

# Exterior corner chamfer on outer walls (45 deg, square profile)
OUTER_CORNER_CHAMFER = WALL_THICKNESS


def magnet_pocket(base, direction):
    """Straight press-fit hole leaving MEMBRANE at the mating face."""
    return Part.makeCylinder(
        MAGNET_DIAMETER / 2.0,
        MAGNET_DEPTH,
        App.Vector(*base),
        App.Vector(*direction),
    )


def exterior_corner_chamfer_cut(size, height, arm_length=ARM_LENGTH):
    """Remove a 45 deg chamfer on the floor corner opposite the origin."""
    x = arm_length
    y = arm_length
    wire = Part.makePolygon(
        [
            App.Vector(x, y, 0),
            App.Vector(x - size, y, 0),
            App.Vector(x, y - size, 0),
            App.Vector(x, y, 0),
        ]
    )
    face = Part.Face(wire)
    return face.extrude(App.Vector(0, 0, height))


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


def add_properties(obj):
    dimensions = [
        ("ArmLength", ARM_LENGTH, "Overall arm length"),
        ("Height", HEIGHT, "Overall clamp height"),
        ("WallThickness", WALL_THICKNESS, "Main structural wall thickness"),
        ("BaseThickness", BASE_THICKNESS, "Outer-piece base thickness"),
        ("Clearance", CLEARANCE, "Gap between the two pieces"),
    ]
    magnets = [
        ("NominalMagnetDiameter", 10.0, "Nominal disc magnet diameter"),
        ("NominalMagnetThickness", 3.0, "Nominal disc magnet thickness"),
        ("PocketDiameter", MAGNET_DIAMETER, "Press-fit magnet pocket diameter"),
        ("PocketDepth", MAGNET_DEPTH, "Magnet pocket depth"),
        ("MembraneThickness", MEMBRANE, "Material left at each mating face"),
        (
            "OuterCornerChamfer",
            OUTER_CORNER_CHAMFER,
            "45 deg chamfer on outer floor far corner",
        ),
    ]
    for name, value, description in dimensions:
        obj.addProperty("App::PropertyLength", name, "Dimensions", description)
        setattr(obj, name, value)
    for name, value, description in magnets:
        obj.addProperty("App::PropertyLength", name, "Magnets", description)
        setattr(obj, name, value)


doc = App.newDocument("Corner_Clamp")

params = doc.addObject("App::FeaturePython", "Parameters")
params.Label = "Design Parameters (mm)"
add_properties(params)
params.addProperty(
    "App::PropertyString",
    "Instructions",
    "Magnets",
    "Magnet installation note",
)
params.Instructions = (
    "Press one 10 x 3 mm disc magnet into each straight pocket. "
    "Check polarity before insertion. Each magnet is covered by a 1 mm membrane."
)

# OUTER PIECE
# L-shaped floor plus two perpendicular outside walls.
outer_floor = Part.makeBox(ARM_LENGTH, ARM_LENGTH, BASE_THICKNESS)
outer_floor = outer_floor.fuse(
    Part.makeBox(BASE_ARM_WIDTH, ARM_LENGTH, BASE_THICKNESS)
)
outer_floor = outer_floor.cut(
    exterior_corner_chamfer_cut(OUTER_CORNER_CHAMFER, BASE_THICKNESS)
)
outer_x_wall = Part.makeBox(WALL_THICKNESS, ARM_LENGTH, HEIGHT)
outer_y_wall = Part.makeBox(ARM_LENGTH, WALL_THICKNESS, HEIGHT)
outer_shape = outer_floor.fuse(outer_x_wall).fuse(outer_y_wall)

# Straight magnet pockets in each leg, inserted from outside.
outer_x_magnet = magnet_pocket(
    (MAGNET_POCKET_START, MAGNET_CENTER, MAGNET_Z),
    (1.0, 0.0, 0.0),
)
outer_y_magnet = magnet_pocket(
    (MAGNET_CENTER, MAGNET_POCKET_START, MAGNET_Z),
    (0.0, 1.0, 0.0),
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
OUTER_COLOR = (1.0, 0.72, 0.05)
if outer.ViewObject:
    outer.ViewObject.Visibility = True
    outer.ViewObject.ShapeColor = OUTER_COLOR

# INNER PIECE
# Upright L-shaped pusher, nested inside the outer walls.
inner_x_leg = Part.makeBox(
    WALL_THICKNESS, INNER_ARM_LENGTH, INNER_HEIGHT, App.Vector(INNER_START, INNER_START, BASE_THICKNESS)
)
inner_y_leg = Part.makeBox(
    INNER_ARM_LENGTH, WALL_THICKNESS, INNER_HEIGHT, App.Vector(INNER_START, INNER_START, BASE_THICKNESS)
)
inner_shape = inner_x_leg.fuse(inner_y_leg)

inner_far_x = INNER_START + WALL_THICKNESS
inner_far_y = INNER_START + WALL_THICKNESS

inner_x_magnet = magnet_pocket(
    (inner_far_x - MAGNET_POCKET_START, MAGNET_CENTER, MAGNET_Z),
    (-1.0, 0.0, 0.0),
)
inner_y_magnet = magnet_pocket(
    (MAGNET_CENTER, inner_far_y - MAGNET_POCKET_START, MAGNET_Z),
    (0.0, -1.0, 0.0),
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
inner.PrintOrientation = "Print with the broad L-shaped end face on the build plate."
INNER_COLOR = (1.0, 0.88, 0.10)
if inner.ViewObject:
    inner.ViewObject.Visibility = True
    inner.ViewObject.ShapeColor = INNER_COLOR

parts = doc.addObject("App::DocumentObjectGroup", "ClampParts")
parts.Label = "Printable Parts"
parts.addObject(outer)
parts.addObject(inner)

doc.recompute()
gui_colors = {
    outer.Name: OUTER_COLOR,
    inner.Name: INNER_COLOR,
}
save_with_gui_view(doc, OUTPUT, [outer, inner], gui_colors)
print("Saved:", OUTPUT)
print("Outer volume (mm^3):", round(outer.Shape.Volume, 2))
print("Inner volume (mm^3):", round(inner.Shape.Volume, 2))
print("Outer valid:", outer.Shape.isValid())
print("Inner valid:", inner.Shape.isValid())
