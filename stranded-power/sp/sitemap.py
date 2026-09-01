"""Interactive site map: candidate locations that filter on checkboxes.

Produces one self-contained HTML file. Site data is embedded as JSON and
filtered in the browser, so ticking a constraint is instant — no server,
no recompute, nothing to go wrong in front of judges.

Leaflet loads from a CDN by default. Before the demo, vendor it locally
(see vendor_leaflet) so the page works with no network at all.
"""

import json
import os

CDN_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"
CDN_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="__CSS__">
<style>
  :root {
    --bg: #0d1817; --panel: #14201f; --line: #2c3d3b;
    --ink: #dee8e5; --dim: #7c8d8a; --accent: #4eab9c; --warn: #dd8b3e;
    --mono: ui-monospace, "SF Mono", Menlo, monospace;
    --sans: "IBM Plex Sans", -apple-system, system-ui, sans-serif;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body { font-family: var(--sans); background: var(--bg); color: var(--ink);
         display: flex; overflow: hidden; }

  #panel { width: 310px; flex: none; background: var(--panel);
           border-right: 1px solid var(--line); padding: 18px 18px 24px;
           overflow-y: auto; display: flex; flex-direction: column; gap: 18px; }
  #map { flex: 1; }

  h1 { font-size: 1.05rem; margin: 0; letter-spacing: -0.01em; }
  .sub { font-size: 0.78rem; color: var(--dim); margin: 4px 0 0; line-height: 1.45; }

  .count { border: 1px solid var(--line); border-radius: 3px; padding: 12px 14px; }
  .count b { font-family: var(--mono); font-size: 2rem; color: var(--accent);
             display: block; line-height: 1; }
  .count span { font-size: 0.72rem; color: var(--dim); text-transform: uppercase;
                letter-spacing: 0.1em; }
  .count .drop { color: var(--warn); font-family: var(--mono); font-size: 0.78rem;
                 margin-top: 6px; display: block; }

  h2 { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.12em;
       color: var(--dim); margin: 0 0 8px; font-weight: 500; }

  label { display: flex; gap: 9px; align-items: flex-start; padding: 7px 0;
          cursor: pointer; font-size: 0.88rem; line-height: 1.35;
          border-bottom: 1px solid var(--line); }
  label:last-child { border-bottom: none; }
  input[type=checkbox] { margin: 2px 0 0; accent-color: var(--accent);
                         width: 15px; height: 15px; flex: none; }
  label .n { margin-left: auto; font-family: var(--mono); font-size: 0.74rem;
             color: var(--dim); }

  #list { font-size: 0.8rem; }
  .site { display: flex; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--line); }
  .site .r { font-family: var(--mono); color: var(--dim); width: 1.6rem; flex: none; }
  .site .s { margin-left: auto; font-family: var(--mono); color: var(--accent); }

  .leaflet-container { background: #0a1211; }
  .pin { border-radius: 50%; border: 2px solid #0d1817; }
  @media (max-width: 720px) { body { flex-direction: column; }
    #panel { width: 100%; height: 46%; border-right: none;
             border-bottom: 1px solid var(--line); } }
</style>
</head>
<body>

<div id="panel">
  <div>
    <h1>__TITLE__</h1>
    <p class="sub">__SUBTITLE__</p>
  </div>

  <div class="count">
    <span>Viable sites</span>
    <b id="n">0</b>
    <span class="drop" id="drop"></span>
  </div>

  <div>
    <h2>Rule out sites that are…</h2>
    <div id="filters"></div>
  </div>

  <div>
    <h2>Shortlist</h2>
    <div id="list"></div>
  </div>
</div>

<div id="map"></div>

<script src="__JS__"></script>
<script>
const SITES = __DATA__;
const FLAGS = __FLAGS__;
const TOTAL = SITES.length;

// The panel is built BEFORE any Leaflet call, and the map is optional.
// If Leaflet or the tile server is unreachable, the counts, checkboxes
// and shortlist still work. Never let a network failure take the whole
// demo down.
let layer = null;

try {
  const map = L.map('map', {zoomControl: true}).setView([54.6, -3.2], 6);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    {attribution: '&copy; OpenStreetMap, &copy; CARTO', maxZoom: 18}).addTo(map);
  layer = L.layerGroup().addTo(map);
} catch (e) {
  document.getElementById('map').innerHTML =
    '<p style="padding:28px;color:#7c8d8a;font:14px system-ui">' +
    'Map unavailable offline. Site list and filters still work.</p>';
}

