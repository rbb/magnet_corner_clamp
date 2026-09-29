"""Shared FreeCAD helpers and corner-clamp geometry for generator scripts."""

import argparse
import math
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

App = None
Part = None
OfflineRenderingUtils = None
coin = None


def import_freecad():
    """Load FreeCAD bindings (not available in a normal system Python)."""
    global App, Part, OfflineRenderingUtils, coin
    if App is not None:
        return
    import FreeCAD as App
    import OfflineRenderingUtils
    import Part
    from pivy import coin


def find_freecad_cmd():
    """Return a FreeCAD headless launcher on PATH, if any."""
    for name in ("freecad.cmd", "FreeCADCmd", "freecadcmd"):
        path = shutil.which(name)
        if path:
            return path
    return None


def run_under_freecad(script_path, script_argv):
    """Re-run a script under FreeCAD's Python (e.g. from a venv CLI)."""
    freecad = find_freecad_cmd()
    if freecad is None:
        print(
            "FreeCAD is not available in this Python environment and "
            "freecad.cmd was not found on PATH.",
            file=sys.stderr,
        )
        print(
            "Install FreeCAD or run: freecad.cmd "
            f"{os.path.abspath(script_path)} ...",
            file=sys.stderr,
        )
        sys.exit(1)
    script_path = os.path.abspath(script_path)
    cmd = [freecad, script_path]
    if script_argv:
        cmd.extend(["--pass", shlex.join(script_argv)])
    completed = subprocess.run(cmd, check=False)
    sys.exit(completed.returncode)


def freecad_running_this_file(script_path):
    """True when FreeCADCmd is executing script_path (not a plain import)."""
    this_path = os.path.abspath(script_path)
    this_name = os.path.basename(this_path)
    for arg in sys.argv[1:]:
        if arg in ("--pass",):
            continue
        if os.path.abspath(arg) == this_path:
            return True
        if os.path.basename(arg) == this_name:
            return True
    return False


def freecad_script_entry(script_path, module_name):
    """True when script_path is the FreeCADCmd script target.

    FreeCADCmd sets ``__name__`` to the script stem (not ``__main__``).
    """
    if module_name == "__main__":
        return True
    if not freecad_running_this_file(script_path):
        return False
    stem = os.path.splitext(os.path.basename(script_path))[0]
    return module_name == stem


def script_argv(argv):
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


HELP_EPILOG = """

Output filenames append three numbers before the extension:
  <stem>_<arm-length>_<height>_<magnet-diameter>.FCStd

All three values are in millimeters (same as --arm-length, --height,
--magnet-diameter). Example: Corner_Clamp_100_60_10.FCStd for defaults.
Other CLI options appear only in the document Comment metadata, not in
the filename.
"""


class _HelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    """Show option defaults and preserve epilog line breaks."""


def build_parser(description: str) -> argparse.ArgumentParser:
    """Return the corner-clamp CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=description,
        epilog=HELP_EPILOG,
        formatter_class=_HelpFormatter,
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


def parse_args(parser: argparse.ArgumentParser, argv=None):
    """Return CLI overrides for overall and magnet-pocket dimensions."""
    args, _unknown = parser.parse_known_args(script_argv(argv))
    return args


def cli_comment(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    script_tag: str,
) -> str:
    """Return all CLI parameters for document Comment metadata."""
    parts = [script_tag]
    for action in parser._actions:
        if action.dest in ("help", "version") or not action.option_strings:
            continue
        opt = max(action.option_strings, key=len)
        value = getattr(args, action.dest)
        if isinstance(value, float):
            parts.append(f"{opt} {value:g}")
        else:
            parts.append(f"{opt} {value}")
    return " ".join(parts)


def output_filename(
    default_output: str,
    arm_length: float,
    height: float,
    magnet_diameter: float,
) -> str:
    """Return the output path with key dimensions in the filename."""
    stem, extension = os.path.splitext(default_output)
    dimensions = (
        f"{arm_length:g}_{height:g}_{magnet_diameter:g}"
    )
    return f"{stem}_{dimensions}{extension}"


def pocket_axis_frame(direction):
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
    axis, e1, e2 = pocket_axis_frame(direction)
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
    OfflineRenderingUtils.save(
        doc, filename=filename, colors=colors, camera=camera
    )


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
        (
            "MembraneThickness",
            membrane_thickness,
            "Material left at each mating face",
        ),
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
