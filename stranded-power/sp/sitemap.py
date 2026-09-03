"""Interactive site map: candidate locations that filter on checkboxes.

Produces one self-contained HTML file. Site data is embedded as JSON and
filtered in the browser, so ticking a constraint is instant — no server,
no recompute, nothing to go wrong in front of judges.

Each flag mask is warped to WGS84, encoded as a base64 PNG, and embedded
in the page. The browser ANDs the ticked masks together on a canvas and
paints the surviving cells as an image overlay. Surviving area in km² is
derived from the pixel count. The top-20 shortlist pins sit on top.

Leaflet loads from a CDN by default. Before the demo, vendor it locally
(see vendor_leaflet) so the page works with no network at all.
"""

import base64
import io
import json
import os

import numpy as np

CDN_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"
CDN_JS  = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"

# Overlay colour: the accent green at 78% opacity.
_ACCENT_RGBA = (78, 171, 156, 200)


def _mask_to_b64png(bool_mask, grid):
    """Warp a bool mask to WGS84 and return (data_url, [[s,w],[n,e]])."""
    from PIL import Image
    from .render import warp_to_wgs84

    arr = np.where(bool_mask, 1.0, np.nan).astype("float32")
    warped, bounds = warp_to_wgs84(arr, grid)

    h, w = warped.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[np.isfinite(warped)] = _ACCENT_RGBA

    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}", bounds


