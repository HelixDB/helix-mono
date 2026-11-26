"""Helix Mono HX-03: curved letters drawn as centre-line paths with an oval pen.

Straight letters come from helix_mono2 (stems, bars, flat-cut diagonals). Every letter with a curve
is redrawn here as a smooth skeleton (lines + squircle corner cubics) stroked by an elliptical pen
whose width is the stem T horizontally and the hairline H vertically, so curves thin naturally at
their tops and bottoms and terminals follow the curve.

Usage: python helix_mono3.py OUT_DIR [Weight ...]
"""
import math
import sys

import pathops
from fontTools.pens.recordingPen import RecordingPen

import helix_mono2 as base
from helix_mono2 import (ADV, ASC, AX, CAP, DSC, HL, HR, LX, MX, O, RX, XH, R, U, D, I, clipy, diag, mirror,
                         rot180, xform, rr)

KC = 0.60  # corner handle fraction for skeleton corners (0.552 = circular)


# ---------------------------------------------------------------- skeleton paths
def _bez(p0, c1, c2, p3, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p3[1])


def _ctrl(kind, p0, p3, k):
    (x0, y0), (x, y) = p0, p3
    if kind == "hv":   # leave horizontally, arrive vertically
        return (x0 + (x - x0) * k, y0), (x, y - (y - y0) * k)
    return (x0, y0 + (y - y0) * k), (x - (x - x0) * k, y)  # vh


class Pb:
    def __init__(self, x, y):
        self.pts = [(x, y)]
        self.cur = (x, y)

    def _sample(self, p0, c1, c2, p3, t0, t1):
        ln = math.hypot(c1[0] - p0[0], c1[1] - p0[1]) + math.hypot(c2[0] - c1[0], c2[1] - c1[1]) + math.hypot(p3[0] - c2[0], p3[1] - c2[1])
        n = max(10, int(ln * (t1 - t0) / 4))
        for i in range(1, n + 1):
            self.pts.append(_bez(p0, c1, c2, p3, t0 + (t1 - t0) * i / n))

    def L(self, x, y):
        self.pts.append((x, y))
        self.cur = (x, y)
        return self

    def C(self, c1, c2, p, t1=1.0):
        self._sample(self.cur, c1, c2, p, 0, t1)
        self.cur = p
        return self

    def hv(self, x, y, t1=1.0, k=KC):
        c1, c2 = _ctrl("hv", self.cur, (x, y), k)
        return self.C(c1, c2, (x, y), t1)

    def vh(self, x, y, t1=1.0, k=KC):
        c1, c2 = _ctrl("vh", self.cur, (x, y), k)
        return self.C(c1, c2, (x, y), t1)

    @classmethod
    def corner(cls, kind, p0, p3, t0, k=KC):
        """Start partway (t0) along a corner curve: used for terminals inside a curve."""
        c1, c2 = _ctrl(kind, p0, p3, k)
        s = cls(*_bez(p0, c1, c2, p3, t0))
        s._sample(p0, c1, c2, p3, t0, 1.0)
        s.cur = p3
        return s


def rrpath(x0, y0, x1, y1, rx, ry):
    ym = (y0 + y1) / 2
    return (Pb(x1, ym).L(x1, y1 - ry).vh(x1 - rx, y1).L(x0 + rx, y1).hv(x0, y1 - ry).L(x0, y0 + ry)
            .vh(x0 + rx, y0).L(x1 - rx, y0).hv(x1, y0 + ry).L(x1, ym))


# ---------------------------------------------------------------- oval-pen stroker
def _support(nx, ny, a, b):
    dd = math.sqrt(a * a * nx * nx + b * b * ny * ny)
    return a * a * nx / dd, b * b * ny / dd


def _area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly))) / 2


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _rdp(pts, eps):
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1e-9
    dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x1 * y0 - y1 * x0) / n
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        return _rdp(pts[: idx + 1], eps)[:-1] + _rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


def _smooth(path, eps=0.45):
    rec = RecordingPen()
    path.draw(rec)
    out = pathops.Path()
    pen = out.getPen()
    contour = []
    for op, args in rec.value:
        if op == "moveTo":
            contour = [args[0]]
        elif op == "lineTo":
            contour.append(args[0])
        elif op in ("closePath", "endPath"):
            if len(contour) > 2:
                # split at the point farthest from the start so RDP keeps both halves
                far = max(range(len(contour)), key=lambda i: math.hypot(contour[i][0] - contour[0][0], contour[i][1] - contour[0][1]))
                pts = _rdp(contour[: far + 1], eps)[:-1] + _rdp(contour[far:] + [contour[0]], eps)[:-1]
                pen.moveTo(pts[0])
                for p in pts[1:]:
                    pen.lineTo(p)
                pen.closePath()
            contour = []
        else:  # curves never come out of the stroker; keep anything else verbatim
            contour.append(args[-1])
    return out


