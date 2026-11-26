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
    big = max(outer_rings(f["geometry"]), key=ring_area_sq_mi)   # label point = center of largest piece
    geom.append({"name": name, "x": xs, "y": ys,
                 "cx": round(float(np.mean([pt[0] for pt in big])), 4),
                 "cy": round(float(np.mean([pt[1] for pt in big])), 4)})
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
    raw = [None if values.get(g["name"]) is None or (isinstance(values.get(g["name"]), float) and np.isnan(values.get(g["name"])))
           else round(float(values[g["name"]]), 2) for g in geom]
    return {"key": key, "label": label, "colors": colors, "values": raw, "log": log,
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
hd = pd.read_csv(hard_path).set_index("county") if hard_path.exists() else None
if hd is not None:
    ok = hd[hd["enough_wells"]]
    v = ok["median_hardness_mg_l"].to_dict()
    t = {}
    for n, r in hd.iterrows():
        if r["enough_wells"]:
            t[n] = (f"<b>{n} County</b><br>median {r['median_hardness_mg_l']:.0f} mg/L ({r['hardness_class']})<br>"
                    f"{int(r['wells'])} wells sampled since 2010")
        else:
            t[n] = f"<b>{n} County</b><br>Only {int(r['wells'])} well(s) sampled, too few to map"
    n_vh = int((ok["hardness_class"] == "very hard").sum())
    layers.append(build_layer(
        "hardness", "Hardness", TEAL_RAMP, v, t, 60, 600, "60 (soft)", "600+ mg/L",
        "How hard the groundwater is",
        f"Hardness is calcium and magnesium dissolved from rock. In <b>{n_vh} of {len(ok)}</b> counties with enough data, "
        f"the typical well is <b>very hard</b> (over 180 mg/L). It's hardest in the southwest and softest up north, where "
        f"the bedrock is granite instead of limestone. Hard water isn't a health risk and isn't regulated, but it's why so "
        f"many Minnesota homes have softeners.",
        "Hardest:<ul>" + top3(v.items(), lambda x: f"{x:,.0f} mg/L") + "</ul>",
        f"Calculated from calcium and magnesium in {int(hd['wells'].sum()):,} wells (Water Quality Portal, 2010 to 2025), "
        f"mostly state groundwater monitoring wells. That's raw groundwater, not what comes out of a city tap. "
        f"Counties with fewer than 5 wells are gray. Very hard = over 180 mg/L."))

# 6. Where it drains: Minnesota sits on three continental divides, so its rivers end in three different seas.
BASINS = {
    "gulf": ("Gulf of Mexico", "#1c5a99", "rgba(28,90,153,0.28)"),
    "hudson": ("Hudson Bay", "#2f9461", "rgba(47,148,97,0.28)"),
    "atlantic": ("Atlantic, via Lake Superior", "#8e4fb8", "rgba(142,79,184,0.25)"),
}
rivers = json.loads((ROOT / "data" / "geo" / "mn_rivers.json").read_text())
# Surface-water systems (rivers and lakes) by where that water drains, using each system's home county.
# Approximate: it assumes a county's surface systems draw from that county's main basin.
COUNTY_BASIN = {"Clay": "hudson", "Otter Tail": "hudson", "Polk": "hudson", "Pennington": "hudson",
                "Koochiching": "hudson", "St. Louis": "atlantic", "Lake": "atlantic", "Cook": "atlantic"}
surf = sys_df[~sys_df["on_wells"] & sys_df["county"].notna()]
surf_by = surf.groupby(surf["county"].map(lambda c: COUNTY_BASIN.get(c, "gulf")))["population_served"].sum()
surf_total = int(surf_by.sum())
surf_pct = {k: 100 * surf_by.get(k, 0) / surf_total for k in BASINS}
# The drainage story gets its own zoomable map (section 02), so it isn't an explorer layer.
SEA_NAME = {k: v[0] for k, v in BASINS.items()}
fc = lambda feats: {"type": "FeatureCollection", "features": feats}
drain_map = {
    "bounds": rivers["bounds"],
    "mask": fc([{"type": "Feature", "properties": {}, "geometry": rivers["mask"]}]),
    "counties": fc([{"type": "Feature", "properties": {"name": f["properties"]["NAME"]}, "geometry": f["geometry"]}
                    for f in geo["features"]]),
    "rivers": fc([{"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": r["coords"]},
                   "properties": {"name": r["name"], "sea": SEA_NAME[r["basin"]], "color": BASINS[r["basin"]][1],
                                  "w": r["w"], "info": f"{r['miles']:,} miles"}}
                  for r in rivers["rivers"]]),
    "lakes": fc([{"type": "Feature", "geometry": k["geometry"],
                  "properties": {"name": k["name"], "sea": SEA_NAME[k["basin"]], "color": BASINS[k["basin"]][1],
                                 "info": f"{k['acres']:,} acres"}}
                 for k in rivers["lakes"]]),
    "basins": fc([{"type": "Feature", "geometry": b["geometry"],
                   "properties": {"name": b["name"] + " basin", "official": b["official"], "sea": SEA_NAME[b["sea"]], "color": BASINS[b["sea"]][1],
                                  "pct": b["pct_state"], "counties": ", ".join(b["counties"]), "n": len(b["counties"])}}
                  for b in rivers.get("basins", [])]),
    "labels": [[b["label"][0], b["label"][1], b["name"], BASINS[b["sea"]][1]] for b in rivers.get("basins", [])
               if b["pct_state"] >= 2],
    "arrows": [[-97.0, 49.05, "&uarr; to Hudson Bay", BASINS["hudson"][1]],
               [-91.75, 43.62, "&darr; to the Gulf of Mexico", BASINS["gulf"][1]],
               [-90.3, 47.25, "&rarr; to the Atlantic", BASINS["atlantic"][1]]],
    "hill": [-92.93, 47.46],
    "legend": [[BASINS[k][0], BASINS[k][1]] for k in ("gulf", "hudson", "atlantic")],
}
has_basins = bool(drain_map["basins"]["features"])
area_pct = {k: sum(b["pct_state"] for b in rivers.get("basins", []) if b["sea"] == k) for k in BASINS}
drain_json = json.dumps(drain_map, separators=(",", ":"))

