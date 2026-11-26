"""Write a specimen page of every character in every Helix Mono style. python specimen.py DIST OUTDIR

The fonts are embedded in the page, so it works opened straight from disk (browsers block font
files next to a file:// page).
"""
import sys, os, json, unicodedata, base64
from fontTools.ttLib import TTFont

dist, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
WEIGHTS = [("ExtraLight", 200), ("Light", 300), ("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700)]
faces = []
for w, n in WEIGHTS:
    for ital in (False, True):
        fn = f"HelixMono-{('Italic' if w == 'Regular' else w + 'Italic') if ital else w}.woff2"
        b64 = base64.b64encode(open(os.path.join(dist, fn), "rb").read()).decode()
        faces.append(f"@font-face{{font-family:'Helix Mono';src:url(data:font/woff2;base64,{b64}) format('woff2');"
                     f"font-weight:{n};font-style:{'italic' if ital else 'normal'};font-display:block}}")
f = TTFont(os.path.join(dist, "HelixMono-Regular.ttf"))
version = f["name"].getDebugName(5).split(";")[0].replace("Version ", "")
BLOCKS = [(0x20, 0x7F, "Basic Latin"), (0xA0, 0xFF, "Latin-1 Supplement"), (0x100, 0x17F, "Latin Extended-A"),
          (0x180, 0x24F, "Latin Extended-B"), (0x250, 0x2AF, "IPA Extensions"), (0x2B0, 0x2FF, "Spacing Modifiers"),
          (0x300, 0x36F, "Combining Marks"), (0x370, 0x3FF, "Greek"), (0x400, 0x52F, "Cyrillic"),
          (0x1E00, 0x1EFF, "Latin Extended Additional"), (0x2000, 0x206F, "General Punctuation"),
          (0x2070, 0x209F, "Superscripts & Subscripts"), (0x20A0, 0x20CF, "Currency"),
          (0x2100, 0x214F, "Letterlike Symbols"), (0x2150, 0x218F, "Number Forms"), (0x2190, 0x21FF, "Arrows"),
          (0x2200, 0x22FF, "Math Operators"), (0x2300, 0x23FF, "Misc Technical"), (0x2400, 0x245F, "Control Pictures"),
          (0x2460, 0x24FF, "Enclosed"), (0x2500, 0x257F, "Box Drawing"), (0x2580, 0x259F, "Block Elements"),
          (0x25A0, 0x25FF, "Geometric Shapes"), (0x2600, 0x26FF, "Misc Symbols"), (0x2700, 0x27BF, "Dingbats"),
          (0x27C0, 0x2BFF, "Arrows & Math, more"), (0xE000, 0xF8FF, "Private Use"), (0xFB00, 0xFFFF, "Specials & Forms"),
          (0x1D400, 0x1D7FF, "Math Alphanumerics")]
groups = {}
for cp in sorted(f.getBestCmap()):
    if cp < 0x20 or 0x7F <= cp < 0xA0 or cp in (0x20, 0xA0):
        continue
    name = next((b[2] for b in BLOCKS if b[0] <= cp <= b[1]), "Other")
    groups.setdefault(name, []).append(cp)
order = [b[2] for b in BLOCKS] + ["Other"]
data = [[g, groups[g]] for g in order if g in groups]
total = sum(len(v) for _, v in data)
names = {cp: unicodedata.name(chr(cp), "") for _, v in data for cp in v}

html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Helix Mono Specimen</title>
<style>
%(faces)s
:root{--bg:#fbfbfa;--fg:#141414;--muted:#77756f;--line:#e4e2dd;--cell:#fff;--acc:#d65414;--chip:#efede8}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#121212;--fg:#ececea;--muted:#8c8a85;--line:#2a2927;--cell:#191918;--acc:#f07a3c;--chip:#232220}}
:root[data-theme=dark]{--bg:#121212;--fg:#ececea;--muted:#8c8a85;--line:#2a2927;--cell:#191918;--acc:#f07a3c;--chip:#232220}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:'Helix Mono',ui-monospace,monospace;font-weight:400}
.wrap{max-width:1400px;margin:0 auto;padding:32px 24px 80px}
h1{font-weight:700;font-size:44px;letter-spacing:-.02em;margin:0 0 6px}
.sub{color:var(--muted);font-size:14px;margin:0 0 28px}
h2{font-size:13px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:44px 0 14px}
.bar{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 0;display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
.seg{display:flex;flex-wrap:wrap;gap:4px}
button{font:inherit;font-size:13px;color:var(--fg);background:var(--chip);border:1px solid transparent;border-radius:6px;padding:6px 10px;cursor:pointer}
button[aria-pressed=true]{background:var(--fg);color:var(--bg)}
label{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:8px}
.styles{display:grid;gap:2px}
.srow{display:grid;grid-template-columns:150px 1fr;gap:16px;align-items:baseline;padding:10px 0;border-bottom:1px solid var(--line);cursor:pointer}
.srow:hover .lbl{color:var(--acc)}
.srow.on .lbl{color:var(--acc)}
.lbl{font-size:12px;color:var(--muted);font-weight:400;font-style:normal}
.sample{font-size:26px;line-height:1.35;overflow-wrap:anywhere}
.sample small{display:block;font-size:17px;color:var(--muted)}
.block h3{font-size:13px;font-weight:600;margin:28px 0 10px;display:flex;gap:10px;align-items:baseline}
.block h3 span{color:var(--muted);font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--cw,72px),1fr));border-top:1px solid var(--line);border-left:1px solid var(--line)}
.c{border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--cell);aspect-ratio:3/4;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;min-width:0}
.c b{font-weight:inherit;font-size:var(--gs,40px);line-height:1}
.c i{font-style:normal;position:absolute;bottom:4px;font-size:9px;color:var(--muted);font-weight:400}
.c:hover{outline:2px solid var(--acc);outline-offset:-2px;z-index:1}
#glyphs{font-weight:var(--w,400);font-style:var(--st,normal)}
.tip{position:fixed;pointer-events:none;background:var(--fg);color:var(--bg);font-size:12px;padding:5px 8px;border-radius:5px;display:none;z-index:9;max-width:320px}
@media (max-width:640px){.srow{grid-template-columns:1fr;gap:4px}.sample{font-size:20px}h1{font-size:32px}.wrap{padding:20px 16px 60px}}
</style></head><body>
<div class="wrap">
<h1>Helix Mono</h1>
<p class="sub">Version %(version)s · 6 weights, each with an italic · %(total)d characters per style</p>

<h2>Every style</h2>
<div class="styles" id="styles"></div>

<h2>Every character</h2>
<div class="bar">
  <div class="seg" id="wbtns"></div>
  <div class="seg"><button id="ital" aria-pressed="false">Italic</button></div>
  <label>Size <input id="size" type="range" min="20" max="96" value="40"></label>
  <label><input id="dots" type="checkbox"> codes</label>
</div>
<div id="glyphs"></div>
</div>
<div class="tip" id="tip"></div>
<script>
const W=[["ExtraLight",200],["Light",300],["Regular",400],["Medium",500],["SemiBold",600],["Bold",700]];
const DATA=%(data)s, NAMES=%(names)s;
const S="The quick brown fox jumps over the lazy dog → {ok: 0x1F, err: null}";
const A="ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789 !?@#$%%&*";
let wt=400, it=false;
const styles=document.getElementById("styles");
for(const [n,w] of W) for(const i of [false,true]){
  const r=document.createElement("div"); r.className="srow"; r.dataset.w=w; r.dataset.i=i;
  r.innerHTML=`<div class="lbl">${i?(n=="Regular"?"Italic":n+" Italic"):n} · ${w}</div><div class="sample" style="font-weight:${w};font-style:${i?"italic":"normal"}">${S}<small>${A}</small></div>`;
  r.onclick=()=>{wt=w;it=i;apply();document.getElementById("glyphs").scrollIntoView({behavior:"smooth"})};
  styles.appendChild(r);
}
const wb=document.getElementById("wbtns");
for(const [n,w] of W){const b=document.createElement("button");b.textContent=n;b.dataset.w=w;b.onclick=()=>{wt=w;apply()};wb.appendChild(b)}
document.getElementById("ital").onclick=()=>{it=!it;apply()};
const g=document.getElementById("glyphs"); let html="";
const hex=c=>c.toString(16).toUpperCase().padStart(4,"0");
for(const [name,cps] of DATA){
  html+=`<div class="block"><h3>${name} <span>${cps.length}</span></h3><div class="grid">`;
  for(const c of cps){const ch=(c>=0x300&&c<=0x36F)?"\\u25CC"+String.fromCodePoint(c):String.fromCodePoint(c);
    html+=`<div class="c" data-c="${c}"><b>${ch.replace(/&/g,"&amp;").replace(/</g,"&lt;")}</b><i hidden>${hex(c)}</i></div>`}
  html+="</div></div>";
}
g.innerHTML=html;
function apply(){
  g.style.setProperty("--w",wt); g.style.setProperty("--st",it?"italic":"normal");
  for(const b of wb.children) b.setAttribute("aria-pressed",b.dataset.w==wt);
  document.getElementById("ital").setAttribute("aria-pressed",it);
  for(const r of styles.children) r.classList.toggle("on",r.dataset.w==wt&&(r.dataset.i==="true")===it);
  try{localStorage.setItem("hm-spec",JSON.stringify({wt,it}))}catch(e){}
}
const size=document.getElementById("size");
size.oninput=()=>{g.style.setProperty("--gs",size.value+"px");g.style.setProperty("--cw",Math.round(size.value*1.8)+"px")};
document.getElementById("dots").onchange=e=>{for(const x of g.querySelectorAll(".c i")) x.hidden=!e.target.checked};
const tip=document.getElementById("tip");
g.addEventListener("mousemove",e=>{const c=e.target.closest(".c");if(!c){tip.style.display="none";return}
  const cp=+c.dataset.c; tip.textContent=`U+${hex(cp)} ${NAMES[cp]||""}`; tip.style.display="block";
  tip.style.left=Math.min(e.clientX+14,innerWidth-330)+"px"; tip.style.top=(e.clientY+16)+"px"});
g.addEventListener("mouseleave",()=>tip.style.display="none");
try{const s=JSON.parse(localStorage.getItem("hm-spec")||"null");if(s){wt=s.wt;it=s.it}}catch(e){}
apply();
</script></body></html>"""
open(os.path.join(out, "index.html"), "w").write(html % dict(
    faces="\n".join(faces), version=version, total=total,
    data=json.dumps(data), names=json.dumps({str(k): v for k, v in names.items()})))
print(total, "characters", len(data), "blocks")
