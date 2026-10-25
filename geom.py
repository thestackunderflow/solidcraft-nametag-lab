"""Geometry for the nametag probe: section a binary STL at a height, read a PrusaSlicer ASCII G-code into per-layer
extrusion segments (G1 lines and G2/G3 arcs, each with its ;WIDTH:), buffer the segments into the printed region, split a
line of text into one cell per letter, and a stroke-width measure (the erosion that first changes a shape's topology)."""
import math
import re
import struct

from shapely.geometry import LineString, MultiPoint, Polygon, box
from shapely.ops import unary_union
import shapely


def read_stl(path):
    data = open(path, 'rb').read()
    n = struct.unpack_from('<I', data, 80)[0]
    if 84 + 50 * n != len(data):
        raise ValueError('not a binary STL')
    tris = []
    for i in range(n):
        v = struct.unpack_from('<12f', data, 84 + 50 * i)
        tris.append((v[3:6], v[6:9], v[9:12]))
    return tris


def _key(p):
    return (round(p[0], 6), round(p[1], 6))


def _weld(segs, tol=2e-4):
    """Snap section points that are within tol of each other to one point. The SolidCraft STL has T-junctions (a vertex
    lying on another triangle's edge), so the same section point comes from two different edges and differs in the
    last float32 bits; without welding the loops do not close."""
    import math as _m
    grid, rep = {}, {}

    def canon(p):
        k = _key(p)
        if k in rep:
            return rep[k]
        gx, gy = int(_m.floor(p[0] / tol)), int(_m.floor(p[1] / tol))
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for q in grid.get((gx + i, gy + j), []):
                    if _m.hypot(q[0] - p[0], q[1] - p[1]) < tol:
                        rep[k] = q
                        return q
        grid.setdefault((gx, gy), []).append(p)
        rep[k] = p
        return p
    out = []
    for a, b in segs:
        a, b = canon(a), canon(b)
        if a != b:
            out.append((a, b))
    return out


def section(tris, z):
    """The solid's cross-section at height z (a shapely geometry): triangle/plane segments chained into loops, loops
    combined even-odd (symmetric difference), so holes and islands in holes come out right."""
    segs = []
    if any(abs(p[2] - z) < 1e-6 for t in tris for p in t):
        z = z + 1e-5          # a mesh vertex lies on the plane (the side walls are split at mid height): nudge it
    for t in tris:
        pts = []
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            if (a[2] - z) * (b[2] - z) < 0:
                a, b = sorted((tuple(a), tuple(b)))          # same edge -> same point, bit for bit
                s = (z - a[2]) / (b[2] - a[2])
                pts.append((a[0] + s * (b[0] - a[0]), a[1] + s * (b[1] - a[1])))
        if len(pts) == 2 and _key(pts[0]) != _key(pts[1]):
            segs.append((pts[0], pts[1]))
    segs = _weld(segs)
    adj = {}
    for a, b in segs:
        adj.setdefault(_key(a), []).append((_key(b), b))
        adj.setdefault(_key(b), []).append((_key(a), a))
    used, loops = set(), []
    for a, b in segs:
        e = frozenset((_key(a), _key(b)))
        if e in used:
            continue
        used.add(e)
        loop, start, cur = [a, b], _key(a), _key(b)
        while cur != start:
            nxt = None
            for k, p in adj[cur]:
                ee = frozenset((cur, k))
                if ee not in used:
                    nxt = (k, p, ee)
                    break
            if nxt is None:
                break
            used.add(nxt[2])
            loop.append(nxt[1])
            cur = nxt[0]
        if len(loop) >= 4:
            loops.append(Polygon(loop).buffer(0))
    out = Polygon()
    for p in loops:
        out = out.symmetric_difference(p)
    return out


def parts(g, min_area=0.0):
    if g.is_empty:
        return []
    gs = list(g.geoms) if hasattr(g, 'geoms') else [g]
    return [p for p in gs if p.geom_type == 'Polygon' and p.area > min_area]


def hole_count(g, min_area=0.0):
    return sum(1 for p in parts(g) for r in p.interiors if Polygon(r).area > min_area)


def holes(g, min_area=0.0):
    return [Polygon(r) for p in parts(g) for r in p.interiors if Polygon(r).area > min_area]