# Spikes: a column on each county whose height is an absolute count, so big and small places
# can be compared at a glance (the color shows the rate, the spike shows how many).
people_served = {n: int(by_name.loc[n, "people"]) for n in by_name.index}
spike_defs = {
    "source": ("people on community systems", people_served),
    "private": ("people off public water (est.)", {n: int(r["est_not_on_community"]) for n, r in pw_by.iterrows()}),
    "quality": ("systems with a health-based violation", {n: int(by_name.loc[n, "with_violation"]) for n in by_name.index}),
    "population": ("people (2025)", {n: int(x) for n, x in pop.items()}),
}
if hd is not None:
    spike_defs["hardness"] = ("wells sampled", {n: int(r["wells"]) for n, r in hd.iterrows()})
rank_labels = {"source": "% of people on well systems", "private": "% of people off public water",
               "quality": "% of systems with a health violation", "population": "people per square mile (log scale)",
               "hardness": "median hardness (mg/L)"}
for L in layers:
    L["rank_label"] = rank_labels.get(L["key"], L["label"])
    L.setdefault("overlay", None)
    if L["key"] in spike_defs:
        lab, vals = spike_defs[L["key"]]
        L["spike_label"] = lab
        L["spikes"] = [vals.get(g["name"], 0) for g in geom]
        # dark gray with a white edge: reads on light counties and, thanks to the edge, on dark ones too
        L["spike_color"] = "rgba(31,41,51,0.78)"

# County profiles: every measure for one county next to the state figure, plus its water systems
state = {
    "wells": pct_people_wells,
    "private": pw_pct,
    "quality": 100 * sys_df["has_violation"].mean(),
    "density": pw_pop / sum(area.values()),
}
if hd is not None:
    state["hardness"] = float(hd.loc[hd["enough_wells"], "median_hardness_mg_l"].median())
