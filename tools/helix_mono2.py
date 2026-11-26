"""Helix Mono HX-02: an original monospace in six weights.

Constructed geometry: squircle bowls (rounded rectangles with cubic corners), straight stems,
horizontals ~12% lighter than verticals, horizontally cut terminals and flat-cut diagonals.
Helix signatures: the rung zero, the double-twist tilde, tailed l/t.

Usage: python helix_mono2.py OUT_DIR
"""
import math
import sys
from pathlib import Path

import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

UPM, ADV = 1000, 600
CAP, XH, ASC, DSC = 700, 530, 750, -210
LX, RX, MX = 66, 534, 300       # round glyph extents, centre
HL, HR = 78, 522                # straight glyph extents
O = 10                          # overshoot
K = 0.60                        # corner squareness (0.552 = circle)
RS = 0.86                       # global corner-radius scale (Berkeley-tight corners)
AX = 330                        # math axis

WEIGHTS = [  # name, class, stem, horizontal
    ("ExtraLight", 200, 40, 37),
    ("Light", 300, 60, 54),
    ("Regular", 400, 80, 70),
    ("Medium", 500, 97, 84),
    ("SemiBold", 600, 113, 96),
    ("Bold", 700, 128, 107),
]


# ---------------------------------------------------------------- path toolkit
def _norm(c, w, h):
    if isinstance(c, (int, float)):
        c = (c, c)
    return max(0.0, min(c[0], w / 2)), max(0.0, min(c[1], h / 2))


def rr(x0, y0, x1, y1, r=0):
    """Rounded rectangle; r is one radius or (tl, tr, br, bl), each a number or (rx, ry)."""
    w, h = x1 - x0, y1 - y0
    tl, tr, br, bl = [_norm(c, w, h) for c in (r if isinstance(r, (list, tuple)) and len(r) == 4 else (r,) * 4)]
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((x0 + bl[0], y0))
    pen.lineTo((x1 - br[0], y0))
    if br[0] and br[1]:
        pen.curveTo((x1 - br[0] + br[0] * K, y0), (x1, y0 + br[1] - br[1] * K), (x1, y0 + br[1]))
    pen.lineTo((x1, y1 - tr[1]))
    if tr[0] and tr[1]:
        pen.curveTo((x1, y1 - tr[1] + tr[1] * K), (x1 - tr[0] + tr[0] * K, y1), (x1 - tr[0], y1))
    pen.lineTo((x0 + tl[0], y1))
    if tl[0] and tl[1]:
        pen.curveTo((x0 + tl[0] - tl[0] * K, y1), (x0, y1 - tl[1] + tl[1] * K), (x0, y1 - tl[1]))
    pen.lineTo((x0, y0 + bl[1]))
    if bl[0] and bl[1]:
        pen.curveTo((x0, y0 + bl[1] - bl[1] * K), (x0 + bl[0] - bl[0] * K, y0), (x0 + bl[0], y0))
    pen.closePath()
    return p


def R(x0, y0, x1, y1):
    return rr(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), 0)


def poly(pts):
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo(pts[0])
    for pt in pts[1:]:
        pen.lineTo(pt)
    pen.closePath()
    p.simplify(fix_winding=True)
    return p


def U(*ps):
    out = pathops.Path()
    for p in ps:
        out = pathops.op(out, p, pathops.PathOp.UNION)
    return out


def D(a, *bs):
    for b in bs:
        a = pathops.op(a, b, pathops.PathOp.DIFFERENCE)
    return a


def I(a, b):
    return pathops.op(a, b, pathops.PathOp.INTERSECTION)


def clipy(p, y0, y1):
    return I(p, R(-600, y0, 1200, y1))


def xform(p, m):
    rec = RecordingPen()
    p.draw(rec)
    out = pathops.Path()
    rec.replay(TransformPen(out.getPen(), m))
    return out


def mirror(p):
    return xform(p, (-1, 0, 0, 1, ADV, 0))


def rot180(p, cy):
    return xform(p, (-1, 0, 0, -1, ADV, 2 * cy))


def ext(p, q, y):
    t = (y - p[1]) / (q[1] - p[1])
    return (p[0] + t * (q[0] - p[0]), y)


