# Corner clamp (parametric FreeCAD)

![Corner clamp outer L bracket in FreeCAD](corner_clamp_screenshot.png)

Two-piece 90 degree corner clamp: an outer L with base and side walls,
and an inner L that nests inside. Geometry is built by
`corner_clamp_generator.py` and saved as a FreeCAD document.

## Repository files

- `corner_clamp_generator.py` - parametric script (constants at top)
- `pyproject.toml` - project metadata and `corner-clamp-generator` CLI
- `Corner_Clamp.FCStd` - generated model (outer and inner solids)
- `corner_clamp_screenshot.png` - CAD screenshot (see above)
- `corner_clamp.png` - reference image

## Requirements

- Python 3.10+ for CLI help and optional [uv](https://docs.astral.sh/uv/)
  workflow (`uv sync`, `uv run`).
- [FreeCAD](https://www.freecad.org/) with a headless CLI to build geometry.
  On Ubuntu via snap, the command is usually `freecad.cmd` (also
  `snap run freecad.cmd`).

FreeCAD provides `FreeCAD`, `Part`, and related modules; they are not
installed by this project's Python environment.

## CLI help

Show script options (no FreeCAD needed):

```bash
python corner_clamp_generator.py -h
```

With uv after `uv sync`:

```bash
uv run corner-clamp-generator -h
uv run corner_clamp_generator.py -h
```

`freecad.cmd corner_clamp_generator.py -h` prints FreeCAD's own help
because the launcher handles `-h` before the script runs. Use `python` or
`uv run` for this script's help.

## Run the generator

With uv installed (`uv sync`), the console script re-invokes `freecad.cmd`
when FreeCAD is not in the venv Python:

```bash
corner-clamp-generator --arm-length 200 --height 200
```

Or call FreeCAD directly from this directory:

```bash
freecad.cmd corner_clamp_generator.py
```

If `freecad.cmd` is not on your PATH:

```bash
snap run freecad.cmd "$(pwd)/corner_clamp_generator.py"
```

Pass dimension overrides after the script name, for example:

```bash
freecad.cmd corner_clamp_generator.py --arm-length 120 --height 50
```

The script prints saved path, part volumes, and whether each solid is
valid. Open the resulting `.FCStd` in the FreeCAD GUI to inspect or
export meshes.

By default, `OUTPUT` in the script is `Corner_Clamp.FCStd` in the current
working directory. Change the constant at the top of
`corner_clamp_generator.py` to write elsewhere.

## Design defaults

- Envelope: 100 mm arms, 60 mm height, 12 mm walls
- Magnets: nominal 10 mm diameter x 3 mm thick; one pair per L leg
- Pockets: straight 9.8 mm diameter x 3.1 mm deep press-fit holes
- 1 mm membrane at each mating face so magnets cannot touch
- Inner legs: 0.4 mm clearance on nested sides; outer corner 45 degree
  chamfer on the square wall profile

## Customize

Adjust the constants at the top of `corner_clamp_generator.py`, or use CLI
flags from `-h`, then run the generator again. The FCStd includes a
`Parameters` object documenting key dimensions.