sys_cols = sys_df.sort_values("population_served", ascending=False)
profiles = []
for g in geom:
    n = g["name"]
    rows = []
    if n in by_name.index:
        r = by_name.loc[n]
        rows.append(["Served by well systems", f"{r['share_on_wells']:.0f}%", r["share_on_wells"] / 100, state["wells"] / 100,
                     f"state {state['wells']:.0f}%"])
        q = 100 * r["with_violation"] / r["systems"]
        rows.append(["Systems with a health violation", f"{int(r['with_violation'])} of {int(r['systems'])} ({q:.0f}%)",
                     q / 100, state["quality"] / 100, f"state {state['quality']:.0f}%"])
    if n in pw_by.index:
        r = pw_by.loc[n]
        rows.append(["Off public water (est.)", f"{r['pct_not_on_community']:.0f}% (~{int(r['est_not_on_community']):,})",
                     r["pct_not_on_community"] / 100, state["private"] / 100, f"state {state['private']:.0f}%"])
    if n in pop:
        dens = pop[n] / area[n]
        f = lambda d: (np.log10(max(d, 2)) - np.log10(2)) / (np.log10(3000) - np.log10(2))
        rows.append(["People per sq mile (log scale)", f"{dens:,.0f}", min(f(dens), 1), f(state["density"]), f"state {state['density']:.0f}"])
    if hd is not None and n in hd.index and hd.loc[n, "enough_wells"]:
        h = hd.loc[n, "median_hardness_mg_l"]
        rows.append(["Hardness (mg/L)", f"{h:,.0f} ({hd.loc[n, 'hardness_class']})", min(h / 600, 1),
                     state["hardness"] / 600, f"typical county {state['hardness']:.0f}"])
    systems = [[r.system_name, int(r.population_served), "Wells" if r.on_wells else ("Surface water" if str(r.source_type).startswith("Surface") else "Mixed"),
                int(r.health_violations_5yr)]
               for r in sys_cols[sys_cols["county"] == n].itertuples()]
    profiles.append({"name": n, "pop": int(pop.get(n, 0)), "rows": [[a, b, round(float(c), 3), round(float(d), 3), e] for a, b, c, d, e in rows],
                     "systems": systems})

explorer_json = json.dumps({"geom": geom, "layers": layers, "profiles": profiles})

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