def stroke(pb, a, b, closed=False):
    P = [pb.pts[0]]
    for p in pb.pts[1:]:
        if math.hypot(p[0] - P[-1][0], p[1] - P[-1][1]) > 0.05:
            P.append(p)
    if closed and math.hypot(P[0][0] - P[-1][0], P[0][1] - P[-1][1]) < 0.05:
        P.pop()
    n = len(P)
    segs = n if closed else n - 1
    path = pathops.Path()
    pen = path.getPen()

    def add(poly):
        if abs(_area(poly)) < 1e-3:
            return
        if _area(poly) < 0:
            poly = poly[::-1]
        pen.moveTo(poly[0])
        for q in poly[1:]:
            pen.lineTo(q)
        pen.closePath()

    sv = []
    for i in range(segs):
        p, q = P[i], P[(i + 1) % n]
        dx, dy = q[0] - p[0], q[1] - p[1]
        ln = math.hypot(dx, dy)
        s = _support(-dy / ln, dx / ln, a, b)
        sv.append(s)
        add([(p[0] + s[0], p[1] + s[1]), (q[0] + s[0], q[1] + s[1]), (q[0] - s[0], q[1] - s[1]), (p[0] - s[0], p[1] - s[1])])
    for i in (range(n) if closed else range(1, n - 1)):
        s0, s1, p = sv[(i - 1) % segs], sv[i % segs], P[i]
        h = _hull([(p[0] + s0[0], p[1] + s0[1]), (p[0] + s1[0], p[1] + s1[1]), (p[0] - s0[0], p[1] - s0[1]), (p[0] - s1[0], p[1] - s1[1])])
        if len(h) >= 3:
            add(h)
    path.simplify(fix_winding=True)
    return _smooth(path)