def _km2_per_pixel(grid):
    """km² represented by one pixel in the warped WGS84 image.

    warp_to_wgs84 changes the pixel count slightly vs the source array.
    Warping the land mask and comparing against the known land cell count
    gives a stable scale factor for converting canvas pixel counts to km².
    Each BNG cell is exactly 1 km² at 1000m resolution.
    """
    from .render import warp_to_wgs84

    land_f = np.where(grid.land, 1.0, np.nan).astype("float32")
    warped, _ = warp_to_wgs84(land_f, grid)
    n_px = int(np.isfinite(warped).sum())
    return grid.n_land / n_px  # km² per warped pixel


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="__CSS__">
<style>
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
    line-height: 1.45;
    color: #1A1A1A;
    background: #FAFAF8;
    display: flex;
    overflow: hidden;
  }

  /* ── Sidebar ──────────────────────────────────────────────────── */
  #panel {
    width: 300px;
    flex: none;
    background: #F2F2EE;
    border-right: 1px solid #DEDED6;
    padding: 0 16px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  #panel > div {
    padding: 12px 0;
    border-bottom: 1px solid #DEDED6;
  }
  #panel > div:last-child { border-bottom: none; }

  h1 { font-size: 13px; font-weight: 600; margin: 0 0 3px; }
  .sub { font-size: 12px; color: #5A5A55; margin: 0; }

  h2 {
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #5A5A55;
    margin: 0 0 8px;
    padding-bottom: 5px;
    border-bottom: 1px solid #DEDED6;
  }

  /* ── Live count ───────────────────────────────────────────────── */
  .count .sites-line { display: block; font-size: 12px; color: #5A5A55; }
  .count .sites-line b {
    display: block;
    font-size: 28px;
    font-weight: 600;
    line-height: 1.1;
    letter-spacing: -0.02em;
    color: #1F5673;
    font-variant-numeric: tabular-nums;
  }

  /* ── Rank slider ──────────────────────────────────────────────── */
  .rank-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
  }
  #rank-slider {
    flex: 1;
    accent-color: #1F5673;
    cursor: pointer;
  }
  #rank-val {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    color: #1F5673;
    width: 3.5rem;
    text-align: right;
    flex: none;
  }

  /* ── Checkbox labels ──────────────────────────────────────────── */
  label {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    padding: 6px 16px;
    margin: 0 -16px;
    cursor: pointer;
    border-bottom: 1px solid #DEDED6;
  }
  label:last-child { border-bottom: none; }
  label:hover { background: #E8E8E2; }
  .flag-caption { font-size: 11px; color: #5A5A55; margin: 3px 0 0 21px; line-height: 1.4; }
  input[type=checkbox] {
    margin: 2px 0 0;
    accent-color: #1F5673;
    width: 13px;
    height: 13px;
    flex: none;
  }
  label .n {
    margin-left: auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
    color: #5A5A55;
    font-variant-numeric: tabular-nums;
  }

  /* ── Shortlist ────────────────────────────────────────────────── */
  #list { font-size: 13px; }
  .site {
    display: flex;
    gap: 8px;
    align-items: baseline;
    padding: 4px 0;
    border-bottom: 1px solid #DEDED6;
    cursor: pointer;
  }
  .site:last-child { border-bottom: none; }
  .site:hover { color: #1F5673; }
  .site .r {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-variant-numeric: tabular-nums;
    font-size: 12px;
    color: #5A5A55;
    width: 2rem;
    flex: none;
  }
  .site .s {
    margin-left: auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-variant-numeric: tabular-nums;
    font-size: 12px;
    color: #5A5A55;
  }

  /* ── Main / tabs ──────────────────────────────────────────────── */
  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  #tab-bar {
    flex: none;
    display: flex;
    background: #F2F2EE;
    border-bottom: 1px solid #DEDED6;
  }
  .tab {
    flex: 1;
    padding: 8px 12px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    font-family: inherit;
    font-size: 13px;
    color: #5A5A55;
    cursor: pointer;
  }
  .tab:hover { color: #1A1A1A; }
  .tab.active { color: #1F5673; border-bottom-color: #1F5673; font-weight: 500; }

  /* ── Map pane ─────────────────────────────────────────────────── */
  #pane-map { flex: 1; display: flex; }
  #map { flex: 1; }
  .leaflet-container { background: #FAFAF8; }
  .pin { border-radius: 50%; border: 1px solid rgba(0,0,0,0.3); }

  /* ── Coordinates pane ─────────────────────────────────────────── */
  #pane-coords { flex: 1; overflow-y: auto; padding: 16px 20px; }
  #coords-table table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    font-variant-numeric: tabular-nums;
  }
  #coords-table th {
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #5A5A55;
    padding: 0 16px 5px 0;
    border-bottom: 1px solid #DEDED6;
    text-align: left;
  }
  #coords-table th.r { text-align: right; padding-right: 0; }
  #coords-table td {
    padding: 4px 16px 4px 0;
    border-bottom: 1px solid #DEDED6;
    color: #1A1A1A;
    text-align: left;
  }
  #coords-table td.r { text-align: right; padding-right: 0; }
  #coords-table td.m {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    text-align: right;
    padding-right: 0;
  }

  /* ── Preset button ───────────────────────────────────────────── */
  #btn-preset {
    display: block;
    width: 100%;
    padding: 7px 12px;
    background: #1F5673;
    color: #FAFAF8;
    border: none;
    border-radius: 2px;
    font-family: inherit;
    font-size: 13px;
    text-align: left;
    cursor: pointer;
  }
  #btn-preset:hover { background: #194558; }
  .preset-caption { font-size: 11px; color: #5A5A55; margin: 5px 0 0; }

  /* ── Responsive ───────────────────────────────────────────────── */
  @media (max-width: 720px) {
    body { flex-direction: column; }
    #panel { width: 100%; height: 46%; border-right: none;
             border-bottom: 1px solid #DEDED6; }
  }
</style>
</head>
<body>

<div id="panel">
  <div>
    <h1>__TITLE__</h1>
    <p class="sub">__SUBTITLE__</p>
  </div>

  <div class="count">
    <span class="sites-line"><b id="n">__TOTAL__</b> sites</span>
  </div>

  <div>
    <h2>Show top N sites</h2>
    <div class="rank-row">
      <input id="rank-slider" type="range" min="0" max="5000" step="50" value="5000">
      <span id="rank-val">5,000</span>
    </div>
  </div>

  <div>
    <h2>Preset</h2>
    <button id="btn-preset">Show high-curtailment sites</button>
    <p class="preset-caption">Measured curtailment. NESO wind BOA volumes, 2025/26.</p>
  </div>

  <div>
    <h2>Requirements</h2>
    <div id="filters"></div>
  </div>

  <div>
    <h2>Shortlist</h2>
    <div id="list"></div>
  </div>
</div>

<div id="main">
  <div id="tab-bar">
    <button class="tab active" data-pane="pane-map">Map</button>
    <button class="tab" data-pane="pane-coords">Coordinates</button>
  </div>
  <div id="pane-map">
    <div id="map"></div>
  </div>
  <div id="pane-coords" style="display:none">
    <h2>Coordinates</h2>
    <div id="coords-table"></div>
  </div>
</div>

<script src="__JS__"></script>
<script>
const SITES = __DATA__;
const FLAGS = __FLAGS__;
const CAPTIONS = __CAPTIONS__;
const TOTAL = SITES.length;

// ── Panel is built here, BEFORE any Leaflet call. ────────────────────────
// If the network is down, the counts, checkboxes and shortlist still work.
const filters = document.getElementById('filters');
FLAGS.forEach(f => {
  const el = document.createElement('label');
  el.innerHTML = `<input type="checkbox" data-flag="${f}"><span>${f}</span>`
               + `<span class="n"></span>`;
  filters.appendChild(el);
  if (CAPTIONS[f]) {
    const cap = document.createElement('p');
    cap.className = 'flag-caption';
    cap.textContent = CAPTIONS[f];
    filters.appendChild(cap);
  }
});

let rankLimit = TOTAL;
const slider = document.getElementById('rank-slider');
const rankVal = document.getElementById('rank-val');
slider.max = TOTAL;
slider.value = TOTAL;
rankVal.textContent = TOTAL.toLocaleString();
slider.addEventListener('input', () => {
  rankLimit = parseInt(slider.value);
  rankVal.textContent = rankLimit.toLocaleString();
  draw();
});

// ── Tab switching ─────────────────────────────────────────────────────────
// Wired before Leaflet so tabs work with no network. Filters live in #panel
// and are untouched by switching tabs.
let map = null;
let markerLayer = null;

document.querySelectorAll('#tab-bar .tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#tab-bar .tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    ['pane-map', 'pane-coords'].forEach(id => {
      document.getElementById(id).style.display = id === btn.dataset.pane ? '' : 'none';
    });
    if (btn.dataset.pane === 'pane-map' && map) map.invalidateSize();
  });
});