DRAIN_JS = """
<script>
(function () {
  const M = JSON.parse(document.getElementById('drain-data').textContent);
  const el = document.getElementById('drain-map');
  if (!window.maplibregl) { el.innerHTML = '<p class="note" style="padding:20px">The map could not load.</p>'; return; }
  const BG = '#f6f4ef';
  const DEM = {type: 'raster-dem', encoding: 'terrarium', tileSize: 256, maxzoom: 12,
    tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
    attribution: 'Relief: <a href="https://registry.opendata.aws/terrain-tiles/">Terrain Tiles</a> &middot; Water: MN DNR'};
  const b = M.bounds;
  const map = new maplibregl.Map({
    container: el, bounds: [[b[0], b[1]], [b[2], b[3]]], fitBoundsOptions: {padding: 16},
    maxBounds: [[-104, 40], [-82, 52]], minZoom: 4.5, maxZoom: 12, cooperativeGestures: true,
    attributionControl: false,
    style: {version: 8, sources: {}, layers: [{id: 'bg', type: 'background', paint: {'background-color': BG}}]}
  });
  map.addControl(new maplibregl.NavigationControl({visualizePitch: true}), 'top-right');
  map.addControl(new maplibregl.AttributionControl({compact: true}), 'bottom-left');

  map.on('load', () => {
    el.querySelectorAll('.maplibregl-compact-show').forEach(x => x.classList.remove('maplibregl-compact-show'));
    map.addSource('dem', DEM);
    map.addSource('dem3d', Object.assign({}, DEM));
    map.addLayer({id: 'relief', type: 'hillshade', source: 'dem', paint: {
      'hillshade-exaggeration': 0.85, 'hillshade-shadow-color': '#2b2b2b',
      'hillshade-highlight-color': '#ffffff', 'hillshade-accent-color': '#4a4a4a'}});
    ['basins', 'mask', 'counties', 'lakes', 'rivers'].forEach(k => map.addSource(k, {type: 'geojson', data: M[k]}));
    map.addLayer({id: 'basin-fill', type: 'fill', source: 'basins',
      paint: {'fill-color': ['get', 'color'], 'fill-opacity': 0.22}});
    map.addLayer({id: 'mask', type: 'fill', source: 'mask', paint: {'fill-color': BG, 'fill-opacity': 0.82}});
    map.addLayer({id: 'county-lines', type: 'line', source: 'counties',
      paint: {'line-color': '#ffffff', 'line-width': 0.6, 'line-opacity': 0.7}});
    map.addLayer({id: 'basin-line', type: 'line', source: 'basins',
      paint: {'line-color': ['get', 'color'], 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 1.2, 9, 2.5]}});
    map.addLayer({id: 'lakes', type: 'fill', source: 'lakes',
      paint: {'fill-color': ['get', 'color'], 'fill-opacity': 0.75, 'fill-outline-color': ['get', 'color']}});
    map.addLayer({id: 'rivers', type: 'line', source: 'rivers', layout: {'line-cap': 'round', 'line-join': 'round'},
      paint: {'line-color': ['get', 'color'],
              'line-width': ['interpolate', ['linear'], ['zoom'], 5, ['*', ['get', 'w'], 0.9], 10, ['*', ['get', 'w'], 3]]}});

    const tag = (html, cls, color) => { const d = document.createElement('div'); d.className = cls; d.innerHTML = html;
      if (color) d.style.color = color; return d; };
    M.labels.forEach(l => new maplibregl.Marker({element: tag(l[2], 'dm-label', l[3])}).setLngLat([l[0], l[1]]).addTo(map));
    M.arrows.forEach(a => new maplibregl.Marker({element: tag(a[2], 'dm-arrow', a[3])}).setLngLat([a[0], a[1]]).addTo(map));
    new maplibregl.Marker({element: tag('<span class="dm-dot"></span>Hill of Three Waters', 'dm-hill')})
      .setLngLat(M.hill).setPopup(new maplibregl.Popup({offset: 10}).setHTML(
        '<b>Hill of Three Waters</b><br>Near Hibbing. Rain that falls here can end up in Hudson Bay, the Atlantic or the Gulf of Mexico.'))
      .addTo(map);

    const pop = new maplibregl.Popup({maxWidth: '280px'});
    map.on('click', e => {
      const f = map.queryRenderedFeatures(e.point, {layers: ['rivers', 'lakes', 'basin-fill']})[0];
      if (!f) return;
      const p = f.properties;
      let h = '<b>' + p.name + '</b>' + (p.info ? ' <span class="dm-small">' + p.info + '</span>' : '') +
              '<br>drains to <b style="color:' + p.color + '">' + p.sea + '</b>';
      if (f.layer.id === 'basin-fill') h += '<br>' + p.pct + '% of Minnesota &middot; ' + p.n + ' counties' +
        (p.counties ? '<br><span class="dm-small">' + p.counties + '</span>' : '');
      pop.setLngLat(e.lngLat).setHTML(h).addTo(map);
    });
    ['rivers', 'lakes', 'basin-fill'].forEach(id => {
      map.on('mouseenter', id, () => map.getCanvas().style.cursor = 'pointer');
      map.on('mouseleave', id, () => map.getCanvas().style.cursor = '');
    });
  });

  const btn = document.getElementById('drain-3d');
  btn.onclick = () => {
    const on = btn.getAttribute('aria-pressed') !== 'true';
    btn.setAttribute('aria-pressed', on);
    btn.textContent = on ? 'Flat view' : 'Tilt in 3D';
    if (on) {
      map.setTerrain({source: 'dem3d', exaggeration: 10});
      // pull back to the whole state, then tilt, so the 3D view shows all three basins at once
      const cam = map.cameraForBounds([[b[0], b[1]], [b[2], b[3]]], {padding: 30});
      map.easeTo({center: cam.center, zoom: cam.zoom - 0.25, pitch: 55, bearing: -12, duration: 1600});
    }
    else { map.easeTo({pitch: 0, bearing: 0, duration: 900}); setTimeout(() => map.setTerrain(null), 900); }
  };
  document.getElementById('drain-reset').onclick = () =>
    map.fitBounds([[b[0], b[1]], [b[2], b[3]]], {padding: 16, pitch: map.getPitch(), bearing: map.getBearing()});
})();
</script>
"""


