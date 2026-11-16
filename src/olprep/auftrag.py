"""A map job: the user's settings, their check, and the run that builds the map folder.

Used by the command line (scripts/make_map.py) and later by the API. Field names are the
ones of the API draft (documentation/projektuebersicht.html).

    auftrag = Auftrag("stadion", (16.415, 48.203, 16.427, 48.211), 4000).geprueft()
    ergebnis = ausfuehren(auftrag, Path("output"), melde=lambda schritt, prozent: ...)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Callable

import pyproj

from .ausgabe.bilder import save_jpg
from .ausgabe.kartenordner import DATA_DIR, sources_text, write_zip
from .ausgabe.omap import OmapDocument
from .quellen import osm as osm_quelle
from .quellen.orthofoto import WIEN, orthofoto
from .ressourcen import CRT_FILES, SYMBOL_SETS, SYMBOLSATZ_TITEL, default_symbol_set, symbol_set_file
from .verarbeitung import osm as osm_zuordnung
from .verarbeitung.georef import Georeferencing, gk_epsg, gk_name
from .verarbeitung.hoehenlinien import contours
from .verarbeitung.schummerung import hillshade

MARGIN_M = 50                   # extra orthophoto and contours around the requested area

# Area the data sources cover (Austria, generous), WGS84: west, south, east, north
GEBIET = (9.4, 46.3, 17.2, 49.1)
# Largest map: the area must fit on A3 at the chosen scale, portrait or landscape
# (decision 2026-11-15: maps are printed on A3 at most). At 1:20 000 that is 8.4 × 5.94 km.
PAPIER_MM = (420, 297)
# Orthophoto resolution: 1 pixel = 0.025 mm on paper (10 cm at 1:4000, 25 cm at 1:10 000,
# 50 cm at 1:20 000), so a full A3 sheet has 16 800 × 11 880 pixels at every scale.
PIXEL_MM = 0.025
NAME_PATTERN = re.compile(r"[\w-]{1,60}")      # letters (incl. umlauts), digits, _ and -

Melde = Callable[[str, int], None]              # (step, percent 0-100)


class Eingabefehler(ValueError):
    """Settings that cannot be used; the message says what to change."""


@dataclass(frozen=True)
class Auftrag:
    name: str                                       # map name = folder and file name
    bbox: tuple[float, float, float, float]         # west, south, east, north in degrees (WGS84)
    massstab: int                                   # scale denominator, e.g. 4000
    symbolsatz: str | None = None                   # default: ISSprOM 2019 at 1:4000, else ISOM 2017-2
    aequidistanz: float | None = None               # contour interval in m; default 2.5 (sprint) or 5
    zaehlkurve: float | None = None                 # index contour interval in m; default 5 × aequidistanz
    osm: bool = True                                # import OpenStreetMap objects

    def geprueft(self) -> Auftrag:
        """Checked settings with all defaults filled in. Raises Eingabefehler."""
        if not NAME_PATTERN.fullmatch(self.name or ""):
            raise Eingabefehler("Name: 1–60 Zeichen, nur Buchstaben, Ziffern, _ und -")
        try:
            west, south, east, north = (float(v) for v in self.bbox)
        except (TypeError, ValueError):
            raise Eingabefehler("Bereich: vier Zahlen West, Süd, Ost, Nord (Grad)") from None
        if not (west < east and south < north):
            raise Eingabefehler("Bereich: West muss kleiner als Ost und Süd kleiner als Nord sein")
        gw, gs, go, gn = GEBIET
        if not (gw <= west and east <= go and gs <= south and north <= gn):
            raise Eingabefehler("Bereich liegt nicht in Österreich (nur dafür gibt es die Daten)")
        if self.symbolsatz is not None and self.symbolsatz not in SYMBOL_SETS:
            raise Eingabefehler(f"Unbekannter Symbolsatz {self.symbolsatz!r}, möglich: {', '.join(SYMBOL_SETS)}")
        try:
            symbolsatz = self.symbolsatz or default_symbol_set(self.massstab)
        except ValueError as e:
            raise Eingabefehler(str(e)) from None
        if self.massstab not in SYMBOL_SETS[symbolsatz]:
            raise Eingabefehler(f"{symbolsatz} gibt es nur für 1:"
                                + ", 1:".join(map(str, SYMBOL_SETS[symbolsatz])))

        width_m, height_m = _size_m(west, south, east, north)
        long_mm, short_mm = (max(width_m, height_m) / self.massstab * 1000,
                             min(width_m, height_m) / self.massstab * 1000)
        if long_mm > PAPIER_MM[0] or short_mm > PAPIER_MM[1]:
            km = [p / 1000 * self.massstab / 1000 for p in PAPIER_MM]
            raise Eingabefehler(
                f"Bereich {width_m / 1000:.2f} × {height_m / 1000:.2f} km passt bei 1:{self.massstab} "
                f"nicht auf A3 (höchstens {km[0]:.2f} × {km[1]:.2f} km)")

        aequidistanz = (2.5 if symbolsatz.startswith("ISSprOM") else 5.0) \
            if self.aequidistanz is None else float(self.aequidistanz)
        if not aequidistanz > 0:
            raise Eingabefehler("Äquidistanz muss größer als 0 sein")
        zaehlkurve = 5 * aequidistanz if self.zaehlkurve is None else float(self.zaehlkurve)
        q = zaehlkurve / aequidistanz
        if abs(q - round(q)) > 1e-6 or q < 1:
            raise Eingabefehler(f"Zählkurvenabstand {zaehlkurve:g} m ist kein Vielfaches von {aequidistanz:g} m")

        return replace(self, bbox=(west, south, east, north), symbolsatz=symbolsatz,
                       aequidistanz=aequidistanz, zaehlkurve=zaehlkurve, osm=bool(self.osm))


@dataclass
class Ergebnis:
    ordner: Path        # map folder
    omap: Path
    zip: Path | None
    osm_objekte: int    # imported OSM features (one can give several map objects)


def _size_m(west, south, east, north) -> tuple[float, float]:
    epsg = gk_epsg((west + east) / 2)
    xmin, ymin, xmax, ymax = pyproj.Transformer.from_crs(4326, epsg, always_xy=True).transform_bounds(
        west, south, east, north, densify_pts=21)
    return xmax - xmin, ymax - ymin


def _quiet(schritt: str, prozent: int) -> None:
    pass


def ausfuehren(auftrag: Auftrag, ziel: Path, melde: Melde = _quiet, mit_zip: bool = True) -> Ergebnis:
    """Build the map folder ziel/<name>/ (and ziel/<name>.zip) for a job.

    melde(schritt, prozent) is called at the start of each step and with 100 at the end.
    """
    a = auftrag.geprueft()
    west, south, east, north = a.bbox
    epsg = gk_epsg((west + east) / 2)
    to_proj = pyproj.Transformer.from_crs(4326, epsg, always_xy=True)
    xmin, ymin, xmax, ymax = to_proj.transform_bounds(west, south, east, north, densify_pts=21)
    area = (xmin - MARGIN_M, ymin - MARGIN_M, xmax + MARGIN_M, ymax + MARGIN_M)
    centre = (round((xmin + xmax) / 2), round((ymin + ymax) / 2))
    out_dir = ziel / a.name

    melde("Georeferenz berechnen", 0)
    g = Georeferencing.create(epsg, a.massstab, *centre)
    print(f"{a.name}: {a.symbolsatz} 1:{a.massstab}, EPSG:{epsg}, {xmax - xmin:.0f} × {ymax - ymin:.0f} m, "
          f"Deklination {g.declination}°, Grivation {g.grivation}°")

    doc = OmapDocument(symbol_set_file(a.symbolsatz, a.massstab))
    doc.set_georeferencing(g)

    data_dir = out_dir / DATA_DIR
    melde("Orthofoto laden", 5)
    ortho = data_dir / "orthofoto.jpg"
    foto = orthofoto(epsg, area, resolution=a.massstab * PIXEL_MM / 1000)
    save_jpg(foto.image, foto.transform, epsg, ortho)
    print(f"  Orthofoto {foto.resolution * 100:.0f} cm/Pixel -> {ortho.name}")
    doc.add_georeferenced_image(ortho, out_dir)

    melde("Geländemodell laden, Schummerung berechnen", 40)
    shade = data_dir / "schummerung.jpg"
    save_jpg(*hillshade(epsg, area), epsg, shade)
    print(f"  Schummerung 1 m/Pixel -> {shade.name}")
    doc.add_georeferenced_image(shade, out_dir, visible=False)    # would hide the orthophoto

    melde("Höhenlinien berechnen", 55)
    cont = contours(epsg, area, a.aequidistanz, a.zaehlkurve, a.massstab)
    for c in cont.contours:
        coords = list(c.line.coords)
        closed = c.line.is_ring
        points = [g.to_paper(x, y) for x, y in (coords[:-1] if closed else coords)]
        points = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
        if len(points) >= 2:
            doc.add_line("102" if c.index else "101", points, closed=closed)

    # data sources used (texts in ausgabe/kartenordner.py); the hillshade always comes from BEV
    quellen = {"wien_orthofoto" if foto.source.key == WIEN.key else "basemap", "bev"}
    if cont.quelle == "wien":
        quellen.add("wien_hoehenlinien")

    osm_note = "OpenStreetMap: nicht importiert."
    total = 0
    if a.osm and a.symbolsatz in CRT_FILES:
        melde("OpenStreetMap laden und zuordnen", 70)
        rules = osm_zuordnung.load_rules(a.symbolsatz)
        bbox_area = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform_bounds(
            *area, densify_pts=21)
        data = osm_quelle.download(bbox_area, osm_zuordnung.query_keys(rules),
                                   lambda tags: osm_zuordnung.symbol_for(tags, rules) is not None)
        (data_dir / "osm.json").write_text(json.dumps(data), encoding="utf-8")
        counts = osm_zuordnung.add_to_map(doc, g, data, epsg, area, rules)
        total = sum(counts.values())
        print(f"  OpenStreetMap: {len(data['elements'])} Elemente geladen, {total} Objekte übernommen")
        for symbol, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"    {n:5d}  {symbol}")
        osm_note = (f"OpenStreetMap: {total} Objekte, zugeordnet mit der Tabelle "
                    f"{CRT_FILES[a.symbolsatz]} aus OpenOrienteering Mapper. "
                    f"Rohdaten in {DATA_DIR}/osm.json.")
        quellen.add("osm")
    elif a.osm:
        print(f"  OpenStreetMap: keine Zuordnungstabelle für {a.symbolsatz}, übersprungen")

    melde("Karte speichern", 90)
    # first paragraph: facts about the map, abbreviations written out (user, 2026-11-16)
    sources = sources_text([
        f"Erstellt mit OL-Karten-prep am {date.today().isoformat()}.",
        f"Bereich (geografische Länge und Breite im World Geodetic System 1984): "
        f"West {west}, Süd {south}, Ost {east}, Nord {north}",
        f"Symbolsatz {a.symbolsatz} ({SYMBOLSATZ_TITEL[a.symbolsatz]}), Maßstab 1:{a.massstab}",
        f"Koordinatensystem {gk_name(epsg)}, Deklination {g.declination}° "
        f"(World Magnetic Model, Stichtag ist das Erstellungsdatum)",
        cont.note,
        "Schummerung (Vorlage, anfangs ausgeblendet): aus dem Geländemodell des Bundesamts für "
        "Eich- und Vermessungswesen, Licht von Nordwesten.",
        osm_note,
    ], quellen, hoehenlinien_aus_bev=cont.quelle == "bev")
    doc.set_notes(sources)
    (out_dir / "QUELLEN.txt").write_text(sources + "\n", encoding="utf-8")

    omap = out_dir / f"{a.name}.omap"
    doc.save(omap)
    print(f"geschrieben: {omap}")
    zip_path = write_zip(out_dir) if mit_zip else None
    melde("fertig", 100)
    return Ergebnis(out_dir, omap, zip_path, total)
