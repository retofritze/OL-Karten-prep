"""The map folder: <name>/<name>.omap + QUELLEN.txt + daten/, and its ZIP for download."""

from __future__ import annotations

import zipfile
from pathlib import Path

DATA_DIR = "daten"      # all downloaded and derived files of a map, next to the .omap

# Data sources and the lines that must be printed on the map (licence text given by the user,
# 2026-11-16). Only the sources actually used appear; the Vienna line only if data of the City
# of Vienna was used.
CC_BY = "https://creativecommons.org/licenses/by/4.0/deed.de"
ODBL = "https://opendatacommons.org/licenses/odbl/"
WIEN_ZEILE = "Datenquelle: Stadt Wien - data.wien.gv.at"

# source key -> (entry under "Datenquellen:", line for the map)
QUELLEN = {
    "basemap": (f"Orthofoto: basemap.at (CC BY 4.0; basemap.at; {CC_BY})",
                "Datenquelle: basemap.at"),
    "wien_orthofoto": (f"Orthofoto: Stadt Wien (CC BY 4.0; data.wien.gv.at; {CC_BY})", WIEN_ZEILE),
    "bev": ("Geländemodell ({abgeleitet}): Bundesamt für Eich- und Vermessungswesen "
            f"(CC BY 4.0; https://www.bev.gv.at/public.html; {CC_BY})",
            "Datenquelle: bev.gv.at/public.html"),
    "wien_hoehenlinien": (f"Höhenlinien in Wien: Stadt Wien (CC BY 4.0; data.wien.gv.at; {CC_BY})", WIEN_ZEILE),
    "osm": (f"Schon vorplatzierte Symbole: OpenStreetMap (ODbL; openstreetmap.org; {ODBL})",
            "Datenquelle: openstreetmap.org / OpenStreetMap-Mitwirkende"),
}
LISTE = ("basemap", "wien_orthofoto", "bev", "wien_hoehenlinien", "osm")         # order of the list
AUF_KARTE = ("basemap", "osm", "bev", "wien_orthofoto", "wien_hoehenlinien")     # order on the map


def sources_text(facts: list[str], quellen: set[str], hoehenlinien_aus_bev: bool) -> str:
    """Text for QUELLEN.txt and the map notes: facts about the map, then the data sources
    used (keys of QUELLEN) and the lines that must be printed on the map."""
    abgeleitet = ("Höhenlinien und Schummerung daraus gerechnet" if hoehenlinien_aus_bev
                  else "Schummerung daraus gerechnet")
    map_lines = []
    for key in AUF_KARTE:
        if key in quellen and QUELLEN[key][1] not in map_lines:
            map_lines.append(QUELLEN[key][1])
    return "\n".join([
        *facts,
        "",
        "Datenquellen:",
        *(f"- {QUELLEN[k][0].format(abgeleitet=abgeleitet)}" for k in LISTE if k in quellen),
        "",
        "Der Text muss auf der Karte stehen:",
        "",
        *map_lines,
        "",
        "Keine Gewähr auf rechtliche Angaben!",
    ])


def write_zip(folder: Path) -> Path:
    """<folder>.zip next to the folder; unpacking it gives the folder again."""
    path = folder.with_name(folder.name + ".zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(folder.parent).as_posix())
    return path
