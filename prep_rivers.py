"""Build the shapes for the zoomable "Three seas, one state" map and tag each with the sea it drains to.

Inputs (all Minnesota DNR, saved from the DNR's public map services as GeoJSON, in data/geo/):
  mn_basins.geojson      Watershed Suite, Level 02 / HUC 04 basins
    .../us_mn_state_dnr/geos_dnr_watersheds/MapServer/7
  mn_dnr_lakes.geojson   DNR Hydrography, lakes and ponds of 500+ acres
    .../us_mn_state_dnr/water_dnr_hydrography/MapServer/1  (where acres >= 500 AND wb_class = 'Lake or Pond')
  mn_dnr_rivers.geojson  Major river centerlines (55 rivers)
    .../us_mn_state_dnr/water_major_river_centerlines/MapServer/0
  (base URL: https://enterprise.gisdata.mn.gov/aghost/rest/services)

Output: data/geo/mn_rivers.json, used by story.py. Run once with shapely installed; the output is
committed so the story page builds without shapely.
"""
import json
from collections import defaultdict
from pathlib import Path

from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

GEO = Path("data/geo")
VIEW = box(-97.6, 43.3, -89.4, 49.45)   # Lake Superior and border lakes run well past Minnesota

# USGS region -> the sea it drains to
SEA = {"04": "atlantic", "07": "gulf", "10": "gulf", "09": "hudson"}
# Plain names for the Minnesota part of each USGS subregion (official name kept as "official")
FRIENDLY = {"1017": "Missouri: Big Sioux", "1023": "Missouri: Little Sioux", "0710": "Des Moines River",
            "0702": "Minnesota River", "0708": "Cedar River", "0704": "Southeast: Zumbro, Root and Cannon",
            "0706": "Upper Iowa River", "0703": "St. Croix River", "0701": "Mississippi Headwaters",
            "0902": "Red River", "0903": "Rainy River", "0401": "Lake Superior"}


def rnd(geom, nd=3):
    """GeoJSON mapping with coordinates rounded (3 decimals is about 100 m), to keep the page small."""
    def r(c):
        return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    m = mapping(geom)
    return {"type": m["type"], "coordinates": r(m["coordinates"])}


LAKE_FIRST = {"Superior", "Minnetonka", "Vermilion", "Winnibigoshish", "Minnewaska", "Bemidji", "Pepin", "Traverse",
              "Kabetogama", "Of the Woods"}


def drop_islands(g, min_area=0.0004):
    """Fill in small islands (holes) so big island-filled lakes like Rainy don't bloat the page."""
    from shapely.geometry import MultiPolygon, Polygon
    fix = lambda p: Polygon(p.exterior, [r for r in p.interiors if Polygon(r).area > min_area])
    if g.geom_type == "Polygon":
        return fix(g)
    if g.geom_type == "MultiPolygon":
        return MultiPolygon([fix(p) for p in g.geoms])
    return g


def load(name):
    return json.loads((GEO / name).read_text())["features"]


counties = load("mn_counties.geojson")
mn = unary_union([shape(f["geometry"]) for f in counties]).simplify(0.003)
out = {"bounds": [round(v, 3) for v in mn.bounds],
       "mask": rnd(box(-104, 40, -82, 52).difference(mn))}   # dims everything outside Minnesota

# Basins
basins = []
cents = {f["properties"]["NAME"]: shape(f["geometry"]).representative_point() for f in counties}
for f in load("mn_basins.geojson"):
    pr = {k.lower(): v for k, v in f["properties"].items()}
    g = shape(f["geometry"]).buffer(0)
    inside = g.intersection(mn)
    if inside.is_empty:
        continue
    rp = inside.representative_point()
    basins.append({"huc4": pr["huc_4"], "name": FRIENDLY.get(pr["huc_4"], pr["huc_4_name"].title()),
                   "official": pr["huc_4_name"].title(), "sea": SEA[pr["huc_2"]], "shape": g,
                   "pct_state": round(100 * inside.area / mn.area, 1),
                   "counties": sorted(n for n, c in cents.items() if g.contains(c)),
                   "label": [round(rp.x, 3), round(rp.y, 3)]})


