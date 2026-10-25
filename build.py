"""P4 + design step of the nametag probe (no AI, $0): build the keychain tag in SolidCraft 0.22.1 headless over MCP
(solidcraft-cli mcp), with sketch.text + solid.emboss (emboss = raised 1 mm, deboss = engraved 0.6 mm), and export one STL
per case. Also records the sketch.text defaults (font) and whether the text stays editable (sketch.edit_text).

    docker run --rm -v <probe>:/w -v <probe>/out:/lab/out -w /w solidcraft-nametag-lab:0.22.1 python3 build.py [CASE ...]

Case names: raised-h2 .. raised-h5, engraved-h2 .. engraved-h5 (h = line-2 cap height in mm).
Tag: 50 x 20 x 3 mm box centred on the origin (x -25..25, y -10..10, z 0..3), ring hole d 4 at x -20.
Line 1 "ALEX" cap 8 mm, baseline y 0.5 (cap top 8.5). Line 2 "GYM BAG" cap h, cap top y -1.0 (baseline -1 - h).
Both lines start at x -16 (ring hole edge at -18)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import McpClient  # noqa: E402  (a copy of solidcraft-tipping-lab/tests/mcp_client.py)

OUT = '/lab/out'
X0 = -16.0
CASES = {f'{m}-h{h}': dict(mode=m, h=float(h)) for m in ('raised', 'engraved') for h in (2, 3, 4, 5)}
EXTRA = {f'{m}-h{h}': dict(mode=m, h=float(h)) for m in ('raised', 'engraved') for h in (1, 1.5)}   # diagnostic only
CASES.update(EXTRA)


def call(m, name, args):
    r = m.call_tool(name, args)
    t = '\n'.join(b.get('text', '') for b in r.get('content', []) if b.get('type') == 'text')
    try:
        return json.loads(t)
    except Exception:
        return t


def steps(mode, h):
    emb = {'emboss': 'emboss', 'deboss': 'deboss'}
    depth = 1.0 if mode == 'raised' else 0.6
    return [
        {'command': 'solid.box', 'params': {'corner': [-25, -10, 0], 'length': 50, 'width': 20, 'height': 3,
                                            'body_name': 'Tag'}},
        {'command': 'solid.hole', 'params': {'position': [-20, 0, 3], 'diameter': 4, 'targets': ['Tag']}},
        {'command': 'sketch.create', 'params': {'plane': 'XY', 'offset': 3, 'name': 'Name'}},
        {'command': 'sketch.text', 'params': {'text': 'ALEX', 'at': [X0, 0.5], 'height': 8}},
        {'command': 'sketch.text', 'params': {'text': 'GYM BAG', 'at': [X0, -1.0 - h], 'height': h}},
        {'command': 'sketch.finish', 'params': {}},
        {'command': 'solid.emboss', 'params': {'sketch': 'Name', 'depth': depth,
                                               'mode': emb['emboss' if mode == 'raised' else 'deboss'],
                                               'targets': ['Tag']}},
    ]


def build(name, spec):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    m = McpClient(['solidcraft-cli', 'mcp', '--allow-path', OUT], timeout_s=240)
    m.start()
    res = {'case': name, 'spec': spec, 'server': m.init_result.get('serverInfo') if isinstance(m.init_result, dict) else None}
    try:
        res['new_design'] = call(m, 'new_design', {'name': name})
        res['batch'] = call(m, 'batch', {'commands': steps(spec['mode'], spec['h'])})
        res['sketch_inspect'] = call(m, 'execute', {'command': 'sketch.inspect', 'params': {'sketch': 'Name'}})
        res['measure'] = call(m, 'measure', {})
        res['export'] = call(m, 'export', {'path': f'{d}/tag.stl', 'bodies': ['Tag']})
        res['save'] = call(m, 'save', {'path': f'{d}/tag.solidcraft'})
    except Exception as e:  # recorded, not hidden
        res['error'] = repr(e)
    finally:
        m.close()
    with open(os.path.join(d, 'build.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, indent=1, default=str)
    b = res.get('batch')
    print(name, 'ok' if isinstance(b, dict) and b.get('ok', True) and 'error' not in res else 'FAIL',
          str(b)[:300] if not (isinstance(b, dict) and b.get('ok', True)) else '', res.get('error', ''), flush=True)


def edit_check():
    """Is the text editable after the emboss? Build raised h5, then sketch.edit + sketch.edit_text (GYM BAG to 3 mm),
    and compare the rebuilt body with a direct raised-h3 build (out/raised-h3/build.json)."""
    d = os.path.join(OUT, 'editcheck')
    os.makedirs(d, exist_ok=True)
    m = McpClient(['solidcraft-cli', 'mcp', '--allow-path', OUT], timeout_s=240)
    m.start()
    res = {}
    try:
        call(m, 'new_design', {'name': 'editcheck'})
        b = call(m, 'batch', {'commands': steps('raised', 5.0)})
        link = b['results'][4]['link']
        res['link_line2'] = link
        res['before'] = call(m, 'measure', {})['total']
        res['edit'] = call(m, 'batch', {'commands': [
            {'command': 'sketch.edit', 'params': {'sketch': 'Name'}},
            {'command': 'sketch.edit_text', 'params': {'link': link, 'height': 3, 'at': [X0, -4.0]}},
            {'command': 'sketch.finish', 'params': {}}]})
        res['after'] = call(m, 'measure', {})['total']
        ref = json.load(open(os.path.join(OUT, 'raised-h3', 'build.json')))['measure']['total']
        res['direct_raised_h3'] = ref
        res['volume_match_mm3'] = abs(res['after']['volume_mm3'] - ref['volume_mm3'])
        res['editable'] = res['volume_match_mm3'] < 1e-3
    except Exception as e:
        res['error'] = repr(e)
    finally:
        m.close()
    with open(os.path.join(d, 'editcheck.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, indent=1, default=str)
    print('editcheck', res.get('editable'), res.get('volume_match_mm3'), res.get('error', ''))


if __name__ == '__main__':
    args = sys.argv[1:] or [c for c in CASES if c not in EXTRA] + ['editcheck']
    for n in args:
        edit_check() if n == 'editcheck' else build(n, CASES[n])