EXPLORER_JS = """
<script>
(function () {
  const D = JSON.parse(document.getElementById('explorer-data').textContent);
  const N = D.geom.length;
  const mapEl = document.getElementById('explorer-map');
  const stripEl = document.getElementById('explorer-strip');
  const st = {key: D.layers[0].key, sel: null, spikes: true};
  const INK = '#1f2933';
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const layer = () => D.layers.find(l => l.key === st.key);
  const baseLayout = h => ({
    margin: {l: 0, r: 0, t: 0, b: 0}, height: h, showlegend: false, hovermode: 'closest',
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: {family: 'Inter, system-ui, sans-serif', size: 13, color: INK},
    hoverlabel: {bgcolor: 'white', bordercolor: '#d0d7de', font: {size: 13, color: INK}}
  });

  function mapTraces(L) {
    const t = D.geom.map((g, i) => ({
      type: 'scatter', x: g.x, y: g.y, fill: 'toself', fillcolor: L.colors[i], mode: 'lines',
      line: {color: i === st.sel ? INK : 'white', width: i === st.sel ? 2.5 : 0.8},
      hoveron: 'fills', text: L.tips[i] + '<br><i>Click for the county profile</i>', hoverinfo: 'text'
    }));
    if (st.spikes && L.spikes) {
      const vmax = Math.max(...L.spikes), sx = [], sy = [], tx = [], ty = [], tt = [], ti = [];
      D.geom.forEach((g, i) => {
        const v = L.spikes[i]; if (!v) return;
        const h = 1.6 * v / vmax, w = 0.09;
        sx.push(g.cx - w, g.cx, g.cx + w, g.cx - w, null);
        sy.push(g.cy, g.cy + h, g.cy, g.cy, null);
        tx.push(g.cx); ty.push(g.cy + h); ti.push(i);
        tt.push('<b>' + g.name + ' County</b><br>' + v.toLocaleString() + ' ' + L.spike_label);
      });
      t.push({type: 'scatter', x: sx, y: sy, fill: 'toself', fillcolor: L.spike_color, mode: 'lines',
              line: {color: 'white', width: 1.3}, hoverinfo: 'skip'});
      t.push({type: 'scatter', x: tx, y: ty, mode: 'markers', marker: {size: 9, color: 'rgba(0,0,0,0)'},
              text: tt, hoverinfo: 'text', customdata: ti});
    }
    if (L.overlay) {
      const O = L.overlay;
      O.lakes.forEach(k => t.push({type: 'scatter', x: k.x, y: k.y, fill: 'toself', fillcolor: k.c, mode: 'lines',
        line: {color: k.lc, width: 0.8}, hoveron: 'fills', text: k.t, hoverinfo: 'text'}));
      O.rivers.forEach(r => t.push({type: 'scatter', x: r.x, y: r.y, mode: 'lines',
        line: {color: r.c, width: r.w, shape: 'spline', smoothing: 0.6}, text: r.t, hoverinfo: 'text'}));
      t.push({type: 'scatter', x: [O.marker[0]], y: [O.marker[1]], mode: 'markers',
        marker: {size: 11, color: 'white', line: {color: INK, width: 2}}, hoverinfo: 'text',
        text: '<b>' + O.marker[2] + '</b><br>Near Hibbing. Rain here can reach<br>all three seas.'});
    }
    return t;
  }

  function overlayNotes(L) {
    if (!L.overlay) return [];
    const O = L.overlay;
    const a = O.arrows.map(r => ({x: r[0], y: r[1], ax: r[2], ay: r[3], text: '<b>' + r[4] + '</b>', showarrow: true,
      arrowhead: 2, arrowsize: 1.4, arrowwidth: 2.5, arrowcolor: r[5], font: {size: 12, color: r[5]},
      bgcolor: 'rgba(255,255,255,0.85)', standoff: 2}));
    a.push({x: O.marker[0], y: O.marker[1], text: O.marker[2], showarrow: false, xanchor: 'left', xshift: 9,
            font: {size: 11, color: INK}, bgcolor: 'rgba(255,255,255,0.8)'});
    return a;
  }

  function drawMap() {
    const L = layer(), w = mapEl.clientWidth || 500;
    const lay = Object.assign(baseLayout(Math.min(540, Math.round(w * 1.1))), {
      xaxis: {visible: false, fixedrange: true},
      yaxis: {visible: false, fixedrange: true, scaleanchor: 'x', scaleratio: 1 / Math.cos(46.3 * Math.PI / 180)},
      annotations: overlayNotes(L)
    });
    Plotly.react(mapEl, mapTraces(L), lay, {displayModeBar: false, responsive: true});
  }

  function drawStrip() {
    const L = layer(), idx = [], xs = [], ys = [], cs = [], tt = [], sz = [], ln = [];
    D.geom.forEach((g, i) => {
      const v = L.values[i]; if (v === null) return;
      idx.push(i); xs.push(L.log ? Math.max(v, 1) : v);
      ys.push(((i * 37) % 11 - 5) / 10);          // fixed small spread so dots don't overlap
      cs.push(L.colors[i]); tt.push(L.tips[i]);
      sz.push(i === st.sel ? 16 : 11); ln.push(i === st.sel ? 2.5 : 0.8);
    });
    const lay = Object.assign(baseLayout(110), {
      margin: {l: 10, r: 10, t: 8, b: 30},
      xaxis: {type: L.log ? 'log' : 'linear', fixedrange: true, gridcolor: '#eceff2', zeroline: false},
      yaxis: {visible: false, fixedrange: true, range: [-1, 1]}
    });
    Plotly.react(stripEl, [{type: 'scatter', x: xs, y: ys, mode: 'markers', customdata: idx, text: tt, hoverinfo: 'text',
      marker: {size: sz, color: cs, line: {color: INK, width: ln}}}], lay, {displayModeBar: false, responsive: true});
  }

  function overview() {
    const L = layer();
    return '<h3>' + L.title + '</h3><p>' + L.body + '</p>' + L.top +
           (L.spikes ? '<p class="note">Spikes show the number of ' + L.spike_label + '.</p>' : '') +
           '<p class="note">' + esc(L.note) + '</p><p class="note"><b>Click any county</b> for its full profile.</p>';
  }

  function profile(i) {
    const P = D.profiles[i];
    let h = '<a href="#" id="ex-back" class="note">&larr; Back to the layer summary</a>' +
            '<h3>' + esc(P.name) + ' County</h3>' +
            (P.pop ? '<p class="note">' + P.pop.toLocaleString() + ' people (2025)</p>' : '');
    P.rows.forEach(r => {
      h += '<div class="pr-row"><div class="pr-top"><span>' + esc(r[0]) + '</span><b>' + esc(r[1]) + '</b></div>' +
           '<div class="pr-track"><div class="pr-fill" style="width:' + Math.max(r[2] * 100, 1) + '%"></div>' +
           '<div class="pr-state" style="left:' + (r[3] * 100) + '%" title="' + esc(r[4]) + '"></div></div>' +
           '<div class="pr-cap">' + esc(r[4]) + ' (line)</div></div>';
    });
    const S = P.systems;
    if (S.length) {
      const row = s => '<li><b>' + esc(s[0]) + '</b><br><span class="note">' + s[1].toLocaleString() + ' people &middot; ' + s[2] +
                       (s[3] ? ' &middot; <span class="hl">' + s[3] + ' health violation' + (s[3] > 1 ? 's' : '') + '</span>' : '') + '</span></li>';
      h += '<h4>' + S.length + ' community water system' + (S.length > 1 ? 's' : '') + '</h4><ul class="sys">' + S.slice(0, 6).map(row).join('') + '</ul>';
      if (S.length > 6) h += '<details><summary>Show all ' + S.length + '</summary><ul class="sys">' + S.slice(6).map(row).join('') + '</ul></details>';
    } else {
      h += '<p>No community water systems in the EPA data for this county.</p>';
    }
    return h;
  }

  function renderPanel() {
    const panel = document.getElementById('ex-panel');
    panel.innerHTML = st.sel === null ? overview() : profile(st.sel);
    const back = document.getElementById('ex-back');
    if (back) back.onclick = e => { e.preventDefault(); select(null); };
  }

  function renderKey() {
    const L = layer();
    const leg = document.getElementById('ex-legend'), grad = document.getElementById('ex-grad');
    if (L.legend) {
      leg.innerHTML = L.legend.map(l => '<span><i style="background:' + l[1] + '"></i>' + esc(l[0]) + '</span>').join('');
      leg.style.display = 'flex'; grad.style.display = 'none';
    } else {
      leg.style.display = 'none'; grad.style.display = 'block';
      document.getElementById('ex-bar').style.background = L.gradient;
      document.getElementById('ex-lo').textContent = L.lo;
      document.getElementById('ex-hi').textContent = L.hi;
    }
    document.getElementById('ex-strip-wrap').style.display = L.nostrip ? 'none' : 'block';
    document.getElementById('ex-spikes-wrap').style.visibility = L.spikes ? 'visible' : 'hidden';
    document.getElementById('ex-strip-title').textContent = 'Every county by ' + L.rank_label + '. Click a dot to open that county.';
  }

  function render() { renderKey(); drawMap(); drawStrip(); renderPanel();
    document.querySelectorAll('.ex-btn').forEach(b => b.setAttribute('aria-pressed', b.dataset.key === st.key)); }
  function select(i) { st.sel = i; render(); }

  const btns = document.getElementById('ex-buttons');
  D.layers.forEach(L => {
    const b = document.createElement('button');
    b.className = 'ex-btn'; b.dataset.key = L.key; b.textContent = L.label;
    b.onclick = () => { st.key = L.key; render(); };
    btns.appendChild(b);
  });
  document.getElementById('ex-spikes').onchange = e => { st.spikes = e.target.checked; drawMap(); };
  const list = document.getElementById('ex-county-list');
  D.geom.map(g => g.name).sort().forEach(n => { const o = document.createElement('option'); o.value = n; list.appendChild(o); });
  document.getElementById('ex-search').onchange = e => {
    const q = e.target.value.trim().toLowerCase().replace(/ county$/, '');
    const i = D.geom.findIndex(g => g.name.toLowerCase() === q);
    if (i >= 0) select(i);
  };

  render();
  mapEl.on('plotly_click', ev => {
    const p = ev.points[0];
    if (p.curveNumber < N) select(p.curveNumber);
    else if (p.customdata !== undefined) select(p.customdata);
  });
  stripEl.on('plotly_click', ev => select(ev.points[0].customdata));
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
  #drain-map {{ height:560px; border-radius:8px; overflow:hidden; }}
  .dm-label {{ font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; text-align:center;
               text-shadow:0 0 3px #fff, 0 0 3px #fff, 0 0 6px #fff; pointer-events:none; max-width:120px; line-height:1.2; }}
  .dm-arrow {{ font-size:13px; font-weight:700; background:rgba(255,255,255,.9); padding:2px 7px; border-radius:6px;
               pointer-events:none; white-space:nowrap; }}
  .dm-hill {{ font-size:12px; font-weight:600; color:var(--ink); cursor:pointer; white-space:nowrap;
              text-shadow:0 0 3px #fff, 0 0 3px #fff; display:flex; align-items:center; gap:5px; }}
  .dm-dot {{ width:10px; height:10px; border-radius:50%; background:#fff; border:2.5px solid var(--ink); display:inline-block; }}
  .dm-small {{ font-size:12px; color:var(--muted); }}
  .dm-tools {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:12px 0 0; }}
  @media (max-width: 720px) {{ #drain-map {{ height:460px; }} .dm-arrow {{ display:none; }} .dm-label {{ font-size:9.5px; max-width:80px; }} .dm-hill {{ font-size:10.5px; }} }}
  .ex-legend {{ display:none; flex-wrap:wrap; gap:6px 16px; font-size:13px; color:var(--ink); }}
  .ex-legend span {{ display:inline-flex; align-items:center; gap:6px; }}
  .ex-legend i {{ display:inline-block; width:18px; height:4px; border-radius:2px; }}
  .ex-controls {{ display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:8px; }}
  .ex-tools {{ display:flex; gap:12px; align-items:center; }}
  #ex-search {{ font:inherit; font-size:14px; padding:7px 12px; border:1px solid #cfd6dd; border-radius:8px; width:170px; }}
  .ex-check {{ font-size:14px; color:var(--muted); white-space:nowrap; }}
  .ex-panel h4 {{ margin:16px 0 6px; font-size:15px; }}
  .pr-row {{ margin:10px 0 12px; }}
  .pr-top {{ display:flex; justify-content:space-between; gap:8px; font-size:14px; }}
  .pr-track {{ position:relative; height:10px; background:#eceff2; border-radius:5px; margin-top:4px; }}
  .pr-fill {{ height:100%; background:#0b3566; border-radius:5px; }}
  .pr-state {{ position:absolute; top:-3px; width:2px; height:16px; background:{ORANGE}; }}
  .pr-cap {{ font-size:12px; color:var(--muted); margin-top:2px; }}
  ul.sys {{ list-style:none; padding:0; margin:0; }}
  ul.sys li {{ padding:6px 0; border-bottom:1px solid #eceff2; font-size:14px; line-height:1.35; }}
  details summary {{ cursor:pointer; color:var(--blue); font-size:14px; margin-top:6px; }}
  @media (max-width: 720px) {{ .ex-grid {{ grid-template-columns: 1fr; }} #ex-search {{ width:140px; }} }}
</style>
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
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
  <p>Pick a layer to recolor Minnesota's 87 counties. Color shows the rate; the dark spikes show how many,
     so a big county and a small one can be compared at a glance. Click any county for its full profile.</p>
  <div class="ex-controls">
    <div class="ex-buttons" id="ex-buttons"></div>
    <div class="ex-tools">
      <input id="ex-search" list="ex-county-list" placeholder="Find your county" aria-label="Find your county">
      <datalist id="ex-county-list"></datalist>
      <label class="ex-check" id="ex-spikes-wrap"><input type="checkbox" id="ex-spikes" checked> Spikes</label>
    </div>
  </div>
  <div class="ex-grid">
    <div class="chart" style="margin-top:8px">
      <div id="explorer-map"></div>
      <div class="ex-key"><div id="ex-grad"><div class="bar" id="ex-bar"></div>
        <div class="ends"><span id="ex-lo"></span><span id="ex-hi"></span></div></div>
        <div class="ex-legend" id="ex-legend"></div></div>
    </div>
    <div class="ex-panel" id="ex-panel"></div>
  </div>
  <div class="chart" id="ex-strip-wrap">
    <div class="note" id="ex-strip-title" style="margin:2px 8px 0"></div>
    <div id="explorer-strip"></div>
  </div>
  <script type="application/json" id="explorer-data">{explorer_json}</script>
  {EXPLORER_JS}
</section>

<section>
  <div class="num">02</div>
  <h2>Three seas, one state</h2>
  <p>Rain that falls in Minnesota ends up in one of three places: the <b>Gulf of Mexico</b> by the Mississippi,
     <b>Hudson Bay</b> by the Red and Rainy rivers, or the <b>Atlantic</b> by Lake Superior. The divides meet at the
     Hill of Three Waters near Hibbing. Almost nothing flows in from other states; it all flows out.</p>
  <p>By land area, about <b>{area_pct["gulf"]:.0f}%</b> of the state drains to the Gulf, <b>{area_pct["hudson"]:.0f}%</b>
     to Hudson Bay and <b>{area_pct["atlantic"]:.0f}%</b> to the Atlantic.</p>
  <p>Of the ~{surf_total/1e6:.1f} million people whose community system draws from a river or lake,
     <b>{surf_pct["gulf"]:.0f}%</b> are on water headed for the Gulf, {surf_pct["atlantic"]:.0f}% for the Atlantic
     and {surf_pct["hudson"]:.0f}% for Hudson Bay.</p>
  <div class="dm-tools">
    <button class="ex-btn" id="drain-3d" aria-pressed="false">Tilt in 3D</button>
    <button class="ex-btn" id="drain-reset">Reset view</button>
    <div class="ex-legend" style="display:flex">{"".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in drain_map["legend"])}</div>
  </div>
  <div class="chart"><div id="drain-map"></div></div>
  <p class="note">Zoom with the + and &minus; buttons, or pinch (two fingers on a phone, Ctrl or Cmd + scroll on a computer).
     Click a {"basin, " if has_basins else ""}river or lake to see where it drains. Shading shows the land's relief, exaggerated in 3D so
     Minnesota's gentle hills show up. Drinking water shares go by each system's home county, so they're approximate.</p>
  <script type="application/json" id="drain-data">{drain_json}</script>
  {DRAIN_JS}
</section>

<section>
  <div class="num">03</div>
  <h2>Every system, by size</h2>
  <p>Each dot is one water system. Orange means at least one health-based violation in the last five years.
     <span class="hl">{pct_small_viol:.0f}%</span> of systems under {SMALL} people had one, compared with
     {pct_big_viol:.0f}% of systems serving 10,000 or more. Diamonds are tribal systems, which EPA regulates directly.</p>
  <div class="chart">{div(c2, "dots")}</div>
  <p class="note">Dots are spread up and down within each row so they don't sit on top of each other; the vertical position means nothing.</p>
</section>

<section id="compare-section">
  <div class="num">04</div>
  <h2>Among small systems, tribal systems had about {ratio:.1f}x the violation rate</h2>
  <p>Because small systems have more violations everywhere, this compares only systems under {SMALL} people: <b>{t_hit} of {t_n}</b> tribal systems had a recorded
     health-based violation in the last five years, versus <b>{s_hit} of {s_n}</b> state-regulated ones.</p>
  <div class="chart">{div(c3, "compare")}</div>
  <p class="note">{t_n} systems is a small group, so one or two systems moves the rate a lot. A recorded violation also
     depends on testing and reporting, so this measures what's on the record, not water quality directly.</p>
</section>

<section>
  <div class="num">05</div>
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
  Data: EPA SDWIS via ECHO (SDWA public water systems, geographic areas, and violations/enforcement files); U.S. Census Bureau Vintage 2025 county population estimates; Minnesota Department of Health for the 1.2 million private well users figure; Water Quality Portal (USGS, EPA, and Minnesota agencies) for calcium and magnesium in well water, used to calculate hardness; Minnesota DNR for basins (Watershed Suite), lakes of 500+ acres (DNR Hydrography) and major rivers; Natural Earth for Lake Superior; AWS Terrain Tiles (USGS and other sources) for relief. Map built with MapLibre.
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