# ---------------------------------------------------------------- curved glyphs
def curved(T, H):
    g = base.glyphs(T, H)
    a, b = T / 2, H / 2
    S = lambda pb, closed=False, f=1.0: stroke(pb, a * f, b * f, closed)
    cl, cr = LX + a, RX - a
    cb, ct = -O + b, CAP + O - b
    xb, xt = -O + b, XH + O - b
    CM = 362
    half = (cr - cl) / 2
    rxC, ryC = half * 0.94, (ct - cb) * 0.31
    rxo, ryo = half * 0.94, (xt - xb) * 0.40
    d = T * 1.32

    def dot(cx, y):
        return rr(cx - d / 2, y, cx + d / 2, y + d, d * 0.22)

    # ---------- capitals
    g["O"] = S(rrpath(cl, cb, cr, ct, rxC, ryC), True)
    g["Q"] = U(g["O"], clipy(diag((MX + 60, 170), (RX - 6, -150), T * 0.97), -150, CAP))
    tC = 0.30
    g["C"] = S(Pb.corner("vh", (cr, ct - ryC), (cr - rxC, ct), tC).L(cl + rxC, ct).hv(cl, ct - ryC).L(cl, cb + ryC)
               .vh(cl + rxC, cb).L(cr - rxC, cb).hv(cr, cb + ryC, 1 - tC))
    gy = 300
    g["G"] = U(S(Pb.corner("vh", (cr, ct - ryC), (cr - rxC, ct), tC).L(cl + rxC, ct).hv(cl, ct - ryC).L(cl, cb + ryC)
                 .vh(cl + rxC, cb).L(cr - rxC, cb).hv(cr, cb + ryC).L(cr, gy + b)), R(MX + 14, gy - b, RX, gy + b))
    sl = HL + 6 + a  # stem centre for D/P/R/B
    g["D"] = U(R(HL + 6, 0, HL + 6 + T, CAP),
               S(Pb(sl, CAP - b).L(cr - 205, CAP - b).hv(cr, CAP - b - 230).L(cr, b + 230).vh(cr - 205, b).L(sl, b)))
    pbm = CM - 26
    bowlP = S(Pb(sl, CAP - b).L(cr - 170, CAP - b).hv(cr, CAP - b - 150).L(cr, pbm + 140).vh(cr - 170, pbm).L(sl, pbm))
    g["P"] = U(R(HL + 6, 0, HL + 6 + T, CAP), bowlP)
    g["R"] = U(R(HL + 6, 0, HL + 6 + T, CAP), bowlP, clipy(diag((MX - 4, pbm), (RX - T * 0.5 - 4, 0), T * 0.97), 0, pbm))
    g["B"] = U(R(HL + 6, 0, HL + 6 + T, CAP),
               S(Pb(sl, CAP - b).L(cr - 28 - 150, CAP - b).hv(cr - 28, CAP - b - 140).L(cr - 28, CM + 135).vh(cr - 28 - 150, CM).L(sl, CM)),
               S(Pb(sl, CM).L(cr - 170, CM).hv(cr, CM - 150).L(cr, b + 150).vh(cr - 170, b).L(sl, b)))
    jr = HR - a
    g["J"] = U(R(MX - 70, CAP - H, HR, CAP),
               S(Pb(jr, CAP - H).L(jr, cb + 200).vh(jr - (jr - cl) / 2 * 0.94, cb).L(cl + (jr - cl) / 2 * 0.94, cb).hv(cl, cb + 200, 0.55)))
    ul, ur = HL + a, HR - a
    rxu = (ur - ul) / 2 * 0.94
    g["U"] = S(Pb(ul, CAP).L(ul, cb + 210).vh(ul + rxu, cb).L(ur - rxu, cb).hv(ur, cb + 210).L(ur, CAP))

    def s_path(top, bot, mid, inset, t0, f=1.0):
        aa = a * f
        l, r = LX + aa, RX - aa
        ul_, ur_ = l + inset, r - inset
        ryu, ryl = (top - mid) / 2, (mid - bot) / 2
        rxu_, rxl_ = (ur_ - ul_) / 2 * 0.96, (r - l) / 2 * 0.96
        return (Pb.corner("vh", (ur_, top - ryu), (ur_ - rxu_, top), t0).L(ul_ + rxu_, top).hv(ul_, top - ryu)
                .vh(MX, mid).hv(r, mid - ryl).vh(r - rxl_, bot).L(l + rxl_, bot).hv(l, bot + ryl, 1 - t0))

    g["S"] = S(s_path(ct, cb, CM + 4, 16, 0.32))
    g["$"] = U(S(s_path(ct - 45, cb + 45, CM + 4, 18, 0.32)),
               R(MX - T * 0.42, CAP - 60, MX + T * 0.42, CAP + 55), R(MX - T * 0.42, -55, MX + T * 0.42, 60))

    # ---------- lowercase
    g["o"] = S(rrpath(cl, xb, cr, xt, rxo, ryo), True)
    tc = 0.30
    g["c"] = S(Pb.corner("vh", (cr, xt - ryo), (cr - rxo, xt), tc).L(cl + rxo, xt).hv(cl, xt - ryo).L(cl, xb + ryo)
               .vh(cl + rxo, xb).L(cr - rxo, xb).hv(cr, xb + ryo, 1 - tc))
    em = 268
    g["e"] = U(R(LX, em - b, RX, em + b),
               S(Pb(cr, em).L(cr, xt - ryo).vh(cr - rxo, xt).L(cl + rxo, xt).hv(cl, xt - ryo).L(cl, xb + ryo)
                 .vh(cl + rxo, xb).L(cr - rxo, xb).hv(cr, xb + ryo, 0.55)))
    sx = cl + a * 0.45   # arches leave the stem from inside it, thinning the join
    ryn = 205

    def arch(l, r, rad_y=ryn, f=1.0, t_end=None, end_y=0):
        rxn = (r - l) / 2 * 0.94
        p = Pb(l, xt - rad_y - 90).L(l, xt - rad_y).vh(l + rxn, xt).L(r - rxn, xt)
        if t_end:
            return p.hv(r, xt - rad_y, t_end)
        return p.hv(r, xt - rad_y).L(r, end_y)

    n = U(R(LX, 0, LX + T, XH), S(arch(cl, cr)))
    g["n"] = n
    g["h"] = U(R(LX, 0, LX + T, ASC), S(arch(cl, cr)))
    g["u"] = rot180(n, XH / 2)
    fm = 0.8
    am = a * fm
    ml, mr = LX + am, RX - am
    g["m"] = U(R(LX, 0, LX + 2 * am, XH), S(arch(ml, MX, 175, fm), f=fm), S(arch(MX, mr, 175, fm), f=fm))
    rl = LX + 46 + a
    g["r"] = U(R(LX + 46, 0, LX + 46 + T, XH), S(arch(rl, cr + 6, 190, t_end=0.5)))

    def bowl_r():
        rj = 120
        return (Pb(cl, xt - 230).L(cl, xt - 150).vh(cl + rj, xt).L(cr - rxo, xt).hv(cr, xt - ryo).L(cr, xb + ryo)
                .vh(cr - rxo, xb).L(cl + rj, xb).hv(cl, xb + 150).L(cl, xb + 230))

    g["b"] = U(R(LX, 0, LX + T, ASC), S(bowl_r()))
    g["d"] = mirror(g["b"])
    g["p"] = U(R(LX, DSC, LX + T, XH), S(bowl_r()))
    g["q"] = mirror(g["p"])
    dcb = DSC - O + b
    g["g"] = U(mirror(S(bowl_r())), R(RX - T, dcb + 180, RX, XH),
               S(Pb(cr, 200).L(cr, dcb + 180).vh(cr - 200, dcb).L(cl + 36, dcb)))
    abt = 300
    g["a"] = U(S(Pb.corner("vh", (cl + 8, xt - 190), (cl + 8 + 190, xt), 0.5).L(cr - 190, xt).hv(cr, xt - 190).L(cr, 0)),
               S(Pb(cr, abt).L(cl + 160, abt).hv(cl, abt - 135).L(cl, xb + 135).vh(cl + 160, xb).L(cr - 120, xb).hv(cr, xb + 130).L(cr, xb + 200)))
    At = ASC + O - b
    fx = MX - 34
    g["f"] = U(S(Pb(fx, 0).L(fx, At - 140).vh(fx + 130, At).L(cr - 70, At).hv(cr, At - 70, 0.45)), R(LX + 28, XH - H, RX - 28, XH))
    tx = MX - 44
    g["t"] = U(S(Pb(tx, XH + 150).L(tx, xb + 130).vh(tx + 130, xb).L(cr - 70, xb).hv(cr, xb + 70, 0.45)), R(LX + 28, XH - H, RX - 28, XH))
    lx = MX - 34
    g["l"] = U(R(LX + 40, ASC - H, lx + a, ASC), S(Pb(lx, ASC).L(lx, xb + 140).vh(lx + 140, xb).L(RX - 4, xb)))
    jx = MX + 40
    g["j"] = U(R(LX + 74, XH - H, jx + a, XH), S(Pb(jx, XH).L(jx, dcb + 170).vh(jx - 180, dcb).L(LX + 30, dcb)), dot(jx, XH + 118))
    g["s"] = S(s_path(xt, xb, 272, 12, 0.32))

    # ---------- figures
    n0, n1 = cl + 10, cr - 10
    rung = rr(MX - T * 0.42, 255, MX + T * 0.42, 455, T * 0.22)
    g["0"] = U(S(rrpath(n0, cb, n1, ct, (n1 - n0) / 2 * 0.94, ryC), True), rung)
    r2 = (n1 - n0) / 2 * 0.94
    g["2"] = U(S(Pb.corner("vh", (n0, ct - 190), (n0 + r2, ct), 0.45).L(n1 - r2, ct).hv(n1, ct - 190)
                 .C((n1, ct - 190 - 150), (n0 + 70, 250), (n0, b + 4))), R(n0 - a, 0, n1 + a + 4, H))
    g["3"] = U(S(Pb.corner("vh", (n0, ct - 160), (n0 + 160, ct), 0.45).L(n1 - 12 - 160, ct).hv(n1 - 12, ct - 145)
                 .L(n1 - 12, CM + 120).vh(n1 - 12 - 150, CM).L(MX - 40, CM)),
               S(Pb(MX - 40, CM).L(n1 - 170, CM).hv(n1, CM - 155).L(n1, cb + 165).vh(n1 - 180, cb).L(n0 + 180, cb).hv(n0, cb + 165, 0.55)))
    x5 = n0 + 22
    bt5 = 432
    g["5"] = U(R(x5 - a, CAP - H, n1 + a, CAP), R(x5 - a, bt5 - b, x5 + a, CAP),
               S(Pb(x5, bt5).L(n1 - 180, bt5).hv(n1, bt5 - 170).L(n1, cb + 170).vh(n1 - 180, cb).L(n0 + 180, cb).hv(n0, cb + 165, 0.5)))
    bt6 = 455 - b
    six = U(S(Pb.corner("vh", (n1, ct - ryC), (n1 - r2, ct), 0.4).L(n0 + r2, ct).hv(n0, ct - ryC).L(n0, cb + 170)),
            S(rrpath(n0, cb, n1, bt6, r2, (bt6 - cb) * 0.42), True))
    g["6"] = six
    g["9"] = rot180(six, CAP / 2)
    g["8"] = U(S(rrpath(n0 + 22, CM + 4, n1 - 22, ct, (n1 - n0 - 44) / 2 * 0.94, (ct - CM) * 0.44), True),
               S(rrpath(n0, cb, n1, CM + 4, r2, (CM - cb) * 0.42), True))
    g["?"] = U(S(Pb.corner("vh", (cl + 14, ct - 170), (cl + 14 + 180, ct), 0.45).L(cr - 14 - 180, ct).hv(cr - 14, ct - 170)
                 .L(cr - 14, 470).vh(cr - 14 - 100, 400).L(MX + 70, 400).hv(MX, 330).L(MX, 215)), dot(MX, 0))

    # ---------- punctuation with curves
    g["("] = S(Pb(RX - 60, ASC - 6).C((MX - 120, ASC - 150), (MX - 120, DSC + 150), (RX - 60, DSC + 6)))
    g[")"] = mirror(g["("])
    bm = (ASC + DSC) / 2
    top = S(Pb(RX - 46, ASC - 10 - b).L(MX + 90, ASC - 10 - b).hv(MX, ASC - 10 - b - 90).L(MX, bm + 90).vh(MX - 90, bm).L(LX + 40, bm))
    g["{"] = U(top, xform(top, (1, 0, 0, -1, 0, 2 * bm)))
    g["}"] = mirror(g["{"])
    wave = Pb(LX + 22 + a, AX)
    x0w, x1w = LX + 22 + a, RX - 22 - a
    for i in range(1, 121):
        t = i / 120
        wave.L(x0w + (x1w - x0w) * t, AX + 62 * math.sin(2 * math.pi * t))
    g["~"] = S(wave, f=0.95)   # the Helix tilde: one full strand twist
    sm = 0.85
    g["%"] = U(S(rrpath(LX + 4 + a * sm, CAP - 270 + b, 268 - a * sm, CAP - b, 70, 80), True, sm),
               S(rrpath(332 + a * sm, b, RX - 4 - a * sm, 270 - b, 70, 80), True, sm),
               clipy(diag((RX - T * 0.5, CAP), (LX + T * 0.5, 0), T * 0.97), 0, CAP))
    loop = S(rrpath(LX + 48 + a, 395 + b, MX + 98 - a, ct, 70, 85), True)
    g["&"] = U(loop, clipy(diag((LX + 70 + a, 450), (RX - T * 0.5, 0), T * 0.97), 0, 470),
               S(Pb(cl + 64, 445).C((cl + 10, 410), (cl, 380), (cl, 320)).L(cl, cb + 140).vh(cl + 160, cb).L(MX + 40, cb).hv(cr - 30, cb + 150, 0.55)))
    ir = RX - 46 - a * 0.9
    g["@"] = U(S(rrpath(MX - 80 + a * 0.9, 175 + b, ir, 470 - b, 90, 100), True, 0.9),
               R(RX - 46 - T * 0.9, 175, RX - 46, 470),
               S(Pb(RX - a * 0.9 - 4, 300).L(RX - a * 0.9 - 4, CAP - b - 190).vh(RX - a * 0.9 - 4 - 200, CAP - b).L(LX + a * 0.9 + 200, CAP - b)
                 .hv(LX + a * 0.9, CAP - b - 200).L(LX + a * 0.9, -60 + b + 180).vh(LX + a * 0.9 + 200, -60 + b).L(RX - 40, -60 + b), f=0.9))
    return g


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "dist3"
    only = sys.argv[2:] or None
    base.glyphs = (lambda orig: (lambda T, H: orig(T, H)))(base.glyphs)
    orig_glyphs = base.glyphs
    for name, wc, T, H in base.WEIGHTS:
        if only and name not in only:
            continue
        base.glyphs = orig_glyphs
        g = curved(T, H)
        base.glyphs = lambda T_, H_, g=g: g
        print("built", base.build(name, wc, T, H, out))
