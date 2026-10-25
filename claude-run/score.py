"""Score a nametag-lab run against out/pass_rule.json (written before run 1). Steps, each in the image with its tool:

  python3 claude-run/score.py export /lab/s      (SolidCraft image): open the run's saved design, export every body
                                                 -> score/tag.stl, the bodies, the text commands it sent
  bash claude-run/slice_run.sh out/runs/run-N    (slicer image): stock presets, --binary-gcode=0 -> score/tag.gcode
  python claude-run/score.py measure /lab/s      (analysis image, shapely): the text layers found from the run's own
                                                 design, per-letter metrics as in the probe (analyse.py) -> score.json
  python claude-run/score.py table               -> out/runs/SCORES.json

Generic version of the probe's analysis: the tag is wherever the run put it. The tag top is the highest z where the
section still covers most of the tag's outline; raised text = the pieces above it, engraved text = the slots below it.
Rows = the letter pieces split at the biggest gap in y; row 2 = the row with the smaller letters."""
import glob
import json
import os
import re
import sys

LAB = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, LAB)


def export(s):
    sys.path.insert(0, LAB)
    from mcp_client import McpClient
    d = os.path.join(s, 'score')
    os.makedirs(d, exist_ok=True)
    m = McpClient(['solidcraft-cli', 'mcp', '--allow-path', s], timeout_s=240)
    m.start()

    def call(n, a):
        r = m.call_tool(n, a)
        t = '\n'.join(b.get('text', '') for b in r.get('content', []) if b.get('type') == 'text')
        try:
            return json.loads(t)
        except Exception:
            return t
    info = {}
    try:
        info['open'] = call('open', {'path': os.path.join(s, 'work', 'tag.solidcraft')})
        info['measure'] = call('measure', {})
        info['export'] = call('export', {'path': f'{d}/tag.stl', 'format': 'stl'})
    finally:
        m.close()
    json.dump(info, open(os.path.join(d, 'export.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)


def text_calls(s):
    out = []
    if not os.path.exists(os.path.join(s, 'transcript.jsonl')):
        return out
    for line in open(os.path.join(s, 'transcript.jsonl'), encoding='utf-8'):
        d = json.loads(line)
        m = d.get('msg')
        if isinstance(m, dict) and m.get('method') == 'tools/call':
            a = (m.get('params') or {}).get('arguments') or {}
            for c in [a] + (a.get('commands') if isinstance(a.get('commands'), list) else []):
                if isinstance(c, dict) and c.get('command') in ('sketch.text', 'solid.emboss', 'sketch.edit_text'):
                    out.append({'seq': d['seq'], 'command': c['command'], 'params': c.get('params')})
    return out


def measure(s):
    from shapely.geometry import Point, box
    from shapely.ops import unary_union
    import geom as G
    import analyse as A
    d = os.path.join(s, 'score')
    rule = json.load(open(os.path.join(LAB, 'out', 'pass_rule.json'), encoding='utf-8'))
    res = {'rule': rule['written']}
    ex = json.load(open(os.path.join(d, 'export.json'), encoding='utf-8'))
    bodies = (ex.get('measure') or {}).get('bodies', []) if isinstance(ex.get('measure'), dict) else []
    res['bodies'] = [b.get('name') for b in bodies]
    tris = G.read_stl(os.path.join(d, 'tag.stl'))
    zs = [p[2] for t in tris for p in t]
    z0, z1 = min(zs), max(zs)
    full = G.section(tris, z0 + 0.25)
    tag_area = full.area
    outline = unary_union([G.Polygon(p.exterior) for p in G.parts(full)]) if hasattr(G, 'Polygon') else full
    # the tag top: sample upward; raised text starts where the section drops well below the tag's area
    step, ztop, mode = 0.05, None, None
    z = z0 + 0.25
    prev = tag_area
    while z < z1:
        a = G.section(tris, z).area
        if a < 0.6 * tag_area and mode is None:
            ztop, mode = z - step, 'raised'
            break
        if a < 0.995 * tag_area and mode is None:
            mode, zslot = 'engraved', z
        prev = a
        z += step
    if mode == 'raised':
        lo, hi = ztop, z1
    elif mode == 'engraved':
        lo, hi = zslot - step, z1
    else:
        res.update({'pass': False, 'why': ['no text layers found']})
        json.dump(res, open(os.path.join(s, 'score.json'), 'w'), indent=1)
        return
    res.update({'mode': mode, 'tag_z': [round(z0, 3), round(ztop if ztop else lo, 3)], 'text_z': [round(lo, 3), round(hi, 3)]})
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    dx, dy = cx - 125.0, cy - 105.0
    gtext = open(os.path.join(d, 'tag.gcode'), encoding='utf-8', errors='replace').read()
    layers = G.parse_gcode(gtext)
    lh = 0.2
    lz = sorted(zz for zz in layers if lo + 1e-6 < zz - lh / 2 and zz <= hi + 1e-6)
    # the key-ring hole: the largest hole of the tag's outline at mid-tag height
    mid = G.section(tris, (z0 + (ztop if ztop else lo)) / 2)
    holes = sorted([h for p in G.parts(mid) for h in G.holes(p)], key=lambda h: -h.area)
    ring = holes[0] if holes else None
    res['ring_hole_mm2'] = round(ring.area, 3) if ring else None
    tag_poly = unary_union([p for p in G.parts(full)])
    tag_box = tag_poly.envelope
    res['layers'] = {}
    worst = 'FINE'
    counts_ok = True
    for zz in lz:
        zs_ = round(zz - lh / 2, 4)
        sec = G.section(tris, zs_)
        if mode == 'raised':
            L = G.parts(sec, 1e-4)
        else:
            empty = tag_poly.buffer(-0.05).difference(sec)
            L = [p for p in G.parts(empty, 1e-4) if not (ring and p.buffer(0.01).intersects(ring) and p.area > 0.7 * ring.area)]
        L = [p for p in L if p.area > 0.02]
        ys_ = sorted(p.centroid.y for p in L)
        if len(ys_) < 2:
            counts_ok = False
            continue
        gaps = [(ys_[i + 1] - ys_[i], i) for i in range(len(ys_) - 1)]
        g, i = max(gaps)
        cut = (ys_[i] + ys_[i + 1]) / 2
        top = sorted([p for p in L if p.centroid.y > cut], key=lambda p: p.centroid.x)
        bot = sorted([p for p in L if p.centroid.y <= cut], key=lambda p: p.centroid.x)
        hgt = lambda r: sorted(p.bounds[3] - p.bounds[1] for p in r)[len(r) // 2] if r else 0  # noqa: E731
        row1, row2 = (top, bot) if hgt(top) >= hgt(bot) else (bot, top)
        segs = [(sg[0] + dx, sg[1] + dy, sg[2] + dx, sg[3] + dy, sg[4], sg[5]) for sg in layers[zz]]
        P = G.beads(segs)
        cells = G.owner_cells(row1 + row2, tag_box.buffer(1))
        rows = {}
        A_inner = box(*tag_poly.buffer(-0.3).bounds)
        for k, (D, cell) in enumerate(zip(row1 + row2, cells)):
            sin = [sg for sg in segs if cell.contains(Point((sg[0] + sg[2]) / 2, (sg[1] + sg[3]) / 2))]
            if mode == 'engraved':
                A.box = lambda *a, _b=A_inner: _b      # the probe's inner tag box, here the run's own tag
            r = A.per_letter(f'#{k}', D, cell, P, mode, sin)
            r['line'] = 1 if k < len(row1) else 2
            r['verdict'] = A.verdict_letter(r, mode)
            rows[f'{r["line"]}_{k}'] = r
        ring_open = None
        if ring is not None:
            ring_open = round(ring.difference(P).area / ring.area, 3)
        lay = {'slice_z': zs_, 'pieces': [len(row1), len(row2)], 'row_cap_mm': [round(hgt(row1), 3), round(hgt(row2), 3)],
               'letters': rows}
        res['layers'][str(zz)] = lay
        if [len(row1), len(row2)] != [4, 6]:
            counts_ok = False
        for r in rows.values():
            if A.RANK[r['verdict']] > A.RANK[worst]:
                worst = r['verdict']
    # the ring hole through the tag's own layers
    ring_ok = True
    if ring is not None:
        for zz in sorted(layers):
            if zz <= lo + 1e-6:
                segs = [(sg[0] + dx, sg[1] + dy, sg[2] + dx, sg[3] + dy, sg[4], sg[5]) for sg in layers[zz]]
                if ring.difference(G.beads(segs)).area < 0.5 * ring.area:
                    ring_ok = False
    else:
        ring_ok = False
    l2 = [r for lay in res['layers'].values() for r in lay['letters'].values() if r['line'] == 2]
    key = 'area_ratio' if mode == 'raised' else 'open_area_ratio'
    res['row2_ratio_range'] = [min(r[key] for r in l2), max(r[key] for r in l2)] if l2 else None
    res['row_cap_mm'] = next(iter(res['layers'].values()))['row_cap_mm'] if res['layers'] else None
    why = []
    if len(res['bodies']) > 1:
        why.append(f'{len(res["bodies"])} bodies: the text is a separate body')
    if not counts_ok:
        why.append('letter counts do not match ALEX (4) and GYM BAG (6) on every text layer')
    if worst != 'FINE':
        why.append(f'worst letter verdict {worst}')
    if not ring_ok:
        why.append('key-ring hole not open on every layer')
    res['worst_verdict'] = worst
    res['ring_hole_open'] = ring_ok
    res['pass'] = not why
    res['why'] = why or ['pass']
    res['text_calls'] = text_calls(s)
    for line in (open(os.path.join(s, 'session.jsonl'), encoding='utf-8') if os.path.exists(os.path.join(s, 'session.jsonl')) else []):
        dd = json.loads(line)
        if dd.get('type') == 'result':
            res['final_reply'], res['cost_usd'] = dd.get('result', ''), dd.get('total_cost_usd')
    json.dump(res, open(os.path.join(s, 'score.json'), 'w', encoding='utf-8', newline='\n'), indent=1, ensure_ascii=False)
    print(os.path.basename(s), mode, res['row_cap_mm'], res['row2_ratio_range'], res['why'])


def table():
    rows = []
    for s in sorted(glob.glob(os.path.join(LAB, 'out', 'runs', 'run-*'))):
        f = os.path.join(s, 'score.json')
        if os.path.exists(f):
            r = json.load(open(f, encoding='utf-8'))
            rows.append({k: r.get(k) for k in ('pass', 'why', 'mode', 'row_cap_mm', 'row2_ratio_range', 'worst_verdict',
                                                'ring_hole_open', 'bodies', 'cost_usd', 'text_z', 'tag_z')} |
                        {'run': os.path.basename(s), 'final_reply': (r.get('final_reply') or '')[:1200],
                         'text_calls': r.get('text_calls')})
    json.dump(rows, open(os.path.join(LAB, 'out', 'runs', 'SCORES.json'), 'w', encoding='utf-8', newline='\n'),
              indent=1, ensure_ascii=False)
    for r in rows:
        print(r['run'], r['pass'], r['mode'], r['row_cap_mm'], r['row2_ratio_range'], r['why'])


if __name__ == '__main__':
    {'export': lambda: export(sys.argv[2]), 'measure': lambda: measure(sys.argv[2]), 'table': table}[sys.argv[1]]()
