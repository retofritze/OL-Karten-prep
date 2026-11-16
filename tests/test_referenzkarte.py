"""Reference map: build the "stadion" map and compare it with tests/referenz/stadion.json.

Safety net for refactoring: the result must stay the same. Needs internet (about a minute):
    pytest -m netz
Write a new reference (only when a change of the result is intended):
    $env:OLPREP_REFERENZ_NEU = "1"; pytest -m netz; Remove-Item Env:OLPREP_REFERENZ_NEU

OpenStreetMap changes over time, and the fallback (OSM API instead of Overpass) returns the
same objects in a different form. The test therefore uses a stored Overpass download
(tests/referenz/stadion_osm.json.gz, 2026-11-15) instead of live OSM data. Orthophoto,
terrain model and Vienna contours are downloaded (they change rarely).
"""

import datetime
import gzip
import hashlib
import json
import os
import sys
import warnings
import zipfile
from pathlib import Path

import pytest
import rasterio
from lxml import etree

from olprep.ausgabe.omap import NS

from conftest import needs_oom

pytestmark = [pytest.mark.netz, needs_oom]

REFERENCE = Path(__file__).parent / "referenz" / "stadion.json"
OSM_SNAPSHOT = Path(__file__).parent / "referenz" / "stadion_osm.json.gz"
NAME, BBOX, SCALE = "stadion", (16.415, 48.203, 16.427, 48.211), 4000
FIXED_DAY = datetime.date(2026, 11, 15)     # declination (and so all paper coordinates) depends on the day
Q = {"m": NS}


class FixedDate(datetime.date):
    @classmethod
    def today(cls):
        return cls(FIXED_DAY.year, FIXED_DAY.month, FIXED_DAY.day)


def _sha(items) -> str:
    h = hashlib.sha256()
    for item in items:
        h.update(item.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def summarize(out_dir: Path) -> dict:
    root = etree.parse(str(out_dir / f"{NAME}.omap")).getroot()
    symbols = {s.get("id"): s.get("code") for s in root.iterfind(".//m:symbols/m:symbol", Q)}
    counts = {"osm": {}, "andere": {}}
    lines = {"osm": [], "andere": []}
    for obj in root.iterfind(".//m:part/m:objects/m:object", Q):
        code = symbols[obj.get("symbol")]
        tags = {t.get("k"): t.text or "" for t in obj.iterfind("m:tags/m:t", Q)}
        kind = "osm" if "osm_id" in tags else "andere"
        counts[kind][code] = counts[kind].get(code, 0) + 1
        lines[kind].append(f"{code}|{json.dumps(tags, sort_keys=True)}|{obj.find('m:coords', Q).text}")

    geo = root.find("m:georeferencing", Q)
    images = {}
    for jpg in sorted((out_dir / "daten").glob("*.jpg")):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with rasterio.open(jpg) as ds:
                images[jpg.name] = {"pixel": [ds.width, ds.height],
                                    "jgw": jpg.with_suffix(".jgw").read_text().split()}
    quellen = (out_dir / "QUELLEN.txt").read_text(encoding="utf-8").splitlines()

    return {
        "dateien": sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file()),
        "georeferenzierung": {k: geo.get(k) for k in sorted(geo.keys())}
        | {"epsg": geo.find("m:projected_crs/m:parameter", Q).text,
           "ref_point": dict(geo.find("m:projected_crs/m:ref_point", Q).attrib)},
        "vorlagen": [[t.get("relpath"), r.get("visible")] for t, r in zip(
            root.iterfind(".//m:templates/m:template", Q),
            root.iterfind(".//m:view/m:map_view/m:templates/m:ref", Q))],
        "bilder": images,
        "objekte_andere": dict(sorted(counts["andere"].items())),
        "objekte_andere_sha256": _sha(lines["andere"]),
        "osm_json_sha256": hashlib.sha256((out_dir / "daten" / "osm.json").read_bytes()).hexdigest(),
        "objekte_osm": dict(sorted(counts["osm"].items())),
        "objekte_osm_sha256": _sha(lines["osm"]),
        "quellen": [ln for ln in quellen if not ln.startswith("Erstellt mit")],
    }


def build_reference_map(out_root: Path, monkeypatch, melde):
    from olprep.auftrag import Auftrag, ausfuehren      # imported first, so its "date" gets patched
    # freeze "today" in every olprep module that uses it (module layout changes while refactoring)
    for name, module in list(sys.modules.items()):
        if name.startswith("olprep") and getattr(module, "date", None) is datetime.date:
            monkeypatch.setattr(module, "date", FixedDate)
    snapshot = json.loads(gzip.decompress(OSM_SNAPSHOT.read_bytes()))
    monkeypatch.setattr("olprep.quellen.osm.download", lambda *args, **kwargs: snapshot)
    return ausfuehren(Auftrag(NAME, BBOX, SCALE), out_root, melde=melde)


def test_reference_map_unchanged(tmp_path, monkeypatch):
    steps = []
    ergebnis = build_reference_map(tmp_path, monkeypatch, lambda s, p: steps.append((s, p)))
    actual = summarize(ergebnis.ordner)

    # progress: rising, from 0 to 100; ZIP holds exactly the map folder
    percents = [p for _, p in steps]
    assert percents[0] == 0 and percents[-1] == 100 and percents == sorted(percents)
    with zipfile.ZipFile(ergebnis.zip) as z:
        assert sorted(z.namelist()) == [f"{NAME}/{f}" for f in actual["dateien"]]
    # OSM features imported (one feature can give several map objects, e.g. a multipolygon)
    assert any(ln.startswith(f"OpenStreetMap: {ergebnis.osm_objekte} Objekte") for ln in actual["quellen"])
    # first paragraph of QUELLEN.txt: abbreviations written out (user, 2026-11-16)
    first_paragraph = "\n".join(actual["quellen"][:actual["quellen"].index("")])
    for abbreviation in ("WGS84", "EPSG", "WMM", "OOM", "BEV", "ALS", "EVRF", "ü."):
        assert abbreviation not in first_paragraph, abbreviation

    if os.environ.get("OLPREP_REFERENZ_NEU") == "1" or not REFERENCE.exists():
        REFERENCE.parent.mkdir(exist_ok=True)
        REFERENCE.write_text(json.dumps(actual, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        pytest.skip(f"Referenz neu geschrieben: {REFERENCE}")

    expected = json.loads(REFERENCE.read_text(encoding="utf-8"))
    assert actual.keys() == expected.keys()
    for key in expected:
        assert actual[key] == expected[key], key