def diag(p, q, t, over=120):
    """Straight stroke p->q of perpendicular thickness t, ends cut horizontally, over-extended for clipping."""
    if p[1] < q[1]:
        p, q = q, p
    p2, q2 = ext(p, q, p[1] + over), ext(p, q, q[1] - over)
    dx, dy = q2[0] - p2[0], q2[1] - p2[1]
    hw = t / 2 * math.hypot(dx, dy) / abs(dy)
    return poly([(p2[0] - hw, p2[1]), (p2[0] + hw, p2[1]), (q2[0] + hw, q2[1]), (q2[0] - hw, q2[1])])


def bar(p, q, t):
    """Stroke p->q with perpendicular (butt) ends; for rotated arms."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy)
    nx, ny = -dy / n * t / 2, dx / n * t / 2
    return poly([(p[0] + nx, p[1] + ny), (q[0] + nx, q[1] + ny), (q[0] - nx, q[1] - ny), (p[0] - nx, p[1] - ny)])


# ---------------------------------------------------------------- glyphs
def glyphs(T, H):
    def ring(x0, y0, x1, y1, r, tv=T, th=H, scale=True):
        w, h = x1 - x0, y1 - y0
        cs = r if isinstance(r, (list, tuple)) and len(r) == 4 else (r,) * 4
        f = RS if scale else 1.0
        outer, inner = [], []
        for c in cs:
            if isinstance(c, (int, float)):
                c = (c, c)
            rx, ry = _norm((c[0] * f, c[1] * f), w, h)
            outer.append((rx, ry) if rx and ry else 0)
            inner.append((max(rx - tv * 0.8, rx * 0.38), max(ry - th * 0.8, ry * 0.38)) if rx and ry else 0)
        return D(rr(x0, y0, x1, y1, outer), rr(x0 + tv, y0 + th, x1 - tv, y1 - th, inner))

    def bend(x0, y0, x1, y1, corner, r, tv=T, th=H, scale=True):
        """L-shaped stroke: the two sides of a ring meeting at one rounded corner, clipped to the box."""
        big = 4000
        bx = {"bl": (x0, y0, x1 + big, y1 + big), "tl": (x0, y0 - big, x1 + big, y1),
              "br": (x0 - big, y0, x1, y1 + big), "tr": (x0 - big, y0 - big, x1, y1)}[corner]
        rs = {"tl": (r, 0, 0, 0), "tr": (0, r, 0, 0), "br": (0, 0, r, 0), "bl": (0, 0, 0, r)}[corner]
        return I(ring(*bx, rs, tv, th, scale), R(x0, y0, x1, y1))

    d = T * 1.32  # dot size

    def dot(cx, y):
        return rr(cx - d / 2, y, cx + d / 2, y + d, d * 0.2)

    rC = (205, 228)   # cap rounds
    rX = (200, 186)   # lowercase rounds
    CM = 362          # cap crossbar centre
    XM = 272          # lowercase bar centre
    Td = T * 0.97     # diagonal stroke
    g = {}

    # ---------------- uppercase
    g["A"] = clipy(U(diag((MX - 22, CAP), (LX + T * 0.46, 0), Td), diag((MX + 22, CAP), (RX - T * 0.46, 0), Td),
                     R(LX + 70, 190, RX - 70, 190 + H)), 0, CAP)
    g["B"] = U(ring(HL + 6, CM - H / 2, RX - 30, CAP, (0, (165, 150), (165, 150), 0)),
               ring(HL + 6, 0, RX - 4, CM + H / 2, (0, (185, 165), (185, 165), 0)))
    g["C"] = D(ring(LX, -O, RX, CAP + O, rC), R(MX + 20, 205, RX + 99, CAP - 205))
    g["D"] = ring(HL + 6, 0, RX - 4, CAP, (0, (215, 240), (215, 240), 0))
    g["E"] = U(R(HL + 14, 0, HL + 14 + T, CAP), R(HL + 14, CAP - H, HR, CAP), R(HL + 14, CM - H / 2, HR - 34, CM + H / 2),
               R(HL + 14, 0, HR, H))
    g["F"] = U(R(HL + 14, 0, HL + 14 + T, CAP), R(HL + 14, CAP - H, HR, CAP), R(HL + 14, CM - H / 2, HR - 34, CM + H / 2))
    g["G"] = U(D(ring(LX, -O, RX, CAP + O, rC), R(MX + 20, CM - H / 2, RX + 99, CAP - 205)),
               R(MX + 10, CM - H / 2, RX, CM + H / 2))
    g["H"] = U(R(HL, 0, HL + T, CAP), R(HR - T, 0, HR, CAP), R(HL, CM - H / 2, HR, CM + H / 2))
    g["I"] = U(R(130, CAP - H, 470, CAP), R(130, 0, 470, H), R(MX - T / 2, 0, MX + T / 2, CAP))
    g["J"] = U(D(clipy(ring(LX + 8, -O, HR, CAP + 600, (0, 0, rC, rC)), -O, CAP), R(0, 205, MX, CAP + 50)),
               R(MX - 70, CAP - H, HR, CAP))
    kj = (HL + T * 0.6, 250)
    g["K"] = U(R(HL, 0, HL + T, CAP),
               I(clipy(U(diag((HR - T * 0.5, CAP), kj, Td), clipy(diag((MX - 40, 440), (HR - T * 0.5, 0), Td * 1.02), -9, 440)), 0, CAP), R(HL + T / 2, -9, 999, 999)))
    g["L"] = U(R(HL + 14, 0, HL + 14 + T, CAP), R(HL + 14, 0, HR, H))
    g["M"] = U(R(HL, 0, HL + T, CAP), R(HR - T, 0, HR, CAP),
               clipy(U(diag((HL + T * 0.5, CAP), (MX, 290), T * 0.86), diag((HR - T * 0.5, CAP), (MX, 290), T * 0.86)), 290, CAP))
    g["N"] = U(R(HL, 0, HL + T, CAP), R(HR - T, 0, HR, CAP),
               clipy(diag((HL + T * 0.5, CAP), (HR - T * 0.5, 0), T * 0.95), 0, CAP))
    g["O"] = ring(LX, -O, RX, CAP + O, rC)
    bowlP = ring(HL + 6, CM - H / 2 - 18, RX - 4, CAP, (0, (190, 175), (190, 175), 0))
    g["P"] = U(R(HL + 6, 0, HL + 6 + T, CAP), bowlP)
    g["Q"] = U(ring(LX, -O, RX, CAP + O, rC), clipy(diag((MX + 50, 170), (RX - 10, -150), Td), -150, CAP))
    g["R"] = U(R(HL + 6, 0, HL + 6 + T, CAP), bowlP,
               clipy(diag((MX - 10, CM - 18), (RX - T * 0.5 - 4, 0), Td), 0, CM))

    def s_shape(top, bot, mid, inset_top, rt, rb, cut):
        up = D(ring(LX + inset_top, mid - H / 2, RX - inset_top, top, rt), R(MX, mid - H / 2 - 5, RX + 99, top - cut))
        lo = D(ring(LX, bot, RX, mid + H / 2, rb), R(-99, bot + cut, MX, mid + H / 2 + 5))
        return U(up, lo)

    g["S"] = s_shape(CAP + O, -O, CM + 8, 16, (180, 165), (195, 175), 200)
    g["T"] = U(R(LX, CAP - H, RX, CAP), R(MX - T / 2, 0, MX + T / 2, CAP))
    g["U"] = clipy(ring(HL, -O, HR, CAP + 600, (0, 0, rC, rC)), -O, CAP)
    g["V"] = clipy(U(diag((LX + T * 0.46, CAP), (MX, 0), Td), diag((RX - T * 0.46, CAP), (MX, 0), Td)), 0, CAP)
    Tw = T * 0.82
    g["W"] = clipy(U(diag((LX + Tw * 0.4, CAP), (LX + 112, 0), Tw), clipy(U(diag((LX + 112, 0), (MX, 455), Tw), diag((MX, 455), (RX - 112, 0), Tw)), 0, 455), diag((RX - 112, 0), (RX - Tw * 0.4, CAP), Tw)), 0, CAP)
    g["X"] = clipy(U(diag((LX + T * 0.46, CAP), (RX - T * 0.46, 0), Td), diag((RX - T * 0.46, CAP), (LX + T * 0.46, 0), Td)), 0, CAP)
    g["Y"] = U(clipy(U(diag((LX + T * 0.46, CAP), (MX, 320), Td), diag((RX - T * 0.46, CAP), (MX, 320), Td)), 300, CAP),
               R(MX - T / 2, 0, MX + T / 2, 330))
    g["Z"] = U(R(LX + 22, CAP - H, RX - 18, CAP), R(LX + 14, 0, RX - 14, H),
               clipy(diag((RX - 18 - T * 0.55, CAP - H), (LX + 14 + T * 0.55, H), Td), H, CAP - H))

    # ---------------- lowercase
    def arch(x0, x1, rad=rX, t=T):
        return I(ring(x0, -400, x1, XH + O, (rad, rad, 0, 0), t), R(x0, 0, x1, XH + O))

    n = U(arch(LX, RX), R(LX, 0, LX + T, XH))
    g["n"] = n
    g["h"] = U(arch(LX, RX), R(LX, 0, LX + T, ASC))
    Tm = T * 0.8
    g["m"] = U(arch(LX, MX + Tm / 2, (118, 165), Tm), arch(MX - Tm / 2, RX, (118, 165), Tm), R(LX, 0, LX + Tm, XH))
    g["u"] = rot180(n, XH / 2)
    g["r"] = U(D(arch(LX + 46, RX + 6), R(MX + 30, -10, RX + 99, XH - 150)), R(LX + 46, 0, LX + 46 + T, XH))
    g["o"] = ring(LX, -O, RX, XH + O, rX)
    g["b"] = U(R(LX, 0, LX + T, ASC), ring(LX, -O, RX, XH + O, (0, rX, rX, 0)))
    g["d"] = mirror(g["b"])
    g["p"] = U(R(LX, DSC, LX + T, XH), ring(LX, -O, RX, XH + O, (0, rX, rX, 0)))
    g["q"] = mirror(g["p"])
    g["c"] = D(ring(LX, -O, RX, XH + O, rX), R(MX + 20, 168, RX + 99, XH - 168))
    g["e"] = U(D(ring(LX, -O, RX, XH + O, rX), R(MX + 20, 160, RX + 99, XM - H / 2)), R(LX, XM - H / 2, RX, XM + H / 2))
    g["g"] = U(ring(LX, 0, RX, XH + O, (rX, 0, (150, 140), rX)), R(RX - T, DSC + 150, RX, XH),
               bend(LX + 54, DSC - O, RX, DSC + 200, "br", (190, 175)))
    g["s"] = s_shape(XH + O, -O, XM + 6, 12, (165, 128), (180, 138), 160)
    ax = (LX + 10, XH * 0.56)
    top_a = D(I(ring(LX + 8, -400, RX, XH + O, ((175, 160), (175, 160), 0, 0)), R(0, XH * 0.5, 999, 999)),
              R(-99, -99, MX - 40, XH - 160))
    g["a"] = U(top_a, R(RX - T, 0, RX, XH * 0.52),
               ring(LX, -O, RX, 316, ((150, 120), 0, 0, (150, 120))))
    fx = MX - T / 2 - 34
    g["f"] = U(bend(fx, 0, RX - 4, ASC + O, "tl", (170, 165)), R(LX + 28, XH - H, RX - 28, XH))
    tx = MX - T / 2 - 44
    g["t"] = U(bend(tx, -O, RX - 4, XH + 150, "bl", (160, 150)), R(LX + 28, XH - H, RX - 28, XH))
    lx = MX - T / 2 - 34
    g["l"] = U(bend(lx, -O, RX - 4, ASC, "bl", (160, 150)), R(LX + 40, ASC - H, lx + T, ASC))
    ix = MX - T / 2 + 6
    g["i"] = U(R(ix, 0, ix + T, XH), R(LX + 54, XH - H, ix + T, XH), R(LX + 36, 0, RX - 36, H), dot(ix + T / 2, XH + 118))
    jx = MX + 40 - T / 2
    g["j"] = U(bend(LX + 34, DSC - O, jx + T, XH, "br", (175, 165)), R(LX + 74, XH - H, jx + T, XH), dot(jx + T / 2, XH + 118))
    kk = (LX + T * 0.8, 170)
    g["k"] = U(R(LX, 0, LX + T, ASC),
               I(clipy(U(diag((RX - T * 0.5, XH), kk, Td), clipy(diag((MX - 40, 315), (RX - T * 0.5, 0), Td * 1.02), -9, 315)), 0, XH), R(LX + T / 2, -9, 999, 999)))
    g["v"] = clipy(U(diag((LX + T * 0.46, XH), (MX, 0), Td), diag((RX - T * 0.46, XH), (MX, 0), Td)), 0, XH)
    g["w"] = clipy(U(diag((LX + Tw * 0.4, XH), (LX + 110, 0), Tw), clipy(U(diag((LX + 110, 0), (MX, 360), Tw), diag((MX, 360), (RX - 110, 0), Tw)), 0, 360), diag((RX - 110, 0), (RX - Tw * 0.4, XH), Tw)), 0, XH)
    g["x"] = clipy(U(diag((LX + T * 0.46, XH), (RX - T * 0.46, 0), Td), diag((RX - T * 0.46, XH), (LX + T * 0.46, 0), Td)), 0, XH)
    yr = ((RX - T * 0.46, XH), (LX + 96, DSC))
    yb = ext(yr[0], yr[1], 0)
    g["y"] = clipy(U(diag(yr[0], yr[1], Td), clipy(diag((LX + T * 0.46, XH), yb, Td), 0, XH)), DSC, XH)
    g["z"] = U(R(LX + 30, XH - H, RX - 24, XH), R(LX + 22, 0, RX - 20, H),
               clipy(diag((RX - 24 - T * 0.55, XH - H), (LX + 22 + T * 0.55, H), Td), H, XH - H))

    # ---------------- figures
    nx0, nx1 = LX + 10, RX - 10
    rung = rr(MX - T * 0.42, 255, MX + T * 0.42, 455, T * 0.2)
    g["0"] = U(ring(nx0, -O, nx1, CAP + O, (195, 230)), rung)   # the Helix rung zero
    g["1"] = U(R(MX - T / 2 + 20, 0, MX + T / 2 + 20, CAP), R(LX + 60, 0, RX - 50, H),
               clipy(diag((MX - T / 2 + 30, CAP + 4), (LX + 54, CAP - 190), T * 0.9), CAP - 250, CAP))
    two_top = D(I(ring(nx0, 300, nx1, CAP + O, (190, 200)), R(0, 470, 999, 999)), R(-99, 300, MX - 20, CAP - 195))
    g["2"] = U(two_top, clipy(diag((nx1 - T * 0.5, 480), (nx0 + T * 0.5, H / 2), Td), H, 480), R(nx0, 0, nx1 + 4, H))
    up3 = D(ring(nx0 + 22, CM - H / 2, nx1 - 8, CAP + O, (170, 165)), R(-99, CM - H / 2 - 5, MX - 50, CAP - 195))
    lo3 = D(ring(nx0, -O, nx1, CM + H / 2, (190, 180)), R(-99, 195, MX - 50, CM + H / 2 + 5))
    g["3"] = U(up3, lo3)
    f4 = nx1 - 70
    g["4"] = U(R(f4 - T, 0, f4, CAP), R(nx0, 200, nx1 + 8, 200 + H),
               clipy(diag((f4 - T * 0.5, CAP), (nx0 + T * 0.5, 200), Td), 200, CAP))
    g["5"] = U(R(nx0 + 26, CAP - H, nx1, CAP), R(nx0 + 26, 410, nx0 + 26 + T, CAP),
               D(ring(nx0, -O, nx1, 440, (0, (190, 175), (190, 175), (190, 175))), R(-99, 165, nx0 + 26, 440 - H + 1),
                 R(-99, 165, nx0 + 25, 999)))
    six_big = D(ring(nx0, -O, nx1, CAP + O, (195, 230)), R(MX, -99, 999, CAP - 195))
    g["6"] = U(six_big, ring(nx0, -O, nx1, 455, (190, 178)))
    g["9"] = rot180(g["6"], CAP / 2)
    g["7"] = U(R(nx0, CAP - H, nx1, CAP), clipy(diag((nx1 - T * 0.5, CAP - H), (MX - 50, 0), Td), 0, CAP - H))
    g["8"] = U(ring(nx0 + 24, CM - H / 2 + 4, nx1 - 24, CAP + O, (165, 160)), ring(nx0, -O, nx1, CM + H / 2 + 4, (190, 182)))

    # ---------------- punctuation
    g["space"] = pathops.Path()
    g["."] = dot(MX, 0)
    comma = U(dot(MX, 0), clipy(diag((MX + d * 0.2, d * 0.6), (MX - 70, -170), T * 0.82), -150, d))
    g[","] = comma
    g[":"] = U(dot(MX, 0), dot(MX, XH - d))
    g[";"] = U(comma, dot(MX, XH - d))
    g["!"] = U(R(MX - T / 2, 210, MX + T / 2, CAP), dot(MX, 0))
    q_top = D(ring(LX + 26, 370, RX - 26, CAP + O, ((185, 175), (185, 175), (150, 130), 0)),
              R(-99, 360, MX - T / 2, CAP - 190))
    g["?"] = U(q_top, R(MX - T / 2, 210, MX + T / 2, 370 + H), dot(MX, 0))
    g['"'] = U(R(MX - 85 - T / 2, CAP - 220, MX - 85 + T / 2, CAP), R(MX + 85 - T / 2, CAP - 220, MX + 85 + T / 2, CAP))
    g["'"] = R(MX - T / 2, CAP - 220, MX + T / 2, CAP)
    g["`"] = clipy(diag((MX - 70, CAP + 60), (MX + 60, CAP - 90), T * 0.9), CAP - 90, CAP + 60)
    g["^"] = clipy(U(diag((MX, CAP), (LX + 50, CM + 40), Td * 0.9), diag((MX, CAP), (RX - 50, CM + 40), Td * 0.9)), CM + 40, CAP)
    g["-"] = R(LX + 66, AX - H / 2, RX - 66, AX + H / 2)
    g["_"] = R(0, DSC + 50, ADV, DSC + 50 + H)
    g["+"] = U(R(LX + 30, AX - H / 2, RX - 30, AX + H / 2), R(MX - T / 2, AX - 205, MX + T / 2, AX + 205))
    g["="] = U(R(LX + 30, AX + 70, RX - 30, AX + 70 + H), R(LX + 30, AX - 70 - H, RX - 30, AX - 70))
    lt = U(bar((RX - 40, AX + 215), (LX + 60, AX), Td), bar((LX + 60, AX), (RX - 40, AX - 215), Td))
    lt = D(lt, R(-99, -999, LX + 40, 999))
    g["<"] = U(lt, rr(LX + 36, AX - Td * 0.5, LX + 36 + Td * 1.1, AX + Td * 0.5, 0))
    g[">"] = mirror(g["<"])
    g["/"] = clipy(diag((RX - 30, ASC), (LX + 30, DSC + 40), Td), DSC + 40, ASC)
    g["\\"] = mirror(g["/"])
    g["|"] = R(MX - T / 2, DSC, MX + T / 2, ASC)
    paren = I(ring(MX - 70, DSC + 10, MX + 700, ASC - 10, ((300, 330), 0, 0, (300, 330)), scale=False), R(MX - 70, DSC, RX - 40, ASC))
    g["("] = paren
    g[")"] = mirror(paren)
    g["["] = U(R(MX - 60, DSC + 10, MX - 60 + T, ASC - 10), R(MX - 60, ASC - 10 - H, RX - 46, ASC - 10),
               R(MX - 60, DSC + 10, RX - 46, DSC + 10 + H))
    g["]"] = mirror(g["["])
    bm = (ASC + DSC) / 2
    brace = U(bend(MX - T / 2, bm, RX - 40, ASC - 10, "tl", (95, 95)), bend(MX - T / 2, DSC + 10, RX - 40, bm, "bl", (95, 95)),
              R(LX + 40, bm - H / 2, MX, bm + H / 2))
    g["{"] = brace
    g["}"] = mirror(brace)
    acy, ar = CAP - 190, 175
    g["*"] = U(*[bar((MX + ar * math.cos(a), acy + ar * math.sin(a)), (MX - ar * math.cos(a), acy - ar * math.sin(a)), T * 0.86)
                 for a in (math.pi / 2, math.pi / 6, -math.pi / 6)])
    g["#"] = U(clipy(U(diag((246, CAP - 20), (206, 20), T * 0.9), diag((406, CAP - 20), (366, 20), T * 0.9)), 20, CAP - 20),
               R(LX + 8, CM + 100 - H / 2, RX - 8, CM + 100 + H / 2), R(LX + 8, CM - 120 - H / 2, RX - 8, CM - 120 + H / 2))
    g["$"] = U(s_shape(CAP - 40 + O, 40 - O, CM + 8, 16, (170, 150), (185, 160), 185),
               R(MX - T * 0.45, CAP - 60, MX + T * 0.45, CAP + 50), R(MX - T * 0.45, -50, MX + T * 0.45, 60))
    sm = T * 0.9
    g["%"] = U(ring(LX + 4, CAP - 270, 268, CAP, 90, sm, sm * .9), ring(332, 0, RX - 4, 270, 90, sm, sm * .9),
               clipy(diag((RX - T * 0.5, CAP), (LX + T * 0.5, 0), Td), 0, CAP))
    amp_top = ring(LX + 46, 392, MX + 96, CAP + O, (125, 125))
    amp_bot = D(ring(LX, -O, RX - 56, 445, ((140, 140), 0, (160, 160), (170, 170))), R(MX - 30, 120, 999, 999))
    amp_leg = clipy(diag((LX + 46 + T * 0.6, 430), (RX - T * 0.5, 0), Td), 0, 445)
    g["&"] = U(amp_top, amp_bot, amp_leg, clipy(diag((RX - 60, 330), (RX - 150, 120), T * 0.9), 120, 330))
    at_in = ring(MX - 85, 175, RX - 46, 470, ((100, 110), 0, 0, (100, 110)), T * 0.9, H * 0.9)
    at_out = D(ring(LX - 4, -60, RX + 2, CAP, ((200, 220), (200, 220), (60, 60), (200, 220)), T * 0.9, H * 0.9),
               R(RX - 140, -99, 999, 175 + H))
    g["@"] = U(at_in, at_out, R(RX - 46 - T * 0.9, 175, RX + 2, 470))
    # the Helix tilde: one full strand twist
    hump = I(ring(LX + 10, AX - 150, MX + T * 0.45, AX + 95, ((115, 110), (115, 110), 0, 0), T * 0.92, H * 0.92, False), R(0, AX - 75, 999, 999))
    trough = I(ring(MX - T * 0.45, AX - 95, RX - 10, AX + 150, (0, 0, (115, 110), (115, 110)), T * 0.92, H * 0.92, False), R(0, -999, 999, AX + 75))
    g["~"] = U(hump, trough)

    # ---------------- extras
    g["periodcentered"] = dot(MX, AX - d / 2)
    g["bullet"] = rr(MX - 85, AX - 85, MX + 85, AX + 85, 34)
    arr = U(R(LX + 10, AX - H / 2, RX - 30, AX + H / 2), bar((RX - 200, AX + 180), (RX - 20, AX), Td), bar((RX - 20, AX), (RX - 200, AX - 180), Td))
    g["arrowright"] = D(arr, R(RX - 18, -999, 999, 999))
    g["arrowleft"] = mirror(g["arrowright"])
    g["multiply"] = U(bar((LX + 70, AX + 190), (RX - 70, AX - 190), Td), bar((LX + 70, AX - 190), (RX - 70, AX + 190), Td))
    g["endash"] = R(0, AX - H / 2, ADV, AX + H / 2)
    g["emdash"] = R(0, AX - H / 2, ADV, AX + H / 2)
    st, sh = T * 0.62, H * 0.62
    g["registered"] = U(ring(LX, 300, RX, CAP + 70, (120, 120), st, sh),
                        R(MX - 70, 390, MX - 70 + st, CAP - 30), ring(MX - 70, 520, MX + 85, CAP - 30, (0, 50, 50, 0), st, sh),
                        clipy(diag((MX, 525), (MX + 95, 390), st), 390, 530))
    g["trademark"] = U(R(LX - 10, CAP - sh, MX - 30, CAP), R((LX + MX) / 2 - 20 - st / 2, 420, (LX + MX) / 2 - 20 + st / 2, CAP),
                       R(MX, 420, MX + st, CAP), R(RX + 10 - st, 420, RX + 10, CAP),
                       clipy(U(diag((MX + st / 2, CAP), (MX + 112, 520), st), diag((RX + 10 - st / 2, CAP), (MX + 112, 520), st)), 500, CAP))
    return g


NAMES = {
    "space": 0x20, "periodcentered": 0xB7, "arrowright": 0x2192, "arrowleft": 0x2190, "multiply": 0xD7,
    "endash": 0x2013, "emdash": 0x2014, "registered": 0xAE, "trademark": 0x2122, "bullet": 0x2022,
}
PUNCT = {
    "!": "exclam", '"': "quotedbl", "#": "numbersign", "$": "dollar", "%": "percent", "&": "ampersand",
    "'": "quotesingle", "(": "parenleft", ")": "parenright", "*": "asterisk", "+": "plus", ",": "comma",
    "-": "hyphen", ".": "period", "/": "slash", ":": "colon", ";": "semicolon", "<": "less", "=": "equal",
    ">": "greater", "?": "question", "@": "at", "[": "bracketleft", "\\": "backslash", "]": "bracketright",
    "^": "asciicircum", "_": "underscore", "`": "grave", "{": "braceleft", "|": "bar", "}": "braceright",
    "~": "asciitilde", "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
    "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


def charstring(path):
    path = pathops.Path(path)
    path.simplify(fix_winding=True)
    rec = RecordingPen()
    path.draw(rec)
    ap = AreaPen()
    rec.replay(ap)
    pen = T2CharStringPen(ADV, None)
    # PostScript outlines run counter-clockwise (positive area).
    rec.replay(ReverseContourPen(pen) if ap.value < 0 else pen)
    b = path.bounds if rec.value else (0, 0, 0, 0)
    return pen.getCharString(), b


def build(name, wclass, T, H, out_dir):
    defs = glyphs(T, H)
    order, cmap, cs, metrics = [".notdef"], {}, {}, {}
    nd = U(R(70, 0, 530, 700))
    nd = D(nd, R(70 + T, H, 530 - T, 700 - H))
    cs[".notdef"], b = charstring(nd)
    metrics[".notdef"] = (ADV, int(b[0]))
    for key, path in defs.items():
        gname, cp = (key, NAMES[key]) if key in NAMES else (PUNCT.get(key, key), ord(key))
        order.append(gname)
        cmap[cp] = gname
        cs[gname], b = charstring(path)
        metrics[gname] = (ADV, int(math.floor(b[0])))
    fb = FontBuilder(UPM, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    ps = f"HelixMono-{name}"
    fb.setupCFF(ps, {"FullName": f"Helix Mono {name}", "Weight": name, "isFixedPitch": True}, cs, {})
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=960, descent=-240)
    fb.setupNameTable({
        "familyName": "Helix Mono", "styleName": name, "uniqueFontIdentifier": f"HelixMono-HX02-{name}",
        "fullName": f"Helix Mono {name}", "psName": ps, "version": "Version 0.200",
        "copyright": "Copyright 2026 HelixDB", "designer": "HelixDB",
        "description": "Helix Mono HX-02: industrial monospace with the Helix rung zero.",
        "typographicFamily": "Helix Mono", "typographicSubfamily": name,
    })
    bold = wclass >= 700
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, sTypoLineGap=200, usWinAscent=960, usWinDescent=240,
                sxHeight=XH, sCapHeight=CAP, usWeightClass=wclass, achVendID="HLIX", version=4,
                fsSelection=(0x20 if bold else (0x40 if wclass == 400 else 0)) | 0x80)
    fb.setupPost(isFixedPitch=1, underlinePosition=-150, underlineThickness=int(H))
    fb.setupMaxp()
    f = fb.font
    f["OS/2"].panose.bFamilyType = 2
    f["OS/2"].panose.bProportion = 9
    if bold:
        f["head"].macStyle = 1
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    f.save(str(out / f"{ps}.otf"))
    f = TTFont(str(out / f"{ps}.otf"))
    f.flavor = "woff2"
    f.save(str(out / f"{ps}.woff2"))
    return out / f"{ps}.otf"


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "dist2"
    only = sys.argv[2:] or None
    for name, wc, T, H in WEIGHTS:
        if only and name not in only:
            continue
        print("built", build(name, wc, T, H, out))
