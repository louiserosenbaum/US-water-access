"""Clip Natural Earth rivers and lakes to Minnesota and tag each with where its water ends up.

Natural Earth (public domain, naturalearthdata.com) is downloaded from its GitHub mirror.
Output: data/geo/mn_rivers.json, used by story.py for the "Where it drains" layer.
Run once; the output is committed so the story page builds without a download.
"""
import json
import urllib.request
from pathlib import Path

from shapely.geometry import box, shape
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

out["skipped"] = sorted(set(out["skipped"]))
Path("data/geo/mn_rivers.json").write_text(json.dumps(out))
print(f"{len(out['rivers'])} river pieces, {len(out['lakes'])} lakes; not tagged: {out['skipped']}")