def sea_of_point(pt):
    for b in basins:
        if b["shape"].contains(pt):
            return b["sea"]
    return min(basins, key=lambda b: b["shape"].distance(pt))["sea"]   # outside Minnesota: nearest basin


# Rivers: the sea that most of the river's length falls in
out["rivers"] = []
for f in load("mn_dnr_rivers.geojson"):
    g = shape(f["geometry"])
    by_sea = defaultdict(float)
    for b in basins:
        by_sea[b["sea"]] += g.intersection(b["shape"]).length
    sea = max(by_sea, key=by_sea.get) if any(by_sea.values()) else sea_of_point(g.representative_point())
    g = g.simplify(0.002)
    lines = [g] if g.geom_type == "LineString" else list(g.geoms)
    miles = f["properties"].get("length_mi") or 0
    out["rivers"].append({"name": f["properties"]["kittle_name"], "basin": sea, "miles": round(miles),
                          "w": 3.2 if miles > 400 else 2.3 if miles > 150 else 1.6,
                          "coords": [[[round(x, 3), round(y, 3)] for x, y in ln.coords] for ln in lines]})

# Lakes: biggest first, skipping sub-basins that sit inside a lake already kept (e.g. "Red (Lower Red)" inside "Red")
kept = []
out["lakes"] = []
for f in sorted(load("mn_dnr_lakes.geojson"), key=lambda f: -(f["properties"]["acres"] or 0)):
    g = shape(f["geometry"]).buffer(0)
    if any(g.intersection(k).area > 0.8 * g.area for k in kept):
        continue
    kept.append(g)
    raw = (f["properties"]["pw_basin_name"] or "").strip()
    if raw.startswith("Superior"):
        continue   # DNR splits Lake Superior along state lines; the whole lake comes from Natural Earth below
    base, _, rest = raw.partition(" (")
    if not base:
        name = "Unnamed lake"
    elif base.startswith(("Lake ", "Lac ")):
        name = raw
    elif base in LAKE_FIRST:
        name = f"Lake {base}" + (f" ({rest}" if rest else "")
    else:
        name = f"{base} Lake" + (f" ({rest}" if rest else "")
    sea = sea_of_point(g.representative_point())
    clipped = drop_islands(g.intersection(VIEW)).simplify(0.004 if g.area > 0.01 else 0.002)
    if clipped.is_empty:
        continue
    out["lakes"].append({"name": name, "basin": sea, "acres": round(f["properties"]["acres"]),
                         "geometry": rnd(clipped)})

# Lake Superior as one shape, from Natural Earth (public domain), clipped to the map view
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_lakes.geojson"
cache = Path("/tmp/ne_10m_lakes.geojson")
if not cache.exists():
    import urllib.request
    urllib.request.urlretrieve(NE, cache)
sup = next(shape(f["geometry"]) for f in json.loads(cache.read_text())["features"]
           if f["properties"].get("name") == "Lake Superior")
out["lakes"].insert(0, {"name": "Lake Superior", "basin": "atlantic", "acres": 20_300_000,
                        "geometry": rnd(sup.intersection(VIEW).simplify(0.004))})

out["basins"] = [{k: (rnd(v.simplify(0.004)) if k == "shape" else v) for k, v in b.items()} for b in basins]
for b in out["basins"]:
    b["geometry"] = b.pop("shape")

(GEO / "mn_rivers.json").write_text(json.dumps(out, separators=(",", ":")))
print(f"{len(out['basins'])} basins, {len(out['rivers'])} rivers, {len(out['lakes'])} lakes")
for sea in ("gulf", "hudson", "atlantic"):
    print(sea, sum(b["pct_state"] for b in out["basins"] if b["sea"] == sea), "% of state;",
          sum(1 for r in out["rivers"] if r["basin"] == sea), "rivers;",
          sum(1 for k in out["lakes"] if k["basin"] == sea), "lakes")
