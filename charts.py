"""Make README charts from the CSVs in output/. Run after build.py."""
import csv
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

# Same colors as the story page
BLUE, GRAY, ORANGE = "#1c5a99", "#b8bcc2", "#d9622b"
RAMP = LinearSegmentedColormap.from_list("wells", ["#eef4fb", "#c6dbef", "#85b4dc", "#3f83c4", "#1c5a99", "#0b3566"])
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 11,
                     "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED})
Path("images").mkdir(exist_ok=True)

rows = list(csv.DictReader(open("output/mn_system_violations.csv")))
for r in rows:
    r["pop"] = int(r["population_served"] or 0)
    r["tribal"] = r["is_tribal_epa_regulated"] == "true"
    r["viol"] = int(r["health_violations_5yr"] or 0) > 0

def style(ax):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)

# Chart 1: share of systems vs. share of people, by source
wells = [r for r in rows if r["source_type"] == "Groundwater (wells)"]
total_sys, total_pop = len(rows), sum(r["pop"] for r in rows)
sys_share = 100 * len(wells) / total_sys
pop_share = 100 * sum(r["pop"] for r in wells) / total_pop

fig, ax = plt.subplots(figsize=(8, 3.2), dpi=200)
labels = ["Share of water systems", "Share of people served"]
vals = [sys_share, pop_share]
ax.barh(labels, vals, color=BLUE, height=0.55)
ax.barh(labels, [100 - v for v in vals], left=vals, color=GRAY, height=0.55)
for i, v in enumerate(vals):
    ax.text(2, i, f"{v:.0f}% wells", va="center", ha="left", color="white", fontweight="bold")
    ax.text(102, i, f"{100 - v:.0f}% rivers\nand lakes", va="center", ha="left", color=INK, fontsize=10)
ax.set_xlim(0, 125); ax.invert_yaxis(); ax.set_xticks([])
for side in ("top", "right", "left", "bottom"):
    ax.spines[side].set_visible(False)
ax.tick_params(length=0)
fig.text(0.01, 0.93, "Most Minnesota water systems use wells,\nbut rivers and lakes serve a third of people",
         color=INK, fontsize=12, fontweight="bold", va="top")
fig.text(0.01, 0.02, "Active community water systems. Rivers and lakes includes 3 mixed-source systems. Source: EPA SDWIS.", color=MUTED, fontsize=9)
fig.tight_layout(rect=(0, 0.06, 1, 0.78))
fig.savefig("images/wells_vs_people.png", facecolor="white")
plt.close(fig)

# Chart 2: violation rate, small systems only (under 500 people), tribal vs. state-regulated
small = [r for r in rows if r["pop"] < 500]
groups = [("State-regulated", False, GRAY), ("Tribal (EPA-regulated)", True, ORANGE)]
fig, ax = plt.subplots(figsize=(8, 3.2), dpi=200)
rates = {}
for i, (name, flag, color) in enumerate(groups):
    g = [r for r in small if r["tribal"] == flag]
    pct = 100 * sum(r["viol"] for r in g) / len(g)
    rates[flag] = pct
    ax.barh(i, pct, color=color, height=0.55)
    ax.text(pct + 0.6, i, f"{pct:.1f}%  ({sum(r['viol'] for r in g)} of {len(g)} systems)",
            va="center", color=INK)
ax.set_yticks([0, 1], [g[0] for g in groups])
ax.invert_yaxis(); ax.set_xlim(0, max(rates.values()) * 1.6)
ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
style(ax)
ratio = rates[True] / rates[False]
fig.text(0.01, 0.93, f"Among small systems, tribal water systems had about {ratio:.1f}x\nthe rate of recorded health-based violations",
         color=INK, fontsize=12, fontweight="bold", va="top")
fig.text(0.01, 0.02, "Systems serving under 500 people with a health-based violation, last 5 years. "
         "Source: EPA SDWIS.", color=MUTED, fontsize=9)
fig.tight_layout(rect=(0, 0.06, 1, 0.78))
fig.savefig("images/small_system_violations.png", facecolor="white")
plt.close(fig)
# Chart 3: county map, share of people on well systems
geo = json.loads(Path("data/geo/mn_counties.geojson").read_text())
by_county = {}
for r in rows:
    if not r["county"] or not r["pwsid"].startswith(("MN", "05")):
        continue
    c = by_county.setdefault(r["county"], [0, 0])
    c[1] += r["pop"]
    if r["source_type"] == "Groundwater (wells)":
        c[0] += r["pop"]
fig, ax = plt.subplots(figsize=(6.4, 6.4), dpi=200)
patches, colors = [], []
for f in geo["features"]:
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    c = by_county.get(f["properties"]["NAME"])
    color = RAMP(c[0] / c[1]) if c and c[1] else "#e4e7eb"
    for poly in polys:
        patches.append(Polygon(poly[0], closed=True)); colors.append(color)
ax.add_collection(PatchCollection(patches, facecolor=colors, edgecolor="white", linewidth=0.6))
ax.autoscale_view(); ax.set_aspect(1 / 0.69); ax.axis("off")
sm = plt.cm.ScalarMappable(cmap=RAMP, norm=plt.Normalize(0, 100))
cb = fig.colorbar(sm, ax=ax, shrink=0.45, pad=0.02, format="%.0f%%")
cb.outline.set_visible(False); cb.ax.tick_params(length=0, labelsize=9, colors=MUTED)
fig.text(0.02, 0.97, "Share of people on well systems, by county", color=INK, fontsize=12, fontweight="bold", va="top")
fig.text(0.02, 0.02, "Community water systems only (not private wells). Gray: no community system. Source: EPA SDWIS.",
         color=MUTED, fontsize=8)
fig.savefig("images/county_map.png", facecolor="white", bbox_inches="tight")
plt.close(fig)
print("Wrote images/wells_vs_people.png, images/small_system_violations.png, images/county_map.png")
