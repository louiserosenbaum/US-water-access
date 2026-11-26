"""Clip Natural Earth rivers and lakes to Minnesota and tag each with where its water ends up.

Natural Earth (public domain, naturalearthdata.com) is downloaded from its GitHub mirror.
Also builds the zoomable drainage map's shapes: a mask that dims everything outside Minnesota, and
(if data/geo/mn_basins.geojson is there) the Minnesota DNR basins, each tagged with its sea and its counties.
Basins come from the MN DNR Watershed Suite map service (Level 02, HUC 04):
https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_dnr/geos_dnr_watersheds/MapServer/7

Output: data/geo/mn_rivers.json, used by story.py. Run once; the output is committed so the story
page builds without a download or shapely.
"""
import json
import urllib.request
from pathlib import Path

from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
FILES = {"rivers_big": "ne_10m_rivers_lake_centerlines.geojson",
         "rivers_na": "ne_10m_rivers_north_america.geojson",
         "lakes": "ne_10m_lakes.geojson",
         "lakes_na": "ne_10m_lakes_north_america.geojson"}

# Which ocean each river or lake drains to. Minnesota sits on three continental divides.
HUDSON = {"Red", "Rainy", "Red Lake", "Otter Tail", "Pembina", "Roseau", "Little Fork", "Vermilion", "Sturgeon",
          "Pelican", "Lake of the Woods", "Rainy Lake", "Upper Red Lake", "Lower Red Lake", "Lake Traverse",
          "Vermilion Lake", "Lac la Croix", "Basswood Lake", "Otter Tail Lake", "Pelican Lake"}  # the Pelican Lake near Orr; see below
ATLANTIC = {"Saint Louis", "Pigeon", "Arrow", "Lake Superior", "Arrow Lake", "Northern Light Lake"}
GULF = {"Mississippi", "Minnesota", "St. Croix", "Des Moines", "E.  Fk.  Des Moines", "Cedar", "Crow", "North Fork Crow",
        "Zumbro", "Middle Fork Zumbro", "Chippewa", "Big Sioux", "Little Sioux", "Gull", "Whitefish", "Lac des Mille Lacs",
        "Mille Lacs Lake", "Leech Lake", "Lake Winnibigoshish", "Cass Lake", "Gull Lake", "Pokegama Lake",
        "Big Sandy Lake", "North Long Lake", "Lower Whitefish Lake", "Whitefish Lake", "Lake Chippewa"}


def basin(name):
    for key, names in (("hudson", HUDSON), ("atlantic", ATLANTIC), ("gulf", GULF)):
        if name in names:
            return key
    return None


def load(fname):
    cache = Path("/tmp") / fname
    if not cache.exists():
        urllib.request.urlretrieve(NE + fname, cache)
    return json.loads(cache.read_text())["features"]


counties = json.loads(Path("data/geo/mn_counties.geojson").read_text())["features"]
mn = unary_union([shape(f["geometry"]) for f in counties]).buffer(0.01)

VIEW = box(-97.3, 43.45, -89.6, 49.4)
out = {"rivers": [], "lakes": [], "skipped": []}
for key in ("rivers_big", "rivers_na"):
    for f in load(FILES[key]):
        name, g = f["properties"].get("name"), f["geometry"]
        if not g or not name:
            continue
        clipped = shape(g).intersection(mn)
        if clipped.is_empty:
            continue
        b = basin(name)
        if b is None:
            out["skipped"].append(name)
            continue
        rank = f["properties"].get("scalerank") or 12
        lines = [clipped] if clipped.geom_type == "LineString" else [x for x in getattr(clipped, "geoms", []) if x.geom_type == "LineString"]
        for ln in lines:
            # Natural Earth reuses "Saint Louis" for a few unrelated streams in central Minnesota; keep the real one
            if name == "Saint Louis" and ln.bounds[0] < -93:
                continue
            ln = ln.simplify(0.005)
            out["rivers"].append({"name": name, "basin": b, "rank": rank,
                                  "x": [round(p[0], 3) for p in ln.coords], "y": [round(p[1], 3) for p in ln.coords]})
for key in ("lakes", "lakes_na"):
    for f in load(FILES[key]):
        name, g = f["properties"].get("name"), f["geometry"]
        if not g or not name:
            continue
        s = shape(g)
        if not (s.intersects(mn.buffer(-0.01)) or name == "Lake Superior"):
            continue
        s = s.intersection(VIEW)   # Lake Superior and border lakes run well past Minnesota
        if s.is_empty:
            continue
        b = basin(name)
        if name == "Pelican Lake" and s.centroid.y < 47:   # the Brainerd-area Pelican Lake drains to the Mississippi
            b = "gulf"
        if b is None:
            out["skipped"].append(name)
            continue
        polys = [s] if s.geom_type == "Polygon" else [x for x in s.geoms if x.geom_type == "Polygon"]
        for p in polys:
            p = p.simplify(0.01)
            if p.is_empty:
                continue
            out["lakes"].append({"name": name, "basin": b,
                                 "x": [round(c[0], 3) for c in p.exterior.coords], "y": [round(c[1], 3) for c in p.exterior.coords]})

# Mask: a big box with Minnesota cut out, drawn semi-opaque so the state stands out
mn_plain = unary_union([shape(f["geometry"]) for f in counties]).simplify(0.003)
mask = box(-104, 40, -82, 52).difference(mn_plain)
out["mask"] = mapping(mask)
out["bounds"] = [round(v, 3) for v in mn_plain.bounds]

# Basins (HUC 04) from MN DNR, tagged with the sea they drain to
# Plain names for the Minnesota part of each USGS subregion (official name kept as "official")
FRIENDLY = {"1017": "Missouri: Big Sioux", "1023": "Missouri: Little Sioux", "0710": "Des Moines River",
            "0702": "Minnesota River", "0708": "Cedar River", "0704": "Southeast: Zumbro, Root and Cannon",
            "0706": "Upper Iowa River", "0703": "St. Croix River", "0701": "Mississippi Headwaters",
            "0902": "Red River", "0903": "Rainy River", "0401": "Lake Superior"}
SEA = {"04": "atlantic", "07": "gulf", "10": "gulf", "09": "hudson"}
bpath = Path("data/geo/mn_basins.geojson")
out["basins"] = []
if bpath.exists():
    cents = {f["properties"]["NAME"]: shape(f["geometry"]).representative_point() for f in counties}
    for f in json.loads(bpath.read_text())["features"]:
        pr = {k.lower(): v for k, v in f["properties"].items()}
        g = shape(f["geometry"]).buffer(0).simplify(0.004)
        inside = g.intersection(mn_plain)
        if inside.is_empty:
            continue
        name = FRIENDLY.get(pr["huc_4"], pr["huc_4_name"].title())
        rp = inside.representative_point()
        out["basins"].append({
            "huc4": pr["huc_4"], "name": name, "official": pr["huc_4_name"].title(), "sea": SEA[pr["huc_2"]],
            "pct_state": round(100 * inside.area / mn_plain.area, 1),
            "counties": sorted(n for n, c in cents.items() if g.contains(c)),
            "label": [round(rp.x, 3), round(rp.y, 3)],
            "geometry": mapping(g),
        })
    print(f"{len(out['basins'])} basins:", [(b["name"], b["sea"], b["pct_state"]) for b in out["basins"]])

out["skipped"] = sorted(set(out["skipped"]))
Path("data/geo/mn_rivers.json").write_text(json.dumps(out))
print(f"{len(out['rivers'])} river pieces, {len(out['lakes'])} lakes; not tagged: {out['skipped']}")
