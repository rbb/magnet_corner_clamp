# Corner clamp (parametric FreeCAD)

Two-piece 90 degree corner clamp: an outer L with base and side walls,
and an inner L that nests inside. Geometry is built by
`corner_clamp_generator.py` and saved as a FreeCAD document.

## Repository files

- `corner_clamp_generator.py` - parametric script (constants at top)
- `Corner_Clamp.FCStd` - generated model (outer and inner solids)
- `corner_clamp.png` - reference image

## Requirements

- [FreeCAD](https://www.freecad.org/) with a headless CLI. On Ubuntu via
  snap, the command is usually `freecad.cmd` (also `snap run freecad.cmd`).

## Run the generator

From this directory:

```bash
freecad.cmd corner_clamp_generator.py
```

If `freecad.cmd` is not on your PATH:

```bash
snap run freecad.cmd "$(pwd)/corner_clamp_generator.py"
```

The script prints saved path, part volumes, and whether each solid is
valid. Open the resulting `.FCStd` in the FreeCAD GUI to inspect or
export meshes.

By default, `OUTPUT` in the script is an absolute path
(`/home/russ/Downloads/Corner_Clamp.FCStd`). Change it to write next to
the script, for example:

```python
OUTPUT = "Corner_Clamp.FCStd"
```

## Design defaults

- Envelope: 100 mm arms, 60 mm height, 12 mm walls
- Magnets: nominal 10 mm diameter x 3 mm thick; one pair per L leg
- Pockets: straight 9.8 mm diameter x 3.1 mm deep press-fit holes
- 1 mm membrane at each mating face so magnets cannot touch
- Inner legs: 0.4 mm clearance on nested sides; outer corner 45 degree
  chamfer on the square wall profile

## Customize

Adjust the constants at the top of `corner_clamp_generator.py`, then run
the generator again. The FCStd includes a `Parameters` object documenting
key dimensions.
