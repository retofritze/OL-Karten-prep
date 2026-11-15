"""OpenStreetMap objects assigned to orienteering symbols and written into the map.

Data comes from quellen.osm. The assignment uses the cross-reference tables
(.crt) shipped with OOM, the same rules OOM applies when importing OSM data:
one rule per line, "<symbol code>  <query>", e.g.
    521    building ~= "" AND building != ruins
If several rules match, the last one wins (the files list general rules first,
special cases after). Objects matching no rule are dropped.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass

import pyproj
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polygonize, unary_union

from ..ressourcen import crt_file

# Closed ways with these keys are areas (unless area=no); everything else is a line
AREA_KEYS = {"building", "landuse", "natural", "leisure", "amenity", "waterway", "man_made", "tourism"}
LINEAR_VALUES = {("natural", "cliff"), ("natural", "tree_row"), ("natural", "ridge"),
                 ("waterway", "stream"), ("waterway", "ditch"), ("waterway", "drain"),
                 ("waterway", "river"), ("man_made", "cutline"), ("man_made", "pipeline")}


# --- rules -----------------------------------------------------------------

_TOKEN = re.compile(r'"[^"]*"|\(|\)|!=|~=|=|[^\s()=!~"]+')


class Query:
    """Parsed query of a .crt rule: key = v, key != v, key ~= v, AND, OR, ( )."""

    def __init__(self, text: str):
        self.tokens = [t[1:-1] if t.startswith('"') else t for t in _TOKEN.findall(text)]
        self.pos = 0
        self.tree = self._or()
        if self.pos != len(self.tokens):
            raise ValueError(f"Regel nicht verstanden: {text}")

    def _next(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _or(self):
        left = self._and()
        while self._peek() == "OR":
            self._next()
            left = ("OR", left, self._and())
        return left

    def _and(self):
        left = self._term()
        while self._peek() == "AND":
            self._next()
            left = ("AND", left, self._term())
        return left

    def _term(self):
        if self._peek() == "(":
            self._next()
            inner = self._or()
            self._next()            # ")"
            return inner
        key, op, value = self._next(), self._next(), self._next()
        return (op, key, value)

    def matches(self, tags: dict[str, str], node=None) -> bool:
        op, a, b = node or self.tree
        if op == "AND":
            return self.matches(tags, a) and self.matches(tags, b)
        if op == "OR":
            return self.matches(tags, a) or self.matches(tags, b)
        if op == "=":
            return tags.get(a) == b
        if op == "!=":
            return tags.get(a) != b         # also true if the key is missing
        if op == "~=":
            return a in tags and b in tags[a]
        raise ValueError(op)


# Our changes to the OOM tables: (query text, OOM code) -> our code.
# Plain forest is white "405 Forest" (good runnability) instead of light green
# "406 Vegetation: slow running"; OSM rarely says how runnable a forest is.
# Explicit wood:density / wood:age rules further down still apply.
RULE_CHANGES = {
    ("natural = wood", "406"): "405",
    ("landuse = forest", "406"): "405",
}


def load_rules(symbol_set: str) -> list[tuple[str, Query]]:
    rules = []
    for line in crt_file(symbol_set).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            code, query = line.split(maxsplit=1)
            code = RULE_CHANGES.get((query, code), code)
            rules.append((code, Query(query)))
    return rules


def symbol_for(tags: dict[str, str], rules: list[tuple[str, Query]]) -> str | None:
    code = None
    for c, q in rules:
        if q.matches(tags):
            code = c                        # last match wins
    return code


# --- what to download ------------------------------------------------------

def query_keys(rules) -> list[str]:
    """Main OSM key of each rule (its first key, e.g. 'highway'); secondary keys such as
    'surface' only refine a rule and are not needed to select what to download."""
    return sorted({next(t for t in q.tokens if t != "(") for _, q in rules})


# --- geometry --------------------------------------------------------------

@dataclass
class Feature:
    geom: object            # shapely geometry in the map CRS
    tags: dict[str, str]
    osm_id: str


def _is_area(tags: dict[str, str]) -> bool:
    if tags.get("area") == "yes":
        return True
    if tags.get("area") == "no":
        return False
    return any(k in AREA_KEYS and (k, v) not in LINEAR_VALUES for k, v in tags.items())


def features(data: dict, epsg: int) -> list[Feature]:
    t = pyproj.Transformer.from_crs(4326, epsg, always_xy=True)

    def xy(pts):
        return list(zip(*t.transform([p["lon"] for p in pts], [p["lat"] for p in pts])))

    out = []
    for el in data["elements"]:
        tags = el.get("tags", {})
        oid = f"{el['type']}/{el['id']}"
        if el["type"] == "node":
            out.append(Feature(Point(t.transform(el["lon"], el["lat"])), tags, oid))
        elif el["type"] == "way" and len(el.get("geometry", [])) >= 2:
            pts = xy(el["geometry"])
            closed = len(pts) >= 4 and pts[0] == pts[-1]
            geom = Polygon(pts) if closed and _is_area(tags) else LineString(pts)
            out.append(Feature(geom.buffer(0) if isinstance(geom, Polygon) else geom, tags, oid))
        elif el["type"] == "relation":
            rings = {"outer": [], "inner": []}
            for m in el.get("members", []):
                if m["type"] == "way" and len(m.get("geometry") or []) >= 2:
                    rings["inner" if m.get("role") == "inner" else "outer"].append(LineString(xy(m["geometry"])))
            # GEOS emits a harmless "invalid value encountered in polygonize" for some large
            # multipolygons (e.g. relation/279039, 55 members); the result is complete
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", "invalid value encountered in polygonize")
                outer = unary_union(list(polygonize(rings["outer"])))
                inner = unary_union(list(polygonize(rings["inner"])))
            geom = outer.difference(inner) if not inner.is_empty else outer
            if not geom.is_empty:
                out.append(Feature(geom, tags, oid))
    return out


# --- into the map ------------------------------------------------------------

def add_to_map(doc, g, data: dict, epsg: int, bounds: tuple[float, float, float, float],
               rules) -> dict[str, int]:
    """Assign symbols, clip to bounds and write objects. Returns counts per symbol name."""
    clip = box(*bounds)
    counts: dict[str, int] = {}
    min_area = (0.3 * g.scale / 1000) ** 2         # areas below 0.3 x 0.3 mm on paper are dropped
    for f in features(data, epsg):
        code = symbol_for(f.tags, rules)
        if code is None or code not in doc.symbol_types:
            continue
        geom = f.geom.intersection(clip)
        if geom.is_empty:
            continue
        stype = doc.symbol_types[code]
        tags = {**f.tags, "osm_id": f.osm_id}
        written = False
        if stype == 1:                                      # point symbol
            p = geom if isinstance(geom, Point) else geom.representative_point()
            doc.add_point(code, g.to_paper(p.x, p.y), tags)
            written = True
        else:
            polys = [p for p in getattr(geom, "geoms", [geom]) if isinstance(p, Polygon)]
            lines = [p for p in getattr(geom, "geoms", [geom]) if isinstance(p, LineString)]
            if polys and stype in (4, 16):                  # area (or combined) symbol
                for p in polys:
                    if p.area < min_area:
                        continue
                    rings = [_paper(g, p.exterior.coords)] + [_paper(g, r.coords) for r in p.interiors]
                    doc.add_rings(code, [r for r in rings if len(r) >= 3], True, tags)
                    written = True
            elif polys and stype == 2:                      # area outline drawn as line (fence, hedge)
                for p in polys:
                    for r in [p.exterior, *p.interiors]:
                        doc.add_line(code, _paper(g, r.coords), closed=True, tags=tags)
                        written = True
            if lines and stype in (2, 16):
                for ln in lines:
                    pts = _paper(g, ln.coords)
                    if len(pts) >= 2:
                        doc.add_line(code, pts, tags=tags)
                        written = True
        if written:
            name = doc.symbol_names.get(code, code)
            counts[f"{code} {name}"] = counts.get(f"{code} {name}", 0) + 1
    return counts


def _paper(g, coords) -> list[tuple[int, int]]:
    """Map CRS -> paper, dropping duplicate points and the closing repeat of a ring."""
    pts = []
    for x, y in coords:
        p = g.to_paper(x, y)
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts
