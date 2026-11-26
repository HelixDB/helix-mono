"""Before/after strip. python ba.py OLD_DIST NEW_DIST OUT.png TEXT [weights]"""
import sys
from PIL import Image, ImageDraw, ImageFont
old, new, out, txt = sys.argv[1:5]
ws = sys.argv[5].split(",") if len(sys.argv) > 5 else ["Regular"]
size = 150
rows = [(w, d, lab) for w in ws for d, lab in ((old, "before"), (new, "after"))]
im = Image.new("RGB", (len(txt) * int(size * 0.6) + 260, len(rows) * (size + 40) + 30), "white")
dr = ImageDraw.Draw(im)
sm = ImageFont.truetype(f"{new}/HelixMono-Regular.ttf", 22)
y = 20
for w, d, lab in rows:
    dr.text((20, y + size * 0.45), f"{w}\n{lab}", font=sm, fill=(214, 84, 20) if lab == "after" else (150, 150, 150))
    dr.text((230, y), txt, font=ImageFont.truetype(f"{d}/HelixMono-{w}.ttf", size), fill="black")
    y += size + 40
im.save(out)
