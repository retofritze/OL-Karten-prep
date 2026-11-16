"""QUELLEN.txt / map notes: data sources and the lines to print on the map (text of 2026-11-16)."""

from olprep.ausgabe.kartenordner import sources_text
from olprep.verarbeitung.georef import gk_name

FACTS = ["Erstellt mit OL-Karten-prep am 2026-11-16."]


def test_outside_vienna_with_osm():
    text = sources_text(FACTS, {"basemap", "bev", "osm"}, hoehenlinien_aus_bev=True)
    assert text == "\n".join([
        "Erstellt mit OL-Karten-prep am 2026-11-16.",
        "",
        "Datenquellen:",
        "- Orthofoto: basemap.at (CC BY 4.0; basemap.at; https://creativecommons.org/licenses/by/4.0/deed.de)",
        "- Geländemodell (Höhenlinien und Schummerung daraus gerechnet): Bundesamt für Eich- und "
        "Vermessungswesen (CC BY 4.0; https://www.bev.gv.at/public.html; "
        "https://creativecommons.org/licenses/by/4.0/deed.de)",
        "- Schon vorplatzierte Symbole: OpenStreetMap (ODbL; openstreetmap.org; "
        "https://opendatacommons.org/licenses/odbl/)",
        "",
        "Der Text muss auf der Karte stehen:",
        "",
        "Datenquelle: basemap.at",
        "Datenquelle: openstreetmap.org / OpenStreetMap-Mitwirkende",
        "Datenquelle: bev.gv.at/public.html",
        "",
        "Keine Gewähr auf rechtliche Angaben!",
    ])


def test_vienna_line_only_with_vienna_data_and_only_once():
    vienna = sources_text(FACTS, {"wien_orthofoto", "bev", "wien_hoehenlinien"}, hoehenlinien_aus_bev=False)
    assert vienna.count("Datenquelle: Stadt Wien - data.wien.gv.at") == 1
    assert vienna.rstrip().splitlines()[-3] == "Datenquelle: Stadt Wien - data.wien.gv.at"   # last map line
    assert "Höhenlinien in Wien: Stadt Wien" in vienna and "Orthofoto: Stadt Wien" in vienna
    assert "Geländemodell (Schummerung daraus gerechnet)" in vienna
    assert "basemap" not in vienna and "openstreetmap" not in vienna
    outside = sources_text(FACTS, {"basemap", "bev"}, hoehenlinien_aus_bev=True)
    assert "Stadt Wien" not in outside


def test_gk_names_written_out():
    assert gk_name(31256).startswith("Gauß-Krüger Österreich Ost (Mittelmeridian 16°20′ östlich von Greenwich")
    assert "Code 31254 der European Petroleum Survey Group" in gk_name(31254)
