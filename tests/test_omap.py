"""Writing .omap files: objects, georeferencing, templates, notes."""

from datetime import date

from lxml import etree

from olprep.verarbeitung.georef import Georeferencing
from olprep.ausgabe.omap import NS, OmapDocument
from olprep.ressourcen import symbol_set_file

from conftest import needs_oom

pytestmark = needs_oom
Q = {"m": NS}


def make_doc(tmp_path):
    g = Georeferencing.create(31256, 4000, 6601.4, 340984.2, on=date(2026, 11, 1))
    doc = OmapDocument(symbol_set_file("ISSprOM 2019", 4000))
    doc.set_georeferencing(g)
    return doc, g


def test_symbol_set_loaded_without_sample_objects(tmp_path):
    doc, _ = make_doc(tmp_path)
    assert len(doc.objects) == 0
    assert "101" in doc.symbol_ids and "102" in doc.symbol_ids
    assert doc.symbol_types["101"] == 2                 # contour: line symbol


def test_write_and_read_back(tmp_path):
    doc, g = make_doc(tmp_path)
    doc.add_point("418", (0, 0), tags={"osm_id": "node/1"})
    doc.add_line("101", [(0, 0), (1000, 0), (1000, 1000)])
    doc.add_area("401", [(0, 0), (2000, 0), (2000, 2000)])
    doc.add_rings("521", [[(0, 0), (5000, 0), (5000, 5000), (0, 5000)],
                          [(1000, 1000), (2000, 1000), (2000, 2000)]])
    image = tmp_path / "daten" / "orthofoto.jpg"
    doc.add_georeferenced_image(image, tmp_path)
    doc.add_georeferenced_image(tmp_path / "daten" / "schummerung.jpg", tmp_path, visible=False)
    doc.set_notes("Quellen: Test")
    out = tmp_path / "test.omap"
    doc.save(out)

    root = etree.parse(str(out)).getroot()
    objects = root.find(".//m:part/m:objects", Q)
    assert objects.get("count") == "4"
    point, line, area, rings = objects.findall("m:object", Q)
    assert point.get("type") == "0" and point.find("m:tags/m:t", Q).text == "node/1"
    assert line.find("m:coords", Q).text == "0 0;1000 0;1000 1000;"
    # closed path: first point repeated with CLOSE_POINT|HOLE_POINT (2|16 = 18)
    assert area.find("m:coords", Q).text == "0 0;2000 0;2000 2000;0 0 18;"
    assert rings.find("m:coords", Q).get("count") == "9"

    geo = root.find("m:georeferencing", Q)
    assert geo.get("scale") == "4000"
    assert geo.get("declination") == "5.39" and geo.get("grivation") == "5.33"
    assert geo.find("m:projected_crs/m:parameter", Q).text == "31256"

    templates = root.findall(".//m:templates/m:template", Q)
    assert [t.get("relpath") for t in templates] == ["daten/orthofoto.jpg", "daten/schummerung.jpg"]
    refs = root.findall(".//m:view/m:map_view/m:templates/m:ref", Q)
    assert [r.get("visible") for r in refs] == ["true", "false"]
    assert root.find("m:notes", Q).text == "Quellen: Test"
