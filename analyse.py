"""P1/P3 analysis of the nametag probe ($0, no AI): for each case, at every layer inside the letter height, compare the
printed region (the G-code's extruding moves buffered by their own ;WIDTH:) with the design's section at the slicer's
slice plane (layer z - layer height / 2), per letter. Writes out/<case>/analysis.json, out/<case>/layer.png (the
headline layer: raised z 3.6, engraved z 2.8), out/results.json (one row per case) and out/preset.json.

    docker run --rm -v <probe>:/w -w /w nametag-analyse:0.1 python analyse.py

Raised: a letter = a piece of the design section above the tag top; printed = beads inside that letter's cell (points
nearer to that letter than to any other). Engraved: a letter = a slot = a piece of (tag rectangle - section), ring hole
left out; "open" = slot area with no bead on it. Counter = a hole in a raised letter (A 1, B 2); its open area = the
designed counter minus the beads. Island = the plastic inside an engraved A/B, a hole in the slot polygon."""
import json
import os
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from shapely.geometry import Point, box  # noqa: E402

import geom as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
CASES = [f'{m}-h{h}' for m in ('raised', 'engraved') for h in (2, 3, 4, 5)]
DIAG = [f'{m}-h{h}' for m in ('raised', 'engraved') for h in (1, 1.5)]   # diagnostic, below the plan's range
LINE1, LINE2 = 'ALEX', 'GYMBAG'
DESIGN_HOLES = {'A': 1, 'B': 1 + 1, 'G': 0, 'Y': 0, 'M': 0, 'L': 0, 'E': 0, 'X': 0}
MIN_PIECE = 0.01     # mm2: smaller printed or open specks are not counted as pieces
MIN_HOLE = 0.003     # mm2: a counter/opening smaller than this counts as closed
FAT_AREA = 1.15      # raised: printed / designed area above this = FAT; engraved: open / designed slot above this = FAT
NARROW_OPEN = 0.85   # engraved: open / designed slot area below this = slot narrowed (FAT for engraved)
HEADLINE = {'raised': 3.6, 'engraved': 2.8}


def footer(gcode):
    return dict(re.findall(r'^; ([^=\n]+?) = (.+)$', gcode, re.M))


def letters_at(tris, z, mode):
    s = G.section(tris, z)
    if mode == 'raised':
        L = G.parts(s, 1e-4)
    else:
        empty = box(-25, -10, 25, 10).difference(s)
        L = [p for p in G.parts(empty, 1e-4) if Point(-20, 0).distance(p) > 0.5]
    l1 = sorted([p for p in L if p.centroid.y > -0.5], key=lambda p: p.centroid.x)
    l2 = sorted([p for p in L if p.centroid.y <= -0.5], key=lambda p: p.centroid.x)
    return s, l1, l2


def per_letter(name, D, cell, P, mode, segs_in):
    pr = P.intersection(cell)
    dh = G.holes(D)                                   # counters (raised) / islands (engraved) of the design
    if mode == 'raised':
        got = pr
        ratio = got.area / D.area
        uncovered = D.difference(P)
        counters = [h.difference(P) for h in dh]
        kept = [max([p.area for p in G.parts(c)] or [0.0]) > MIN_HOLE for c in counters]
        counter_open = [round(c.area / h.area, 3) for c, h in zip(counters, dh)]
        pieces = len(G.parts(got, MIN_PIECE))
        present = got.area > MIN_PIECE
        r = {'extrusion_present': present, 'pieces': pieces, 'design_pieces': 1,
             'counters_design': len(dh), 'counters_kept': sum(kept), 'counter_open_ratio': counter_open,
             'area_ratio': round(ratio, 3), 'uncovered_frac': round(uncovered.area / D.area, 3),
             'largest_uncovered_mm2': round(max([p.area for p in G.parts(uncovered)] or [0.0]), 4)}
    else:
        inner = box(-24.7, -9.7, 24.7, 9.7)
        opn = inner.intersection(cell).difference(P)
        opn_pieces = [p for p in G.parts(opn, MIN_PIECE) if p.intersects(D)]
        # islands = the plastic inside an engraved A/B (its counters): printed if beads cover part of it
        isl_cov = [round(h.intersection(P).area / h.area, 3) for h in dh]
        isl_kept = sum(1 for h in dh if h.intersection(P).area > MIN_HOLE)
        ratio = sum(p.area for p in opn_pieces) / D.area
        present = ratio > 0.05
        r = {'slot_open': present, 'open_pieces': len(opn_pieces), 'design_pieces': 1,
             'islands_design': len(dh), 'islands_kept': isl_kept, 'island_area_printed_ratio': isl_cov,
             'island_area_mm2': [round(h.area, 4) for h in dh],
             'open_area_ratio': round(ratio, 3),
             'filled_frac': round(D.intersection(P).area / D.area, 3)}
    ws = [s[4] for s in segs_in]
    r['bead_width_min'] = round(min(ws), 3) if ws else None
    r['bead_width_max'] = round(max(ws), 3) if ws else None
    r['design_area_mm2'] = round(D.area, 4)
    r['design_break_width_mm'] = G.break_width(D)
    return r


