"""Checks of the user settings (Auftrag.geprueft). They run before anything is downloaded."""

import zipfile

import pytest

from olprep.auftrag import MAX_FLAECHE_KM2, Auftrag, Eingabefehler, ausfuehren
from olprep.ausgabe.kartenordner import write_zip
from olprep.ressourcen import SCALES, SYMBOL_SETS, default_symbol_set

BBOX = (16.415, 48.203, 16.427, 48.211)     # Ernst-Happel-Stadion, about 0.9 × 0.9 km


def test_symbol_sets_and_scales():
    assert SYMBOL_SETS["ISSprOM 2019"] == (4000,)
    assert SCALES == [4000, 5000, 7500, 10000, 12500, 15000, 20000]


@pytest.mark.parametrize("scale, name", [
    (4000, "ISSprOM 2019"), (10000, "ISOM 2017-2"), (15000, "ISOM 2017-2"),
    (5000, "ISMTBOM"), (20000, "ISMTBOM"), (12500, "ISSkiOM 2019"),
])
def test_default_symbol_set(scale, name):
    assert default_symbol_set(scale) == name


def test_defaults_filled_in():
    a = Auftrag("stadion", [16.415, 48.203, 16.427, 48.211], 4000).geprueft()
    assert a.symbolsatz == "ISSprOM 2019"
    assert (a.aequidistanz, a.zaehlkurve) == (2.5, 12.5)
    assert a.bbox == BBOX and isinstance(a.bbox, tuple)
    assert a.osm is True
    forest = Auftrag("wald", (14.765, 47.955, 14.781, 47.965), 10000, zaehlkurve=25).geprueft()
    assert (forest.symbolsatz, forest.aequidistanz, forest.zaehlkurve) == ("ISOM 2017-2", 5.0, 25.0)


def test_check_is_idempotent():
    a = Auftrag("stadion", BBOX, 4000, aequidistanz=2, zaehlkurve=10).geprueft()
    assert a.geprueft() == a


@pytest.mark.parametrize("changes, message", [
    ({"name": ""}, "Name"),
    ({"name": "../stadion"}, "Name"),
    ({"name": "a b"}, "Name"),
    ({"bbox": (16.4, 48.2, 16.4)}, "vier Zahlen"),
    ({"bbox": ("a", 48.2, 16.4, 48.3)}, "vier Zahlen"),
    ({"bbox": (16.427, 48.203, 16.415, 48.211)}, "West muss kleiner"),
    ({"bbox": (13.0, 52.4, 13.1, 52.5)}, "nicht in Österreich"),           # Berlin
    ({"bbox": (16.3, 48.15, 16.4, 48.25)}, "zu groß"),                      # about 7.4 × 11 km
    ({"massstab": 3000}, "1:3000"),
    ({"massstab": 10000, "symbolsatz": "ISSprOM 2019"}, "nur für 1:4000"),
    ({"symbolsatz": "ISOM 2000"}, "Unbekannter Symbolsatz"),
    ({"aequidistanz": 0}, "größer als 0"),
    ({"aequidistanz": -2.5}, "größer als 0"),
    ({"aequidistanz": 2, "zaehlkurve": 5}, "kein Vielfaches"),
    ({"aequidistanz": 5, "zaehlkurve": 2.5}, "kein Vielfaches"),
])
def test_invalid_settings(changes, message):
    settings = {"name": "stadion", "bbox": BBOX, "massstab": 4000} | changes
    with pytest.raises(Eingabefehler, match=message):
        Auftrag(**settings).geprueft()


def test_area_limit_is_provisional_value():
    assert MAX_FLAECHE_KM2 == 4.0      # change together with project.md when decided


def test_run_checks_before_download(tmp_path):
    with pytest.raises(Eingabefehler):
        ausfuehren(Auftrag("x", BBOX, 10000, symbolsatz="ISSprOM 2019"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_write_zip(tmp_path):
    folder = tmp_path / "karte"
    (folder / "daten").mkdir(parents=True)
    (folder / "karte.omap").write_text("x", encoding="utf-8")
    (folder / "daten" / "osm.json").write_text("{}", encoding="utf-8")
    with zipfile.ZipFile(write_zip(folder)) as z:
        assert sorted(z.namelist()) == ["karte/daten/osm.json", "karte/karte.omap"]
