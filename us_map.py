"""Build docs/us/index.html: a first national county map of community water systems.

Inputs (all small, all in the repo): output/us_county_summary.csv, output/us_tribal_by_region.csv,
data/geo/us_counties.json. Run us_build.py first to refresh the CSVs.
"""
import json
from pathlib import Path

import pandas as pd
from plotly.offline import get_plotlyjs_version
from shapely.geometry import shape

PLOTLY_JS = f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"
MIN_SMALL = 5           # counties need at least this many small systems for a violation rate

geo = json.loads(Path("data/geo/us_counties.json").read_text())
names, cents = {}, {}
for f in geo["features"]:
    names[f["id"]] = f["properties"]["name"]
    c = shape(f["geometry"]).representative_point()
    cents[f["id"]] = [round(c.x, 3), round(c.y, 3)]

d = pd.read_csv("output/us_county_summary.csv", dtype={"fips": str})
d = d[d["fips"].isin(names)].copy()
d["name"] = d["fips"].map(names)
d["wells_pct"] = (100 * d["share_on_wells"]).round(1)
d["viol_pct"] = (100 * d["small_with_violation"] / d["small_systems"]).where(d["small_systems"] >= MIN_SMALL).round(1)

nat_rate = 100 * d["small_with_violation"].sum() / d["small_systems"].sum()
nat_wells = 100 * (d["share_on_wells"] * d["people_served"]).sum() / d["people_served"].sum()
counties_rated = int(d["viol_pct"].notna().sum())

def num(v):
    return None if pd.isna(v) else float(v)

data = {
    "fips": d["fips"].tolist(),
    "label": [f"{n}, {s}" for n, s in zip(d["name"], d["state"])],
    "systems": d["systems"].astype(int).tolist(),
    "served": d["people_served"].astype(int).tolist(),
    "small": d["small_systems"].astype(int).tolist(),
    "small_hit": d["small_with_violation"].astype(int).tolist(),
    "wells": [num(v) for v in d["wells_pct"]],
    "viol": [num(v) for v in d["viol_pct"]],
    "cent": [cents[f] for f in d["fips"]],
}

tr = pd.read_csv("output/us_tribal_by_region.csv", dtype={"epa_region": str})
REGION_NAMES = {"01": "New England", "02": "NY, NJ", "04": "Southeast", "05": "Great Lakes (incl. MN)",
                "06": "South Central", "07": "Plains (IA, KS, MO, NE)", "08": "Mountain / N. Plains",
                "09": "Southwest, CA, NV", "10": "Pacific Northwest"}
rows = []
for _, r in tr.iterrows():
    few = r["tribal_systems"] < 10
    ratio = "too few to say" if few else f"{r['ratio']:.2g}x"
    rows.append(f"<tr{' class=\"few\"' if few else ''}><td>{r['epa_region'].lstrip('0')} &middot; {REGION_NAMES.get(r['epa_region'], '')}</td>"
                f"<td>{int(r['tribal_with_violation'])} of {int(r['tribal_systems'])} ({r['tribal_pct']:.0f}%)</td>"
                f"<td>{r['state_pct']:.0f}%</td><td><b>{ratio}</b></td></tr>")
t_hit, t_n = int(tr["tribal_with_violation"].sum()), int(tr["tribal_systems"].sum())
s_hit, s_n = int(tr["state_with_violation"].sum()), int(tr["state_systems"].sum())

geo_js = json.dumps(geo, separators=(",", ":"))
data_js = json.dumps(data, separators=(",", ":"))

