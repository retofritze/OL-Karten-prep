"""Write OpenOrienteering Mapper (.omap, XML v9) files.

Starts from a symbol set file shipped with OOM, removes its sample objects and
fills in georeferencing, map objects and templates.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree

if TYPE_CHECKING:       # type hint only: output does not depend on processing
    from ..verarbeitung.georef import Georeferencing

NS = "http://openorienteering.org/apps/mapper/xml/v2"

# Coordinate flags (third number in <coords>)
CURVE_START = 1
CLOSE_POINT = 2
HOLE_POINT = 16     # end of a (sub)path
DASH_POINT = 32

OBJ_POINT = 0
OBJ_PATH = 1


def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _fixed(value: float, decimals: int) -> str:
    """Fixed-point without trailing zeros, like OOM writes numbers (1.000005, 5.3)."""
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".")


class OmapDocument:
    def __init__(self, symbol_set: Path):
        parser = etree.XMLParser(remove_blank_text=False)
        self.tree = etree.parse(str(symbol_set), parser)
        self.root = self.tree.getroot()
        symbols = self.root.find(f".//{_q('symbols')}").findall(_q("symbol"))
        self.symbol_ids = {s.get("code"): s.get("id") for s in symbols}
        # 1 point, 2 line, 4 area, 8 text, 16 combined (line and/or area)
        self.symbol_types = {s.get("code"): int(s.get("type")) for s in symbols}
        self.symbol_names = {s.get("code"): s.get("name") for s in symbols}
        self.objects = self.root.find(f".//{_q('part')}/{_q('objects')}")
        for obj in list(self.objects):
            self.objects.remove(obj)
        self.templates = self.root.find(f".//{_q('templates')}")
        self.template_visible: list[bool] = []
        self.georef: Georeferencing | None = None

    def set_notes(self, text: str) -> None:
        """Map notes (OOM: Karte -> Kartennotizen), used for data source attribution."""
        notes = self.root.find(_q("notes"))
        if notes is None:
            notes = etree.Element(_q("notes"))
            self.root.insert(0, notes)
        notes.text = text

    # --- georeferencing -------------------------------------------------

    def set_georeferencing(self, g: Georeferencing) -> None:
        self.georef = g
        old = self.root.find(_q("georeferencing"))
        new = etree.Element(_q("georeferencing"), {
            "scale": str(g.scale),
            "grid_scale_factor": _fixed(g.grid_scale_factor, 6),
            "auxiliary_scale_factor": "1",
            "declination": _fixed(g.declination, 2),
            "grivation": _fixed(g.grivation, 2),
        })
        proj = etree.SubElement(new, _q("projected_crs"), id="EPSG")
        etree.SubElement(proj, _q("spec"), language="PROJ.4").text = f"+init=epsg:{g.epsg}"
        etree.SubElement(proj, _q("parameter")).text = str(g.epsg)
        etree.SubElement(proj, _q("ref_point"), x=f"{g.ref_easting:.6f}", y=f"{g.ref_northing:.6f}")
        geo = etree.SubElement(new, _q("geographic_crs"), id="Geographic coordinates")
        etree.SubElement(geo, _q("spec"), language="PROJ.4").text = "+proj=latlong +datum=WGS84"
        etree.SubElement(geo, _q("ref_point_deg"), lat=f"{g.ref_lat:.8f}", lon=f"{g.ref_lon:.8f}")
        new.tail = old.tail
        old.getparent().replace(old, new)

    # --- objects --------------------------------------------------------

    def _add_object(self, obj_type: int, code: str, coords: list[tuple[int, int, int]],
                    tags: dict[str, str] | None = None) -> None:
        obj = etree.SubElement(self.objects, _q("object"), type=str(obj_type),
                               symbol=self.symbol_ids[code])
        if tags:    # object tags, shown in OOM's tag editor and usable in "select by tag"
            tags_el = etree.SubElement(obj, _q("tags"))
            for k, v in tags.items():
                etree.SubElement(tags_el, _q("t"), k=k).text = v
        text = "".join(f"{x} {y} {f};" if f else f"{x} {y};" for x, y, f in coords)
        etree.SubElement(obj, _q("coords"), count=str(len(coords))).text = text
        if obj_type == OBJ_PATH:
            pattern = etree.SubElement(obj, _q("pattern"), rotation="0")
            etree.SubElement(pattern, _q("coord"), x="0", y="0")
        obj.tail = "\n"
        self.objects.set("count", str(len(self.objects)))

    def add_point(self, code: str, xy: tuple[int, int], tags: dict[str, str] | None = None) -> None:
        self._add_object(OBJ_POINT, code, [(xy[0], xy[1], 0)], tags)

    def add_line(self, code: str, points: list[tuple[int, int]], closed: bool = False,
                 tags: dict[str, str] | None = None) -> None:
        self.add_rings(code, [points], closed, tags)

    def add_area(self, code: str, points: list[tuple[int, int]]) -> None:
        self.add_line(code, points, closed=True)

    def add_rings(self, code: str, rings: list[list[tuple[int, int]]], closed: bool = True,
                  tags: dict[str, str] | None = None) -> None:
        """One path object of several parts, e.g. an area with holes (outer ring first).
        Each part ends with HOLE_POINT; closed parts repeat their first point with CLOSE_POINT."""
        coords = []
        for points in rings:
            part = [(x, y, 0) for x, y in points]
            if closed:
                part.append((points[0][0], points[0][1], CLOSE_POINT | HOLE_POINT))
            else:
                part[-1] = (*part[-1][:2], HOLE_POINT)
            coords += part
        if not closed and len(rings) == 1:
            coords[-1] = (*coords[-1][:2], 0)     # single open line: no flags, as before
        self._add_object(OBJ_PATH, code, coords, tags)

    # --- templates ------------------------------------------------------

    def add_georeferenced_image(self, path: Path, omap_dir: Path, visible: bool = True) -> None:
        """Image with world file (.jgw/.tfw) or GeoTIFF, referenced relative to the map.
        Templates are drawn in the order added, the first at the bottom."""
        self.template_visible.append(visible)
        rel = Path(os.path.relpath(path, omap_dir)).as_posix()
        t = etree.Element(_q("template"), {
            "type": "TemplateImage", "open": "true", "name": path.name,
            "path": path.resolve().as_posix(), "relpath": rel, "georef": "true",
        })
        etree.SubElement(t, _q("crs_spec")).text = f"+init=epsg:{self.georef.epsg}"
        t.tail = "\n"
        existing = self.templates.findall(_q("template"))
        (existing[-1].addnext(t) if existing else self.templates.insert(0, t))
        count = len(existing) + 1
        self.templates.set("count", str(count))
        self.templates.set("first_front_template", str(count))   # all templates below the map

    # --- output ---------------------------------------------------------

    def _write_view(self) -> None:
        view = self.root.find(f".//{_q('view')}")
        for mv in view.findall(_q("map_view")):
            view.remove(mv)
        mv = etree.SubElement(view, _q("map_view"), zoom="1", position_x="0", position_y="0")
        etree.SubElement(mv, _q("map"), opacity="1", visible="true")
        refs = etree.SubElement(mv, _q("templates"),
                                count=str(len(self.templates.findall(_q("template")))))
        for i in range(int(refs.get("count"))):
            visible = self.template_visible[i] if i < len(self.template_visible) else True
            etree.SubElement(refs, _q("ref"), template=str(i), visible=str(visible).lower(), opacity="1")
        mv.tail = "\n"

    def save(self, path: Path) -> None:
        self._write_view()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.tree.write(str(path), xml_declaration=True, encoding="UTF-8")
