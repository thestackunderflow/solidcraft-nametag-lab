"""Resolve a stock PrusaSlicer system preset from the vendor bundle (e.g. /usr/share/PrusaSlicer/profiles/
PrusaResearch.ini) into one flat config file for `prusa-slicer --load`, because the headless CLI in our image can't
load bundled presets by name (no datadir). Parents in `inherits = a; b` apply left to right (later wins), then the
preset's own keys. Bookkeeping keys (inherits, compatible_*, renamed_from, alias) are dropped.

    python3 resolve_preset.py BUNDLE.ini "PRINT" "FILAMENT" "PRINTER" > config.ini"""
import sys

DROP = {'inherits', 'compatible_printers', 'compatible_printers_condition', 'compatible_prints',
        'compatible_prints_condition', 'renamed_from', 'alias'}


def parse(text):
    secs, cur = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue
        if line.startswith('[') and line.endswith(']'):
            cur = line[1:-1]
            secs[cur] = {}
            continue
        if cur is not None and ' = ' in raw or (cur is not None and '=' in line):
            k, v = line.split('=', 1)
            secs[cur][k.strip()] = v.strip()
    return secs


def resolve(secs, kind, name, _seen=None):
    key = f'{kind}:{name}'
    if key not in secs:
        raise KeyError(key)
    seen = (_seen or set()) | {key}
    own = secs[key]
    out = {}
    for parent in [p.strip() for p in own.get('inherits', '').split(';') if p.strip()]:
        if f'{kind}:{parent}' in seen:
            raise ValueError('inherits loop at ' + parent)
        out.update(resolve(secs, kind, parent, seen))
    out.update(own)
    return {k: v for k, v in out.items() if k not in DROP}


def flat_config(secs, print_name, filament_name, printer_name):
    merged = {}
    for kind, name in (('printer', printer_name), ('filament', filament_name), ('print', print_name)):
        if name:
            merged.update(resolve(secs, kind, name))
            merged[f'{kind}_settings_id'] = name     # so the G-code names the preset it came from
    head = f'# resolved: print "{print_name}", filament "{filament_name}", printer "{printer_name}"\n'
    return head + '\n'.join(f'{k} = {v}' for k, v in sorted(merged.items())) + '\n'


if __name__ == '__main__':
    bundle, pr, fi, pt = sys.argv[1:5]
    sys.stdout.write(flat_config(parse(open(bundle, encoding='utf-8').read()), pr, fi, pt))
