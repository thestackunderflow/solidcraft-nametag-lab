"""Tests for geom.py (run first, red, then green):
    docker run --rm -v <probe>:/w -w /w nametag-analyse:0.1 python -m pytest -q test_geom.py"""
import math
import struct

import pytest

import geom as G


def box_tris(x0, y0, z0, x1, y1, z1):
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    out = []
    for a, b, c, d in q:
        out += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return out


def write_stl(path, tris):
    with open(path, 'wb') as f:
        f.write(b'test'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for t in tris:
            f.write(struct.pack('<3f', 0, 0, 0))
            for p in t:
                f.write(struct.pack('<3f', *p))
            f.write(b'\0\0')


def test_section_of_box_with_box_hole(tmp_path):
    p = tmp_path / 'b.stl'
    write_stl(p, box_tris(0, 0, 0, 10, 6, 3) + [tuple(reversed(t)) for t in box_tris(2, 2, -1, 4, 4, 4)])
    s = G.section(G.read_stl(str(p)), 1.5)
    assert s.area == pytest.approx(60 - 4, abs=1e-6)
    assert len(G.parts(s)) == 1 and G.hole_count(s) == 1


def test_gcode_layers_widths_and_arcs():
    g = '\n'.join([
        'M83', ';LAYER_CHANGE', ';Z:0.2', ';HEIGHT:0.2', ';TYPE:Perimeter', ';WIDTH:0.4',
        'G1 X0 Y0 F100', 'G1 X10 Y0 E1', 'G1 X10 Y5 F9000', 'G1 E-0.5', 'G1 X0 Y5',
        ';LAYER_CHANGE', ';Z:0.4', ';HEIGHT:0.2', ';WIDTH:0.5', 'G1 X0 Y0', 'G1 X0 Y10 E1',
        ';WIDTH:0.3', 'G2 X10 Y0 I5 J-5 E1',   # quarter... a half circle centre (5,5)? centre = (0,10)+(5,-5) = (5,5)
    ])
    L = G.parse_gcode(g)
    assert sorted(L) == [0.2, 0.4]
    a = L[0.2]
    assert len(a) == 1 and a[0][4] == 0.4                     # travel and retract skipped
    reg = G.beads(a)
    assert reg.area == pytest.approx(10 * 0.4 + math.pi * 0.2 ** 2, rel=1e-2)
    b = L[0.4]
    assert b[0][4] == 0.5 and all(s[4] == 0.3 for s in b[1:])
    end = b[-1]
    assert (end[2], end[3]) == pytest.approx((10, 0), abs=1e-6)
    r = [math.hypot(s[2] - 5, s[3] - 5) for s in b[1:]]
    assert min(r) == pytest.approx(math.hypot(5, 5), abs=1e-6) and max(r) == pytest.approx(math.hypot(5, 5), abs=1e-6)


def test_owner_cells_partition():
    from shapely.geometry import box
    letters = [box(0, 0, 1, 2), box(1.2, 0, 2.2, 2)]
    cells = G.owner_cells(letters, box(-1, -1, 4, 3))
    assert len(cells) == 2
    assert cells[0].contains(letters[0].centroid) and cells[1].contains(letters[1].centroid)
    assert cells[0].intersection(cells[1]).area == pytest.approx(0, abs=1e-6)


def test_topology_break_width():
    from shapely.geometry import box
    bar = box(0, 0, 5, 0.3)
    assert G.break_width(bar) == pytest.approx(0.30, abs=0.01)


def test_full_circle_arc_is_kept():
    g = '\n'.join(['M83', ';LAYER_CHANGE', ';Z:0.2', ';WIDTH:0.4', 'G1 X1 Y0', 'G3 X1 Y0 I-1 J0 E1'])
    a = G.parse_gcode(g)[0.2]
    assert len(a) > 50
    assert sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in a) == pytest.approx(2 * math.pi, rel=1e-3)
