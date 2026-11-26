# Helix Mono build

Helix Mono is JetBrains Mono NL 2.304 (OFL 1.1) with Helix's own glyph edits. The site's fonts in
`src/fonts/helix-mono/` are built by these scripts.

## Build

1. Download JetBrains Mono 2.304 and unzip it. The build uses `fonts/ttf` (the `JetBrainsMonoNL-*.ttf`
   files).
2. Install the tools: `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
3. Build: `.venv/bin/python helix_jb.py <path-to>/fonts/ttf out`
4. Copy `out/*.woff2` to `src/fonts/helix-mono/`.
5. Optional: `.venv/bin/python specimen.py out specimen` writes `specimen/index.html`, every character
   in every style, with the fonts embedded so it opens straight from disk.

## Weights

`SOURCES` in `helix_jb.py` says which JetBrains weight each Helix weight starts from. Regular is drawn
as light as JetBrains Light, so ExtraLight and Light each step down one. Medium and SemiBold match
JetBrains. Bold steps up one to JetBrains ExtraBold, so it stays clearly heavier than SemiBold.
Every glyph in a weight comes from the same JetBrains weight, so all its strokes are the same
thickness.

Each weight also has an italic (`italic.py`): the finished upright slanted 9 degrees, JetBrains Mono
Italic's angle and placement, so every Helix edit carries over. The site doesn't load the italics.

- The & and ? that `jbedit.py` draws are as much lighter than the stems as JetBrains' own & and
  ? are in the same source weight (`jb_lightness`), so they don't look darker than the letters.
- The @ and & that `jbedit.py` draws follow the same rule, and the @ keeps a minimum counter
  (`AT_COUNTER`). ExtraLight's @ has a wider gap between its ring and its a (`AT_GAP`).

## Files

- `helix_jb.py`: entry point. Picks each weight's source, renames the family and runs every edit.
- `italic.py`: slants each finished upright into its italic.
- `specimen.py`: writes the specimen page of every character in every style.
- `corners.py`: makes the rounded corners slightly more angular.
- `jbedit.py`: the per-glyph edits (`EDITS` list): k/K, r with a square end (no lip) whose arm eases slightly down toward its end in one curve (`R_BEND`, `R_FLOW`), u as a turned n,
  the point of every V notch rounded off by a small circle that touches both edges, nothing else
  moved (`TIP_ROUND` x stem width, so heavier weights are rounder: a b d g h m n p q r, M, W).
  Notches side by side (m's two, M's, W's) are rounded to the same depth, so they stay level.
  t/f cuts, g and y tails (the g's bottom-left hook is its bottom-right corner mirrored, stem
  thickness included, and stays clear of the bowl; the y's foot stops below its crotch), 4/7, Q
  (its tail stays clear of the counter's left side, `Q_GAP`), 6, !, &, dots and others.
  M is exactly symmetric and the inner edges of its uprights run straight up its grooves. The t
  crossbar's right end is pulled in by `T_BAR_TRIM` x stem width (less in Bold, so it reaches further). The 0's dot is the shared dot
  size, but no wider than `ZERO_DOT` x its counter, so Bold's dot doesn't fill its counter.
- `helix_mono2.py`, `helix_mono3.py`: shared outline helpers used by `jbedit.py`.
- `grid.py`: draws a review sheet of every glyph. `python grid.py out sheet.png`

Change `VERSION` in `helix_jb.py` for each release. The licence is in `OFL.txt`.
