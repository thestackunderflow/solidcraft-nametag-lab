# PROBE: name keychain, do small letters VANISH, CLOSE or get FAT? (25 Oct 2026, $0)

This is a feasibility probe for `../PLAN.md` §3 (P1 to P4), set up the way `../REVIEW-accuracy.md` MUST-FIX 1 to 4 asked.
No AI or model calls, no paid APIs, nothing installed on the Windows host (everything ran in Docker), and nothing was printed.
Every number here is the slicer's **plan** (its G-code), not a physical print.

## Setup
| Item | Value |
|---|---|
| CAD | SolidCraft **0.22.0** (MCP `serverInfo.version`), headless `solidcraft-cli mcp`, image `solidcraft-tipping-lab:0.22.0` (431aca93ee48), used read-only |
| Slicer | **PrusaSlicer 2.9.2**, image `habs-slicer:0.2` (441dc65153f3), bundled `PrusaResearch.ini` config_version **2.2.7** |
| Preset | print "0.20mm SPEED @MK4S 0.4", filament "Prusament PLA @MK4S", printer "Original Prusa MK4S 0.4 nozzle" (non-HF), resolved from the bundle by `resolve_preset.py` (a copy of the tipping lab's) |
| Only override | `--binary-gcode=0` (the preset has `binary_gcode = 1`). The footer confirms `binary_gcode = 0`, and every G-code has `;WIDTH:` tags (725 to 2130 per file) |
| Analysis | image `nametag-analyse:0.1` (`Dockerfile.analyse`: python 3.12.13-slim, shapely 2.0.6, matplotlib 3.9.2, numpy 2.1.3); 5 unit tests in `test_geom.py` (red log `out/red-phase-geom.log`, green `out/green-phase-geom.log`) |

**Preset as the slicer used it** (from the G-code footer, `out/preset.json`): `perimeter_generator = arachne`;
`min_feature_size = 25%` (= **0.10 mm**); `min_bead_width = 85%` (= **0.34 mm**); perimeter, external perimeter,
solid infill and infill widths **0.45**; top infill **0.42**; first layer 0.5; `slice_closing_radius = 0.049`;
`thin_walls = 0`; perimeters 2; top_solid_layers 5; layer 0.2; wall_transition_length 100%; wall_transition_angle 10;
wall_distribution_count 1; arc_fitting emit_center (the G2/G3 arcs are parsed, full circles included).
These match the values the review read from 2.9.6 / bundle 2.4.14.

**P4, SolidCraft text** (`out/p4-commands.json`, `out/editcheck/editcheck.json`): the tag was built with `solid.box` +
`solid.hole` + `sketch.text` x2 + `solid.emboss` (`mode: emboss`, depth 1, or `mode: deboss`, depth 0.6). All 12 builds
returned `ok`. The default font is "the built-in Liberation Sans": this comes from the command's own docs, and the
`sketch.text` reply does not name the font. `height` is the capital height. **The text stays editable after the
emboss.** `sketch.edit` + `sketch.edit_text` (link `j2`) changed GYM BAG from 5 mm to 3 mm and the body rebuilt to
3052.002 mm³, the same as a direct 3 mm build (it was 3085.225 before the edit). OpenSCAD was not needed.

**Object:** tag 50 x 20 x 3 mm, Ø 4 hole at x -20. "ALEX" has a cap height of 8 mm with its baseline at y 0.5.
"GYM BAG" has a cap height h with its cap top at y -1. Both lines start at x -16.

**Method:** we slice the SolidCraft STL. For every layer inside the letters (raised: z 3.2 to 4.0, 5 layers; engraved:
z 2.6 to 3.0, 3 layers), we cut the design at the slicer's slice plane (z - 0.1). We then draw every extruding move at
its own `;WIDTH:` (round ends) and union them into the printed region. Each design letter gets a cell: the points
closer to that letter than to any other. In each cell we compare:
- **Raised letters:** printed area / designed area, the number of printed pieces, and how much of each counter (the
  holes in A and B) is left open.
- **Engraved letters:** open slot area (no bead) / designed slot area, the open pieces, and the share of each
  "island" (the plastic inside an engraved A or B) that is printed.

The headline layer is z 3.6 for raised and z 2.8 for engraved, as the review asked. The verdict is the worst over all
letter layers. How the method checks itself: line 1 "ALEX" at 8 mm comes out at **0.993 to 1.004** in every case,
so the bead model has no systematic bias.

Verdict rules (`analyse.py`):
- **VANISH:** a raised letter has no extrusion, splits into more pieces, or has more than 25% of its area uncovered.
- **CLOSE:** an engraved slot has less than 5% open, splits into pieces, or more than 25% of it is filled.
- **FAT:** raised area more than 1.15x the design, or a lost counter. For engraved: open area below 0.85x or above
  1.15x the design, a lost island, or an island less than 50% printed.
- **FINE:** none of the above.

## Results (line 2 "GYM BAG"; one PNG per case: `out/<case>/layer.png`)
| Case | Vanished letters | Closed slots / lost counters | Line-2 area ratio (raised: printed/design; engraved: open/design) | Counters (open share; engraved: island printed share) | Verdict |
|---|---|---|---|---|---|
| raised 2 mm | none | none closed | **1.44 to 1.56** | B 0.61 / 0.66, A 0.50 | **FAT** |
| raised 3 mm | none | none | 1.03 to 1.10 | B 0.88 / 0.90, A 0.91 | FINE (slightly fat) |
| raised 4 mm | none | none | 0.99 to 1.03 | B 0.94 / 0.95, A 0.98 | FINE |
| raised 5 mm | none | none | 0.99 to 1.01 | B 0.98 / 0.98, A 0.98 | FINE |
| engraved 2 mm | none | no slot closed; **B's upper counter island not printed** (0.51 mm², 0 extrusion on all 3 layers) | 0.99 to 1.33 (M 1.27, B 1.33) | B island 0.00 / 0.95, A 0.73 | **FAT** |
| engraved 3 mm | none | none | 0.98 to 1.12 | B 0.95 / 0.95, A 0.87 | FINE |
| engraved 4 mm | none | none | 0.99 to 1.07 | B 0.96 / 0.94, A 0.88 | FINE |
| engraved 5 mm | none | none | 0.99 to 1.05 | B 0.98 / 0.99, A 0.93 | FINE |
| *raised 1.5 mm (diagnostic)* | none | none | 1.78 to 2.09 | B 0.33 / 0.45, A 0.20 | FAT |
| *raised 1 mm (diagnostic)* | **G, Y, A, G: no extrusion at all**; M and B only as blobs | | 0 to 1.78 | | **VANISH** |
| *engraved 1.5 mm (diagnostic)* | none | B loses both counter islands | 0.97 to 1.68 | B 0 / 0 | FAT |
| *engraved 1 mm (diagnostic)* | none | **G, B, A, G partly filled** (A 47% open, 58% filled) | 0.48 to 1.77 | | **CLOSE** |

Other measured facts:
- **Raised 2 mm.** Every line-2 stroke is planned as a single bead **0.383 mm** wide. The designed thinnest stroke is
  0.15 to 0.29 mm, measured as the erosion that first changes the letter's shape. So a stroke drawn at 0.15 to 0.29 mm
  is printed at 0.383 mm, and the letters gain 44 to 56% in area. Pointed tips are trimmed: M has 6.5% of its area
  uncovered, the largest gap 0.05 mm². No letters merge into each other, and every counter stays open (but smaller).
- **Engraved 2 mm.** No slot closes: at most 7.6% of any slot is under a bead. Instead the **plastic** between and
  inside the letters is dropped or trimmed. B's upper island is 0.89 x 0.63 mm and gets no move at all on z 2.6, 2.8
  or 3.0. The plastic wedges inside the M are cut short, so its slot comes out 27% wider. The engraved letters get
  bolder, not filled in.
- **Designed thinnest stroke / gap** (erosion measure, line 2): 2 mm 0.15 to 0.29; 3 mm 0.22 to 0.45; 4 mm 0.30 to
  0.60; 5 mm 0.37 to 0.75; 1.5 mm 0.11 to 0.22; 1 mm 0.075 to 0.14.
- **Arachne's thinnest planned bead on line 2** is 0.353 to 0.383 mm in every case. That is close to the 0.34 mm
  `min_bead_width`. The widest is 0.82 mm.

## What the data supports
- **Hook variant C ("blob" / FAT)**, as the accuracy review predicted. From 2 to 5 mm nothing vanishes and no engraved
  slot closes. At 2 mm, raised letters are planned 44 to 56% fatter, with B's and A's counters only 50 to 66% open.
  Engraved letters keep their slots but lose B's upper counter island, and the M's slot is 27% wider.
- **Variant A ("vanish")** shows up only at **1 mm** cap height. That is below the plan's range, so it can only be a
  diagnostic: 4 of 6 raised letters get no plastic at all.
- **Variant B ("blur/close")** shows up only at **1 mm engraved**, where it is partial.
- The plan's kill rule as written ("every letter of line 2 at 2 mm present and readable in both modes") would fire
  for A/B, because every letter has plastic or an open slot. The review's MUST-FIX 4 rule does **not** fire: there is
  a clear, measured change at 2 mm.

**Smallest line-2 cap height where every GYM BAG letter keeps its pieces and counters** (from the tested 2, 3, 4, 5):
- **Raised: 2 mm.** Topology is kept, even at 1.5 mm in the diagnostic run, but the letters are FAT. The smallest
  height that is also not FAT (area within 15%, counters 88% or more open) is **3 mm**.
- **Engraved: 3 mm.** At 2 mm, B loses a counter island.

## Limits
- This is a slicer plan, not a print. Squish, ooze and elephant's foot are not modelled.
- Beads are modelled as round-ended rectangles at `;WIDTH:`, which is checked against the 8 mm line within ±0.7%.
- The design outline is the SolidCraft STL, which is what the slicer saw. Its curves are faceted, and it has
  T-junctions, so section points are welded within 0.2 µm.
- One font (Liberation Sans regular) and one preset (non-HF; the review says the HF preset has the same values).
- The thresholds (1.15, 0.85, 25%, 0.5) are this probe's choices. The raw ratios are all in `out/<case>/analysis.json`.

## Files and rerun
- `build.py`, `explore_cmds.py`, `mcp_client.py` (a copy of the tipping lab's): run in `solidcraft-tipping-lab:0.22.0`.
- `slice.sh` (with `resolve_preset.py`): runs in `habs-slicer:0.2`.
- `geom.py`, `analyse.py`, `test_geom.py`: run in `nametag-analyse:0.1` (`Dockerfile.analyse`).
- Outputs: `out/<case>/{tag.solidcraft, tag.stl, tag.gcode, build.json, analysis.json, layer.png}`,
  `out/results.json`, `out/preset.json`, `out/preset-resolved.ini`, `out/slicer-version.txt`.

```
docker build -t nametag-analyse:0.1 -f Dockerfile.analyse .
docker run --rm -v "$PWD:/w" -v "$PWD/out:/lab/out" -w /w solidcraft-tipping-lab:0.22.0 python3 build.py
bash slice.sh
docker run --rm -v "$PWD:/w" -w /w nametag-analyse:0.1 python -m pytest -q test_geom.py
docker run --rm -v "$PWD:/w" -w /w nametag-analyse:0.1 python analyse.py
```
(The 1 and 1.5 mm cases are built with `build.py raised-h1 raised-h1.5 engraved-h1 engraved-h1.5`.)
