"""Checks of the user settings (Auftrag.geprueft). They run before anything is downloaded."""

import zipfile

import pytest

from olprep.auftrag import PIXEL_MM, Auftrag, Eingabefehler, ausfuehren
from olprep.quellen.orthofoto import MAX_RESOLUTION_M, ZOOM_TOLERANCE, ground_resolution, start_zoom
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
    ({"bbox": (16.3, 48.15, 16.4, 48.25)}, "nicht auf A3"),                 # about 7.4 × 11 km
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


def bbox_km(width_km, height_km, west=16.30, south=48.20):
    """Bounding box of about width × height km near Vienna (1° lon ≈ 74.2 km, 1° lat ≈ 111.2 km)."""
    return (west, south, west + width_km / 74.2, south + height_km / 111.2)


@pytest.mark.parametrize("width, height, scale, fits", [
    (4.0, 2.8, 10000, True),        # A3 landscape at 1:10 000 = 4.2 × 2.97 km
    (2.8, 4.0, 10000, True),        # portrait
    (4.5, 2.0, 10000, False),       # long side too long
    (3.5, 3.2, 10000, False),       # short side too long for both orientations
    (4.0, 2.8, 4000, False),        # A3 at 1:4000 = 1.68 × 1.19 km
    (1.6, 1.1, 4000, True),
    (8.0, 5.5, 20000, True),        # A3 at 1:20 000 = 8.4 × 5.94 km
    (8.0, 6.2, 20000, False),
])
def test_area_must_fit_on_a3(width, height, scale, fits):
    auftrag = Auftrag("karte", bbox_km(width, height), scale)
    if fits:
        auftrag.geprueft()
    else:
        with pytest.raises(Eingabefehler, match=f"passt bei 1:{scale} nicht auf A3"):
            auftrag.geprueft()


def test_a3_message_names_the_limit():
    with pytest.raises(Eingabefehler, match=r"höchstens 4\.20 × 2\.97 km"):
        Auftrag("karte", bbox_km(5, 2), 10000).geprueft()


@pytest.mark.parametrize("scale, zoom, reduced_to", [
    (4000, 20, None),       # 10 cm wanted, tiles have 10 cm: kept as is (reference map unchanged)
    (5000, 20, 0.125),
    (7500, 19, None),       # 18.75 cm wanted, 20 cm tiles are close enough
    (10000, 19, 0.25),      # 20 cm tiles reduced to 25 cm
    (12500, 19, 0.3125),
    (15000, 18, None),      # 37.5 cm wanted, 40 cm tiles close enough
    (20000, 18, 0.5),
])
def test_orthophoto_zoom_and_reduction(scale, zoom, reduced_to):
    wanted = scale * PIXEL_MM / 1000
    lat = 48.2
    assert start_zoom(20, lat, wanted) == zoom
    tile_res = round(ground_resolution(zoom, lat), 2)
    assert (tile_res < wanted / ZOOM_TOLERANCE) == (reduced_to is not None)
    if reduced_to:
        assert wanted == pytest.approx(reduced_to)
    assert wanted <= MAX_RESOLUTION_M


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
