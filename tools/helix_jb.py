"""Helix Mono (JB base): JetBrains Mono NL (OFL 1.1) renamed, with per-glyph edits.

Usage: python helix_jb.py SRC_TTF_DIR OUT_DIR
Per-letter edits go in EDITS: {glyph_name: fn(font, glyph_name)}; v0 = untouched baseline.
"""
import sys, os
from fontTools.ttLib import TTFont
import corners
import jbedit
import italic

WEIGHTS = ["ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold"]
# Which JetBrains Mono NL weight each Helix weight is built from. Regular is drawn as light as
# JetBrains Light, so ExtraLight and Light step down one each to stay distinct. Bold steps up one
# to JetBrains ExtraBold so it stays clearly heavier than SemiBold. Every glyph in a weight comes
# from the same JetBrains weight, so all its strokes are the same thickness.
SOURCES = {"ExtraLight": "Thin", "Light": "ExtraLight", "Regular": "Light",
           "Medium": "Medium", "SemiBold": "SemiBold", "Bold": "ExtraBold"}
WEIGHT_CLASS = {"ExtraLight": 200, "Light": 300, "Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}
VERSION = "0.46"
CORNER_K = 0.20  # v0.2: corners slightly more angular (0 = JetBrains original)
EDITS = {}  # filled in as per-letter changes come in


def rename(f, weight, ital=False):
    fam = "Helix Mono"
    if ital:  # Regular's italic is just "Italic"; the others are "<weight> Italic"
        style = "Italic" if weight == "Regular" else f"{weight} Italic"
    else:
        style = weight
    full, ps = f"{fam} {style}", f"HelixMono-{style.replace(' ', '')}"
    rib = weight in ("Regular", "Bold")
    name = f["name"]
    jb_copy = name.getDebugName(0) or "Copyright 2020 The JetBrains Mono Project Authors"
    for rec in list(name.names):
        if rec.nameID in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25):
            name.removeNames(nameID=rec.nameID)
    entries = {
        0: jb_copy + ". Helix Mono modifications copyright 2026 HelixDB.",
        1: fam if rib else f"{fam} {weight}",
        2: (("Bold Italic" if weight == "Bold" else "Italic") if ital else weight) if rib
           else ("Italic" if ital else "Regular"),
        3: f"{VERSION};HELX;{ps}",
        4: full,
        5: f"Version {VERSION}; based on JetBrains Mono 2.304",
        6: ps,
        16: fam,
        17: style,
    }
    for nid, s in entries.items():
        name.setName(s, nid, 3, 1, 0x409)
        name.setName(s, nid, 1, 0, 0)
    os2 = f["OS/2"]
    os2.achVendID = "HELX"
    os2.usWeightClass = WEIGHT_CLASS[weight]
    # fsSelection: bit 5 bold, bit 6 regular; head.macStyle bit 0 bold.
    os2.fsSelection = ((os2.fsSelection & ~0b1100001) | (1 << 5 if weight == "Bold" else 0)
                       | (1 if ital else 1 << 6 if weight == "Regular" else 0))
    f["head"].macStyle = (f["head"].macStyle & ~3) | (1 if weight == "Bold" else 0) | (2 if ital else 0)


def main(src, out):
    os.makedirs(out, exist_ok=True)
    for w in WEIGHTS:
        path = os.path.join(src, f"JetBrainsMonoNL-{SOURCES[w]}.ttf")
        f = TTFont(path)
        o = TTFont(path)
        corners.apply(f, CORNER_K)
        c = jbedit.measure(o)
        c.update(weight=w, src=src, Vbusy=c["V"], Hbusy=c["H"])
        for fn in jbedit.EDITS:
            fn(f, o, c)
        jbedit.finalize(f)
        rename(f, w)
        f.save(os.path.join(out, f"HelixMono-{w}.ttf"))
        f.flavor = "woff2"
        f.save(os.path.join(out, f"HelixMono-{w}.woff2"))
        # the italic is the finished upright, slanted (italic.py)
        it = TTFont(os.path.join(out, f"HelixMono-{w}.ttf"))
        italic.italicize(it)
        rename(it, w, ital=True)
        name = "Italic" if w == "Regular" else f"{w}Italic"
        it.save(os.path.join(out, f"HelixMono-{name}.ttf"))
        it.flavor = "woff2"
        it.save(os.path.join(out, f"HelixMono-{name}.woff2"))
        print(w, len(f.getGlyphOrder()), "glyphs, + italic")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
