"""Eigene Neuer-Tab-Startseite über ein Custom-URL-Schema ``app://newtab``.

Warum ein eigenes Schema statt einer file://-Seite: so können wir die Seite
dynamisch mit dem aktuellen Theme erzeugen UND das Wallpaper (Bild/GIF/Video)
aus ``themes/`` ausliefern, ohne file://-Sicherheitsbeschränkungen.

Farben laufen über CSS-Variablen (:root). Bei reinem Farbwechsel ruft das
Fenster ``window.__setColors(...)`` per JS auf → sofort, ohne Reload. Nur wenn
sich Wallpaper/Animation ändern, wird die Seite neu geladen.

Routen:
  app://newtab/            -> generiertes HTML (Uhr, Suche, Hintergrund)
  app://newtab/wallpaper   -> Rohdaten des Wallpapers des aktuellen Themes
"""

from PyQt6.QtCore import QBuffer, QIODevice, QByteArray, QUrlQuery, Qt
from PyQt6.QtGui import QImage, QImageReader
from PyQt6.QtWebEngineCore import (
    QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler,
    QWebEngineUrlRequestJob,
)

from .theming import THEMES_DIR, DEFAULT_THEME

SCHEME = b"app"

_MIME = {
    "mp4": b"video/mp4",
    "webm": b"video/webm",
    "ogg": b"video/ogg",
    "gif": b"image/gif",
    "png": b"image/png",
    "jpg": b"image/jpeg",
    "jpeg": b"image/jpeg",
    "webp": b"image/webp",
}


def register_app_scheme() -> None:
    """Muss vor der QApplication-Instanz laufen (siehe main.py)."""
    scheme = QWebEngineUrlScheme(SCHEME)
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.ContentSecurityPolicyIgnored
        | QWebEngineUrlScheme.Flag.CorsEnabled
    )
    QWebEngineUrlScheme.registerScheme(scheme)


class AppSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self):
        super().__init__()
        self.theme = dict(DEFAULT_THEME)
        self._rev = 0  # steigt pro Theme → Cache-Buster für das Wallpaper-URL
        self.glossy = True  # Glas-Look der Startseite (vom Glanz-Schalter gesetzt)
        self.glass = (0.65, 0.35, 0.45)  # (Frost, Kante, Dicke) je 0–1
        self.immersive = False  # Bild-Theme + Glas-Leisten → .bg an Fenster-Cover koppeln
        self.insets = (0, 0, 0, 0)  # Chrome-Höhen (top, right, bottom, left) für .bg-Insets
        self.dim_override = None  # Abdunklung im Immersiv-Modus = Host-dim (sonst None)
        self._blur_cache = {}  # (Wallpaper-Pfad, Frost) → geblurrte PNG-Bytes (Glas-Frost)

    def set_theme(self, theme: dict) -> None:
        self.theme = {**DEFAULT_THEME, **(theme or {})}
        self._rev += 1

    def requestStarted(self, job) -> None:  # noqa: N802 (Qt-Signatur)
        path = job.requestUrl().path()
        if path == "/wallpaper":
            self._serve_wallpaper(job)
        elif path in ("", "/"):
            html = build_newtab_html(
                self.theme, self._rev, self.glossy, self.glass,
                self.immersive, self.insets, self.dim_override,
            ).encode("utf-8")
            self._reply(job, b"text/html", html)
        else:
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)

    def _serve_wallpaper(self, job) -> None:
        wp = self.theme.get("wallpaper")
        if wp:
            path = THEMES_DIR / wp
            if path.is_file():
                ext = path.suffix.lower().lstrip(".")
                # ?blur=<0..1> → Wallpaper Qt-seitig runter-/hochskalieren (gleicher
                # Downscale-Algorithmus wie der Leisten-Frost) und als PNG ausliefern →
                # das Glas zeigt dieselbe Körnung statt des glatten CSS-filter:blur.
                blur = self._blur_param(job)
                if blur > 0 and ext not in ("mp4", "webm", "ogg"):
                    png = self._blurred_png(str(path), blur)
                    if png is not None:
                        self._reply(job, b"image/png", png)
                        return
                mime = _MIME.get(ext, b"application/octet-stream")
                self._reply(job, mime, path.read_bytes())
                return
        job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)

    @staticmethod
    def _blur_param(job) -> float:
        q = QUrlQuery(job.requestUrl())
        try:
            return max(0.0, min(1.0, float(q.queryItemValue("blur"))))
        except (ValueError, TypeError):
            return 0.0

    def _blurred_png(self, path: str, frost: float):
        """Wallpaper per Downscale→Upscale weichzeichnen (identisch zum Leisten-Frost in
        window._blur_pixmap) und als PNG-Bytes liefern. Pro (Datei, Frost) gecacht."""
        key = (path, round(frost, 2))
        cached = self._blur_cache.get(key)
        if cached is not None:
            return cached
        img = QImage(path)
        if img.isNull():
            return None
        if img.width() > 1600:  # auf Anzeige-nahe Grösse begrenzen (Tempo + Körnung wie Chrome)
            img = img.scaledToWidth(1600, Qt.TransformationMode.SmoothTransformation)
        f = 1.0 + frost * 22.0
        sw = max(1, int(img.width() / f))
        sh = max(1, int(img.height() / f))
        small = img.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.FastTransformation)
        blurred = small.scaled(img.width(), img.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        blurred.save(buf, "PNG")
        buf.close()
        data = bytes(ba)
        self._blur_cache[key] = data
        return data

    @staticmethod
    def _reply(job, mime: bytes, data: bytes) -> None:
        buf = QBuffer(job)
        buf.setData(data)
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(mime, buf)


_handler = None


def get_handler() -> AppSchemeHandler:
    global _handler
    if _handler is None:
        _handler = AppSchemeHandler()
    return _handler


# --- HTML-Erzeugung -------------------------------------------------------
_MATRIX_JS = """
(function(){
const c=document.getElementById('anim'),x=c.getContext('2d');
function rs(){c.width=window.innerWidth;c.height=window.innerHeight;}
rs();window.addEventListener('resize',rs);
let drops=Array(Math.ceil(c.width/16)).fill(1);
const ch='アイウエオカキクケサシ0123456789ABCDEF<>/*+=';
function draw(){
 x.fillStyle='rgba(0,0,0,0.07)';x.fillRect(0,0,c.width,c.height);
 x.fillStyle='__ACC__';x.font='15px monospace';
 for(let i=0;i<drops.length;i++){
  x.fillText(ch[Math.floor(Math.random()*ch.length)],i*16,drops[i]*16);
  if(drops[i]*16>c.height&&Math.random()>0.975)drops[i]=0;
  drops[i]++;
 }
}
setInterval(draw,50);
})();
"""

_STARS_JS = """
(function(){
const c=document.getElementById('anim'),x=c.getContext('2d');
function rs(){c.width=window.innerWidth;c.height=window.innerHeight;}
rs();window.addEventListener('resize',rs);
let st=[...Array(180)].map(()=>({x:Math.random()*c.width,y:Math.random()*c.height,z:Math.random()*1.4+0.3}));
function draw(){
 x.fillStyle='__BGC__';x.fillRect(0,0,c.width,c.height);
 x.fillStyle='__ACC__';
 for(const s of st){ s.x-=s.z; if(s.x<0){s.x=c.width;s.y=Math.random()*c.height;}
  x.globalAlpha=Math.min(1,s.z/1.6); x.fillRect(s.x,s.y,s.z*1.7,s.z*1.7); }
 x.globalAlpha=1; requestAnimationFrame(draw);
}
draw();
})();
"""

_GRID_JS = """
(function(){
const c=document.getElementById('anim'),x=c.getContext('2d');
function rs(){c.width=window.innerWidth;c.height=window.innerHeight;}
rs();window.addEventListener('resize',rs);
let off=0;
function draw(){
 const w=c.width,h=c.height,hz=h*0.42,cx=w/2;
 x.fillStyle='__BGC__';x.fillRect(0,0,w,h);
 x.strokeStyle='__ACC__';x.lineWidth=1.2;
 x.globalAlpha=0.32;
 for(let i=-12;i<=12;i++){ x.beginPath();x.moveTo(cx+i*26,hz);x.lineTo(cx+i*(w/9),h);x.stroke(); }
 for(let i=0;i<20;i++){
  let p=((i+off)%20)/20, y=hz+(h-hz)*p*p;
  x.globalAlpha=0.08+0.4*p; x.beginPath();x.moveTo(0,y);x.lineTo(w,y);x.stroke();
 }
 x.globalAlpha=1; off+=0.05; requestAnimationFrame(draw);
}
draw();
})();
"""

_ORBS_JS = """
(function(){
const c=document.getElementById('anim'),x=c.getContext('2d');
function rs(){c.width=window.innerWidth;c.height=window.innerHeight;}
rs();window.addEventListener('resize',rs);
let orbs=[...Array(22)].map(()=>({x:Math.random()*c.width,y:Math.random()*c.height,r:20+Math.random()*70,s:0.2+Math.random()*0.5,a:0.05+Math.random()*0.13}));
function draw(){
 x.fillStyle='__BGC__';x.fillRect(0,0,c.width,c.height);
 for(const o of orbs){
  o.y-=o.s; if(o.y+o.r<0){o.y=c.height+o.r;o.x=Math.random()*c.width;}
  let g=x.createRadialGradient(o.x,o.y,0,o.x,o.y,o.r);
  g.addColorStop(0,'__ACC__');g.addColorStop(1,'transparent');
  x.globalAlpha=o.a;x.fillStyle=g;x.beginPath();x.arc(o.x,o.y,o.r,0,7);x.fill();
 }
 x.globalAlpha=1;requestAnimationFrame(draw);
}
draw();
})();
"""

_WAVE_JS = """
(function(){
const c=document.getElementById('anim'),x=c.getContext('2d');
function rs(){c.width=window.innerWidth;c.height=window.innerHeight;}
rs();window.addEventListener('resize',rs);
let t=0;
function draw(){
 x.fillStyle='__BGC__';x.fillRect(0,0,c.width,c.height);
 x.strokeStyle='__ACC__';
 for(let k=0;k<4;k++){
  x.globalAlpha=0.10+k*0.06;x.lineWidth=2;x.beginPath();
  const baseY=c.height*(0.50+k*0.11), amp=28+k*14, len=0.008-k*0.0012;
  for(let px=0;px<=c.width;px+=8){
   let y=baseY+Math.sin(px*len+t+k)*amp;
   px===0?x.moveTo(px,y):x.lineTo(px,y);
  }
  x.stroke();
 }
 x.globalAlpha=1;t+=0.03;requestAnimationFrame(draw);
}
draw();
})();
"""

_CONSTELLATION_JS = """
(function(){
const c=document.getElementById('anim'),x=c.getContext('2d');
function rs(){c.width=window.innerWidth;c.height=window.innerHeight;}
rs();window.addEventListener('resize',rs);
let pts=[...Array(48)].map(()=>({x:Math.random()*c.width,y:Math.random()*c.height,vx:(Math.random()-0.5)*0.4,vy:(Math.random()-0.5)*0.4}));
function draw(){
 x.fillStyle='__BGC__';x.fillRect(0,0,c.width,c.height);
 for(const p of pts){p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>c.width)p.vx*=-1;if(p.y<0||p.y>c.height)p.vy*=-1;}
 x.strokeStyle='__ACC__';
 for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
  let dx=pts[i].x-pts[j].x,dy=pts[i].y-pts[j].y,d=Math.hypot(dx,dy);
  if(d<120){x.globalAlpha=(1-d/120)*0.4;x.beginPath();x.moveTo(pts[i].x,pts[i].y);x.lineTo(pts[j].x,pts[j].y);x.stroke();}
 }
 x.globalAlpha=0.85;x.fillStyle='__ACC__';
 for(const p of pts){x.beginPath();x.arc(p.x,p.y,1.6,0,7);x.fill();}
 x.globalAlpha=1;requestAnimationFrame(draw);
}
draw();
})();
"""

_CANVAS_ANIMS = {
    "matrix": _MATRIX_JS,
    "stars": _STARS_JS,
    "grid": _GRID_JS,
    "orbs": _ORBS_JS,
    "wave": _WAVE_JS,
    "constellation": _CONSTELLATION_JS,
}

_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
/* Typisierte Custom-Properties: sonst aktualisiert Chromium `var()` in `calc()`
   innerhalb von rgba()/box-shadow NICHT live (Slider ändert die Variable, aber das
   Rendering bleibt eingefroren). Mit @property lösen sie sich korrekt neu auf. */
@property --g-frost { syntax:"<number>"; inherits:true; initial-value:0.65; }
@property --g-edge { syntax:"<number>"; inherits:true; initial-value:0.35; }
@property --g-depth { syntax:"<number>"; inherits:true; initial-value:0.45; }
:root {
  --accent: __ACCENT__;
  --bg: __BG__;
  --bg-alt: __BG_ALT__;
  --text: __TEXT__;
  --text-dim: __TEXT_DIM__;
  --g-frost: __G_FROST__;   /* Frost 0–1 → Blur-Radius der Wallpaper-Kopie */
  --g-edge: __G_EDGE__;     /* Kante 0–1 */
  --g-depth: __G_DEPTH__;   /* Dicke 0–1 */
  --wp: __WP__;             /* scharfes Wallpaper (oder none) */
  --wp-frost: __WP_FROST__; /* Qt-vorab-geblurrtes Wallpaper fürs Glas (Downscale-Körnung) */
  /* Entsättigte SVG-Noise als Glas-Körnung (simuliert Brechung, ~0 GPU-Kosten,
     Zero-Request Data-URI). Idee von Gemini, hier entsättigt + tilebar. */
  --glass-noise: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 140"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter><rect width="100%" height="100%" filter="url(%23n)" opacity="0.09"/></svg>');
}
* { margin:0; padding:0; box-sizing:border-box; }
html,body { height:100%; overflow:hidden;
  font-family:"Segoe UI Variable Display","Segoe UI",system-ui,sans-serif;
  background:__HTMLBG__; color:var(--text); -webkit-font-smoothing:antialiased; }
.bg { position:fixed; inset:0; width:100%; height:100%; object-fit:cover; z-index:0; }
.overlay { position:fixed; inset:0; background:rgba(0,0,0,__DIM__); z-index:1; }
/* WICHTIG: KEINE opacity-Animation/-Filter auf .content — das macht .content zur
   "Backdrop-Root", dann blurrt backdrop-filter der Kinder nur bis .content (ohne
   Hintergrund) statt bis zum .bg-Canvas → Blur unsichtbar (Gemini-Analyse). */
.content { position:relative; z-index:2; min-height:100%; display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:36px; padding:40px 24px; }
.clockwrap { text-align:center; }
.clock { font-size:82px; font-weight:600; letter-spacing:1px; line-height:1;
  font-variant-numeric:tabular-nums; text-shadow:0 4px 32px rgba(0,0,0,.45); }
.sub { margin-top:10px; font-size:15.5px; color:var(--text-dim); letter-spacing:.3px;
  text-shadow:0 2px 16px rgba(0,0,0,.5); }
/* Suchleiste = Glas-Shell (Input transparent darin), damit auch sie via ::before
   ein echtes filter:blur des Wallpapers tragen kann (<input> selbst kann kein ::before).
   overflow:hidden clippt die Blur-Kopie auf die runde Form (kappt leider den Aussen-
   schatten – Fokus daher über border-color statt Ring). */
.search { width:min(620px,88vw); position:relative; border-radius:30px; overflow:hidden;
  border:1px solid rgba(255,255,255, calc(.08 + var(--g-edge)*.7));
  border-top-color:rgba(255,255,255, calc(.20 + var(--g-edge)*.5));
  transition:border-color .25s; }
/* Glas-Hintergrund: Qt-vorab-geblurrtes Wallpaper (--wp-frost). JS (alignGlass) setzt
   background-size/-position pro Element INLINE → deckungsgleich mit dem Haupt-Hintergrund
   (echtes Glas), statt dass jedes Element das ganze Bild cover-zeigt. Frost 0 → opacity 0
   = klares Glas. Eigenes <i>-Element statt ::before, damit JS es direkt stylen kann. */
.gb { position:absolute; inset:0; z-index:0; pointer-events:none;
  background-image:var(--wp-frost); background-repeat:no-repeat;
  opacity:var(--g-frost); }
.search::after { content:""; position:absolute; inset:0; z-index:1; pointer-events:none;
  background-color:rgba(12,14,18,.10);  /* kleiner KONSTANTER Ton, NICHT vom Frost → Slider dunkelt nicht */
  background-image:var(--glass-noise); background-size:140px 140px; }
.search svg { position:absolute; left:20px; top:50%; transform:translateY(-50%);
  width:20px; height:20px; stroke:var(--text-dim); fill:none; stroke-width:2;
  stroke-linecap:round; pointer-events:none; z-index:3; transition:stroke .25s; }
.search:focus-within svg { stroke:var(--accent); }
.search input { width:100%; padding:17px 22px 17px 54px; border:none; background:transparent;
  position:relative; z-index:2; color:var(--text); font-size:16px; outline:none; }
.search input::placeholder { color:var(--text-dim); }
.search:focus-within { border-color:var(--accent); }
.dial { display:flex; flex-wrap:wrap; justify-content:center; gap:16px; max-width:660px; }
.tile { width:94px; padding:16px 8px 12px; border-radius:18px; text-decoration:none;
  display:flex; flex-direction:column; align-items:center; gap:10px; color:var(--text);
  position:relative; overflow:hidden; background:transparent;
  border:1px solid rgba(255,255,255, calc(.05 + var(--g-edge)*.45));
  border-top-color:rgba(255,255,255, calc(.14 + var(--g-edge)*.5));
  box-shadow:0 8px 22px rgba(0,0,0, calc(.24 + var(--g-depth)*.30));
  transition:transform .22s cubic-bezier(.2,.7,.2,1), box-shadow .22s, border-color .22s; }
.tile::after { content:""; position:absolute; inset:0; z-index:1; pointer-events:none;
  background-color:rgba(12,14,18,.10);  /* kleiner KONSTANTER Ton, NICHT vom Frost */
  background-image:var(--glass-noise); background-size:140px 140px; }
.tile > :not(.gb) { position:relative; z-index:2; }
.tile:hover { transform:translateY(-5px);
  border-color:color-mix(in srgb,var(--accent) 55%,transparent);
  box-shadow:0 16px 30px rgba(0,0,0,.46); }
.tile .ic { width:44px; height:44px; border-radius:13px; display:grid; place-items:center;
  font-size:18px; font-weight:700; color:var(--text); background:rgba(255,255,255,.05);
  border:1.5px solid color-mix(in srgb, var(--text) 45%, transparent);
  text-shadow:0 1px 3px rgba(0,0,0,.55); }
.tile .nm { font-size:12.5px; color:var(--text-dim); max-width:84px; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; transition:color .22s; }
.tile:hover .nm { color:var(--text); }
/* Glanz aus → flacher, matter Look (kein Verlauf/Blur/Glaskante) */
body.flat .search, body.flat .tile {
  background:rgba(12,14,18,.6); border:1px solid rgba(255,255,255,.08);
  border-top-color:rgba(255,255,255,.08); transform:none;
  box-shadow:0 6px 18px rgba(0,0,0,.22); }
body.flat .search input { background:transparent; }
body.flat .search::before, body.flat .search::after,
body.flat .tile::before, body.flat .tile::after { display:none; }
body.flat .search:focus-within { border-color:var(--accent); }
body.flat .tile:hover { transform:translateY(-3px); box-shadow:0 10px 24px rgba(0,0,0,.3); }
.aurora { position:fixed; inset:-25%; z-index:0; opacity:.6; filter:blur(48px);
  will-change:transform; transform:translateZ(0);
  background:
    radial-gradient(40% 40% at 30% 30%, var(--accent) 0%, transparent 60%),
    radial-gradient(45% 45% at 70% 65%, var(--bg-alt) 0%, transparent 60%),
    linear-gradient(120deg, var(--bg), var(--bg-alt));
  animation:aurora 28s ease-in-out infinite; }
@keyframes aurora {
  0%   { transform:translate3d(-3%,-2%,0) scale(1.10) rotate(0deg); }
  50%  { transform:translate3d(3%,2%,0)   scale(1.25) rotate(7deg); }
  100% { transform:translate3d(-3%,-2%,0) scale(1.10) rotate(0deg); } }
.brand { position:fixed; bottom:16px; right:20px; z-index:2; color:var(--text-dim); font-size:12px; opacity:.65; }
</style>
</head>
<body class="__BODYCLASS__">
__BG_LAYER__
<div class="overlay"></div>
<div class="content">
  <div class="clockwrap">
    <div class="clock" id="clock">--:--</div>
    <div class="sub" id="sub"></div>
  </div>
  <form class="search" onsubmit="return go(event)">
    <i class="gb"></i>
    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"></circle><line x1="16.5" y1="16.5" x2="21" y2="21"></line></svg>
    <input id="q" placeholder="Suchen oder Adresse eingeben …" autofocus autocomplete="off" spellcheck="false">
  </form>
  <div class="dial">__DIAL__</div>
</div>
<div class="brand">Cipher</div>
<script>
window.__setColors = function(c){
  const r = document.documentElement.style;
  if(c.accent) r.setProperty('--accent', c.accent);
  if(c.bg) r.setProperty('--bg', c.bg);
  if(c.bg_alt) r.setProperty('--bg-alt', c.bg_alt);
  if(c.text) r.setProperty('--text', c.text);
  if(c.text_dim) r.setProperty('--text-dim', c.text_dim);
  const ov = document.querySelector('.overlay');
  if(ov && c.dim != null) ov.style.background = 'rgba(0,0,0,'+c.dim+')';
};
window.__setGlass = function(frost, edge, depth){
  const r = document.documentElement.style;
  if(frost != null) r.setProperty('--g-frost', String(frost));
  if(edge != null) r.setProperty('--g-edge', String(edge));
  if(depth != null) r.setProperty('--g-depth', String(depth));
};
const SEARCH="__SEARCH_URL__";
function go(e){
  e.preventDefault();
  const v=document.getElementById('q').value.trim();
  if(!v) return false;
  let url;
  if(/^https?:\\/\\//.test(v)) url=v;
  else if(!v.includes(' ') && v.includes('.')) url='https://'+v;
  else url=SEARCH.replace('{}', encodeURIComponent(v));
  location.href=url;
  return false;
}
const DAYS=['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag'];
const MONTHS=['Januar','Februar','März','April','Mai','Juni','Juli','August',
  'September','Oktober','November','Dezember'];
function set(id,val){ const e=document.getElementById(id); if(e.textContent!==val) e.textContent=val; }
function tick(){
  const d=new Date(), p=n=>String(n).padStart(2,'0'), h=d.getHours();
  set('clock', p(h)+':'+p(d.getMinutes()));
  const greet=h<5?'Gute Nacht':h<12?'Guten Morgen':h<18?'Guten Tag':'Guten Abend';
  set('sub', greet+', Damien · '+DAYS[d.getDay()]+', '+d.getDate()+'. '+MONTHS[d.getMonth()]);
}
tick(); setInterval(tick,10000);

/* Echtes Glas: das geblurrte Glas-Bild (.gb) deckungsgleich zum Haupt-Hintergrund
   ausrichten. Der Haupt-Hintergrund (.bg) ist cover-skaliert auf die FENSTER-Box
   (Viewport + Chrome-Insets, 0 wenn nicht immersiv), zentriert. Pro Glas-Element setzen
   wir background-size = diese Cover-Grösse und background-position = Versatz seiner
   Bildschirmposition → jedes Element zeigt den Ausschnitt, der WIRKLICH dahinter liegt
   (statt jeweils das ganze Bild). Inline-Style = rendert zuverlässig auch bei Resize. */
const WP_W=__WP_W__, WP_H=__WP_H__, INS=[__INS_T__,__INS_R__,__INS_B__,__INS_L__];
function alignGlass(){
  if(!WP_W||!WP_H) return;
  const [iT,iR,iB,iL]=INS;
  const Ww=innerWidth+iL+iR, Wh=innerHeight+iT+iB;
  const s=Math.max(Ww/WP_W, Wh/WP_H), Sw=WP_W*s, Sh=WP_H*s;
  const wx=-iL+(Ww-Sw)/2, wy=-iT+(Wh-Sh)/2;
  document.querySelectorAll('.gb').forEach(g=>{
    const r=g.parentElement.getBoundingClientRect();
    g.style.backgroundSize=Sw+'px '+Sh+'px';
    g.style.backgroundPosition=(wx-r.left)+'px '+(wy-r.top)+'px';
  });
}
alignGlass();
addEventListener('resize', alignGlass);
__ANIM_JS__
</script>
</body>
</html>
"""


# Speed-Dial-Standardkacheln (Name, URL). Später aus den Einstellungen editierbar.
_DEFAULT_DIAL = [
    ("YouTube", "https://www.youtube.com"),
    ("GitHub", "https://github.com"),
    ("Reddit", "https://www.reddit.com"),
    ("Twitch", "https://www.twitch.tv"),
    ("Wikipedia", "https://www.wikipedia.org"),
    ("ChatGPT", "https://chatgpt.com"),
]


def _dial_html(items) -> str:
    cells = []
    for name, url in items:
        cells.append(
            f'<a class="tile" href="{url}"><i class="gb"></i>'
            f'<span class="ic">{name[0].upper()}</span>'
            f'<span class="nm">{name}</span></a>'
        )
    return "".join(cells)


def build_newtab_html(theme: dict, rev: int = 0, glossy: bool = True,
                      glass: tuple = (0.65, 0.35, 0.45), immersive: bool = False,
                      insets: tuple = (0, 0, 0, 0), dim_override=None) -> str:
    from .profile import get_search_url  # lazy: vermeidet Import-Zyklus

    g_frost, g_edge, g_depth = glass

    t = {**DEFAULT_THEME, **(theme or {})}
    dim = (theme or {}).get("wallpaper_dim", 0.35)
    wallpaper = (theme or {}).get("wallpaper")
    animation = (theme or {}).get("animation")

    bg_layer = ""
    anim_js = ""
    if wallpaper:
        ext = wallpaper.lower().rsplit(".", 1)[-1] if "." in wallpaper else ""
        # Extern via Handler ausliefern (HTML bleibt winzig, statt das Bild als
        # MB-grosse Base64-Data-URL einzubetten). ?v=rev = Cache-Buster pro Theme,
        # sonst serviert Blink fürs gleiche app://-URL das alte Bild aus dem Cache.
        src = f"app://newtab/wallpaper?v={rev}"
        if ext in ("mp4", "webm", "ogg"):
            bg_layer = (
                '<video class="bg" autoplay muted loop playsinline>'
                f'<source src="{src}"></video>'
            )
        else:
            bg_layer = (
                f'<div class="bg" style="background-image:url(\'{src}\');'
                'background-size:cover;background-position:center;"></div>'
            )
    elif animation == "aurora":
        bg_layer = '<div class="aurora"></div>'
    elif animation in _CANVAS_ANIMS:
        bg_layer = '<canvas class="bg" id="anim"></canvas>'
        anim_js = _CANVAS_ANIMS[animation].replace("__ACC__", t["accent"]).replace("__BGC__", t["bg"])

    body_classes = "" if glossy else "flat"

    # Wallpaper-URLs fürs Glas. Nur bei BILD-Wallpaper (sonst none). --wp = scharf,
    # --wp-frost = Qt-vorab-geblurrt (Downscale, identisch zum Leisten-Frost; Blur =
    # aktueller Frost in die URL gebacken → Reload bei Frost-Änderung holt die neue).
    is_image = bool(wallpaper) and "." in wallpaper and \
        wallpaper.lower().rsplit(".", 1)[-1] not in ("mp4", "webm", "ogg")
    wp_css = f"url('app://newtab/wallpaper?v={rev}')" if is_image else "none"
    wp_frost_css = (f"url('app://newtab/wallpaper?v={rev}&blur={g_frost}')"
                    if is_image else "none")
    # Wallpaper-Naturgrösse + Insets → die JS-Glas-Ausrichtung (alignGlass) positioniert
    # das Glas-Bild deckungsgleich zum Haupt-Hintergrund (echtes Glas statt „jedes Element
    # zeigt das ganze Bild"). Insets = (top, right, bottom, left); 0 wenn nicht immersiv.
    wp_w = wp_h = 0
    if is_image:
        _sz = QImageReader(str(THEMES_DIR / wallpaper)).size()
        wp_w, wp_h = max(0, _sz.width()), max(0, _sz.height())
    ins_t, ins_r, ins_b, ins_l = insets

    # Immersiv (Bild-Theme + Glas-Leisten): das Fenster malt das Wallpaper hinter dem
    # Chrome (Fenster-Cover). Die Startseite rendert ihr EIGENES .bg (Web-View bleibt
    # opak – transparent zeigt in QtWebEngine nur Schwarz statt des Host-Bilds), aber
    # an die FENSTER-Cover-Skalierung gekoppelt: das .bg ragt per negativen Insets
    # (= Chrome-Höhen) bis an die Fensterkanten → deckungsgleich mit dem Host-Bild,
    # keine Naht am Chrome↔Inhalt-Übergang. Abdunklung = Host-dim (sonst Helligkeits-
    # sprung). Sonst (kein Immersiv): normales Viewport-Cover.
    html_bg = "var(--bg)"
    if immersive and bg_layer.startswith('<div class="bg"'):
        it, ir, ib, il = insets
        bg_layer = (
            f'<div class="bg" style="position:fixed;width:auto;height:auto;'
            f'top:-{it}px;right:-{ir}px;bottom:-{ib}px;left:-{il}px;'
            f"background-image:url('app://newtab/wallpaper?v={rev}');"
            'background-size:cover;background-position:center;"></div>'
        )
        if dim_override is not None:
            dim = dim_override

    repl = {
        "__TITLE__": "Neuer Tab",
        "__BG_LAYER__": bg_layer,
        "__ANIM_JS__": anim_js,
        "__SEARCH_URL__": get_search_url(),
        "__DIAL__": _dial_html(_DEFAULT_DIAL),
        "__BODYCLASS__": body_classes,
        "__HTMLBG__": html_bg,
        "__WP__": wp_css,
        "__WP_FROST__": wp_frost_css,
        "__WP_W__": str(wp_w),
        "__WP_H__": str(wp_h),
        "__INS_T__": str(ins_t), "__INS_R__": str(ins_r),
        "__INS_B__": str(ins_b), "__INS_L__": str(ins_l),
        "__G_FROST__": str(g_frost),
        "__G_EDGE__": str(g_edge),
        "__G_DEPTH__": str(g_depth),
        "__DIM__": str(dim),
        "__ACCENT__": t["accent"],
        "__BG_ALT__": t["bg_alt"],
        "__BG__": t["bg"],
        "__TEXT_DIM__": t["text_dim"],
        "__TEXT__": t["text"],
    }
    html = _HTML
    for key, value in repl.items():
        html = html.replace(key, value)
    return html
