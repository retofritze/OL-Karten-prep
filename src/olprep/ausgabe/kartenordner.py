"""The map folder: <name>/<name>.omap + QUELLEN.txt + daten/, and its ZIP for download."""

from __future__ import annotations

import zipfile
from pathlib import Path

DATA_DIR = "daten"      # all downloaded and derived files of a map, next to the .omap

LICENSE_NOTE = """\
WICHTIG – Lizenz CC BY 4.0 (Namensnennung):
Die Daten dürfen frei verwendet werden, auch kommerziell, aber nur mit Nennung der Quelle.
Die oben genannten Datenquellen MÜSSEN deshalb auf der fertigen Karte stehen
(z. B. im Kartenrand beim Impressum), auch auf jedem Ausdruck und jeder veröffentlichten Version.
Lizenztext: https://creativecommons.org/licenses/by/4.0/deed.de"""

OSM_LICENSE_NOTE = """\
OpenStreetMap-Daten stehen unter der ODbL. Auch hier gilt: "© OpenStreetMap-Mitwirkende"
muss auf der Karte stehen. Lizenz: https://www.openstreetmap.org/copyright"""


def sources_text(facts: list[str], attributions: list[str], with_osm_license: bool) -> str:
    """Text for QUELLEN.txt and the map notes: facts about the map, data sources, licence notes."""
    return "\n".join([
        *facts,
        "",
        "Datenquellen:",
        *(f"- {a}" for a in attributions),
        "",
        LICENSE_NOTE,
        *(["", OSM_LICENSE_NOTE] if with_osm_license else []),
    ])


def write_zip(folder: Path) -> Path:
    """<folder>.zip next to the folder; unpacking it gives the folder again."""
    path = folder.with_name(folder.name + ".zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(folder.parent).as_posix())
    return path
