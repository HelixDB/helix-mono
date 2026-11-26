"""Global pass: pull quadratic off-curve points toward each curve's tangent corner -> more angular corners."""
import math
from fontTools.ttLib.tables import ttProgram


def _isect(p0, d0, p1, d1):
    den = d0[0] * d1[1] - d0[1] * d1[0]
    if abs(den) < 1e-9:
        return None
    t = ((p1[0] - p0[0]) * d1[1] - (p1[1] - p0[1]) * d1[0]) / den
    s = ((p1[0] - p0[0]) * d0[1] - (p1[1] - p0[1]) * d0[0]) / den
    return t, s, (p0[0] + t * d0[0], p0[1] + t * d0[1])


def tighten_glyph(gl, glyf, k):
    if gl.numberOfContours <= 0:
        return 0
    coords, ends, flags = gl.getCoordinates(glyf)
    pts = [list(c) for c in coords]
    changed, start = 0, 0
    for end in ends:
        idx = list(range(start, end + 1))
        n = len(idx)
        on = [flags[i] & 1 for i in idx]
        for a in range(n):
            if not on[a]:
                continue
            # run of off-curves after on-curve a
            run, b = [], (a + 1) % n
            while not on[b] and len(run) < n:
                run.append(b); b = (b + 1) % n
            if len(run) < 2 or b == a:
                continue
            P0, P3 = pts[idx[a]], pts[idx[b]]
            A, B = pts[idx[run[0]]], pts[idx[run[-1]]]
            d0 = (A[0] - P0[0], A[1] - P0[1]); d1 = (B[0] - P3[0], B[1] - P3[1])
            l0, l1 = math.hypot(*d0), math.hypot(*d1)
            if l0 < 1 or l1 < 1:
                continue
            ang = math.degrees(math.acos(max(-1, min(1, (d0[0] * d1[0] + d0[1] * d1[1]) / (l0 * l1)))))
            if not 45 <= ang <= 135:  # only real corners (tangents roughly perpendicular)
                continue
            r = _isect(P0, d0, P3, d1)
            if not r:
                continue
            t, s, X = r
            if t <= 1 or s <= 1 or t > 6 or s > 6:  # corner must lie beyond the handles, not wildly far
                continue
            for j in run:
                p = pts[idx[j]]
                p[0] += k * (X[0] - p[0]); p[1] += k * (X[1] - p[1])
            changed += 1
        start = end + 1
    gl.coordinates.__init__([(round(x), round(y)) for x, y in pts]) if False else None
    for i, (x, y) in enumerate(pts):
        gl.coordinates[i] = (round(x), round(y))
    gl.recalcBounds(glyf)
    return changed


def apply(font, k):
    glyf, hmtx = font["glyf"], font["hmtx"]
    total = 0
    for name in font.getGlyphOrder():
        total += tighten_glyph(glyf[name], glyf, k)
    for name in font.getGlyphOrder():  # composites + lsb
        gl = glyf[name]
        if gl.isComposite():
            gl.recalcBounds(glyf)
        adv, _ = hmtx[name]
        hmtx[name] = (adv, getattr(gl, "xMin", 0))
        if hasattr(gl, "program"):
            gl.program = ttProgram.Program(); gl.program.fromBytecode(b"")
    for t in ("fpgm", "prep", "cvt "):  # outlines changed -> drop stale hinting
        if t in font:
            del font[t]
    if "gasp" in font:
        font["gasp"].gaspRange = {0xFFFF: 0x000A}
    return total