// ── Leaflet map (optional — wrapped so offline doesn't break the demo). ──
try {
  map = L.map('map', {zoomControl: true}).setView([54.6, -3.2], 6);
  L.tileLayer('https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_2t3z_1_3c570bf24e91b3a22f2de003',
    {attribution: '&copy; OpenStreetMap, &copy; CARTO', maxZoom: 18}).addTo(map);
  markerLayer = L.layerGroup().addTo(map);
} catch (e) {
  document.getElementById('map').innerHTML =
    '<p style="padding:28px;color:#7c8d8a;font:14px system-ui">' +
    'Map unavailable offline. Area counts, filters and site list still work.</p>';
}

// ── Helpers ───────────────────────────────────────────────────────────────
function active() {
  return [...document.querySelectorAll('#filters input:checked')]
    .map(i => i.dataset.flag);
}

// ── Main draw ─────────────────────────────────────────────────────────────
function draw() {
  const on = active();

  // Apply rank limit first, then AND of ticked requirements.
  const ranked = rankLimit >= TOTAL ? SITES : SITES.filter(s => s.rank <= rankLimit);
  const shown = on.length === 0
    ? ranked
    : ranked.filter(s => on.every(f => s.flags.includes(f)));

  // ── Per-checkbox counts: sites in current shown set meeting each flag. ─
  document.querySelectorAll('#filters input[data-flag]').forEach(inp => {
    const cnt = shown.filter(s => s.flags.includes(inp.dataset.flag)).length;
    inp.closest('label').querySelector('.n').textContent = cnt;
  });

  // ── Dots: all shown sites ─────────────────────────────────────────────
  if (markerLayer) {
    markerLayer.clearLayers();
    shown.forEach(s => {
      L.circleMarker([s.lat, s.lon], {
        radius: 4, className: 'pin',
        fillColor: '#4eab9c', fillOpacity: 0.8, weight: 1, color: '#0d1817',
      }).bindPopup(`<b>#${s.rank}</b> ${s.council}<br>score ${s.score}`)
        .addTo(markerLayer);
    });
  }

  // ── Site count line ───────────────────────────────────────────────────
  document.getElementById('n').textContent = shown.length;
  document.querySelector('.count .sites-line').innerHTML =
    `<b>${shown.length}</b> of top ${rankLimit} sites`;

  // ── Shortlist ─────────────────────────────────────────────────────────
  if (shown.length === 0 && on.length > 0) {
    document.getElementById('list').innerHTML =
      '<p class="sub">No site in Great Britain satisfies all selected conditions.</p>';
  } else {
    document.getElementById('list').innerHTML = shown.slice(0, 20).map(s =>
      `<div class="site"><span class="r">#${s.rank}</span>` +
      `<span>${s.council}</span><span class="s">${s.score}</span></div>`
    ).join('');
  }

  // ── Coordinates table (same shown array — row count equals sidebar count) ─
  document.getElementById('coords-table').innerHTML = shown.length === 0
    ? '<p style="color:#5A5A55;font-size:12px">No sites match current filters.</p>'
    : '<table><thead><tr>'
    + '<th class="r">Rank</th><th class="r">Score</th><th>Local authority</th>'
    + '<th class="r">Easting</th><th class="r">Northing</th>'
    + '<th class="r">Lat</th><th class="r">Lon</th>'
    + '</tr></thead><tbody>'
    + shown.map(s =>
        `<tr><td class="r">${s.rank}</td><td class="r">${s.score.toFixed(3)}</td>`
      + `<td>${s.council}</td>`
      + `<td class="m">${s.easting}</td><td class="m">${s.northing}</td>`
      + `<td class="m">${s.lat.toFixed(5)}</td><td class="m">${s.lon.toFixed(5)}</td></tr>`
      ).join('')
    + '</tbody></table>';
}

