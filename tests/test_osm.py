"""OSM: rule parser, symbol assignment and import into the map (no download)."""

from datetime import date

import pytest

from olprep.verarbeitung import osm
from olprep.verarbeitung.georef import Georeferencing
from olprep.ausgabe.omap import OmapDocument
from olprep.ressourcen import symbol_set_file

from conftest import needs_oom


@pytest.mark.parametrize("query, tags, expected", [
    ("building = yes", {"building": "yes"}, True),
    ("building = yes", {"building": "house"}, False),
    ('building ~= ""', {"building": "house"}, True),       # key present
    ('building ~= ""', {}, False),
    ("building != ruins", {}, True),                        # missing key counts as "not equal"
    ("highway = path AND surface = asphalt", {"highway": "path", "surface": "asphalt"}, True),
    ("highway = path AND surface = asphalt", {"highway": "path"}, False),
    ("natural = wood OR landuse = forest", {"landuse": "forest"}, True),
    ("(natural = wood OR landuse = forest) AND leaf_type = needleleaved",
     {"natural": "wood", "leaf_type": "needleleaved"}, True),
    ("(natural = wood OR landuse = forest) AND leaf_type = needleleaved",
     {"natural": "wood"}, False),
])
def test_query(query, tags, expected):
    assert osm.Query(query).matches(tags) is expected


def test_query_rejects_garbage():
    with pytest.raises((ValueError, IndexError)):
        osm.Query("building = yes )")


def test_last_matching_rule_wins():
    rules = [("521", osm.Query('building ~= ""')), ("526", osm.Query("building = ruins"))]
    assert osm.symbol_for({"building": "ruins"}, rules) == "526"
    assert osm.symbol_for({"building": "yes"}, rules) == "521"
    assert osm.symbol_for({"highway": "path"}, rules) is None


@needs_oom
def test_forest_rule_changed_to_white_forest():
    rules = osm.load_rules("ISOM 2017-2")
    assert osm.symbol_for({"natural": "wood"}, rules) == "405"
    assert osm.symbol_for({"landuse": "forest"}, rules) == "405"


def test_query_keys():
    rules = [("1", osm.Query("highway = path AND surface = asphalt")),
             ("2", osm.Query("(natural = wood OR landuse = forest)"))]
    assert osm.query_keys(rules) == ["highway", "natural"]


# A tiny Overpass "out geom" answer around the Ernst-Happel-Stadion
LON, LAT = 16.4205, 48.2072
D = 0.0005                      # about 37 m east-west, 55 m north-south
SQUARE = [{"lon": LON, "lat": LAT}, {"lon": LON + D, "lat": LAT}, {"lon": LON + D, "lat": LAT + D},
          {"lon": LON, "lat": LAT + D}, {"lon": LON, "lat": LAT}]
DATA = {"elements": [
    {"type": "way", "id": 1, "tags": {"building": "yes"}, "geometry": SQUARE},
    {"type": "way", "id": 2, "tags": {"highway": "footway"},
     "geometry": [{"lon": LON - D, "lat": LAT - D}, {"lon": LON + 2 * D, "lat": LAT - D}]},
    {"type": "way", "id": 3, "tags": {"barrier": "fence"}, "geometry": SQUARE},
    {"type": "node", "id": 4, "lon": LON, "lat": LAT, "tags": {"natural": "tree"}},
    {"type": "way", "id": 5, "tags": {"name": "ohne Regel"}, "geometry": SQUARE},
]}


def test_features_geometry_types():
    feats = {f.osm_id: f for f in osm.features(DATA, 31256)}
    assert feats["way/1"].geom.geom_type == "Polygon"       # closed building -> area
    assert feats["way/2"].geom.geom_type == "LineString"
    assert feats["way/3"].geom.geom_type == "LineString"    # closed fence stays a line
    assert feats["node/4"].geom.geom_type == "Point"
    assert feats["way/1"].geom.area == pytest.approx(37 * 56, rel=0.05)


@needs_oom
def test_add_to_map_counts_and_tags():
    g = Georeferencing.create(31256, 4000, 6601.4, 340984.2, on=date(2026, 11, 1))
    doc = OmapDocument(symbol_set_file("ISSprOM 2019", 4000))
    doc.set_georeferencing(g)
    rules = osm.load_rules("ISSprOM 2019")
    e, n = 6601.4, 340984.2
    counts = osm.add_to_map(doc, g, DATA, 31256, (e - 500, n - 500, e + 500, n + 500), rules)
    codes = {k.split()[0] for k in counts}
    assert osm.symbol_for({"building": "yes"}, rules) in codes
    assert sum(counts.values()) == len(doc.objects)
    assert all(obj.find(f"{{{doc.root.nsmap[None]}}}tags") is not None for obj in doc.objects)
