"""Build the one-page story site (docs/index.html) from the CSVs that build.py writes.

Every number on the page is calculated here from output/*.csv, so if the data
changes, rerunning this script updates the text and the charts together.

Run:  python3 build.py && python3 story.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).parent
OUT = ROOT / "docs"
OUT.mkdir(exist_ok=True)

from plotly.offline import get_plotlyjs_version
# Pin the plotly.js version to the one this Python Plotly was built for, so the charts always match
PLOTLY_JS = f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"
SMALL = 500  # "very small" system cutoff, same as charts.py

# Colors: one blue for magnitude, one orange to call out violations, gray for everything else
BLUE_RAMP = ["#eef4fb", "#c6dbef", "#85b4dc", "#3f83c4", "#1c5a99", "#0b3566"]
ORANGE = "#d9622b"
GRAY = "#9aa3ad"
INK = "#1f2933"
MUTED = "#5f6b76"

# ---------- load ----------
sys_df = pd.read_csv(ROOT / "output" / "mn_system_violations.csv", dtype={"pwsid": str})
# Safety net: only Minnesota IDs (MN...) and EPA Region 5 tribal IDs (05...).
sys_df = sys_df[sys_df["pwsid"].str.startswith(("MN", "05"))].copy()
sys_df["tribal"] = sys_df["pwsid"].str.startswith("05")
sys_df["has_violation"] = sys_df["health_violations_5yr"] > 0
sys_df["on_wells"] = sys_df["source_type"].eq("Groundwater (wells)")

geo = json.loads((ROOT / "data" / "geo" / "mn_counties.geojson").read_text())

# ---------- numbers for the text ----------
n_systems = len(sys_df)
n_people = int(sys_df["population_served"].sum())
pct_systems_wells = 100 * sys_df["on_wells"].mean()
pct_people_wells = 100 * sys_df.loc[sys_df["on_wells"], "population_served"].sum() / n_people
n_small = int((sys_df["population_served"] < SMALL).sum())

county = (
    sys_df.assign(well_people=np.where(sys_df["on_wells"], sys_df["population_served"], 0))
    .groupby("county", as_index=False)
    .agg(systems=("pwsid", "count"),
         people=("population_served", "sum"),
         well_people=("well_people", "sum"),
         with_violation=("has_violation", "sum"))
)
county["share_on_wells"] = 100 * county["well_people"] / county["people"]
mn_names = {f["properties"]["NAME"] for f in geo["features"]}
county = county[county["county"].isin(mn_names)]
n_counties = len(county)
n_counties_mostly_wells = int((county["share_on_wells"] >= 50).sum())
# biggest counties that mostly DON'T use wells, for the text
exceptions = county[county["share_on_wells"] < 50].nlargest(4, "people")["county"].tolist()
exceptions_txt = ", ".join(exceptions[:-1]) + " and " + exceptions[-1] if len(exceptions) > 1 else "".join(exceptions)

small = sys_df[sys_df["population_served"] < SMALL]
grp = small.groupby("tribal")["has_violation"].agg(["sum", "count"])
grp["pct"] = 100 * grp["sum"] / grp["count"]
t_hit, t_n, t_pct = int(grp.loc[True, "sum"]), int(grp.loc[True, "count"]), grp.loc[True, "pct"]
s_hit, s_n, s_pct = int(grp.loc[False, "sum"]), int(grp.loc[False, "count"]), grp.loc[False, "pct"]
ratio = t_pct / s_pct

big = sys_df[sys_df["population_served"] >= 10_000]
pct_big_viol = 100 * big["has_violation"].mean()
pct_small_viol = 100 * small["has_violation"].mean()

BASE_LAYOUT = dict(
    font=dict(family="Inter, system-ui, sans-serif", size=13, color=INK),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    hoverlabel=dict(bgcolor="white", font=dict(size=13, color=INK), bordercolor="#d0d7de"),
)

# ---------- chart 1: county map ----------
# Drawn as plain filled shapes on x/y axes (no map projection), so it renders the
# same in every browser and doesn't depend on Plotly downloading a world map.
from plotly.colors import sample_colorscale

SCALE = [[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)]
NO_DATA = "#e4e7eb"
by_name = county.set_index("county")


def outer_rings(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [poly[0] for poly in polys]  # outer ring of each piece


def draw_map(values, scale, bar_title):
    """values: county name -> (percent 0-100, hover text). Counties not in values are gray."""
    fig = go.Figure()
    for f in geo["features"]:
        name = f["properties"]["NAME"]
        xs, ys = [], []
        for ring in outer_rings(f["geometry"]):
            xs += [pt[0] for pt in ring] + [None]
            ys += [pt[1] for pt in ring] + [None]
        if name in values:
            pct, tip = values[name]
            color = sample_colorscale(scale, max(0, min(pct, 100)) / 100)[0]
        else:
            color, tip = NO_DATA, f"<b>{name} County</b><br>No data"
        fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor=color, mode="lines",
                                 line=dict(color="white", width=0.8), hoveron="fills",
                                 text=tip, hoverinfo="text", showlegend=False))
    # colorbar only (one invisible point carries the scale)
    fig.add_trace(go.Scatter(x=[-94], y=[46], mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(size=0.1, opacity=0, color=[0], cmin=0, cmax=100, colorscale=scale,
                                         showscale=True,
                                         colorbar=dict(title=dict(text=bar_title, side="top"),
                                                       orientation="h", x=0.5, xanchor="center", y=-0.02, yanchor="top",
                                                       ticksuffix="%", thickness=10, len=0.7, outlinewidth=0))))
    fig.update_layout(
        **BASE_LAYOUT, height=600, margin=dict(l=0, r=0, t=0, b=70),
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True, scaleanchor="x", scaleratio=1 / np.cos(np.radians(46.3))),
        hovermode="closest",
    )
    return fig



# ---------- chart 4: people not on a community system (mostly private wells) ----------
pw = pd.read_csv(ROOT / "output" / "mn_private_wells.csv")
GREEN_RAMP = ["#f1f7f4", "#c8e6d6", "#8fcbae", "#4ea883", "#22805c", "#0c573d"]
SCALE_PW = [[i / (len(GREEN_RAMP) - 1), c] for i, c in enumerate(GREEN_RAMP)]
map4_values = {}
for _, r in pw.iterrows():
    note = "<br><i>Set to 0: water systems here also serve other counties</i>" if r["served_exceeds_population"] else ""
    map4_values[r["county"]] = (r["pct_not_on_community"],
        f"<b>{r['county']} County</b><br>{r['pct_not_on_community']:.0f}% not on a community system<br>"
        f"about {int(r['est_not_on_community']):,} of {int(r['population_2025']):,} people{note}")
pw_total = int(pw["est_not_on_community"].sum())
pw_pop = int(pw["population_2025"].sum())
pw_pct = 100 * pw_total / pw_pop
pw_top_share = pw.nlargest(3, "pct_not_on_community")
pw_top_people = pw.nlargest(1, "est_not_on_community").iloc[0]
pw_n_majority = int((pw["pct_not_on_community"] >= 50).sum())
pw_flagged = ", ".join(sorted(pw.loc[pw["served_exceeds_population"], "county"]))

# ---------- map explorer: one county map, several layers ----------
# Each layer recolors the same counties and swaps the text panel next to the map.
# Colors and hover text are computed here; the page's JavaScript only switches between them.
ORANGE_RAMP = ["#fdf1ea", "#f9d2bd", "#f2a77f", "#e47a48", "#c9551f", "#8f3610"]
PURPLE_RAMP = ["#f4f2fa", "#d9d3ee", "#b2a6dc", "#8774c4", "#5e4aa3", "#3b2c70"]
TEAL_RAMP = ["#effafa", "#c6ecec", "#8fd3d4", "#4fb2b6", "#22878d", "#0d5a5f"]


def ring_area_sq_mi(ring):
    # shoelace formula on lon/lat, scaled to miles at the ring's latitude
    lat0 = np.radians(np.mean([pt[1] for pt in ring]))
    xs = np.array([pt[0] for pt in ring]) * 69.17 * np.cos(lat0)
    ys = np.array([pt[1] for pt in ring]) * 69.0
    return abs(np.dot(xs, np.roll(ys, 1)) - np.dot(ys, np.roll(xs, 1))) / 2


names_sorted = sorted(mn_names)
geom = []
area = {}
for f in geo["features"]:
    name = f["properties"]["NAME"]
    xs, ys = [], []
    for ring in outer_rings(f["geometry"]):
        xs += [round(pt[0], 4) for pt in ring] + [None]
        ys += [round(pt[1], 4) for pt in ring] + [None]
    geom.append({"name": name, "x": xs, "y": ys})
    area[name] = sum(ring_area_sq_mi(r) for r in outer_rings(f["geometry"]))

pw_by = pw.set_index("county")
pop = pw_by["population_2025"].to_dict()


def top3(pairs, fmt):
    pairs = sorted(pairs, key=lambda t: t[1], reverse=True)[:3]
    return "".join(f"<li>{n}: {fmt(v)}</li>" for n, v in pairs)


def build_layer(key, label, ramp, values, tips, lo, hi, lo_txt, hi_txt, title, body, top_html, note, log=False):
    scale = [[i / (len(ramp) - 1), c] for i, c in enumerate(ramp)]
    colors = []
    for g in geom:
        v = values.get(g["name"])
        if v is None or (isinstance(v, float) and np.isnan(v)):
            colors.append(NO_DATA)
            continue
        t = (np.log10(max(v, lo)) - np.log10(lo)) / (np.log10(hi) - np.log10(lo)) if log else (v - lo) / (hi - lo)
        colors.append(sample_colorscale(scale, float(min(max(t, 0), 1)))[0])
    return {"key": key, "label": label, "colors": colors,
            "tips": [tips.get(g["name"], f"<b>{g['name']} County</b><br>No data") for g in geom],
            "gradient": f"linear-gradient(90deg, {', '.join(ramp)})", "lo": lo_txt, "hi": hi_txt,
            "title": title, "body": body, "top": top_html, "note": note}


layers = []

# 1. Water source
v, t = {}, {}
for name in names_sorted:
    if name in by_name.index:
        r = by_name.loc[name]
        v[name] = r["share_on_wells"]
        t[name] = (f"<b>{name} County</b><br>{r['share_on_wells']:.0f}% of people served by well systems<br>"
                   f"{int(r['systems'])} community systems, {int(r['people']):,} people")
low_wells = sorted(((n, x) for n, x in v.items()), key=lambda q: q[1])[:3]
layers.append(build_layer(
    "source", "Water source", BLUE_RAMP, v, t, 0, 100, "0% wells", "100% wells",
    "Where the water comes from",
    f"In <b>{n_counties_mostly_wells} of {n_counties}</b> counties with a community system, most people served get groundwater. "
    f"Statewide, {pct_people_wells:.0f}% of people on community systems drink well water. The big exceptions draw from "
    f"Lake Superior or rivers.",
    "Least well water:<ul>" + "".join(f"<li>{n}: {x:.0f}% wells</li>" for n, x in low_wells) + "</ul>",
    "Community water systems only. Each system counts in one home county."))

# 2. Private wells
v = {n: r["pct_not_on_community"] for n, r in pw_by.iterrows()}
t = {}
for n, r in pw_by.iterrows():
    note = "<br><i>Set to 0: systems here also serve other counties</i>" if r["served_exceeds_population"] else ""
    t[n] = (f"<b>{n} County</b><br>{r['pct_not_on_community']:.0f}% not on a community system<br>"
            f"about {int(r['est_not_on_community']):,} of {int(r['population_2025']):,} people{note}")
layers.append(build_layer(
    "private", "Private wells", GREEN_RAMP, v, t, 0, 100, "0%", "100% off public water",
    "Who's not on public water",
    f"About <b>{pw_total:,}</b> Minnesotans ({pw_pct:.0f}%) aren't on a community system, mostly private wells that "
    f"federal drinking water rules don't cover. That matches the Minnesota Department of Health's figure of about 1.2 million. "
    f"In <b>{pw_n_majority}</b> counties it's at least half the people.",
    "Highest share:<ul>" + top3(v.items(), lambda x: f"{x:.0f}%") + "</ul>",
    f"Estimate: Census 2025 population minus people served. Set to 0 where systems cross county lines ({pw_flagged})."))

# 3. Water quality: share of community systems with a health-based violation
v, t = {}, {}
for name in names_sorted:
    if name in by_name.index:
        r = by_name.loc[name]
        v[name] = 100 * r["with_violation"] / r["systems"]
        t[name] = (f"<b>{name} County</b><br>{int(r['with_violation'])} of {int(r['systems'])} community systems "
                   f"had a health-based violation (5 yrs)")
worst = [(n, x) for n, x in v.items() if by_name.loc[n, "systems"] >= 5]
layers.append(build_layer(
    "quality", "Water quality", ORANGE_RAMP, v, t, 0, 40, "0% of systems", "40%+ with a violation",
    "Health-based violations",
    f"Share of each county's community systems with at least one health-based violation in the last five years. "
    f"Statewide it's {100 * sys_df['has_violation'].mean():.0f}%. Small systems have more violations, and small tribal systems "
    f"the most ({ratio:.1f}x similar state systems).",
    "Highest share (counties with 5+ systems):<ul>" + top3(worst, lambda x: f"{x:.0f}%") + "</ul>",
    "Counts systems, not people, so one big utility doesn't swamp a county. Tribal systems have no county and aren't shown here."))

# 4. Population density
v = {n: pop[n] / area[n] for n in pop if n in area}
t = {n: f"<b>{n} County</b><br>{pop[n]:,} people (2025)<br>{v[n]:,.0f} people per square mile" for n in v}
layers.append(build_layer(
    "population", "Population", PURPLE_RAMP, v, t, 2, 3000, "2 per sq mi", "3,000+",
    "Where people live",
    "People per square mile, 2025. Compare it with the other layers: the dense metro counties are mostly on big "
    "community systems, while the lightly populated north relies most on private wells.",
    "Most dense:<ul>" + top3(v.items(), lambda x: f"{x:,.0f} per sq mi") + "</ul>",
    "Census Vintage 2025 county estimates. Area is approximate, from the county outlines.", log=True))

# 5. Hardness (only if build.py produced it)
hard_path = ROOT / "output" / "mn_hardness.csv"
if hard_path.exists():
    hd = pd.read_csv(hard_path).set_index("county")
    v = hd["median_hardness_mg_l"].to_dict()
    t = {n: (f"<b>{n} County</b><br>median {r['median_hardness_mg_l']:.0f} mg/L as CaCO3 ({r['hardness_class']})<br>"
             f"{int(r['wells'])} wells, {int(r['samples'])} samples since 2010") for n, r in hd.iterrows()}
    layers.append(build_layer(
        "hardness", "Hardness", TEAL_RAMP, v, t, 0, 400, "soft", "very hard (400+ mg/L)",
        "How hard the groundwater is",
        "Median hardness of groundwater samples from wells, by county. Hard water isn't a health risk and isn't regulated, "
        "but it's why so many Minnesota homes have water softeners.",
        "Hardest:<ul>" + top3(v.items(), lambda x: f"{x:.0f} mg/L") + "</ul>",
        "Water Quality Portal well samples, 2010 to now. USGS classes: soft under 60, moderate 61 to 120, hard 121 to 180, very hard over 180 mg/L."))

explorer_json = json.dumps({"geom": geom, "layers": layers})

# ---------- chart 2: every system as a dot ----------
order = ["Groundwater (wells)", "Groundwater influenced by surface water"]
order += sorted(set(sys_df["source_type"]) - set(order))
short = {s: ("Surface water" if s.startswith("Surface") else
             "Wells, surface-influenced" if "influenced" in s else
             "Wells" if s.startswith("Groundwater") else s) for s in order}
rng = np.random.default_rng(7)
# Row centers and spread: the Wells row holds ~95% of systems, so it gets a taller band
centers = {order[0]: 0.0, order[1]: 1.35, order[2]: 2.2}
spread = {order[0]: 0.55, order[1]: 0.15, order[2]: 0.3}
for s_ in order[3:]:
    centers[s_] = max(centers.values()) + 0.85; spread[s_] = 0.3
sys_df["y"] = [centers[t] + rng.uniform(-spread[t], spread[t]) for t in sys_df["source_type"]]

c2 = go.Figure()
for label, mask, color, size, symbol in [
    ("No health-based violation", ~sys_df["has_violation"] & ~sys_df["tribal"], GRAY, 8, "circle"),
    ("Health-based violation in last 5 yrs", sys_df["has_violation"] & ~sys_df["tribal"], ORANGE, 8, "circle"),
    ("Tribal system, no violation", ~sys_df["has_violation"] & sys_df["tribal"], GRAY, 9, "diamond"),
    ("Tribal system, violation", sys_df["has_violation"] & sys_df["tribal"], ORANGE, 9, "diamond"),
]:
    d = sys_df[mask]
    c2.add_trace(go.Scatter(
        x=d["population_served"], y=d["y"], mode="markers", name=label,
        marker=dict(color=color, size=size, symbol=symbol, opacity=0.8,
                    line=dict(color="white", width=1)),
        customdata=d[["system_name", "county", "health_violations_5yr"]].to_numpy(),
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} County<br>"
                      "%{x:,} people<br>%{customdata[2]} health-based violation(s)<extra></extra>",
    ))
for s_ in order:
    top = centers[s_] - spread[s_] - 0.12
    c2.add_annotation(x=0, xref="paper", y=top, yref="y", text=f"<b>{short[s_]}</b>", showarrow=False,
                      xanchor="left", yanchor="bottom", font=dict(size=12, color=INK), bgcolor="white")
c2.add_vline(x=SMALL, line=dict(color=MUTED, width=1, dash="dot"))
c2.add_annotation(x=np.log10(SMALL), y=max(centers.values()) + 0.42, text=f" {SMALL} people",
                  showarrow=False, xanchor="left", font=dict(color=MUTED, size=12))
c2.update_layout(
    **BASE_LAYOUT, height=500, margin=dict(l=10, r=10, t=10, b=40),
    xaxis=dict(type="log", title="People served (log scale)", gridcolor="#eceff2", zeroline=False,
               range=[np.log10(sys_df["population_served"].min() * 0.7), np.log10(sys_df["population_served"].max() * 1.5)],
               tickvals=[10, 100, 1_000, 10_000, 100_000, 1_000_000], ticktext=["10", "100", "1k", "10k", "100k", "1M"]),
    yaxis=dict(showticklabels=False, range=[max(centers.values()) + 0.5, -1.05], showgrid=False, zeroline=False),
    legend=dict(orientation="h", y=-0.22, x=0, font=dict(size=12)),
)

# ---------- chart 3: small systems, tribal vs state ----------
# Group names sit above each bar (not beside it) so the bars keep their width on phones
names = ["State-regulated", "Tribal (EPA-regulated)"]
c3 = go.Figure(go.Bar(
    y=[0, 1], x=[s_pct, t_pct], orientation="h",
    marker=dict(color=[GRAY, ORANGE], cornerradius=4),
    text=[f"<b>{s_pct:.1f}%</b>  ({s_hit} of {s_n})", f"<b>{t_pct:.1f}%</b>  ({t_hit} of {t_n})"],
    textposition="outside", cliponaxis=False, customdata=names,
    hovertemplate="%{customdata}: %{x:.1f}%<extra></extra>", width=0.45,
))
for i, n in enumerate(names):
    c3.add_annotation(x=0, y=i - 0.28, text=n, showarrow=False, xanchor="left", yanchor="bottom",
                      font=dict(size=13, color=INK))
c3.update_layout(
    **BASE_LAYOUT, height=260, margin=dict(l=10, r=10, t=10, b=50),
    xaxis=dict(range=[0, max(t_pct, s_pct) * 1.7], ticksuffix="%", gridcolor="#eceff2",
               title="% with a violation, last 5 years"),
    yaxis=dict(autorange="reversed", showticklabels=False, range=[1.5, -0.75]), showlegend=False,
)


def div(fig, name):
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "responsive": True})



EXPLORER_JS = """
<script>
(function () {
  const D = JSON.parse(document.getElementById('explorer-data').textContent);
  const el = document.getElementById('explorer-map');
  const layout = {
    margin: {l: 0, r: 0, t: 0, b: 0}, height: Math.min(520, Math.round(el.clientWidth * 1.05)), showlegend: false, hovermode: 'closest',
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: {family: 'Inter, system-ui, sans-serif', size: 13, color: '#1f2933'},
    hoverlabel: {bgcolor: 'white', bordercolor: '#d0d7de', font: {size: 13, color: '#1f2933'}},
    xaxis: {visible: false, fixedrange: true},
    yaxis: {visible: false, fixedrange: true, scaleanchor: 'x', scaleratio: 1 / Math.cos(46.3 * Math.PI / 180)}
  };
  function traces(L) {
    return D.geom.map((g, i) => ({
      type: 'scatter', x: g.x, y: g.y, fill: 'toself', fillcolor: L.colors[i], mode: 'lines',
      line: {color: 'white', width: 0.8}, hoveron: 'fills', text: L.tips[i], hoverinfo: 'text'
    }));
  }
  function show(key) {
    const L = D.layers.find(l => l.key === key);
    Plotly.react(el, traces(L), layout, {displayModeBar: false, responsive: true});
    document.getElementById('ex-title').textContent = L.title;
    document.getElementById('ex-body').innerHTML = L.body;
    document.getElementById('ex-top').innerHTML = L.top;
    document.getElementById('ex-note').textContent = L.note;
    document.getElementById('ex-bar').style.background = L.gradient;
    document.getElementById('ex-lo').textContent = L.lo;
    document.getElementById('ex-hi').textContent = L.hi;
    document.querySelectorAll('.ex-btn').forEach(b => b.setAttribute('aria-pressed', b.dataset.key === key));
  }
  const btns = document.getElementById('ex-buttons');
  D.layers.forEach(L => {
    const b = document.createElement('button');
    b.className = 'ex-btn'; b.dataset.key = L.key; b.textContent = L.label;
    b.onclick = () => show(L.key);
    btns.appendChild(b);
  });
  show(D.layers[0].key);
})();
</script>
"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Minnesota drinking water: small tribal systems had {ratio:.1f}x the violation rate</title>
<script src="{PLOTLY_JS}"></script>
<style>
  :root {{ --ink:{INK}; --muted:{MUTED}; --accent:{ORANGE}; --blue:#1c5a99; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:Inter, system-ui, -apple-system, sans-serif; color:var(--ink);
         background:#fbfaf7; line-height:1.6; }}
  header {{ background:#0b3566; color:white; padding:72px 24px 56px; }}
  header .wrap, main {{ max-width:880px; margin:0 auto; }}
  .kicker {{ text-transform:uppercase; letter-spacing:.12em; font-size:12px; opacity:.75; }}
  h1 {{ font-size:clamp(32px,5vw,48px); line-height:1.1; margin:.3em 0 .4em; }}
  header p {{ font-size:18px; max-width:680px; opacity:.9; }}
  .hero {{ display:flex; gap:28px; align-items:center; flex-wrap:wrap; margin-top:12px; }}
  .hero .big {{ font-size:clamp(72px,12vw,120px); font-weight:800; line-height:1; color:#ff9a66; }}
  .hero h1 {{ flex:1; min-width:280px; font-size:clamp(24px,3.2vw,34px); margin:0; }}
  .jump {{ color:#ffd2bb; white-space:nowrap; }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:16px; margin-top:36px; }}
  .stat b {{ display:block; font-size:34px; line-height:1.1; }}
  .stat span {{ font-size:14px; opacity:.8; }}
  main {{ padding:0 24px 80px; }}
  section {{ padding-top:64px; }}
  .num {{ color:var(--accent); font-weight:700; font-size:14px; letter-spacing:.08em; }}
  h2 {{ font-size:28px; line-height:1.2; margin:.2em 0 .5em; }}
  .chart {{ background:white; border:1px solid #e6e3dc; border-radius:10px; padding:12px; margin:20px 0 10px; }}
  .note {{ color:var(--muted); font-size:14px; }}
  .hl {{ color:var(--accent); font-weight:600; }}
  footer {{ border-top:1px solid #e6e3dc; margin-top:64px; padding-top:24px; font-size:14px; color:var(--muted); }}
  a {{ color:var(--blue); }}
  .ex-buttons {{ display:flex; flex-wrap:wrap; gap:8px; margin:16px 0 4px; }}
  .ex-btn {{ font:inherit; font-size:14px; padding:7px 14px; border-radius:999px; border:1px solid #cfd6dd;
             background:white; color:var(--ink); cursor:pointer; }}
  .ex-btn[aria-pressed="true"] {{ background:#0b3566; border-color:#0b3566; color:white; }}
  .ex-grid {{ display:grid; grid-template-columns: minmax(0,1.6fr) minmax(0,1fr); gap:20px; align-items:start; }}
  .ex-panel h3 {{ margin:4px 0 8px; font-size:20px; }}
  .ex-panel p {{ margin:0 0 10px; }}
  .ex-panel ul {{ margin:4px 0 10px; padding-left:20px; }}
  .ex-key {{ margin:6px 12px 4px; }}
  .ex-key .bar {{ height:10px; border-radius:5px; }}
  .ex-key .ends {{ display:flex; justify-content:space-between; font-size:12px; color:var(--muted); margin-top:3px; }}
  @media (max-width: 720px) {{ .ex-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header><div class="wrap">
  <div class="kicker">Minnesota drinking water &middot; EPA SDWIS data</div>
  <div class="hero">
    <div class="big">{ratio:.1f}x</div>
    <h1>Small tribal water systems in Minnesota had {ratio:.1f} times the rate of health-based violations of similar-size state systems.</h1>
  </div>
  <p>{t_hit} of {t_n} tribal systems serving under {SMALL} people had a recorded health-based violation in the last five years,
     versus {s_hit} of {s_n} state-regulated ones. <a class="jump" href="#compare-section">See the comparison &darr;</a></p>
  <div class="stats">
    <div class="stat"><b>{n_systems:,}</b><span>active community water systems</span></div>
    <div class="stat"><b>{pct_systems_wells:.0f}%</b><span>of those systems run on wells</span></div>
    <div class="stat"><b>{n_small:,}</b><span>serve fewer than {SMALL} people</span></div>
    <div class="stat"><b>~{pw_total/1e6:.1f}M</b><span>Minnesotans not on a community system, mostly private wells</span></div>
  </div>
</div></header>
<main>

<section>
  <div class="num">01</div>
  <h2>Explore the map</h2>
  <p>Pick a layer to recolor Minnesota's 87 counties. Hover or tap a county for its numbers.</p>
  <div class="ex-buttons" id="ex-buttons"></div>
  <div class="ex-grid">
    <div class="chart" style="margin-top:8px">
      <div id="explorer-map"></div>
      <div class="ex-key"><div class="bar" id="ex-bar"></div>
        <div class="ends"><span id="ex-lo"></span><span id="ex-hi"></span></div></div>
    </div>
    <div class="ex-panel">
      <h3 id="ex-title"></h3>
      <p id="ex-body"></p>
      <div id="ex-top"></div>
      <p class="note" id="ex-note"></p>
    </div>
  </div>
  <script type="application/json" id="explorer-data">{explorer_json}</script>
  {EXPLORER_JS}
</section>

<section>
  <div class="num">02</div>
  <h2>Every system, by size</h2>
  <p>Each dot is one water system. Orange means at least one health-based violation in the last five years.
     <span class="hl">{pct_small_viol:.0f}%</span> of systems under {SMALL} people had one, compared with
     {pct_big_viol:.0f}% of systems serving 10,000 or more. Diamonds are tribal systems, which EPA regulates directly.</p>
  <div class="chart">{div(c2, "dots")}</div>
  <p class="note">Dots are spread up and down within each row so they don't sit on top of each other; the vertical position means nothing.</p>
</section>

<section id="compare-section">
  <div class="num">03</div>
  <h2>Among small systems, tribal systems had about {ratio:.1f}x the violation rate</h2>
  <p>Because small systems have more violations everywhere, this compares only systems under {SMALL} people: <b>{t_hit} of {t_n}</b> tribal systems had a recorded
     health-based violation in the last five years, versus <b>{s_hit} of {s_n}</b> state-regulated ones.</p>
  <div class="chart">{div(c3, "compare")}</div>
  <p class="note">{t_n} systems is a small group, so one or two systems moves the rate a lot. A recorded violation also
     depends on testing and reporting, so this measures what's on the record, not water quality directly.</p>
</section>

<section>
  <div class="num">04</div>
  <h2>About 1 in 5 Minnesotans aren't on a community system at all</h2>
  <p>Subtracting the people community systems serve from each county's population leaves about
     <b>{pw_total:,}</b> people ({pw_pct:.0f}%) who get water some other way, mostly private wells.
     Federal drinking water rules don't cover private wells, so testing is up to the owner. That estimate lines up
     with the Minnesota Department of Health's own figure of about 1.2 million private well users.</p>
  <p>In <b>{pw_n_majority}</b> counties, at least half the people are off community systems. The highest shares are
     {pw_top_share.iloc[0]["county"]} ({pw_top_share.iloc[0]["pct_not_on_community"]:.0f}%),
     {pw_top_share.iloc[1]["county"]} ({pw_top_share.iloc[1]["pct_not_on_community"]:.0f}%) and
     {pw_top_share.iloc[2]["county"]} ({pw_top_share.iloc[2]["pct_not_on_community"]:.0f}%). The most people are in
     {pw_top_people["county"]} County, about {int(pw_top_people["est_not_on_community"]):,}.</p>
  <p class="note">Switch the map in section 01 to <b>Private wells</b> to see it by county.</p>
  <p class="note">Estimate: Census 2025 county population minus people served by community systems. Some of these people
     are on small non-community systems, not private wells. Each system counts in one home county, so where systems
     serve across county lines the estimate is set to 0 ({pw_flagged}). Tribal systems have no county in the EPA data
     and aren't subtracted.</p>
</section>

<footer>
  Data: EPA SDWIS via ECHO (SDWA public water systems, geographic areas, and violations/enforcement files); U.S. Census Bureau Vintage 2025 county population estimates; Minnesota Department of Health for the 1.2 million private well users figure.
  Built with DuckDB SQL and Python/Plotly. Code and method:
  <a href="https://github.com/louiserosenbaum/US-water-access">github.com/louiserosenbaum/US-water-access</a>.
  &middot; Louise Rosenbaum
</footer>
</main>
</body>
</html>
"""
(OUT / "index.html").write_text(html)
print(f"wrote docs/index.html  ({n_systems} systems, small tribal {t_hit}/{t_n} = {t_pct:.1f}%, "
      f"small state {s_hit}/{s_n} = {s_pct:.1f}%, ratio {ratio:.1f}x)")