document.getElementById('btn-preset').addEventListener('click', () => {
  document.querySelectorAll('#filters input').forEach(cb => { cb.checked = false; });
  const cb = document.querySelector('#filters input[data-flag="High curtailment"]');
  if (cb) { cb.checked = true; }
  draw();
});

filters.addEventListener('change', draw);
draw();
</script>
</body>
</html>
"""


def site_map(sites, flags, grid, path="out/sites.html",
             title="Candidate Sites",
             subtitle="Tick a requirement — only sites meeting all ticked conditions are shown.",
             captions=None,
             leaflet_css=CDN_CSS, leaflet_js=CDN_JS):
    """Write the interactive site map to `path`.

    flags    : dict of {display_name: bool_array} — one entry per checkbox.
    captions : dict of {display_name: caption_text} — optional sub-label per checkbox.
    grid     : Grid object — used for the land mask extent.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    html = (TEMPLATE
            .replace("__TITLE__",    title)
            .replace("__SUBTITLE__", subtitle)
            .replace("__CSS__",      leaflet_css)
            .replace("__JS__",       leaflet_js)
            .replace("__DATA__",     json.dumps(sites))
            .replace("__FLAGS__",    json.dumps(list(flags)))
            .replace("__CAPTIONS__", json.dumps(captions or {}))
            .replace("__TOTAL__",    str(len(sites))))

    with open(path, "w") as f:
        f.write(html)
    return path


def vendor_leaflet(dest="out/vendor"):
    """Download Leaflet locally so the demo works with no network.

    Run once, well before the day. Then pass the local paths:

        site_map(sites, flags, grid,
                 leaflet_css="vendor/leaflet.css",
                 leaflet_js="vendor/leaflet.js")
    """
    import urllib.request

    os.makedirs(dest, exist_ok=True)
    for url, name in ((CDN_CSS, "leaflet.css"), (CDN_JS, "leaflet.js")):
        urllib.request.urlretrieve(url, os.path.join(dest, name))
    return dest
