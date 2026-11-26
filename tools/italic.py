"""Helix Mono italics: each finished upright slanted to JetBrains Mono's italic angle.

Slanting the finished upright keeps every Helix glyph edit in the italic. The slant is JetBrains'
own: 9 degrees, about the same centre (a point at x-height/2 hardly moves), so the italic sits in
the cell where JetBrains Mono Italic does.
"""
import math

ANGLE = 9.0  # degrees, JetBrains Mono Italic's post.italicAngle
SHIFT = -44  # x shift at the baseline, so the slant pivots near y = 278 as in JetBrains Mono Italic


def italicize(f):
    """Slant every outline in place and mark the font italic."""
    k = math.tan(math.radians(ANGLE))
    glyf = f["glyf"]
    for n in f.getGlyphOrder():
        g = glyf[n]
        if g.isComposite():
            for c in g.components:
                c.x = round(c.x + k * c.y)  # the base glyph is already slanted about the baseline
        elif g.numberOfContours > 0:
            g.coordinates = type(g.coordinates)(
                [(round(x + k * y + SHIFT), y) for x, y in g.coordinates])
        if hasattr(g, "program"):
            g.program.fromBytecode(b"")  # upright hinting no longer fits the slanted outlines
    for t in ("fpgm", "prep", "cvt ", "gasp"):
        if t in f:
            del f[t]
    hmtx = f["hmtx"]
    for n in f.getGlyphOrder():
        glyf[n].recalcBounds(glyf)
        hmtx[n] = (hmtx[n][0], getattr(glyf[n], "xMin", 0))
    f["post"].italicAngle = -ANGLE
    f["hhea"].caretSlopeRise, f["hhea"].caretSlopeRun = 1000, round(1000 * k)
    os2 = f["OS/2"]
    os2.fsSelection = (os2.fsSelection & ~(1 << 6)) | 1  # italic, not regular
    f["head"].macStyle |= 2
