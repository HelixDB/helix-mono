"""Per-letter edits for Helix Mono (JetBrains Mono base). Each edit: fn(f, o, c) where
f = font being built (corner pass already applied), o = untouched source font, c = measured context."""
import copy
import json
import math
import os

import pathops
from pathops import Path, PathOp, op
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

import helix_mono3 as hm3


# ---------------------------------------------------------------- path helpers
def gpath(f, name):
    p = Path()
    f.getGlyphSet()[name].draw(p.getPen())
    return p


def poly(pts):
    p = Path()
    pen = p.getPen()
    if hm3._area(pts) < 0:
        pts = pts[::-1]
    pen.moveTo(pts[0])
    for q in pts[1:]:
        pen.lineTo(q)
    pen.closePath()
    return p


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def U(*ps):
    r = ps[0]
    for p in ps[1:]:
        r = op(r, p, PathOp.UNION, fix_winding=True, clockwise=True)
    return r


def D(a, b):
    return op(a, b, PathOp.DIFFERENCE, fix_winding=True, clockwise=True)


def I(a, b):
    return op(a, b, PathOp.INTERSECTION, fix_winding=True, clockwise=True)


def setpath(f, name, path):
    p = Path()
    path.draw(p.getPen())
    p.simplify(fix_winding=True, keep_starting_points=False, clockwise=True)
    pen = TTGlyphPen(None)
    p.draw(Cu2QuPen(pen, 0.6, reverse_direction=False))
    f["glyf"][name] = pen.glyph()


def hspans(p, y):
    r = I(p, rect(-2000, y - 0.5, 3000, y + 0.5))
    return sorted((c.bounds[0], c.bounds[2]) for c in r.contours)


def vspans(p, x):
    r = I(p, rect(x - 0.5, -2000, x + 0.5, 3000))
    return sorted((c.bounds[1], c.bounds[3]) for c in r.contours)


def contours(f, name):
    """Split a glyph into per-contour recording ops."""
    rec = RecordingPen()
    f.getGlyphSet()[name].draw(rec)
    out, cur = [], []
    for o_, a in rec.value:
        cur.append((o_, a))
        if o_ in ("closePath", "endPath"):
            out.append(cur)
            cur = []
    return out


def ops_path(ops_list):
    p = Path()
    pen = p.getPen()
    for c in ops_list:
        for o_, a in c:
            getattr(pen, o_)(*a)
    return p


def ops_bounds(c):
    pts = [pt for _, a in c for pt in a]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def stroke(pts, a, b, closed=False):
    pb = hm3.Pb(*pts[0])
    for p in pts[1:]:
        pb.L(*p)
    return hm3.stroke(pb, a, b, closed)