def verdict_letter(r, mode):
    if mode == 'raised':
        if not r['extrusion_present'] or r['pieces'] > r['design_pieces'] or r['uncovered_frac'] > 0.25:
            return 'VANISH'
        if r['counters_kept'] < r['counters_design'] or r['area_ratio'] > FAT_AREA:
            return 'FAT'
        return 'FINE'
    if not r['slot_open'] or r['open_pieces'] > r['design_pieces'] or r['filled_frac'] > 0.25:
        return 'CLOSE'
    if r['islands_kept'] < r['islands_design'] or r['open_area_ratio'] < NARROW_OPEN or             r['open_area_ratio'] > FAT_AREA or any(c < 0.5 for c in r['island_area_printed_ratio']):
        return 'FAT'
    return 'FINE'


RANK = {'FINE': 0, 'FAT': 1, 'CLOSE': 2, 'VANISH': 3}


def analyse_case(case, preset):
    mode, h = case.split('-h')[0], float(case.split('-h')[1])
    d = os.path.join(OUT, case)
    tris = G.read_stl(os.path.join(d, 'tag.stl'))
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    dx, dy = cx - 125.0, cy - 105.0                 # G-code is centred at 125,105 (slice.sh --center)
    gtext = open(os.path.join(d, 'tag.gcode'), encoding='utf-8', errors='replace').read()
    layers = G.parse_gcode(gtext)
    lo, hi = (3.0, 4.0) if mode == 'raised' else (2.4, 3.0)
    lz = sorted(z for z in layers if lo < z <= hi + 1e-6)
    lh = float(preset['layer_height'])
    res = {'case': case, 'mode': mode, 'line2_cap_mm': h, 'letter_layers': lz, 'layers': {}}
    for z in lz:
        zs = round(z - lh / 2, 4)
        sec, l1, l2 = letters_at(tris, zs, mode)
        segs = [(s[0] + dx, s[1] + dy, s[2] + dx, s[3] + dy, s[4], s[5]) for s in layers[z]]
        P = G.beads(segs)
        allL = l1 + l2
        names = list(LINE1) + list(LINE2)
        ext = box(-25, -10, 25, 10)
        cells = G.owner_cells(allL, ext)
        rows = {}
        for i, (D, cell) in enumerate(zip(allL, cells)):
            nm = (names[i] if len(allL) == len(names) else f'#{i}') + ('1' if i < len(l1) else '2') + f'_{i}'
            sin = [s for s in segs if cell.contains(Point((s[0] + s[2]) / 2, (s[1] + s[3]) / 2))]
            r = per_letter(nm, D, cell, P, mode, sin)
            r['letter'] = names[i] if len(allL) == len(names) else None
            r['line'] = 1 if i < len(l1) else 2
            r['verdict'] = verdict_letter(r, mode)
            rows[nm] = r
        lay = {'slice_z': zs, 'n_design_letters': [len(l1), len(l2)], 'letters': rows}
        if mode == 'raised':      # merged letters: one printed piece touching two designed letters (line 2)
            band = box(-25, -10, 25, -0.5)
            pcs = G.parts(P.intersection(band), MIN_PIECE)
            lay['line2_printed_pieces'] = len(pcs)
            lay['line2_merged_pieces'] = sum(1 for p in pcs if sum(1 for D in l2 if p.intersection(D).area > 0.005) > 1)
        res['layers'][str(z)] = lay
        if abs(z - HEADLINE[mode]) < 1e-6:
            plot(case, mode, h, z, zs, sec, allL, P, rows, os.path.join(d, 'layer.png'))
    hl = res['layers'][str(HEADLINE[mode])]
    res['headline_layer'] = HEADLINE[mode]
    res['summary'] = summarise(hl, mode)
    res['worst_over_letter_layers'] = max((summarise(v, mode)['verdict'] for v in res['layers'].values()),
                                          key=lambda v: RANK[v])
    with open(os.path.join(d, 'analysis.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, indent=1)
    return res


def summarise(lay, mode):
    for k, r in lay['letters'].items():
        r['id'] = k                  # letter + line + index, e.g. A2_8 (A on line 2): letters repeat across lines
    l2 = [r for r in lay['letters'].values() if r['line'] == 2]
    l1 = [r for r in lay['letters'].values() if r['line'] == 1]
    key = 'area_ratio' if mode == 'raised' else 'open_area_ratio'
    s = {'n_letters_found': lay['n_design_letters'],
         'line2_area_ratio_range': [min(r[key] for r in l2), max(r[key] for r in l2)] if l2 else None,
         'line1_area_ratio_range': [min(r[key] for r in l1), max(r[key] for r in l1)] if l1 else None,
         'line2_letter_verdicts': ''.join(f"{r['id']}:{r['verdict']} " for r in l2).strip()}
    if mode == 'raised':
        s['vanished'] = [r['id'] for r in l2 + l1 if r['verdict'] == 'VANISH']
        s['counters_closed'] = [f"{r['id']}({r['counters_design'] - r['counters_kept']} of {r['counters_design']})"
                                for r in l2 + l1 if r['counters_kept'] < r['counters_design']]
        s['counter_open_ratio'] = {r['id']: r['counter_open_ratio'] for r in l2 + l1 if r['counters_design']}
        s['line2_merged_pieces'] = lay.get('line2_merged_pieces')
        s['closed'] = []
    else:
        s['vanished'] = []
        s['closed'] = [r['id'] for r in l2 + l1 if r['verdict'] == 'CLOSE']
        s['counters_closed'] = [f"{r['id']}(island lost {r['islands_design'] - r['islands_kept']} of {r['islands_design']})"
                                for r in l2 + l1 if r['islands_kept'] < r['islands_design']]
        s['island_area_printed_ratio'] = {r['id']: r['island_area_printed_ratio'] for r in l2 + l1 if r['islands_design']}
        s['line2_filled_frac_max'] = max(r['filled_frac'] for r in l2) if l2 else None
    s['line2_design_break_width_mm'] = {r['id']: r['design_break_width_mm'] for r in l2}
    s['line2_bead_width_range'] = [min(r['bead_width_min'] for r in l2 if r['bead_width_min']),
                                   max(r['bead_width_max'] for r in l2 if r['bead_width_max'])] if l2 else None
    vs = [r['verdict'] for r in l2 + l1]
    s['verdict'] = max(vs, key=lambda v: RANK[v]) if vs else 'NO LETTERS'
    s['line2_all_pieces_and_counters_kept'] = all(
        (r['pieces'] == 1 and r['counters_kept'] == r['counters_design'] and r['extrusion_present']) if mode == 'raised'
        else (r['open_pieces'] == 1 and r['islands_kept'] == r['islands_design'] and r['slot_open'] and min(r['island_area_printed_ratio'] or [1]) >= 0.5) for r in l2) \
        and len(l2) == 6
    return s


def draw(ax, g, **kw):
    for p in G.parts(g):
        for ring in [p.exterior] + list(p.interiors):
            x, y = ring.xy
            ax.plot(x, y, **kw)


def fill(ax, g, **kw):
    for p in G.parts(g):
        x, y = p.exterior.xy
        ax.fill(x, y, **kw)
        for r in p.interiors:
            x, y = r.xy
            ax.fill(x, y, color='white')


def plot(case, mode, h, z, zs, sec, letters, P, rows, path):
    fig, axs = plt.subplots(2, 1, figsize=(12, 9), gridspec_kw={'height_ratios': [1, 0.9]})
    l2 = [L for L in letters if L.centroid.y <= -0.5]
    for k, ax in enumerate(axs):
        fill(ax, P, color='#f0a030', alpha=0.85, lw=0)
        for L in letters:
            draw(ax, L, color='#1040c0' if mode == 'engraved' else 'black', lw=0.9)
        ax.set_aspect('equal')
        if k == 0:
            ax.set_xlim(-25.5, 25.5); ax.set_ylim(-10.5, 10.5)
            ax.set_title(f'{case}: layer z {z} (slice plane {zs}), whole tag. Orange = printed beads at their ;WIDTH:; '
                         f'lines = designed {"letter" if mode == "raised" else "slot"} outline', fontsize=9)
        else:
            if l2:
                x0 = min(L.bounds[0] for L in l2) - 0.6; x1 = max(L.bounds[2] for L in l2) + 0.6
                y0 = min(L.bounds[1] for L in l2) - 0.6; y1 = max(L.bounds[3] for L in l2) + 0.6
                ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
            r2 = [r for r in rows.values() if r['line'] == 2]
            key = 'area_ratio' if mode == 'raised' else 'open_area_ratio'
            ax.set_title('line 2 "GYM BAG" cap %g mm, zoom. ' % h +
                         '  '.join(f"{r['letter']}:{r['verdict']} {key.split('_')[0]} {r[key]}" for r in r2), fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    g0 = open(os.path.join(OUT, CASES[0], 'tag.gcode'), encoding='utf-8', errors='replace').read()
    ft = footer(g0)
    keys = ['print_settings_id', 'filament_settings_id', 'printer_settings_id', 'perimeter_generator', 'min_feature_size',
            'min_bead_width', 'extrusion_width', 'perimeter_extrusion_width', 'external_perimeter_extrusion_width',
            'top_infill_extrusion_width', 'solid_infill_extrusion_width', 'infill_extrusion_width',
            'first_layer_extrusion_width', 'slice_closing_radius', 'thin_walls', 'perimeters', 'top_solid_layers',
            'layer_height', 'first_layer_height', 'nozzle_diameter', 'binary_gcode', 'arc_fitting',
            'wall_transition_length', 'wall_transition_angle', 'wall_distribution_count',
            'wall_transition_filter_deviation', 'gcode_resolution', 'elefant_foot_compensation', 'xy_size_compensation']
    preset = {k: ft.get(k) for k in keys}
    preset['_source'] = 'the G-code footer of out/raised-h2/tag.gcode (what the slicer actually used)'
    preset['_resolved_mm_at_nozzle_0.4'] = {'min_feature_size': 0.25 * 0.4, 'min_bead_width': 0.85 * 0.4}
    preset['_slicer'] = open(os.path.join(OUT, 'slicer-version.txt')).read().strip().splitlines()
    with open(os.path.join(OUT, 'preset.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(preset, f, indent=1)
    rows = []
    for c in CASES + DIAG:
        r = analyse_case(c, preset)
        rows.append({'case': c, 'diagnostic': c in DIAG, **r['summary'], 'worst_over_letter_layers': r['worst_over_letter_layers'],
                     'letter_layers': r['letter_layers']})
        print(c, json.dumps(r['summary']), 'worst', r['worst_over_letter_layers'], flush=True)
    with open(os.path.join(OUT, 'results.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rows, f, indent=1)


if __name__ == '__main__':
    main()