html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>U.S. drinking water by county</title>
<meta name="description" content="Every U.S. county's community water systems: who is on wells, and how often small systems had health-based violations.">
<meta property="og:title" content="U.S. drinking water by county">
<meta property="og:image" content="https://louiserosenbaum.github.io/US-water-access/preview.png">
<script src="{PLOTLY_JS}"></script>
<style>
  :root {{ --ink:#1f2933; --muted:#5f6b76; --paper:#f4f1e6; --card:#fbfaf4; --line:#e3dfcf; }}
  body {{ margin:0; font-family:Inter, system-ui, -apple-system, sans-serif; color:var(--ink); background:var(--paper); }}
  main {{ max-width:1100px; margin:0 auto; padding:32px 20px 60px; }}
  .kicker {{ font-size:13px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }}
  h1 {{ font-size:clamp(28px,4vw,42px); margin:6px 0 8px; line-height:1.1; }}
  h1 em {{ font-style:normal; color:#2f7d52; }}
  .lede {{ font-size:18px; line-height:1.55; max-width:760px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px; margin-top:20px; }}
  .bar {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; justify-content:space-between; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:8px; }}
  .chip {{ border:1px solid var(--line); background:#fff; color:var(--ink); border-radius:999px; padding:7px 14px;
           font:inherit; font-size:14px; cursor:pointer; }}
  .chip.on {{ background:var(--ink); color:#fff; border-color:var(--ink); }}
  #find {{ font:inherit; font-size:14px; padding:7px 12px; border:1px solid var(--line); border-radius:999px; min-width:230px; background:#fff; }}
  #map {{ width:100%; height:min(62vw,600px); min-height:340px; }}
  .legend {{ display:flex; align-items:center; gap:10px; font-size:13px; color:var(--muted); margin:4px 4px 0; }}
  .ramp {{ flex:1; max-width:420px; height:10px; border-radius:6px; }}
  .note {{ font-size:13px; color:var(--muted); line-height:1.5; }}
  #profile {{ font-size:15px; line-height:1.6; min-height:24px; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; }}
  th, td {{ text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.05em; }}
  tr.few td {{ color:var(--muted); }}
  h2 {{ margin:44px 0 6px; font-size:26px; }}
  a {{ color:#1f4e79; }}
</style></head>
<body><main>
  <div class="kicker">Draft &middot; national view</div>
  <h1>Where America's tap water <em>comes from</em></h1>
  <p class="lede">Every county's community water systems, from EPA's drinking water records. Pick a layer, or find your county.
     About <b>{nat_wells:.0f}%</b> of people on community systems get groundwater from wells, and
     <b>{nat_rate:.0f}%</b> of small systems (under 500 people) had a health-based violation in the last five years.</p>

  <div class="card">
    <div class="bar">
      <div class="chips" id="chips">
        <button class="chip on" data-k="wells">Share on wells</button>
        <button class="chip" data-k="viol">Small-system violations</button>
        <button class="chip" data-k="systems">Number of systems</button>
      </div>
      <input id="find" list="counties" placeholder="Find your county">
      <datalist id="counties"></datalist>
    </div>
    <div id="map"></div>
    <div class="legend"><span id="lo"></span><div class="ramp" id="ramp"></div><span id="hi"></span></div>
    <p id="profile" class="note">Hover or tap a county for details.</p>
  </div>
  <p class="note">Community water systems only (year-round systems like city utilities), as of EPA's {pd.Timestamp.today():%B %Y} download.
     Each system is counted in one home county. Violation rates need at least {MIN_SMALL} small systems in a county ({counties_rated:,} counties qualify); the rest are left blank.
     Tribal systems are regulated by EPA and tied to tribal lands rather than counties, so they are compared by region below.</p>

  <h2>Tribal systems, region by region</h2>
  <p class="lede" style="font-size:16px">In Minnesota, small tribal systems had about 3.5x the violation rate of similar state systems.
     Nationally the gap is about <b>{(t_hit/t_n)/(s_hit/s_n):.1f}x</b> ({t_hit} of {t_n} tribal systems, {100*t_hit/t_n:.0f}%, vs. {100*s_hit/s_n:.0f}% of state systems in the same regions),
     and it depends on where you look.</p>
  <div class="card"><table>
    <tr><th>EPA region</th><th>Tribal systems with a violation</th><th>State systems</th><th>Ratio</th></tr>
    {''.join(rows)}
  </table></div>
  <p class="note">Small systems (under 500 people), health-based violations in the last five years. Navajo Nation runs its own program and is not included.
     Recorded violations reflect testing and reporting, not water quality directly.</p>
  <p class="note"><a href="../">&larr; The Minnesota story</a> &middot; <a href="https://github.com/louiserosenbaum/US-water-access">Code and method</a></p>
</main>
<script>
const GEO = {geo_js};
const D = {data_js};
const NAT = {nat_rate:.2f};
const PAPER = '#f4f1e6';
const BLUES = [[0,'#eef2ee'],[0.35,'#b9cfdf'],[0.7,'#5a8dbb'],[1,'#1f4e79']];
// green = below the national rate, cream = about average, blue = above (like a happiness map: green good)
const DIV = [[0,'#1e7a46'],[0.25,'#79b98a'],[0.5,'#f0eedb'],[0.75,'#7fa8cf'],[1,'#1f4e79']];
const TEAL = [[0,'#eef2ee'],[0.5,'#8fc0a9'],[1,'#2f7d52']];
const fmt = n => n.toLocaleString('en-US');
const LAYERS = {{
  wells:   {{ z: D.wells, cs: BLUES, zmin: 0, zmax: 100, lo: '0% on wells', hi: '100% on wells',
             tip: i => D.wells[i] === null ? 'no data' : D.wells[i].toFixed(0) + '% of people served get well water' }},
  viol:    {{ z: D.viol, cs: DIV, zmin: 0, zmax: 2 * NAT, lo: '0%', hi: Math.round(2 * NAT) + '%+ (national ' + Math.round(NAT) + '%)',
             tip: i => D.viol[i] === null ? 'too few small systems to rate (' + D.small[i] + ')'
                     : D.small_hit[i] + ' of ' + D.small[i] + ' small systems (' + D.viol[i].toFixed(0) + '%) had a health-based violation' }},
  systems: {{ z: D.systems.map(v => Math.log10(v)), cs: TEAL, zmin: 0, zmax: 2.5, lo: '1 system', hi: '300+',
             tip: i => fmt(D.systems[i]) + ' community water systems' }},
}};
let cur = 'wells';
const hover = k => D.label.map((l, i) => '<b>' + l + '</b><br>' + LAYERS[k].tip(i) + '<br>' + fmt(D.served[i]) + ' people served');
function trace(k) {{
  const L = LAYERS[k];
  return {{ type: 'choropleth', geojson: GEO, locations: D.fips, z: L.z, zmin: L.zmin, zmax: L.zmax,
           colorscale: L.cs, showscale: false, marker: {{ line: {{ color: PAPER, width: 0.25 }} }},
           text: hover(k), hovertemplate: '%{{text}}<extra></extra>' }};
}}
const hl = {{ type: 'choropleth', geojson: GEO, locations: [], z: [], showscale: false, hoverinfo: 'skip',
             colorscale: [[0,'rgba(0,0,0,0)'],[1,'rgba(0,0,0,0)']], marker: {{ line: {{ color: '#1f2933', width: 2 }} }} }};
const layout = {{ margin: {{ l: 0, r: 0, t: 0, b: 0 }}, paper_bgcolor: PAPER, dragmode: false,
  geo: {{ scope: 'usa', projection: {{ type: 'albers usa', scale: 1 }}, bgcolor: PAPER, showlakes: false,
         showland: true, landcolor: '#e8e4d4', subunitcolor: '#ffffff', subunitwidth: 0.8 }},
  hoverlabel: {{ bgcolor: '#fff', bordercolor: '#e3dfcf', font: {{ family: 'Inter, sans-serif', size: 13, color: '#1f2933' }} }} }};
Plotly.newPlot('map', [trace(cur), hl], layout, {{ displayModeBar: false, responsive: true, scrollZoom: false }});

function legend() {{
  const L = LAYERS[cur];
  document.getElementById('ramp').style.background = 'linear-gradient(90deg,' + L.cs.map(s => s[1] + ' ' + s[0] * 100 + '%').join(',') + ')';
  document.getElementById('lo').textContent = L.lo;
  document.getElementById('hi').textContent = L.hi;
}}
legend();
document.querySelectorAll('.chip').forEach(b => b.onclick = () => {{
  document.querySelectorAll('.chip').forEach(c => c.classList.toggle('on', c === b));
  cur = b.dataset.k;
  Plotly.react('map', [trace(cur), Object.assign({{}}, hl)], document.getElementById('map').layout);
  legend();
}});
function show(i) {{
  document.getElementById('profile').innerHTML = '<b>' + D.label[i] + '</b> &middot; ' + fmt(D.systems[i]) + ' systems serving ' + fmt(D.served[i]) +
    ' people &middot; ' + (D.wells[i] === null ? '' : D.wells[i].toFixed(0) + '% on wells &middot; ') + LAYERS.viol.tip(i);
}}
document.getElementById('map').on('plotly_hover', e => {{ if (e.points[0].curveNumber === 0) show(e.points[0].pointIndex); }});
document.getElementById('map').on('plotly_click', e => {{ if (e.points[0].curveNumber === 0) show(e.points[0].pointIndex); }});

const dl = document.getElementById('counties');
dl.innerHTML = D.label.map(l => '<option value="' + l + '">').join('');
document.getElementById('find').addEventListener('change', ev => {{
  const i = D.label.indexOf(ev.target.value);
  if (i < 0) return;
  hl.locations = [D.fips[i]]; hl.z = [0];
  Plotly.react('map', [trace(cur), hl], Object.assign({{}}, document.getElementById('map').layout,
    {{ geo: Object.assign({{}}, layout.geo, {{ center: {{ lon: D.cent[i][0], lat: D.cent[i][1] }}, projection: {{ type: 'albers usa', scale: 5 }} }}) }}));
  show(i);
}});
</script>
</body></html>
"""
out = Path("docs/us/index.html")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
print(f"wrote {out} ({out.stat().st_size // 1024} KB, {len(d)} counties, national small-system rate {nat_rate:.1f}%, wells {nat_wells:.0f}%)")