def embolden(p, r):
    s = Path()
    p.draw(s.getPen())
    s.stroke(2 * r, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    s.convertConicsToQuads()
    s.simplify(fix_winding=True, clockwise=True)
    return U(p, s)


def xf(p, sx, sy, dx, dy):
    q = Path()
    p.draw(q.getPen())
    return q.transform(sx, 0, 0, sy, dx, dy)


def glyph_coords(f, name):
    g = copy.deepcopy(f["glyf"][name])
    return g, g.coordinates


# ---------------------------------------------------------------- context
def measure(f):
    XH = f["OS/2"].sxHeight
    stemV = hspans(gpath(f, "dotlessi"), 300)[0]
    o = vspans(gpath(f, "o"), 300)
    return dict(XH=XH, CAP=f["OS/2"].sCapHeight, V=stemV[1] - stemV[0], H=o[0][1] - o[0][0])


# ---------------------------------------------------------------- edits
def ed_l(f, o, c):
    """l = a tall i (dotless i stretched to ascender)."""
    g, co = glyph_coords(f, "dotlessi")
    top = max(y for _, y in co)
    d = o["glyf"]["l"].yMax - top
    for i, (x, y) in enumerate(co):
        if y > c["XH"] * 0.55:
            co[i] = (x, y + d)
    f["glyf"]["l"] = g


def _dot_side(f, name="period"):
    for cn in contours(f, name):
        x0, y0, x1, y1 = ops_bounds(cn)
        return x1 - x0
    return 160


def comma_shape(cx, s):
    x0, x1 = cx - s / 2, cx + s / 2
    tw, drop, lean = 0.6 * s, 0.85 * s, 0.42 * s
    tail = poly([(x1 - tw, 0.3 * s), (x1, 0.3 * s), (x1 - lean, -drop), (x1 - lean - tw, -drop)])
    return U(rect(x0, 0, x1, s), tail)


def dot_size(o, c):
    """One shared square-dot side for . , ; : ! ? i j 0: halfway between the v0.9 dot and the stem width."""
    return round((_dot_side(o, "period") * 0.88 + c["V"]) / 2)


def ed_dots(f, o, c):
    """Square dots on . , ; : ! ? and i j (via uni0307)."""
    s = dot_size(o, c)
    for name in ["period", "colon", "exclam", "question", "uni0307", "semicolon", "comma"]:
        keep, adds = [], []
        for cn in contours(f, name):
            x0, y0, x1, y1 = ops_bounds(cn)
            w, h = x1 - x0, y1 - y0
            curvy = any(o_ == "qCurveTo" for o_, _ in cn)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if curvy and 0.75 < w / h < 1.35 and w < 260:  # round dot
                by = 0 if y0 < 20 else round(cy - s / 2)
                adds.append(rect(round(cx - s / 2), by, round(cx - s / 2) + s, by + s))
            elif name in ("comma", "semicolon") and y0 < 0:  # comma tail -> square + tail
                cx_ = cx if name == "comma" else None
                adds.append(("comma", cx_))
            else:
                keep.append(cn)
        parts = [ops_path(keep)] if keep else []
        for a in adds:
            if isinstance(a, tuple):
                cx_ = a[1]
                if cx_ is None:  # semicolon: align under its top dot
                    top = [cn for cn in contours(f, name) if ops_bounds(cn)[1] > 100][0]
                    b = ops_bounds(top)
                    cx_ = (b[0] + b[2]) / 2
                else:
                    pb = ops_bounds(contours(o, "period")[0])
                    cx_ = (pb[0] + pb[2]) / 2
                parts.append(comma_shape(round(cx_), s))
            else:
                parts.append(a)
        setpath(f, name, U(*parts))


KK = dict(K=dict(ja=0.45, px=0.35), k=dict(ja=0.48, px=0.46), k_yj=0.48, t=0.93)


def _kk(f, o, c, name, H, ja, px):
    """K/k: straight arm from the stem (centre line hits the stem's right edge at ja*H) to the
    top right; the leg branches off the arm's centre line px stem-widths right of the stem."""
    p = gpath(o, name)
    sL, sR = hspans(p, 60)[0]
    top = o["glyf"][name].yMax
    top_out = hspans(p, H - 5)[-1][1]
    bot_out = hspans(p, 5)[-1][1]
    V, t = c["V"], c["V"] * KK["t"]
    hw = lambda dx, dy: t / math.sin(math.atan2(dy, dx)) / 2  # horizontal half-width of a bar
    jy = ja * H
    ax = top_out - t
    for _ in range(8):
        ax = top_out - hw(ax - sR, H - jy)
    slope = (H - jy) / (ax - sR)                    # arm: dy/dx
    P = (sR + px * V, jy + px * V * slope)
    lx = bot_out - t
    for _ in range(8):
        lx = bot_out - hw(lx - P[0], P[1])

    def bar(p0, q):
        w = hw(abs(q[0] - p0[0]), abs(q[1] - p0[1]))
        return poly([(p0[0] - w, p0[1]), (p0[0] + w, p0[1]), (q[0] + w, q[1]), (q[0] - w, q[1])])
    arm = bar((sL, jy - (sR - sL) * slope), (ax, H))
    leg = bar(P, (lx, 0))
    body = U(rect(sL, 0, sR, top), arm, leg)
    setpath(f, name, I(body, rect(sL, 0, 2000, top)))


def _k_point(f, o, c, name, H, yj):
    """Arm and leg meet at ONE point on the stem: the inside corner (arm's lower edge meets the
    leg's upper edge) sits exactly on the stem's right edge at height yj*H."""
    p = gpath(o, name)
    sL, sR = hspans(p, 60)[0]
    top = o["glyf"][name].yMax
    top_out = hspans(p, H - 5)[-1][1]
    bot_out = hspans(p, 5)[-1][1]
    t = c["V"] * KK["t"]
    j = (sR, yj * H)

    def bar(q):  # parallelogram whose right edge runs from the junction j to q; horizontal end cuts
        th = math.atan2(abs(q[1] - j[1]), abs(q[0] - j[0]))
        w = t / math.sin(th)
        return poly([j, q, (q[0] - w, q[1]), (j[0] - w, j[1])])
    body = U(rect(sL, 0, sR, top), bar((top_out, H)), bar((bot_out, 0)))
    setpath(f, name, I(body, rect(sL, 0, 2000, top)))


KV = dict(K=0.46, k=0.48, dip=0.15)  # tip height (x H) and how far the tip dips into the stem (x V)


def _k_vee(f, o, c, name, H, yj):
    """Arm + leg form a sharp '<' whose outer point just touches the stem's right edge
    (dipping in by KV['dip'] x stem width) - no other overlap with the stem."""
    p = gpath(o, name)
    sL, sR = hspans(p, 60)[0]
    top = o["glyf"][name].yMax
    top_out = hspans(p, H - 5)[-1][1]
    bot_out = hspans(p, 5)[-1][1]
    V = c["V"]
    t = V * KK["t"]
    T = (sR - KV["dip"] * V, yj * H)

    def far_end(out_x, y):  # far end of a stroke whose left edge starts at T: (left x, horizontal width)
        qx = out_x - t
        for _ in range(8):
            w = t / math.sin(math.atan2(abs(y - T[1]), qx - T[0]))
            qx = out_x - w
        return qx, w
    ax, wa = far_end(top_out, H)
    lx, wl = far_end(bot_out, 0)

    def isect(p1, p2, p3, p4):
        d = (p1[0] - p2[0]) * (p3[1] - p4[1]) - (p1[1] - p2[1]) * (p3[0] - p4[0])
        a, b = p1[0] * p2[1] - p1[1] * p2[0], p3[0] * p4[1] - p3[1] * p4[0]
        return ((a * (p3[0] - p4[0]) - (p1[0] - p2[0]) * b) / d, (a * (p3[1] - p4[1]) - (p1[1] - p2[1]) * b) / d)
    crotch = isect((T[0] + wa, T[1]), (ax + wa, H), (T[0] + wl, T[1]), (lx + wl, 0))
    vee = poly([T, (ax, H), (ax + wa, H), crotch, (lx + wl, 0), (lx, 0)])
    body = U(rect(sL, 0, sR, top), vee)
    setpath(f, name, I(body, rect(sL, 0, 2000, top)))


def ed_k(f, o, c):
    _k_vee(f, o, c, "K", c["CAP"], KV["K"])
    _k_vee(f, o, c, "k", c["XH"], KV["k"])


def ed_four(f, o, c, dx=45):
    """4: move the vertical stem left."""
    g, co = glyph_coords(f, "four")
    xmax = max(x for x, _ in co)
    stemL = min(x for x, y in co if y == 0)
    stemTop = max(y for x, y in co if x == xmax)
    for i, (x, y) in enumerate(co):
        if x >= stemL - 0.5 and y <= stemTop + 0.5:
            co[i] = (x - dx, y)
    f["glyf"]["four"] = g


EIGHT = dict(K=0.62, RF=0.82, hT=0.30, hB=0.27, KS=0.22, TH=26, TC=0.38)  # v0.7: shallow pinched crossing (ref 8)


FOUR_BAR_OUT = 0.9  # how far the 4's crossbar sticks out right of the stem (x stem width)


def ed_seven_four(f, o, c):
    """7: drop the lip hanging off the left of the top bar. 4: crossbar runs through the stem
    and sticks out the right side."""
    _, co = glyph_coords(f, "seven")
    xmin = min(x for x, _ in co)
    lip_x = min(x for x, y in co if x > xmin and y > c["CAP"] / 2)  # inner edge of the lip
    bar_bot = max(y for x, y in co if x == lip_x)              # underside of the top bar
    lip_bot = min(y for x, y in co if x == xmin)
    setpath(f, "seven", D(gpath(f, "seven"), rect(xmin - 10, lip_bot - 10, lip_x, bar_bot)))

    _, co = glyph_coords(f, "four")
    stem_r = max(x for x, y in co if y == 0)              # the stem is the only part on the baseline
    stem_l = min(x for x, y in co if y == 0)
    bar_ys = sorted({y for x, y in co if x == stem_l and 0 < y < 400})  # bar bottom/top where it meets the stem
    b0, b1 = bar_ys[0], bar_ys[-1]
    setpath(f, "four", U(gpath(f, "four"), rect(stem_l, b0, round(stem_r + FOUR_BAR_OUT * c["V"]), b1)))


def ed_eight(f, o, c):
    """8: JetBrains' two rounded-rect bowls, but the middle is a crossing X instead of a pinched waist."""
    import os, json
    P = dict(EIGHT, **json.loads(os.environ.get("EIGHT", "{}")))
    K, RF, hT, hB, KS = P["K"], P["RF"], P["hT"], P["hB"], P["KS"]
    p = gpath(o, "eight")
    CAP = c["CAP"]
    v = vspans(p, 300)
    top_t, bot_t, mid = v[-1][1] - v[-1][0], v[0][1] - v[0][0], v[len(v) // 2]
    # v0.8: keep the original 8 and splice in only the crossing, between YB and YT where both are straight
    F8 = gpath(f, "eight")
    YT, YB = P.get("YT", 540 if c["weight"] == "Bold" else 550), P.get("YB", 210 if c["weight"] == "Bold" else 200)
    ht, hb = hspans(F8, YT), hspans(F8, YB)
    a_ = sum(s1 - s0 for s0, s1 in ht + hb) / 8
    b_ = (top_t + bot_t) / 4
    tL, tR = (ht[0][0] + ht[0][1]) / 2, (ht[-1][0] + ht[-1][1]) / 2
    bL, bR = (hb[0][0] + hb[0][1]) / 2, (hb[-1][0] + hb[-1][1]) / 2

    def splice(newp):
        keep = U(rect(-500, YT, 1500, 2000), rect(-500, -2000, 1500, YB))
        return U(I(F8, keep), I(newp, rect(-500, YB - 1, 1500, YT + 1)))
    ct, cb = v[-1][1] - b_, v[0][0] + b_
    yj = (mid[0] + mid[1]) / 2
    cx = (tL + tR) / 2
    rT, rB = (tR - tL) / 2 * RF, (bR - bL) / 2 * RF
    # middle: one shallow straight line per stroke through the centre, with rounded bends into the sides
    th = math.radians(P.get("TH", 24))
    ct_, st_, tn = math.cos(th), math.sin(th), math.tan(th)
    tc = (bR - bL) / 2 * P.get("TC", 0.38)
    kk = 0.60
    yR = yj + (tR - cx) * tn       # top-right bend (stroke 1 heads down-left)
    yL = yj - (cx - bL) * tn       # bottom-left bend
    yRb = yj - (bR - cx) * tn      # bottom-right bend (stroke 2 heads up-left)
    yLt = yj + (cx - tL) * tn      # top-left bend
    assert yR + tc <= YT <= ct - rT and cb + rB <= YB <= yL - tc, ("splice outside straight sides", yR + tc, ct - rT, cb + rB, yL - tc)
    pb = hm3.Pb(cx, ct).L(tR - rT, ct).hv(tR, ct - rT, k=K).L(tR, yR + tc)
    p2 = (tR - tc * ct_, yR - tc * st_)
    pb.C((tR, yR + tc - tc * kk), (p2[0] + tc * kk * ct_, p2[1] + tc * kk * st_), p2)
    q1 = (bL + tc * ct_, yL + tc * st_)
    pb.L(*q1)
    pb.C((q1[0] - tc * kk * ct_, q1[1] - tc * kk * st_), (bL, yL - tc + tc * kk), (bL, yL - tc))
    pb.L(bL, cb + rB).vh(bL + rB, cb, k=K).L(bR - rB, cb).hv(bR, cb + rB, k=K).L(bR, yRb - tc)
    p3 = (bR - tc * ct_, yRb + tc * st_)
    pb.C((bR, yRb - tc + tc * kk), (p3[0] + tc * kk * ct_, p3[1] - tc * kk * st_), p3)
    q2 = (tL + tc * ct_, yLt - tc * st_)
    pb.L(*q2)
    pb.C((q2[0] - tc * kk * ct_, q2[1] + tc * kk * st_), (tL, yLt + tc - tc * kk), (tL, yLt + tc))
    pb.L(tL, ct - rT).vh(tL + rT, ct, k=K).L(cx, ct)
    for jitter in (0, 0.13, 0.31, 0.57):
        try:
            q = hm3.Pb(cx + jitter, ct)
            q.pts = [(x + jitter, y) for x, y in pb.pts]
            setpath(f, "eight", splice(hm3.stroke(q, a_, b_, True)))
            return
        except pathops.PathOpsError:
            continue
    # fallback: skia's own stroker (round pen, mean of the two stroke widths)
    sk = Path(); pen = sk.getPen()
    pen.moveTo(pb.pts[0])
    for pt in pb.pts[1:]:
        pen.lineTo(pt)
    pen.closePath()
    sk.stroke(a_ + b_, pathops.LineCap.BUTT_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    sk.convertConicsToQuads()
    sk.simplify(fix_winding=True, clockwise=True)
    setpath(f, "eight", splice(sk))


def _stretch(f, name, box):
    """Stretch a glyph with straight sides to a new box, keeping stroke widths."""
    g, co = glyph_coords(f, name)
    xs, ys = [x for x, _ in co], [y for _, y in co]
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    for i, (x, y) in enumerate(co):
        x += (box[2] - max(xs)) if x > mx else (box[0] - min(xs))
        y += (box[3] - max(ys)) if y > my else (box[1] - min(ys))
        co[i] = (x, y)
    p = Path()
    g.draw(p.getPen(), f["glyf"])
    return p


AT_COUNTER = 90  # narrowest the inner a's counter of @ may get, in font units
AT_GAP = {"ExtraLight": 44}  # gap between the ring and the a, in font units, where a weight sets its own


def ed_at(f, o, c):
    """@: a single-storey a whose stem hooks into an open outer ring (a real @)."""
    ob = o["glyf"]["at"]
    V, H = c.get("Vbusy", c["V"]), c.get("Hbusy", c["H"])  # busy glyph: Bold draws it lighter
    ra, rb = V * 0.80 / 2, H * 0.80 / 2
    gap = AT_GAP.get(c["weight"], min(V * 0.45, 50))  # ring to a
    # Across the cell sit ring, gap, a, counter, a, gap, ring. If that leaves the a's counter under
    # AT_COUNTER (Bold), the strokes take only the weight the counter allows.
    span = ob.xMax - ob.xMin - 4
    s = min(2 * ra, (span - 2 * gap - AT_COUNTER) / 4)
    print("  @ counter", round(span - 4 * 2 * ra - 2 * gap), "->", round(span - 4 * s - 2 * gap)) if os.environ.get("ATDBG") else None
    ra, rb = s / 2, rb * s / (2 * ra)
    X0, X1 = ob.xMin + 2 + ra, ob.xMax - 2 - ra
    Y0, Y1 = -120 + rb, 650 - rb
    R = (X1 - X0) / 2 * 0.80
    ix0 = X0 + 2 * ra + gap
    sx = X1 - 2 * ra - gap
    iy0, iy1 = 115, 440
    r1 = (X1 - sx) / 2
    K = 0.62
    tail_end = sx + ra * 0.2
    pb = (hm3.Pb(sx, iy1).L(sx, iy0 + r1).vh(sx + r1, iy0, k=K).hv(X1, iy0 + r1, k=K)
          .L(X1, Y1 - R).vh(X1 - R, Y1, k=K).L(X0 + R, Y1).hv(X0, Y1 - R, k=K)
          .L(X0, Y0 + R).vh(X0 + R, Y0, k=K).L(tail_end, Y0))
    ring = hm3.stroke(pb, ra, rb, False)
    bw = (sx - ix0) / 2
    bowl = hm3.stroke(hm3.rrpath(ix0, iy0, sx, iy1, bw * 0.85, bw * 0.95), ra, rb, True)
    setpath(f, "at", U(ring, bowl))


AMP = dict(bx0=35, bx1=500, ux0=95, ux1=430, ty=0.50, fx=570, yA=0.42, yB=0.75, gx=80, gy=0.56, ul=0.77,
           lc=250, lw0=165, lwv=1.6, hh=95)  # v0.25: small near-square loop (width scales with weight) on a bigger bowl
if os.environ.get("AMP"):
    AMP.update(json.loads(os.environ["AMP"]))


def jb_lightness(o, name, ys, right=False):
    """How much lighter than its stems JetBrains draws a busy glyph: the narrowest stroke at heights
    ys (left stroke, or right with right=True) over the stem width, in the source font o."""
    p = gpath(o, name)
    ws = [(s[-1] if right else s[0]) for s in (hspans(p, y) for y in ys) if s]
    return min(min(b - a for a, b in ws) / measure(o)["V"], 1.0) if ws else 1.0


def ed_amp(f, o, c):
    """&: closed upper loop, crossing strokes, round lower bowl ending in a flat terminal, diagonal leg to a flat foot."""
    CAP = c["CAP"]
    # busy glyph: as much lighter than the stems as JetBrains draws its own & (Bold draws it lighter still)
    k = min(jb_lightness(o, "ampersand", range(120, 200, 10)), jb_lightness(o, "ampersand", range(560, 640, 10)))
    V = min(c.get("Vbusy", c["V"]), c["V"] * k)
    a, b = V * 0.5, min(c.get("Hbusy", c["H"]), c["H"] * k) * 0.5
    K = 0.62
    A = AMP
    x0, x1 = A["bx0"] + a, A["bx1"] - a
    y0 = -10 + b
    if "lc" in A:  # loop sized from the stroke weight so its counter stays open: width = lw0 + lwv * V
        lw = A["lw0"] + A["lwv"] * V
        ux0, ux1 = A["lc"] - lw / 2 + a, A["lc"] + lw / 2 - a
    else:
        ux0, ux1 = A["ux0"] + a, A["ux1"] - a
    uy1 = CAP + 10 - b
    rB = (x1 - x0) / 2 * 0.78
    rU = (ux1 - ux0) / 2 * 0.80
    ty = CAP * A["ty"]
    fx = A["fx"] - V * 0.55
    # stroke 1: terminal -> lower bowl -> up across to the loop's right side -> over the top -> down the left
    yA, yB = CAP * A["yA"], CAP * A["yB"]
    hA = (yB - yA) * 0.45
    pb = (hm3.Pb(x1, ty).L(x1, y0 + rB).vh(x1 - rB, y0, k=K).L(x0 + rB, y0).hv(x0, y0 + rB, k=K).L(x0, yA)
          .C((x0, yA + hA), (ux1, yB - hA), (ux1, yB)).L(ux1, uy1 - rU).vh(ux1 - rU, uy1, k=K)
          .L(ux0 + rU, uy1).hv(ux0, uy1 - rU, k=K).L(ux0, CAP * A.get("ul", 0.70)))
    # leg: from the loop's left side, bend into a straight diagonal to the foot
    G = (ux0 + A["gx"], CAP * A["gy"])
    Fp = (fx, -80)
    dx, dy = Fp[0] - G[0], Fp[1] - G[1]
    ln = math.hypot(dx, dy)
    ux, uy = dx / ln, dy / ln
    hh = A.get("hh", 60)
    pb.C((ux0, CAP * A.get("ul", 0.70) - hh), (G[0] - ux * hh, G[1] - uy * hh), G).L(*Fp)
    shape = hm3.stroke(pb, a, b, False)
    # flat foot on the baseline
    shape = D(shape, rect((x0 + x1) / 2, -500, 900, -10))  # foot flat at the bowl's overshoot line
    setpath(f, "ampersand", shape)
    # drop stroker slivers (tiny stray contours at heavy weights)
    cns = contours(f, "ampersand")
    keep = [cn for cn in cns if (lambda b: (b[2] - b[0]) * (b[3] - b[1]))(ops_bounds(cn)) > 1500]
    if len(keep) < len(cns):
        setpath(f, "ampersand", ops_path(keep))


def ed_j(f, o, c, cut=0.33):
    """j: shorter top arm."""
    g, co = glyph_coords(f, "uni0237")
    xmin = min(x for x, _ in co)
    stemL = min(x for x, y in co if y < c["XH"] * 0.5 and y > 0 and x > xmin + 20)
    d = (stemL - xmin) * cut
    for i, (x, y) in enumerate(co):
        if x == xmin and y > c["XH"] * 0.5:
            co[i] = (x + d, y)
    f["glyf"]["uni0237"] = g


Q_DROP = 25  # v0.19: strike moved down this many units


Q_GAP = 0.25  # least gap between the Q tail's top and the counter's left side (x tail width)


def ed_Q(f, o, c):
    """Q: a straight tail that starts inside the counter and crosses the lower-right of the bowl."""
    O_ = gpath(f, "O")
    b = O_.bounds
    t = c["V"] * 0.95
    p = ((b[0] + b[2]) / 2 - 10, c["CAP"] * 0.40 - Q_DROP)
    yb = -45 - Q_DROP
    th = math.radians(56)
    q = (p[0] + (p[1] - yb) / math.tan(th), yb)
    w = t / math.sin(th) / 2
    # the tail's top stays clear of the counter's left side (a narrow Bold counter would close off)
    inner_l = hspans(O_, p[1])[0][1]
    p = (max(p[0], inner_l + Q_GAP * t + w), p[1])
    q = (p[0] + (p[1] - yb) / math.tan(th), yb)
    bar = poly([(p[0] - w, p[1]), (p[0] + w, p[1]), (q[0] + w, q[1]), (q[0] - w, q[1])])
    setpath(f, "Q", U(O_, I(bar, rect(-500, -500, 599, 2000))))


def _loosen(f, o, name, s=1.9):
    """Scale each joining curve about its tangent corner -> rounder, less tight joins."""
    g = copy.deepcopy(o["glyf"][name])
    glyf = o["glyf"]
    coords, ends, flags = g.getCoordinates(glyf)
    pts = [list(p) for p in coords]
    start = 0
    for end in ends:
        idx = list(range(start, end + 1))
        n = len(idx)
        on = [flags[i] & 1 for i in idx]
        for a in range(n):
            if not on[a]:
                continue
            run, b = [], (a + 1) % n
            while not on[b] and len(run) < n:
                run.append(b)
                b = (b + 1) % n
            if not run or b == a:
                continue
            P0, P3 = pts[idx[a]], pts[idx[b]]
            A, B = pts[idx[run[0]]], pts[idx[run[-1]]]
            d0 = (A[0] - P0[0], A[1] - P0[1])
            d1 = (B[0] - P3[0], B[1] - P3[1])
            from corners import _isect
            r = _isect(P0, d0, P3, d1)
            if not r:
                continue
            t, u, X = r
            if t <= 0.5 or u <= 0.5:
                continue
            prev, nxt = pts[idx[(a - 1) % n]], pts[idx[(b + 1) % n]]
            lim0 = math.hypot(prev[0] - X[0], prev[1] - X[1]) - 8
            lim1 = math.hypot(nxt[0] - X[0], nxt[1] - X[1]) - 8
            r0, r1 = math.hypot(P0[0] - X[0], P0[1] - X[1]), math.hypot(P3[0] - X[0], P3[1] - X[1])
            k = min(s, lim0 / max(r0, 1e-6), lim1 / max(r1, 1e-6))
            if k <= 1:
                continue
            for j in [a] + run + [b]:
                p = pts[idx[j]]
                p[0], p[1] = X[0] + (p[0] - X[0]) * k, X[1] + (p[1] - X[1]) * k
        start = end + 1
    for i, (x, y) in enumerate(pts):
        g.coordinates[i] = (round(x), round(y))
    f["glyf"][name] = g


def _notches(f, name, max_angle=50):
    """Sharp concave tips (the narrow V gaps between strokes): (tip, unit bisector into the gap)."""
    glyf = f["glyf"]
    coords, ends, flags = glyf[name].getCoordinates(glyf)
    out, start = [], 0
    for end in ends:
        idx = list(range(start, end + 1))
        n = len(idx)
        for k in range(n):
            i = idx[k]
            if not flags[i] & 1:
                continue
            p, a, b = coords[i], coords[idx[(k - 1) % n]], coords[idx[(k + 1) % n]]
            u = (a[0] - p[0], a[1] - p[1]); v = (b[0] - p[0], b[1] - p[1])
            lu, lv = math.hypot(*u), math.hypot(*v)
            if lu < 1 or lv < 1:
                continue
            u, v = (u[0] / lu, u[1] / lv * lv / lu), (v[0] / lv, v[1] / lv)
            u = (a[0] - p[0]) / lu, (a[1] - p[1]) / lu
            ang = math.degrees(math.acos(max(-1, min(1, u[0] * v[0] + u[1] * v[1]))))
            cross = (p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0])
            if ang < max_angle and cross > 0:  # reflex for clockwise TT contours
                bx, by = u[0] + v[0], u[1] + v[1]
                lb = math.hypot(bx, by)
                out.append(((p[0], p[1]), (bx / lb, by / lb)))
        start = end + 1
    return out


TIP_ROUND = 0.06  # radius of the circle that rounds off the point of every V notch, x stem width


def _stroked(p, w):
    s = Path(); p.draw(s.getPen())
    s.stroke(w, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    s.convertConicsToQuads()
    return s


def _disc(c, r):
    s = Path(); s.moveTo(c[0], c[1]); s.lineTo(c[0] + 0.01, c[1])
    s.stroke(2 * r, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    s.convertConicsToQuads()
    return s


def _samples(p, step=0.5):
    """Points along a path's outline, about step units apart."""
    from fontTools.pens.basePen import decomposeQuadraticSegment
    out = []
    for cn in p.contours:
        cur = None
        for verb, pts in cn.segments:
            if verb == "moveTo":
                cur = pts[0]
                out.append(cur)
            elif verb == "lineTo":
                n = max(1, int(math.dist(cur, pts[0]) / step))
                out += [(cur[0] + (pts[0][0] - cur[0]) * k / n, cur[1] + (pts[0][1] - cur[1]) * k / n) for k in range(1, n + 1)]
                cur = pts[0]
            elif verb == "qCurveTo":
                for c1, e in decomposeQuadraticSegment(pts) if len(pts) > 2 else [pts]:
                    n = max(2, int((math.dist(cur, c1) + math.dist(c1, e)) / step))
                    for k in range(1, n + 1):
                        t = k / n
                        out.append(((1 - t) ** 2 * cur[0] + 2 * t * (1 - t) * c1[0] + t * t * e[0],
                                    (1 - t) ** 2 * cur[1] + 2 * t * (1 - t) * c1[1] + t * t * e[1]))
                    cur = e
            elif verb == "curveTo":
                c1, c2, e = pts
                n = max(3, int((math.dist(cur, c1) + math.dist(c1, c2) + math.dist(c2, e)) / step))
                for k in range(1, n + 1):
                    t = k / n; u = 1 - t
                    out.append((u ** 3 * cur[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * e[0],
                                u ** 3 * cur[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * e[1]))
                cur = e
    return out


def tip_round(G, tip, bis, rho, reach=150):
    """G with the point of the V gap at tip rounded off by a circle of radius rho, and nothing else
    changed. The circle is the first one, going up the V from its point, that touches both edges;
    the gap below it is filled. The fill is cut from the gap itself, so it keeps the glyph's own
    edges and ends in the circle's arc. Returns None when no such circle is found."""
    box = rect(tip[0] - reach, tip[1] - reach, tip[0] + reach, tip[1] + reach)
    Gl = op(G, box, PathOp.INTERSECTION)
    gap = D(box, Gl)
    centres = D(gap, _stroked(Gl, 2 * rho))  # where a rho circle fits
    cands = sorted(_samples(centres, 0.25), key=lambda q: math.dist(q, tip))
    centre = None
    for q in cands[:4000]:
        # the centre must be reached from the tip without crossing ink (not across a stroke)
        if not any(Gl.contains((tip[0] + (q[0] - tip[0]) * t / 20, tip[1] + (q[1] - tip[1]) * t / 20))
                   for t in range(2, 20)):
            centre = q
            break
    if centre is None:
        return None
    edge = [q for q in _samples(Gl, 0.25) if math.dist(q, centre) < 3 * rho]
    side = lambda q: bis[0] * (q[1] - centre[1]) - bis[1] * (q[0] - centre[0])
    left = [q for q in edge if side(q) > 0]
    right = [q for q in edge if side(q) < 0]
    if not left or not right:
        return None
    A = min(left, key=lambda q: math.dist(q, centre))
    B = min(right, key=lambda q: math.dist(q, centre))
    # the gap on the tip's side of the chord AB, less the circle
    ux, uy = B[0] - A[0], B[1] - A[1]
    lu = math.hypot(ux, uy)
    if lu < 1e-3:
        return None
    ux, uy = ux / lu, uy / lu
    nx, ny = -uy, ux
    if nx * (centre[0] - A[0]) + ny * (centre[1] - A[1]) > 0:
        nx, ny = -nx, -ny
    big = 4 * reach
    poly = Path(); pp = poly.getPen()
    pp.moveTo((A[0] - ux * big, A[1] - uy * big)); pp.lineTo((B[0] + ux * big, B[1] + uy * big))
    pp.lineTo((B[0] + ux * big + nx * big, B[1] + uy * big + ny * big))
    pp.lineTo((A[0] - ux * big + nx * big, A[1] - uy * big + ny * big)); pp.closePath()
    below = op(gap, poly, PathOp.INTERSECTION)
    # the piece that holds the V: a point halfway from the tip to the circle
    d = math.dist(tip, centre)
    k = max(d - rho, 0.5) / (2 * d)
    m = (tip[0] + (centre[0] - tip[0]) * k, tip[1] + (centre[1] - tip[1]) * k)
    piece = Path(); pen = piece.getPen()
    for cn in below.contours:
        if cn.contains(m):
            cn.draw(pen)
    if not piece.contours:
        return None
    # the circle exactly as far out as the edges, so it meets them tangent, without a kink
    fill = D(piece, _disc(centre, max(math.dist(A, centre), math.dist(B, centre)) + 0.02))
    return U(G, fill)


def tidy(f, name, r=1.5):
    """Merge each run of three or more outline points that sit within r units of each other into
    one on-curve point: the tiny zigzags left where a rounded tip meets an edge after rounding to
    the grid."""
    g = f["glyf"][name]
    coords, ends, flags = g.getCoordinates(f["glyf"])
    out_c, out_f, out_e, merged, start = [], [], [], 0, 0
    for end in ends:
        pts = [(tuple(coords[i]), flags[i] & 1) for i in range(start, end + 1)]
        start = end + 1
        # rotate so the contour starts at an on-curve point far from its neighbours
        k = next((i for i, p in enumerate(pts) if p[1] and math.dist(p[0], pts[i - 1][0]) > r), 0)
        pts = pts[k:] + pts[:k]
        res, i = [], 0
        while i < len(pts):
            j = i
            while j + 1 < len(pts) and math.dist(pts[j + 1][0], pts[i][0]) <= r:
                j += 1
            if j - i >= 2:
                ons = [p for p in pts[i:j + 1] if p[1]]
                res.append(((ons or pts[i:j + 1])[-1][0], 1))
                merged += 1
            else:
                res.extend(pts[i:j + 1])
            i = j + 1
        if len(res) >= 3:
            out_c += [p[0] for p in res]; out_f += [p[1] for p in res]; out_e.append(len(out_c) - 1)
    if merged:
        pen = TTGlyphPen(None)
        s0 = 0
        for e in out_e:
            seg = list(zip(out_c[s0:e + 1], out_f[s0:e + 1]))
            s0 = e + 1
            k = next(i for i, p in enumerate(seg) if p[1])
            seg = seg[k:] + seg[:k]
            pen.moveTo(seg[0][0]); offs = []
            for p, on in seg[1:] + [seg[0]]:
                if on:
                    pen.qCurveTo(*offs, p) if offs else pen.lineTo(p)
                    offs = []
                else:
                    offs.append(p)
            pen.closePath()
        f["glyf"][name] = pen.glyph()
    return merged


def clean_path(p, eps=1.0):
    """Drop segments shorter than eps (end point and every control point within eps of the start):
    the slivers path operations leave where two nearly equal edges meet."""
    out = Path()
    pen = out.getPen()
    for cn in p.contours:
        segs = list(cn.segments)
        start = None
        cur = None
        for verb, pts in segs:
            if verb == "moveTo":
                start = cur = pts[0]
                pen.moveTo(cur)
            elif verb in ("lineTo", "qCurveTo", "curveTo"):
                if all(math.dist(q, cur) < eps for q in pts):
                    continue
                getattr(pen, verb)(*pts)
                cur = pts[-1]
            elif verb in ("closePath", "endPath"):
                pen.closePath()
    out.simplify(fix_winding=True)
    return out


def _gap_bottom(G, tip, v):
    """Height where the V gap at tip now ends (v=+1: gap opens upward, so its lowest point)."""
    y = tip[1]
    for _ in range(400):
        if any(a - 1 <= tip[0] + 0.5 and b + 1 >= tip[0] - 0.5 or abs((a + b) / 2 - tip[0]) < 12
               for a, b in [(s1[1], s2[0]) for s1, s2 in zip(hspans(G, y), hspans(G, y)[1:])]):
            return y
        y += 0.5 * v
    return y


def round_tips(G, tips, rho):
    """Round off each tip. Tips side by side that open the same way (the two in m) end level:
    where one's circle would sit higher, it gets a smaller circle."""
    rhos = [rho] * len(tips)
    vert = [i for i, (t, b) in enumerate(tips) if abs(b[0]) < 1e-6]
    for v in (1, -1):
        group = [i for i in vert if tips[i][1][1] * v > 0]
        if len(group) < 2:
            continue
        bottom = lambda i, r: _gap_bottom(tip_round(G, tips[i][0], tips[i][1], r) or G, tips[i][0], v)
        bot = {i: bottom(i, rho) for i in group}
        target = min(bot.values()) if v > 0 else max(bot.values())
        for i in group:
            if abs(bot[i] - target) <= 1:
                continue
            lo, hi = 0.5, rho  # bisect the radius that lands this one's bottom on the target
            for _ in range(12):
                mid = (lo + hi) / 2
                if (bottom(i, mid) - target) * v > 0:
                    hi = mid
                else:
                    lo = mid
            rhos[i] = lo
    for (tip, b), r in zip(tips, rhos):
        G = tip_round(G, tip, b, r) or G
    return clean_path(G)


def round_notches(f, name, w0):
    """Fill each sharp V gap near its tip and give it a round end of width w0 (less tight corners)."""
    G = gpath(f, name)
    fills, cuts = [], []
    for (px, py), (bx, by) in _notches(f, name):
        phi = math.atan2(by, bx)
        rot = math.pi / 2 - phi
        cs, sn = math.cos(rot), math.sin(rot)
        Gr = Path(); G.draw(Gr.getPen())
        Gr = Gr.transform(1, 0, 0, 1, -px, -py).transform(cs, sn, -sn, cs, 0, 0)
        yc, gap = None, None
        for y in range(4, 600, 2):
            sp = hspans(Gr, y)
            left = [x1 for x0, x1 in sp if x1 <= 0.5]
            right = [x0 for x0, x1 in sp if x0 >= -0.5]
            if not left or not right:
                continue
            gx0, gx1 = max(left), min(right)
            if gx1 - gx0 >= w0 * 1.1:
                yc, gap = y, (gx0, gx1)
                break
        if yc is None:
            continue
        gc = (gap[0] + gap[1]) / 2
        fill = rect(gap[0] - 2, -6, gap[1] + 2, yc)
        disc = Path(); dp = disc.getPen()
        N = 48
        pts = [(gc + w0 / 2 * math.cos(2 * math.pi * i / N), yc + w0 / 2 * math.sin(2 * math.pi * i / N)) for i in range(N)]
        disc = poly(pts)
        piece = D(fill, disc)
        back = piece.transform(cs, -sn, sn, cs, 0, 0).transform(1, 0, 0, 1, px, py)
        fills.append(back)
    if fills:
        setpath(f, name, U(G, *fills))


def _straight_M(f):
    """M: exactly symmetric, and the inner edge of each upright runs straight up its groove
    (JetBrains tapers the uprights, so the grooves leaned toward the middle)."""
    p = gpath(f, "M")
    x0, _, x1, y1 = p.bounds
    mid = f["hmtx"]["M"][0] / 2
    inner = max(hspans(p, y)[0][1] for y in range(10, int(y1 * 0.45), 10))  # widest the left upright gets
    half = U(I(p, rect(x0 - 10, -10, mid, y1 + 10)), rect(x0, 0, inner, y1))
    setpath(f, "M", U(half, half.transform(-1, 0, 0, 1, 2 * mid, 0)))


def ed_MW(f, o, c):
    """M and W: the points of their V notches are rounded off like every other notch."""
    _straight_M(f)
    for n in ("M", "W"):
        tips = _notches(f, n)
        if tips:
            setpath(f, n, round_tips(gpath(f, n), tips, TIP_ROUND * c["V"]))
            tidy(f, n)


T_BAR_TRIM = {"Bold": 0.2}  # how far the right end of the t crossbar is pulled in, x stem width
T_BAR_TRIM_DEFAULT = 0.4
CUT_DEG = 30  # angle of the cut on top of the t stem (from horizontal)
BAR_CUT_DEG = 65  # angle of the cut on the left end of the t and f crossbars


def _cut_bar_left(f, name, c):
    """Diagonal '/' cut on the left end of the crossbar (the horizontal near x-height)."""
    g, co = glyph_coords(f, name)
    band = [(i, x, y) for i, (x, y) in enumerate(co) if c["XH"] * 0.6 < y < c["XH"] * 1.12]
    xmin = min(x for _, x, _ in band)
    ends = sorted((i for i, x, y in band if x == xmin), key=lambda i: co[i][1])
    lo, hi = ends[0], ends[-1]
    th = co[hi][1] - co[lo][1]
    stemL = hspans(gpath(f, name), co[hi][1] + 4)[0][0]  # stem's left edge just above the bar
    cut = min(th / math.tan(math.radians(BAR_CUT_DEG)), stemL - co[hi][0] - 0.12 * c["V"])
    co[hi] = (co[hi][0] + cut, co[hi][1])
    f["glyf"][name] = g


def ed_tf(f, o, c):
    """Diagonal cuts: t = top of stem + left end of crossbar; f = left end of crossbar."""
    g, co = glyph_coords(f, "t")
    ymax = max(y for _, y in co)
    tops = sorted(i for i, (x, y) in enumerate(co) if y == ymax)
    li = min(tops, key=lambda i: co[i][0])
    ri = max(tops, key=lambda i: co[i][0])
    cut = (co[ri][0] - co[li][0]) * math.tan(math.radians(CUT_DEG))
    co[li] = (co[li][0], co[li][1] - cut)
    f["glyf"]["t"] = g
    _cut_bar_left(f, "t", c)
    _cut_bar_left(f, "f", c)
    _trim_bar_right(f, "t", c, T_BAR_TRIM.get(c["weight"], T_BAR_TRIM_DEFAULT))


def _trim_bar_right(f, name, c, k):
    """Pull the right end of the crossbar in by k x stem width."""
    g, co = glyph_coords(f, name)
    band = [(i, x) for i, (x, y) in enumerate(co) if c["XH"] * 0.6 < y < c["XH"] * 1.12]
    xmax = max(x for _, x in band)
    d = round(c["V"] * k)
    for i, x in band:
        if x == xmax:
            co[i] = (x - d, co[i][1])
    f["glyf"][name] = g


def ed_question(f, o, c):
    """?: rounded hook ending in a flat left terminal, stem centred over the square dot."""
    CAP = c["CAP"]
    # as much lighter than the stems as JetBrains draws its own ? stem (Bold draws it lighter still)
    k = jb_lightness(o, "question", range(250, 300, 10))
    V = min(c.get("Vbusy", c["V"]), c["V"] * k)
    a, b = V * 0.5, min(c.get("Hbusy", c["H"]), c["H"] * k) * 0.5
    K = 0.62
    dot = [cn for cn in contours(f, "question") if ops_bounds(cn)[3] < 200][0]
    db = ops_bounds(dot)
    sx = (db[0] + db[2]) / 2
    qx0, qx1 = 118 + a, 485 - a
    ct = CAP + 10 - b
    r = (qx1 - qx0) / 2 * 0.80
    yh = CAP * 0.45
    r2 = min(r, (qx1 - sx) * 0.55)
    r3 = c["V"] * 0.55
    pb = (hm3.Pb(qx0, CAP * 0.70).L(qx0, ct - r).vh(qx0 + r, ct, k=K).L(qx1 - r, ct).hv(qx1, ct - r, k=K)
          .L(qx1, yh + r2).vh(qx1 - r2, yh, k=K).L(sx + r3, yh).hv(sx, yh - r3, k=K).L(sx, CAP * 0.27))
    hook = hm3.stroke(pb, a, b, False)
    setpath(f, "question", U(hook, ops_path([dot])))


ZERO_DOT = 0.55  # widest the 0's dot can be, x the width of its counter


def ed_small_dots(f, o, c):
    """Re-square the dots on i j ! ? (after ed_question) and the 0 at the shared dot size."""
    s = dot_size(o, c)
    for name in ("uni0307", "exclam", "question"):
        keep, dots = [], []
        for cn in contours(f, name):
            x0, y0, x1, y1 = ops_bounds(cn)
            w, h = x1 - x0, y1 - y0
            if len(cn) <= 6 and w < 220 and 0.75 < w / max(h, 1) < 1.35:
                dots.append((x0, y0, x1, y1))
            else:
                keep.append(cn)
        parts = [ops_path(keep)] if keep else []
        for x0, y0, x1, y1 in dots:
            cx = round((x0 + x1) / 2 - s / 2)
            by = 0 if y0 < 20 else round((y0 + y1) / 2 - s / 2)
            parts.append(rect(cx, by, cx + s, by + s))
        setpath(f, name, U(*parts))
    # 0: its inner dot (the smallest contour) becomes the same square
    cns = contours(f, "zero")
    area = lambda cn: (ops_bounds(cn)[2] - ops_bounds(cn)[0]) * (ops_bounds(cn)[3] - ops_bounds(cn)[1])
    dot = min(cns, key=area)
    x0, y0, x1, y1 = ops_bounds(dot)
    # no wider than ZERO_DOT x the counter, or a heavy 0's dot fills its counter
    zp = gpath(f, "zero")
    sp = hspans(zp, (y0 + y1) / 2)
    s = min(s, round(ZERO_DOT * (sp[-1][0] - sp[0][1])))
    cx, cy = round((x0 + x1) / 2 - s / 2), round((y0 + y1) / 2 - s / 2)
    setpath(f, "zero", U(ops_path([cn for cn in cns if cn is not dot]), rect(cx, cy, cx + s, cy + s)))


def ed_six(f, o, c):
    """6: lift it so the bowl sits on the baseline (yMin 0) instead of overshooting below."""
    g, co = glyph_coords(f, "six")
    dy = -min(y for _, y in co)
    for i, (x, y) in enumerate(co):
        co[i] = (x, y + dy)
    f["glyf"]["six"] = g


EXCLAM = dict(par=0.40, bot=0.60)  # parallel for the top `par` of the stem, then taper to `bot` x top width


def ed_exclam(f, o, c):
    """!: stem as wide as a letter stem, straight-sided for the top half, then tapering to a narrower flat end."""
    cns = sorted(contours(f, "exclam"), key=lambda cn: ops_bounds(cn)[1])
    dot, stem = ops_bounds(cns[0]), ops_bounds(cns[-1])
    cx = (dot[0] + dot[2]) / 2
    wt = c["V"]                      # v0.22: top = letter stem width
    wb = wt * EXCLAM["bot"]
    y0, y1 = stem[1], stem[3]
    ym = y1 - (y1 - y0) * EXCLAM["par"]
    new = poly([(cx - wt / 2, y1), (cx + wt / 2, y1), (cx + wt / 2, ym), (cx + wb / 2, y0),
                (cx - wb / 2, y0), (cx - wt / 2, ym)])
    setpath(f, "exclam", U(ops_path([cns[0]]), new))


def _stroke_path(pts, width):
    """Stroke a centre line (('L', p) / ('Q', ctrl, p) steps from pts[0]) with butt caps."""
    p = Path()
    pen = p.getPen()
    pen.moveTo(pts[0])
    for step in pts[1:]:
        if step[0] == "Q":
            pen.qCurveTo(step[1], step[2])
        else:
            pen.lineTo(step[1])
    pen.endPath()
    p.stroke(width, pathops.LineCap.BUTT_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    p.convertConicsToQuads()
    p.simplify(fix_winding=True, clockwise=True)
    return p


G_HOOK = dict(R=1.1, e=0.35, gap=0.35)  # g tail: turn radius, straight rise after it, least gap under the bowl (x tail thickness)


def ed_g(f, o, c):
    """g: the tail runs left, then curves up at the bottom left into an upright terminal."""
    p = gpath(f, "g")
    g = f["glyf"]["g"]
    g.recalcBounds(f["glyf"])
    y0 = g.yMin
    t = vspans(p, 250)[0][1] - y0  # tail thickness
    xcut = max(x for (x, y), fl in zip(g.coordinates, g.flags) if fl & 1 and y == y0)
    yc = y0 + t / 2
    x0 = g.xMin + t / 2
    R = G_HOOK["R"] * t
    top = yc + R + G_HOOK["e"] * t
    # a thick tail would rise into the bowl: keep a gap of G_HOOK["gap"] x t under the bowl's bottom
    bowl = min(sp[0] for sp in vspans(p, (g.xMin + g.xMax) / 2 - 40) if sp[0] > y0 + t + 5)
    top = max(min(top, bowl - G_HOOK["gap"] * t), yc + R)
    tail = _stroke_path(
        [(xcut + 1, yc), ("L", (x0 + R, yc)), ("Q", (x0, yc), (x0, yc + R)), ("L", (x0, top))], t
    )
    p = D(p, rect(-200, y0 - 50, xcut, y0 + t + 6))
    setpath(f, "g", U(p, tail))


def ed_g_hook(f, o, c):
    """g: the hook at the bottom left of the tail is the bottom-right corner mirrored (outside and
    inside, so its upright is as thick as the stem), and its upright still stops at the same
    height."""
    p = gpath(f, "g")
    x0, y0, x1, _ = p.bounds
    low = [hspans(p, y) for y in range(int(y0) + 4, 0, 4)]
    hx = min(sp[0][0] for sp in low if sp)  # the hook's left edge
    ycut = max(sp[1] for sp in vspans(p, hx + 3) if sp[0] < 0)  # where its upright stops
    a = (hx + x1) / 2
    yt = next(sp[1] for sp in vspans(p, a) if sp[0] < y0 + 1)  # top of the tail at the middle
    box = rect(a, y0 - 10, x1 + 10, ycut)
    rest = D(box, p)
    outside = Path(); inside = Path()
    for cn in rest.contours:  # below the corner, or inside it (above the tail)
        cn.draw((outside if cn.contains((x1 + 5, y0 - 5)) else inside).getPen())
    solid = D(box, outside)
    mirror = lambda q: q.transform(-1, 0, 0, 1, 2 * a, 0)
    hole = U(mirror(inside), rect(a - 1, yt, a + 1, ycut + 1))
    hook = D(mirror(solid), hole)
    setpath(f, "g", U(D(p, rect(x0 - 10, y0 - 10, a, ycut + 0.5)), hook))


Y_FLICK = dict(r=0.9, tail=0.35)  # y foot: turn radius and the flat run after it (x stroke width)


def ed_y(f, o, c):
    """y: the descender turns left at the bottom into a short flick."""
    p = gpath(f, "y")
    co = f["glyf"]["y"].coordinates
    (lx0, ly0), (lx1, ly1) = co[0], co[1]  # left edge of the descender, bottom up
    (rx1, ry1), (rx0, ry0) = co[12], co[13]  # right edge, top down
    k = ((lx1 - lx0) / (ly1 - ly0) + (rx1 - rx0) / (ry1 - ry0)) / 2  # dx per dy
    w = (rx0 - lx0) / math.sqrt(1 + k * k)  # stroke width across the diagonal
    y0 = ly0
    cx = lambda y: (lx0 + rx0) / 2 + k * (y - y0)
    yc = y0 + w / 2
    r = Y_FLICK["r"] * w
    # Corner of the centre line, then back up along the diagonal by r and along the foot by r.
    ay = yc + r / math.sqrt(1 + k * k)
    hy = min(ay + 1.6 * w, ly1 + 0.5 * w)  # stop below the crotch, or a heavy stroke fills it
    foot = _stroke_path(
        [(cx(hy), hy), ("L", (cx(ay), ay)), ("Q", (cx(yc), yc), (cx(yc) - r, yc)), ("L", (cx(yc) - r - Y_FLICK["tail"] * w, yc))],
        w,
    )
    # Cut just above where the turn starts, and below the arms (the descender's left edge ends at ly1).
    p = D(p, rect(-200, y0 - 50, 900, min(ay + 0.3 * w, ly1 - 2)))
    setpath(f, "y", U(p, foot))


def ed_r(f, o, c):
    """r: no lip, square end. The arm rounds up from the stem to its highest point, then eases down
    in one curve (R_BEND, R_FLOW) to a square end, its underside following the same bend."""
    p = gpath(f, "r")
    x0, y0, x1, y1 = p.bounds
    stem = hspans(p, 200)[0]
    best = None  # (x, underside y) where the arm's underside is highest
    top = None  # (x, y) where the arm's top is highest
    for x in range(int(stem[1]) + 4, int(x1) - 2, 2):
        arm = [s for s in vspans(p, x) if s[1] > y1 - 40]
        if arm and (best is None or arm[0][0] > best[1]):
            best = (x, arm[0][0])
        if arm and (top is None or arm[0][1] > top[1] + 0.01):
            top = (x, arm[0][1])
    xp, yin = best
    p = D(p, rect(xp, -200, 900, yin))
    p = U(p, rect(top[0], yin, x1, top[1]))
    # from its highest point the arm eases down to the end in one flowing curve: level at first,
    # bending more and more toward the end (a cubic, same thickness all along)
    xb, yt = top
    drop = R_BEND * (yt - yin)
    L = x1 - xb
    c1, c2 = xb + R_FLOW[0] * L, xb + R_FLOW[1] * L
    band = Path(); pen = band.getPen()
    pen.moveTo((xb, yt)); pen.curveTo((c1, yt), (c2, yt), (x1, yt - drop))
    pen.lineTo((x1, yin - drop)); pen.curveTo((c2, yin), (c1, yin), (xb, yin)); pen.closePath()
    setpath(f, "r", U(D(p, rect(xb, yin - 1, x1 + 10, yt + 10)), band))


R_BEND = 0.3  # how far the end of the r's arm bends down, x the arm's thickness
R_FLOW = (1 / 3, 2 / 3)  # the bend's two handles along the arm: higher keeps it level longer


# ---------------------------------------------------------------- quiff
# Where an arch or bowl leaves a stem (n, h, m, r, b, p, d, q, g, a), the gap between them ends in a
# sharp V. Its point is rounded off with a small circle (radius TIP_ROUND x stem, so heavier
# weights are rounder); nothing else changes.
QUIFF_GLYPHS = "a b d g h m n p q r aogonek dcaron dcroat eng thorn".split()


def quiff_tips(p, XH):
    """Tips of V gaps that open toward the x-height (v=+1) or downward (v=-1) and close within
    0.4 x-height. Scans start at several heights so a bowl above the baseline (g) is found too."""
    tips = []
    for v, starts in ((1, [XH - k for k in range(12, 100, 12)]), (-1, list(range(12, 100, 12)))):
        for y0 in starts:
            sp = hspans(p, y0)
            for i in range(len(sp) - 1):
                cur, y, closed = (sp[i][1], sp[i + 1][0]), y0, False
                while abs(y - y0) < 0.4 * XH:
                    y -= v
                    s2 = hspans(p, y)
                    ng = next(((s2[k][1], s2[k + 1][0]) for k in range(len(s2) - 1)
                               if s2[k][1] < cur[1] and s2[k + 1][0] > cur[0]), None)
                    if ng is None:
                        closed = True
                        break
                    cur = ng
                # a V tapers to nothing; a plain inside corner closes while still wide
                if closed and cur[1] - cur[0] < 6 and abs(y - y0) > 8:
                    tip = ((cur[0] + cur[1]) / 2, y + v)
                    if all(math.hypot(tip[0] - q[0][0], tip[1] - q[0][1]) > 6 for q in tips):
                        tips.append((tip, (0.0, float(v))))
    return tips


def ed_quiff(f, o, c):
    for name in QUIFF_GLYPHS:
        if name not in f["glyf"] or f["glyf"][name].isComposite():
            continue
        p = gpath(f, name)
        tips = quiff_tips(p, c["XH"])
        if os.environ.get("QDBG"):
            print("  quiff", name, len(tips), round(TIP_ROUND * c["V"], 1))
        if tips:
            setpath(f, name, round_tips(p, tips, TIP_ROUND * c["V"]))
            m = tidy(f, name)
            if os.environ.get("QDBG"):
                print("  tidy", name, m)


def ed_u(f, o, c):
    """u: the n turned 180 degrees in its cell, so the right stem runs straight down to a square
    corner on the baseline, mirroring the corner where the n's stem meets the x-height."""
    from fontTools.pens.transformPen import TransformPen
    p = Path()
    adv = f["hmtx"]["n"][0]
    f.getGlyphSet()["n"].draw(TransformPen(p.getPen(), (-1, 0, 0, -1, adv, c["XH"])))
    was = gpath(f, "u")
    setpath(f, "u", p)
    # u with ogonek and u with horn have their own outlines, so they get their mark put on the new u.
    # The ogonek now hangs from the right stem, so it is taken from a-ogonek (same stem position).
    for name, src, base in (("uogonek", "aogonek", gpath(f, "a")), ("uhorn", "uhorn", was)):
        if name not in f["glyf"] or f["glyf"][name].isComposite():
            continue
        mark = Path()
        for cn in D(gpath(f, src), base).contours:
            x0, y0, x1, y1 = cn.bounds
            if (x1 - x0) * (y1 - y0) > 1500:  # drop slivers left where the outlines differ slightly
                cn.draw(mark.getPen())
        setpath(f, name, U(p, mark))


EDITS = [ed_l, ed_dots, ed_k, ed_four, ed_seven_four, ed_eight, ed_at, ed_amp, ed_j, ed_Q, ed_MW, ed_tf, ed_question, ed_small_dots, ed_exclam, ed_six, ed_g, ed_g_hook, ed_y, ed_r, ed_quiff, ed_u]


def finalize(f):
    glyf, hmtx = f["glyf"], f["hmtx"]
    for n in f.getGlyphOrder():
        glyf[n].recalcBounds(glyf)
    for n in f.getGlyphOrder():
        adv, _ = hmtx[n]
        hmtx[n] = (adv, getattr(glyf[n], "xMin", 0))