_W = re.compile(r'([XYZEIJF])(-?\d*\.?\d+)')


def parse_gcode(text, arc_step=0.05):
    """{layer_z: [(x0, y0, x1, y1, width, type), ...]} for every extruding move (E > 0, relative E as in the preset)."""
    layers, z, w, typ, x, y = {}, None, None, None, 0.0, 0.0
    pending_layer = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(';'):
            if line == ';LAYER_CHANGE':
                pending_layer = True
            elif line.startswith(';Z:') and pending_layer:
                z = round(float(line[3:]), 3)
                layers.setdefault(z, [])
                pending_layer = False
            elif line.startswith(';WIDTH:'):
                w = float(line[7:])
            elif line.startswith(';TYPE:'):
                typ = line[6:]
            continue
        code = line.split(';', 1)[0].strip()
        if not code:
            continue
        cmd = code.split()[0]
        if cmd not in ('G0', 'G1', 'G2', 'G3'):
            continue
        a = dict((k, float(v)) for k, v in _W.findall(code))
        nx, ny = a.get('X', x), a.get('Y', y)
        ext = a.get('E', 0.0) > 0 and z is not None and ((nx, ny) != (x, y) or cmd in ('G2', 'G3'))   # G2/G3 may be a full circle
        if ext and cmd in ('G2', 'G3'):
            cx, cy = x + a.get('I', 0.0), y + a.get('J', 0.0)
            r = math.hypot(x - cx, y - cy)
            t0, t1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
            if cmd == 'G2':          # clockwise
                while t1 >= t0:
                    t1 -= 2 * math.pi
            else:
                while t1 <= t0:
                    t1 += 2 * math.pi
            n = max(2, int(abs(t1 - t0) * r / arc_step) + 1)
            px, py = x, y
            for i in range(1, n + 1):
                t = t0 + (t1 - t0) * i / n
                qx, qy = (cx + r * math.cos(t), cy + r * math.sin(t)) if i < n else (nx, ny)
                layers[z].append((px, py, qx, qy, w, typ))
                px, py = qx, qy
        elif ext:
            layers[z].append((x, y, nx, ny, w, typ))
        x, y = nx, ny
    return layers


def beads(segs, dx=0.0, dy=0.0):
    """The printed region: every segment buffered by half its width (round ends), shifted by (dx, dy)."""
    geoms = [LineString([(s[0] + dx, s[1] + dy), (s[2] + dx, s[3] + dy)]).buffer(s[4] / 2, quad_segs=6) for s in segs]
    return unary_union(geoms) if geoms else Polygon()


def owner_cells(letters, extent, step=0.04):
    """One region per letter: the points of `extent` nearer to that letter's outline than to any other letter's."""
    pts, owner = [], []
    for i, L in enumerate(letters):
        for p in parts(L):
            for ring in [p.exterior] + list(p.interiors):
                n = max(8, int(ring.length / step))
                for k in range(n):
                    q = ring.interpolate(k / n, normalized=True)
                    pts.append((q.x, q.y))
                    owner.append(i)
    vor = shapely.voronoi_polygons(MultiPoint(pts), extend_to=extent)
    cells = [[] for _ in letters]
    tree = shapely.STRtree([shapely.Point(p) for p in pts])
    for c in vor.geoms:
        idx = tree.query(c, predicate='intersects')
        if len(idx):
            # the generator point is the one inside its cell
            for j in idx:
                if c.contains(shapely.Point(pts[j])) or c.touches(shapely.Point(pts[j])):
                    cells[owner[j]].append(c)
                    break
    return [unary_union(c).intersection(extent) for c in cells]


def topo(g, min_area=1e-4):
    return (len(parts(g, min_area)), hole_count(g, min_area))


def break_width(g, hi=3.0, tol=0.002):
    """Twice the smallest erosion r at which the shape's piece/hole count changes (or it vanishes): the thinnest
    stroke (for a raised letter) or gap (for an engraved slot) that holds the shape's topology together."""
    t0 = topo(g)
    lo = 0.0
    if topo(g.buffer(-hi)) == t0:
        return None
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if topo(g.buffer(-mid, quad_segs=8)) == t0:
            lo = mid
        else:
            hi = mid
    return round(2 * (lo + hi) / 2, 3)
