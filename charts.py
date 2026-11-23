"""Make README charts from the CSVs in output/. Run after build.py."""
import csv
from pathlib import Path
import matplotlib.pyplot as plt

BLUE, GRAY = "#2a78d6", "#a8a7a1"
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
ax.barh(labels, vals, color=BLUE, height=0.5)
ax.barh(labels, [100 - v for v in vals], left=vals, color=GRAY, height=0.5)
for i, v in enumerate(vals):
    ax.text(v - 2, i, f"{v:.0f}% wells", va="center", ha="right", color="white", fontweight="bold")
    ax.text(v + 2, i, f"{100 - v:.0f}% rivers and lakes", va="center", ha="left", color=INK)
ax.set_xlim(0, 100); ax.invert_yaxis(); ax.set_xticks([])
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
groups = [("State-regulated", False, GRAY), ("Tribal (EPA-regulated)", True, BLUE)]
fig, ax = plt.subplots(figsize=(8, 3.2), dpi=200)
rates = {}
for i, (name, flag, color) in enumerate(groups):
    g = [r for r in small if r["tribal"] == flag]
    pct = 100 * sum(r["viol"] for r in g) / len(g)
    rates[flag] = pct
    ax.barh(i, pct, color=color, height=0.5)
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
print("Wrote images/wells_vs_people.png and images/small_system_violations.png")
