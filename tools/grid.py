"""Labelled glyph grid for per-letter review. Usage: python grid.py DIST OUT.png [label]"""
import sys
from PIL import Image, ImageDraw, ImageFont

dist, out = sys.argv[1], sys.argv[2]
label = sys.argv[3] if len(sys.argv) > 3 else "BASELINE"
W, PAD, COLS, CELL_W, CELL_H = 2000, 60, 13, 144, 176
BG, INK, MUTED, RULE, ACC = (255, 255, 255), (17, 17, 17), (130, 130, 130), (225, 225, 225), (214, 84, 20)

F = lambda w, s: ImageFont.truetype(f"{dist}/HelixMono-{w}.ttf", s)
sections = [
    ("UPPERCASE", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ("LOWERCASE", "abcdefghijklmnopqrstuvwxyz"),
    ("FIGURES", "0123456789"),
    ("PUNCTUATION", "!?@#$%&*()[]{}<>+-=/\\|~^_:;'\"`.,"),
]
rows = sum((len(s) + COLS - 1) // COLS for _, s in sections)
weights = ["ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold"]
H = 250 + len(weights) * 70 + 40 + len(sections) * 70 + rows * CELL_H + 40
img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

small = F("Regular", 22)
d.text((PAD, 50), f"HELIX MONO  ·  {label}  ·  BASED ON JETBRAINS MONO (OFL 1.1)", font=small, fill=MUTED)
d.text((PAD, 90), "Helix Mono", font=F("Bold", 110), fill=INK)
y = 250
for w in weights:
    d.text((PAD, y + 18), w, font=small, fill=MUTED)
    d.text((PAD + 260, y), "Customer opened Ticket 0x1A", font=F(w, 52), fill=INK)
    y += 70
y += 40
big = F("Regular", 96)
tiny = F("Regular", 18)
for title, chars in sections:
    d.text((PAD, y + 20), f"/ {title}", font=small, fill=ACC)
    y += 70
    for i, ch in enumerate(chars):
        cx = PAD + (i % COLS) * CELL_W
        cy = y + (i // COLS) * CELL_H
        d.rectangle([cx, cy, cx + CELL_W - 8, cy + CELL_H - 8], outline=RULE, width=2)
        d.text((cx + 10, cy + 8), ch if ch.strip() else "sp", font=tiny, fill=MUTED)
        bb = d.textbbox((0, 0), ch, font=big, anchor="ls")
        d.text((cx + (CELL_W - 8) / 2 - (bb[0] + bb[2]) / 2, cy + 128), ch, font=big, fill=INK, anchor="ls")
        d.line([cx + 6, cy + 128, cx + CELL_W - 14, cy + 128], fill=(240, 200, 180), width=1)
    y += ((len(chars) + COLS - 1) // COLS) * CELL_H
img.save(out)
print(out, img.size)
