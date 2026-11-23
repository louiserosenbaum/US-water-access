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


c1 = go.Figure()
for f in geo["features"]:
    name = f["properties"]["NAME"]
    xs, ys = [], []
    for ring in outer_rings(f["geometry"]):
        xs += [pt[0] for pt in ring] + [None]
        ys += [pt[1] for pt in ring] + [None]
    if name in by_name.index:
        r = by_name.loc[name]
        color = sample_colorscale(SCALE, r["share_on_wells"] / 100)[0]
        tip = (f"<b>{name} County</b><br>{r['share_on_wells']:.0f}% of people served by well systems<br>"
               f"{int(r['systems'])} community systems, {int(r['people']):,} people<br>"
               f"{int(r['with_violation'])} with a health-based violation (5 yrs)")
    else:
        color = NO_DATA
        tip = f"<b>{name} County</b><br>No active community water system"
    c1.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor=color, mode="lines",
                            line=dict(color="white", width=0.8), hoveron="fills",
                            text=tip, hoverinfo="text", showlegend=False))
# colorbar only (one invisible point carries the scale)
c1.add_trace(go.Scatter(x=[-94], y=[46], mode="markers", hoverinfo="skip", showlegend=False,
                        marker=dict(size=0.1, opacity=0, color=[0], cmin=0, cmax=100, colorscale=SCALE,
                                    showscale=True,
                                    colorbar=dict(title=dict(text="% of people<br>on well systems", side="top"),
                                                  ticksuffix="%", thickness=12, len=0.6, outlinewidth=0))))
mid_lat = 46.3
c1.update_layout(
    **BASE_LAYOUT, height=560, margin=dict(l=0, r=0, t=0, b=0),
    xaxis=dict(visible=False, fixedrange=True),
    yaxis=dict(visible=False, fixedrange=True, scaleanchor="x", scaleratio=1 / np.cos(np.radians(mid_lat))),
    hovermode="closest",
)

# ---------- chart 2: every system as a dot ----------
order = ["Groundwater (wells)", "Groundwater influenced by surface water"]
order += sorted(set(sys_df["source_type"]) - set(order))
short = {s: ("Surface water" if s.startswith("Surface") else
             "Wells, surface-influenced" if "influenced" in s else
             "Wells" if s.startswith("Groundwater") else s) for s in order}
rng = np.random.default_rng(7)
sys_df["y"] = sys_df["source_type"].map({s: i for i, s in enumerate(order)}) + rng.uniform(-0.3, 0.3, len(sys_df))

c2 = go.Figure()
for label, mask, color, size, symbol in [
    ("No health-based violation", ~sys_df["has_violation"] & ~sys_df["tribal"], GRAY, 6, "circle"),
    ("Health-based violation in last 5 yrs", sys_df["has_violation"] & ~sys_df["tribal"], ORANGE, 8, "circle"),
    ("Tribal system, no violation", ~sys_df["has_violation"] & sys_df["tribal"], GRAY, 10, "diamond"),
    ("Tribal system, violation", sys_df["has_violation"] & sys_df["tribal"], ORANGE, 11, "diamond"),
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
c2.add_vline(x=SMALL, line=dict(color=MUTED, width=1, dash="dot"))
c2.add_annotation(x=np.log10(SMALL), y=-0.55, text=f"← under {SMALL} people",
                  showarrow=False, xanchor="right", font=dict(color=MUTED, size=12))
c2.update_layout(
    **BASE_LAYOUT, height=420, margin=dict(l=10, r=10, t=10, b=40),
    xaxis=dict(type="log", title="People served (log scale)", gridcolor="#eceff2", zeroline=False),
    yaxis=dict(tickvals=list(range(len(order))), ticktext=[short[s] for s in order],
               range=[len(order) - 0.4, -0.6], showgrid=False, zeroline=False),
    legend=dict(orientation="h", y=-0.22, x=0, font=dict(size=12)),
)

# ---------- chart 3: small systems, tribal vs state ----------
c3 = go.Figure(go.Bar(
    y=["State-regulated", "Tribal (EPA-regulated)"], x=[s_pct, t_pct], orientation="h",
    marker=dict(color=[GRAY, ORANGE], cornerradius=4),
    text=[f"{s_pct:.0f}%  ({s_hit} of {s_n})", f"{t_pct:.0f}%  ({t_hit} of {t_n})"],
    textposition="outside", cliponaxis=False,
    hovertemplate="%{y}: %{x:.1f}%<extra></extra>", width=0.55,
))
c3.update_layout(
    **BASE_LAYOUT, height=220, margin=dict(l=10, r=40, t=10, b=40),
    xaxis=dict(range=[0, max(t_pct, s_pct) * 1.45], ticksuffix="%", gridcolor="#eceff2",
               title=f"Share of systems under {SMALL} people with a health-based violation"),
    yaxis=dict(autorange="reversed"), showlegend=False,
)


def div(fig, name):
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displaylogo": False, "responsive": True,
                               "modeBarButtonsToRemove": ["select2d", "lasso2d"]})


html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Who drinks from wells in Minnesota?</title>
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
  header p {{ font-size:18px; max-width:640px; opacity:.9; }}
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
</style>
</head>
<body>
<header><div class="wrap">
  <div class="kicker">Minnesota drinking water &middot; EPA SDWIS data</div>
  <h1>Who drinks from wells in Minnesota?</h1>
  <p>Most of the state's community water systems pump groundwater, and most of them are small.
     Small systems are where health-based violations show up, and tribal systems show them most.</p>
  <div class="stats">
    <div class="stat"><b>{n_systems:,}</b><span>active community water systems</span></div>
    <div class="stat"><b>{pct_systems_wells:.0f}%</b><span>of those systems run on wells</span></div>
    <div class="stat"><b>{n_small:,}</b><span>serve fewer than {SMALL} people</span></div>
    <div class="stat"><b>{ratio:.1f}x</b><span>violation rate, small tribal vs. small state systems</span></div>
  </div>
</div></header>
<main>

<section>
  <div class="num">01</div>
  <h2>In most counties, it's mostly wells</h2>
  <p>In <b>{n_counties_mostly_wells} of {n_counties}</b> counties with a community water system, at least half
     the people served get their water from groundwater systems. Statewide that's
     <b>{pct_people_wells:.0f}%</b> of the {n_people:,} people these systems serve. The largest exceptions are
     {exceptions_txt} counties, where the big systems draw from Lake Superior or rivers. Hover a county for its numbers.</p>
  <div class="chart">{div(c1, "map")}</div>
  <p class="note">Each system is placed in one home county. People on private wells are not counted here; this is community systems only.</p>
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

<section>
  <div class="num">03</div>
  <h2>Among small systems, tribal systems had about {ratio:.1f}x the violation rate</h2>
  <p>Comparing like with like (systems under {SMALL} people), <b>{t_hit} of {t_n}</b> tribal systems had a recorded
     health-based violation in the last five years, versus <b>{s_hit} of {s_n}</b> state-regulated ones.</p>
  <div class="chart">{div(c3, "compare")}</div>
  <p class="note">{t_n} systems is a small group, so one or two systems moves the rate a lot. A recorded violation also
     depends on testing and reporting, so this measures what's on the record, not water quality directly.</p>
</section>

<footer>
  Data: EPA SDWIS via ECHO (SDWA public water systems, geographic areas, and violations/enforcement files).
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
