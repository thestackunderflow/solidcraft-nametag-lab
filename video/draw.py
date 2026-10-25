"""The video's pictures, drawn from the lab's own files (no AI): the design's letters cut at the text layer (from the
STL) and the slicer's planned lines at that layer (from the G-code, each line at its own ;WIDTH:), as in analyse.py.
Cards 1632 x 1200 (the split slide's picture box at 2x); hook pictures 1920 x 1080 and 1080 x 1920.
    docker run --rm -v "$PWD:/w" -w /w nametag-analyse:0.1 python video/draw.py"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon as MPoly  # noqa: E402
from shapely.geometry import box  # noqa: E402

LAB = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, LAB)
import geom as G  # noqa: E402

F = os.path.join(LAB, 'video', 'frames')
os.makedirs(F, exist_ok=True)
BG, INK, RED, GREEN, GREY, BLUE, ORANGE = '#eceff4', '#1f2937', '#b71c1c', '#1b7f3b', '#8a94a6', '#1d4ed8', '#e8902a'
W, H = 1632, 1200
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.weight': 'bold'})
RES = {r['case']: r for r in json.load(open(os.path.join(LAB, 'out', 'results.json')))}


def fig(w=W, h=H):
    f = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    f.patch.set_facecolor(BG)
    return f


def text(f, x, y, s, size=64, color=INK, ha='center', va='top'):
    f.text(x / f.bbox.width * 100 / 100 if False else x / (f.get_figwidth() * 100), 1 - y / (f.get_figheight() * 100), s,
           fontsize=size * 0.72, color=color, ha=ha, va=va, fontweight='bold')


def save(f, name):
    f.savefig(os.path.join(F, name), dpi=100, facecolor=BG)
    plt.close(f)


def layer(case, z):
    """Design pieces (letters, or the plastic between engraved slots) and the planned beads at G-code layer z."""
    d = os.path.join(LAB, 'out', case)
    tris = G.read_stl(os.path.join(d, 'tag.stl'))
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    dx, dy = (min(xs) + max(xs)) / 2 - 125.0, (min(ys) + max(ys)) / 2 - 105.0
    layers = G.parse_gcode(open(os.path.join(d, 'tag.gcode'), encoding='utf-8', errors='replace').read())
    sec = G.section(tris, round(z - 0.1, 4))
    segs = [(s[0] + dx, s[1] + dy, s[2] + dx, s[3] + dy, s[4], s[5]) for s in layers[z]]
    return sec, G.beads(segs)


def draw_geom(ax, g, fc=None, ec=INK, lw=1.5, alpha=1.0, z=1):
    """Fill each polygon with its holes left open (one compound path per polygon, even-odd), so a hole never paints over
    another polygon lying inside it (e.g. the plastic island inside an engraved B's groove)."""
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    for p in G.parts(g):
        rings = [p.exterior] + list(p.interiors)
        if fc:
            verts, codes = [], []
            for ring in rings:
                xy = list(ring.coords)
                verts += xy
                codes += [Path.MOVETO] + [Path.LINETO] * (len(xy) - 2) + [Path.CLOSEPOLY]
            ax.add_patch(PathPatch(Path(verts, codes), fc=fc, ec='none', alpha=alpha, zorder=z))
        for ring in rings:
            x, y = ring.xy
            ax.plot(x, y, color=ec, lw=lw, zorder=z + 1)


def panel(f, rect, case, z, window, show_design=True, show_plan=True, mode='raised', bar=False, islands=False, outline_only=False):
    ax = f.add_axes(rect)
    ax.set_facecolor('white')
    sec, P = layer(case, z)
    win = box(*window)
    if mode == 'engraved':
        tag = box(-25, -10, 25, 10)
        if show_plan:
            draw_geom(ax, P.intersection(win), fc=ORANGE, ec=ORANGE, lw=0.5)
        if show_design:
            draw_geom(ax, tag.difference(sec).intersection(win), ec=BLUE, lw=2.5)
    else:
        if show_plan:
            draw_geom(ax, P.intersection(win), fc=ORANGE, ec=ORANGE, lw=0.5, alpha=0.9)
        if show_design:
            draw_geom(ax, sec.intersection(win), fc=None if (show_plan or outline_only) else INK, ec=INK, lw=2.5, z=3)
    if islands and mode == 'engraved':
        slots = [q for q in G.parts(box(-25, -10, 25, 10).difference(sec)) if q.intersects(win) and q.area < 20]
        isl = sorted([h for q in slots for h in G.holes(q) if h.intersects(win) and h.within(win.buffer(0.01))],
                     key=lambda h: -h.centroid.y)
        for k, h in enumerate(isl[:2]):
            x, y = h.exterior.xy
            got = h.intersection(P).area / h.area
            ax.plot(x, y, color=RED if got < 0.5 else GREEN, lw=4, ls='--', zorder=6)
            ax.text(h.centroid.x, h.centroid.y, 'skipped' if got < 0.5 else 'printed', color=RED if got < 0.5 else GREEN,
                    fontsize=22, fontweight='bold', ha='center', va='center', zorder=7,
                    bbox=dict(fc='white', ec='none', alpha=0.8, pad=1))
    if bar:
        x0, y0 = window[0] + 0.08, window[1] + 0.08
        from matplotlib.patches import Circle
        ax.add_patch(Circle((x0 + 0.2, y0 + 0.2), 0.2, fc=RED, ec='none', zorder=8))
        ax.text(x0 + 0.48, y0 + 0.2, '0.4 mm tip', color=RED, fontsize=22, fontweight='bold', va='center', zorder=8)
    ax.set_xlim(window[0], window[2])
    ax.set_ylim(window[1], window[3])
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(GREY)
    return ax


ROW2 = {2: (-16.4, -3.6, 1.0, -0.6), 3: (-16.4, -4.6, 6.0, -0.6), 5: (-16.4, -6.6, 15.0, -0.6)}
def letter_window(case, z, k=3, pad=0.35):
    """The k-th letter of row 2 (G Y M B A G: k = 3 is the B), from the design's own section."""
    sec, _ = layer(case, z)
    tag = box(-25, -10, 25, 10)
    pieces = G.parts(sec if case.startswith('raised') else tag.difference(sec), 1e-3)
    row2 = sorted([p for p in pieces if p.centroid.y < -0.5 and p.area < 20], key=lambda p: p.centroid.x)
    x0, y0, x1, y1 = row2[k].bounds
    nxt = row2[k + 1].bounds[0] if k + 1 < len(row2) else x1 + pad
    return (x0 - pad, y0 - pad - 0.5, min(x1 + pad, (x1 + nxt) / 2), y1 + pad)   # stop before the next letter; room for the bar


B2 = None


def r2(case):
    return RES[case]['line2_area_ratio_range']


def hook(w, h, name, vertical=False):
    f = fig(w, h)
    lo, hi = r2('raised-h2')
    if vertical:
        text(f, w / 2, 60, 'Small letters,', 76)
        text(f, w / 2, 160, 'planned fat', 84, RED)
        bw = letter_window('raised-h2', 3.6)
        panel(f, [0.25, 0.555, 0.5, 0.27], 'raised-h2', 3.6, bw, show_plan=False)    # y 345..864 px
        text(f, w / 2, 885, 'the B, as designed', 50, INK)
        panel(f, [0.25, 0.235, 0.5, 0.27], 'raised-h2', 3.6, bw)                     # y 955..1469 px
        text(f, w / 2, 1500, f"the slicer's plan: +{(lo - 1) * 100:.0f} to +{(hi - 1) * 100:.0f}%", 50, RED)
        text(f, w / 2, 1600, '2 mm letters · slicer plan, not a print', 38, GREY)
    else:
        text(f, w / 2, 40, f"2 mm letters: planned {(lo - 1) * 100:.0f}-{(hi - 1) * 100:.0f}% fatter", 64, RED)
        bw = letter_window('raised-h2', 3.6)
        panel(f, [0.08, 0.17, 0.38, 0.6], 'raised-h2', 3.6, bw, show_plan=False)
        panel(f, [0.54, 0.17, 0.38, 0.6], 'raised-h2', 3.6, bw)
        text(f, w * 0.27, 140, 'the B, as designed', 46)
        text(f, w * 0.73, 140, "the slicer's plan (orange)", 46, ORANGE)
        text(f, w / 2, 1000, "the B of GYM BAG, 2 mm tall · slicer plan, not a print", 34, GREY)
    save(f, name)


def card_simple(name, title, sub, case, z, window, plan=True, mode='raised', footer=None, design=True):
    f = fig()
    text(f, W / 2, 40, title, 64)
    if sub:
        text(f, W / 2, 130, sub, 46, GREY)
    panel(f, [0.05, 0.18, 0.9, 0.62], case, z, window, show_plan=plan, mode=mode, show_design=design)
    if footer:
        text(f, W / 2, 1110, footer, 40, GREY)
    save(f, name)


def strokes():
    f = fig()
    a = json.load(open(os.path.join(LAB, 'out', 'raised-h2', 'analysis.json')))
    lay = a['layers']['3.6']['letters']
    l2 = [r for r in lay.values() if r['line'] == 2]
    text(f, W / 2, 40, "Thinnest stroke, 2 mm letters", 60)
    text(f, W / 2, 130, 'our measuring program, our 2 mm tag', 40, GREY)
    ax = f.add_axes([0.12, 0.15, 0.8, 0.65])
    ax.set_facecolor(BG)
    names = [r['letter'] for r in l2]
    vals = [r['design_break_width_mm'] for r in l2]
    ax.barh(range(len(vals)), vals, color=INK, height=0.6)
    ax.axvline(0.4, color=RED, lw=5)
    ax.text(0.405, len(vals) - 0.4, '0.4 mm tip', color=RED, fontsize=34, fontweight='bold')
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(names, fontsize=40)
    ax.invert_yaxis()
    ax.set_xlim(0, 0.6)
    ax.tick_params(axis='x', labelsize=28)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    for i, v in enumerate(vals):
        ax.text(v + 0.01, i, f'{v:.2f}', va='center', fontsize=32, fontweight='bold', color=INK)
    save(f, 'card-strokes.png')


def lines():
    f = fig()
    pre = json.load(open(os.path.join(LAB, 'out', 'preset.json')))
    ax = f.add_axes([0.05, 0.2, 0.9, 0.6])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis('off')
    sc = 4.0
    ax.add_patch(FancyBboxPatch((0.5, 2.6), 4.6, 0.45 * sc / 2, boxstyle='round,pad=0,rounding_size=0.4', fc=ORANGE, ec='none'))
    ax.add_patch(FancyBboxPatch((0.5, 0.9), 4.6, 0.36 * sc / 2, boxstyle='round,pad=0,rounding_size=0.35', fc=ORANGE, ec='none'))
    ax.text(5.6, 3.0, f"normal: {pre['perimeter_extrusion_width']} mm", fontsize=40, fontweight='bold', va='center', color=INK)
    ax.text(5.6, 1.25, 'thinnest:\n0.34-0.38 mm', fontsize=40, fontweight='bold', va='center', color=INK)
    text(f, W / 2, 40, 'The lines it draws', 66)
    text(f, W / 2, 1110, 'standard settings (stock preset) · lines drawn to scale', 36, GREY)
    save(f, 'card-lines.png')


def nozzle():
    f = fig()
    ax = f.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis('off')
    ax.add_patch(MPoly([(566, 250), (1066, 250), (896, 700), (736, 700)], closed=True, fc='#c0a060', ec=INK, lw=4))
    ax.add_patch(Rectangle((736, 700), 160, 60, fc='#c0a060', ec=INK, lw=4))
    ax.add_patch(FancyBboxPatch((300, 840), 1032, 80, boxstyle='round,pad=0,rounding_size=40', fc=ORANGE, ec='none'))
    ax.annotate('', xy=(736, 800), xytext=(896, 800), arrowprops=dict(arrowstyle='<->', lw=4, color=RED))
    text(f, W / 2, 40, 'The nozzle = the marker tip', 64)
    text(f, 1200, 640, '0.4 mm', 70, RED)
    text(f, W / 2, 1060, 'melted plastic, squeezed into a line', 44, GREY)
    save(f, 'card-nozzle.png')


def marker():
    f = fig()
    text(f, W / 2, 40, 'A fat marker', 66)
    f.text(0.5, 0.62, 'ALEX', fontsize=230, ha='center', va='center', color=INK, fontweight='bold')
    import matplotlib.patheffects as pe
    t = f.text(0.5, 0.25, 'gym bag', fontsize=70, ha='center', va='center', color=INK)
    t.set_path_effects([pe.withStroke(linewidth=18, foreground=INK)])
    text(f, W / 2, 1110, 'big letters fine · tiny ones smear (a drawing)', 40, GREY)
    save(f, 'card-marker.png')


def prompt():
    f = fig()
    ax = f.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis('off')
    ax.add_patch(FancyBboxPatch((70, 170), 1490, 560, boxstyle='round,pad=14', fc='white', ec=BLUE, lw=5))
    for i, l in enumerate(['Make a keychain tag 50 x 20 mm', 'with the name ALEX and a smaller', 'second row of text, GYM BAG,',
                           'for a printer with a 0.4 mm nozzle.']):
        ax.text(120, 230 + i * 120, l, fontsize=60 * 0.72, color=INK, va='top', fontweight='bold')
    for i in range(3):
        ax.add_patch(FancyBboxPatch((140 + i * 470, 820), 400, 130, boxstyle='round,pad=10', fc='#dbeafe', ec=BLUE, lw=4))
        ax.text(340 + i * 470, 885, f'chat {i + 1}', fontsize=56 * 0.72, color=BLUE, ha='center', va='center', fontweight='bold')
    text(f, W / 2, 40, 'Our request, 3 fresh chats', 64)
    text(f, W / 2, 1060, 'claude-sonnet-5-5 · Claude Code 2.1.310', 40, GREY)
    text(f, W / 2, 1120, 'SolidCraft 0.22.1 · the request, trimmed', 40, GREY)
    save(f, 'card-prompt.png')


def both():
    f = fig()
    text(f, W / 2, 30, '2 mm vs 3 mm, both ways', 62)
    text(f, W * 0.3, 120, 'raised (GYM BAG)', 44, INK)
    text(f, W * 0.8, 120, 'engraved (the B)', 44, INK)
    panel(f, [0.03, 0.47, 0.55, 0.3], 'raised-h2', 3.6, ROW2[2])
    panel(f, [0.03, 0.1, 0.55, 0.3], 'raised-h3', 3.6, ROW2[3])
    panel(f, [0.64, 0.45, 0.32, 0.34], 'engraved-h2', 2.8, letter_window('engraved-h2', 2.8), mode='engraved', islands=True)
    panel(f, [0.64, 0.06, 0.32, 0.34], 'engraved-h3', 2.8, letter_window('engraved-h3', 2.8), mode='engraved', islands=True)
    text(f, W * 0.3, 1010 - 450, '2 mm: fat', 44, RED)
    text(f, W * 0.3, 1140, '3 mm: clean', 44, GREEN)
    save(f, 'card-both.png')


def runs():
    f = fig()
    sc = json.load(open(os.path.join(LAB, 'out', 'runs', 'SCORES.json'), encoding='utf-8'))
    text(f, W / 2, 40, 'Every saved design, sliced by us', 58)
    for i, r in enumerate(sc):
        text(f, W / 2, 200 + i * 300, f"run {i + 1}: raised, small row {r['row_cap_mm'][1]:.1f} mm", 54)
        lo, hi = r['row2_ratio_range']
        text(f, W / 2, 290 + i * 300, f"planned {lo:.2f}-{hi:.2f} x the drawing · PASS", 48, GREEN)
    text(f, W / 2, 1120, 'slicer plans, not prints', 36, GREY)
    save(f, 'card-runs.png')


def replies():
    f = fig()
    text(f, W / 2, 40, 'None of them measured', 64, RED)
    q = ['run 1: "from font proportions,', '  not measured on the model"', 'run 2: "I estimated that from the',
         '  font and didn\'t measure it"', 'run 3: "probably too thin"']
    for i, l in enumerate(q):
        text(f, 120, 200 + i * 110, l, 50, INK, ha='left')
    text(f, W / 2, 800, "the slicer's plan: within 2%", 54, GREEN)
    text(f, W / 2, 900, 'guessed 5.5 mm · enough here: 3 mm', 48, INK)
    text(f, W / 2, 1110, 'quotes from each run\'s own reply', 38, GREY)
    save(f, 'card-replies.png')


def named():
    f = fig()
    nc = json.load(open(os.path.join(LAB, 'out', 'namedcheck', 'namedcheck.json')))
    text(f, W / 2, 40, 'Step 1: one named size', 64)
    text(f, W / 2, 300, 'small_height', 90, BLUE)
    text(f, W / 2, 470, '2 mm  →  3 mm', 110, INK)
    text(f, W / 2, 700, 'one number moves the whole row', 54, INK)
    ok = nc.get('one_number_moves_the_row')
    text(f, W / 2, 860, 'rebuilt = the 3 mm tag, exactly' if ok else '', 46, GREEN)
    text(f, W / 2, 1110, 'set_parameter in SolidCraft (our lab check)', 38, GREY)
    save(f, 'card-named.png')


def why():
    f = fig()
    text(f, W / 2, 40, 'Step 2: taller letters, wider strokes', 58)
    w2 = letter_window('raised-h2', 3.6)
    w3 = letter_window('raised-h3', 3.6)
    span = max(w3[2] - w3[0], w3[3] - w3[1])
    for k, (case, w) in enumerate((('raised-h2', w2), ('raised-h3', w3))):   # the same scale: both windows span the 3 mm B
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        win = (cx - span / 2, cy - span / 2, cx + span / 2, cy + span / 2)
        panel(f, [0.06 + k * 0.48, 0.2, 0.42, 0.57], case, 3.6, win, bar=True)
    lo2, hi2 = r2('raised-h2')
    lo3, hi3 = r2('raised-h3')
    text(f, W * 0.27, 160, '2 mm', 56, INK)
    text(f, W * 0.75, 160, '3 mm', 56, INK)
    text(f, W * 0.27, 980, f'+{(lo2 - 1) * 100:.0f} to +{(hi2 - 1) * 100:.0f}%', 56, RED)
    text(f, W * 0.75, 980, f'+{(lo3 - 1) * 100:.0f} to +{(hi3 - 1) * 100:.0f}%', 56, GREEN)
    text(f, W / 2, 1110, 'the B, same scale · red dot = 0.4 mm tip', 40, GREY)
    save(f, 'card-why.png')


hook(1920, 1080, 'hook-landscape.png')
hook(1080, 1920, 'hook-vertical.png', vertical=True)
card_simple('card-hook.png', '2 mm letters, planned fat', None, 'raised-h2', 3.6, ROW2[2], footer='black = designed · orange = planned · slicer plan')
def stroke_card():
    f = fig()
    text(f, W / 2, 40, 'A stroke: one bar or curve', 64)
    text(f, W / 2, 130, 'the B, 2 mm tall, as designed (outline)', 46, GREY)
    panel(f, [0.25, 0.15, 0.5, 0.67], 'raised-h2', 3.6, letter_window('raised-h2', 3.6), show_plan=False, outline_only=True, bar=True)
    text(f, W / 2, 1110, 'its strokes: thinner than the red 0.4 mm dot', 42, RED)
    save(f, 'card-stroke.png')


stroke_card()
card_simple('card-fixed.png', '3 mm: every letter clean', None, 'raised-h3', 3.6, ROW2[3], footer="the slicer's plan, 3 mm tall")
card_simple('card-tracing.png', 'The slicer traces every line', None, 'raised-h3', 3.6, ROW2[3], footer='each orange line at its own width')
card_simple('card-blob.png', 'Thinner than the line: a blob', 'the B, 2 mm: design (black) vs plan', 'raised-h2', 3.6, letter_window('raised-h2', 3.6))
card_simple('card-counters.png', 'Counters: the holes in a B', 'squeezed by fat strokes', 'raised-h2', 3.6, letter_window('raised-h2', 3.6), footer='2 mm tall · slicer plan')
def engraved_card():
    f = fig()
    text(f, W / 2, 40, 'Engraved: the island skipped', 62)
    text(f, W / 2, 130, 'the B pressed in, 2 mm · orange = planned plastic', 42, GREY)
    panel(f, [0.25, 0.15, 0.5, 0.67], 'engraved-h2', 2.8, letter_window('engraved-h2', 2.8), mode='engraved', islands=True)
    text(f, W / 2, 1110, 'blue = groove · slicer plan, not a print', 40, GREY)
    save(f, 'card-engraved.png')


engraved_card()
card_simple('card-plan2.png', 'The plan: +44 to +56%', 'GYM BAG, 2 mm, one 0.38 mm line per stroke', 'raised-h2', 3.6, ROW2[2])
card_simple('card-proof.png', 'Step 3: rebuilt at 3 mm', 'every counter open', 'raised-h3', 3.6, ROW2[3], footer='slicer plan, not a print')
strokes()
lines()
nozzle()
marker()
prompt()
both()
runs()
replies()
named()
why()
print(sorted(os.listdir(F)))


def _crop(path, pad=30):
    from PIL import Image, ImageChops
    im = Image.open(path).convert('RGB')
    col = im.crop((0, 0, 1, im.height)).resize(im.size)
    bb = ImageChops.difference(im, col).convert('L').point(lambda v: 255 if v > 18 else 0).getbbox()
    return im.crop((max(0, bb[0] - pad), max(0, bb[1] - pad), min(im.width, bb[2] + pad), min(im.height, bb[3] + pad)))


def two_renders(name, title, left, right, llab, rlab, footer):
    f = fig()
    text(f, W / 2, 40, title, 62)
    for k, (img, lab) in enumerate(((left, llab), (right, rlab))):
        ax = f.add_axes([0.03 + k * 0.49, 0.2, 0.45, 0.6])
        ax.imshow(_crop(os.path.join(LAB, 'video', 'renders', img)))
        ax.axis('off')
        text(f, W * (0.255 + k * 0.49), 990, lab, 54, BLUE)
    text(f, W / 2, 1110, footer, 38, GREY)
    save(f, name)


two_renders('card-ways.png', 'Two ways to put text on', 'raised-h3-tilt.png', 'engraved-h3-tilt.png', 'raised: stands up',
            'engraved: pressed in', 'our tags in SolidCraft')
two_renders('card-pick.png', 'At 2 mm, which comes out better?', 'raised-h2-tilt.png', 'engraved-h2-tilt.png', '1 · raised',
            '2 · engraved', 'pick one')
