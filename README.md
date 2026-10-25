# SolidCraft name keychain lab: why small letters turn to blobs

The lab behind "SolidCraft + Claude: Name Keychain, Why Small Letters Turn to Blobs" (SolidCraft for Beginners #10).
SolidCraft 0.22.1 (headless, through its MCP server) and PrusaSlicer 2.9.2 with its stock presets, all in Docker. Nothing
is printed: every result is the slicer's plan. Started from the $0 probe (`PROBE.md`, `probe-0.22.0/`), re-run on 0.22.1.
Results are added when the runs are scored.

## Probe on SolidCraft 0.22.1 (`out/results.json`, `out/<case>/analysis.json`, `out/<case>/layer.png`)
Tag 50 x 20 x 3 mm, a 4 mm ring hole, row 1 "ALEX" 8 mm, row 2 "GYM BAG" h mm, raised 1 mm or engraved 0.6 mm, built by
`build.py` (sketch.text + solid.emboss), sliced by `slice.sh` (PrusaSlicer 2.9.2, stock "0.20mm SPEED @MK4S 0.4" +
"Prusament PLA @MK4S", only `--binary-gcode=0`), measured by `analyse.py` (tests: `test_geom.py`). Same numbers as the
0.22.0 probe: at 2 mm raised, every row-2 stroke (designed 0.15 to 0.29 mm) is planned as one line about 0.38 mm wide and
the letters grow 44 to 56% (B's counters 61-66% open, A's 50%); at 2 mm engraved, B's upper island gets no plastic;
at 3 mm both are within 15% (raised +3 to +10%). Row 1 at 8 mm: 0.995-1.004 (the measure has no bias).

## Agent runs (`out/runs`, pass rule `out/pass_rule.json` written before run 1)
3 sealed Claude Code sessions (claude-sonnet-5-5, Claude Code 2.1.310), prompt in `claude-run/run.sh`, $0.38 in all.
Scored by `claude-run/score.py` (generic: the text layers and rows found from each run's own design; validated on the
probe's raised/engraved 2 mm (fail) and 3 mm (pass) tags).
- **3 of 3 pass.** All three raised the text and made row 2 5 to 5.5 mm tall (run 1 5.5, run 2 5.0, run 3 5.5; row 1
  8 to 8.5 mm): planned area 0.99 to 1.02 of design, every counter open, the ring hole open.
- **None measured.** All three asked for bold first (the built-in font has none; run 1 also tried a Windows font file,
  which SolidCraft refused as outside its allowed folders), then went regular and larger. Each reply estimates the
  row-2 strokes at about 0.7 mm "from the font", not measured; runs 1 and 2 say to check the slicer preview; run 3
  says they are "probably too thin" (the slicer's plan shows them within 2% of design).