const filters = document.getElementById('filters');
FLAGS.forEach(f => {
  const n = SITES.filter(s => s.flags.includes(f)).length;
  const l = document.createElement('label');
  l.innerHTML = `<input type="checkbox" data-flag="${f}"><span>${f}</span>`
              + `<span class="n">${n}</span>`;
  filters.appendChild(l);
});

function active() {
  return [...document.querySelectorAll('#filters input:checked')]
    .map(i => i.dataset.flag);
}

function radius(score, lo, hi) {
  return 5 + 9 * (hi > lo ? (score - lo) / (hi - lo) : 0.5);
}

function draw() {
  const off = active();
  const shown = SITES.filter(s => !s.flags.some(f => off.includes(f)));

  if (layer) {
    layer.clearLayers();
    const lo = Math.min(...SITES.map(s => s.score));
    const hi = Math.max(...SITES.map(s => s.score));

    shown.forEach(s => {
      L.circleMarker([s.lat, s.lon], {
        radius: radius(s.score, lo, hi),
        className: 'pin', color: '#0d1817', weight: 2,
        fillColor: '#4eab9c', fillOpacity: 0.9,
      }).bindPopup(
        `<b>#${s.rank} &middot; ${s.council}</b><br>score ${s.score}` +
        (s.flags.length ? `<br><i>${s.flags.join(', ')}</i>` : '')
      ).addTo(layer);
    });
  }

  document.getElementById('n').textContent = shown.length;
  const removed = TOTAL - shown.length;
  document.getElementById('drop').textContent =
    removed ? `\\u2212${removed} ruled out of ${TOTAL}` : `all ${TOTAL} viable`;

  document.getElementById('list').innerHTML = shown.slice(0, 14).map(s =>
    `<div class="site"><span class="r">${s.rank}</span>` +
    `<span>${s.council}</span><span class="s">${s.score}</span></div>`
  ).join('') || '<p class="sub">No sites meet every constraint.</p>';
}

filters.addEventListener('change', draw);
draw();
</script>
</body>
</html>
"""


def site_map(sites, flags, path="out/sites.html",
             title="Candidate Sites",
             subtitle="Tick a constraint to rule out sites that breach it.",
             leaflet_css=CDN_CSS, leaflet_js=CDN_JS):
    """Write the interactive site map to `path`."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    html = (TEMPLATE
            .replace("__TITLE__", title)
            .replace("__SUBTITLE__", subtitle)
            .replace("__CSS__", leaflet_css)
            .replace("__JS__", leaflet_js)
            .replace("__DATA__", json.dumps(sites))
            .replace("__FLAGS__", json.dumps(list(flags))))

    with open(path, "w") as f:
        f.write(html)
    return path


def vendor_leaflet(dest="out/vendor"):
    """Download Leaflet locally so the demo works with no network.

    Run once, well before the day. Then pass the local paths:

        site_map(sites, flags,
                 leaflet_css="vendor/leaflet.css",
                 leaflet_js="vendor/leaflet.js")
    """
    import urllib.request

    os.makedirs(dest, exist_ok=True)
    for url, name in ((CDN_CSS, "leaflet.css"), (CDN_JS, "leaflet.js")):
        urllib.request.urlretrieve(url, os.path.join(dest, name))
    return dest
