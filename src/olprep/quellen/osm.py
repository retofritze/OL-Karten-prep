"""OpenStreetMap data for a map area, in Overpass "out geom" form (elements with geometry).

Overpass is the intended service for read-only use. If it is down (it was on
2026-11-02), the OSM editing API is used as fallback for the small map areas.
"""

from __future__ import annotations

import os
from typing import Callable

import requests

from .netz import USER_AGENT

OVERPASS = ("https://overpass-api.de/api/interpreter",)
OSM_API = "https://api.openstreetmap.org/api/0.6"
ATTRIBUTION = "Wege, Gebäude u. a.: © OpenStreetMap-Mitwirkende (ODbL)"


class OsmNichtErreichbar(RuntimeError):
    """Overpass is down and the OSM API fallback is not allowed (public website)."""


def api_fallback_allowed() -> bool:
    """The OSM editing API may serve as fallback for single users only, not for a public
    website (OSM API usage policy). Set OLPREP_OSM_API_ERSATZ=0 in the cloud."""
    return os.environ.get("OLPREP_OSM_API_ERSATZ", "1") != "0"


def download(bbox_wgs84: tuple[float, float, float, float], keys: list[str],
             wanted: Callable[[dict[str, str]], bool]) -> dict:
    """All objects with one of the OSM keys (e.g. 'highway') in the area.

    wanted(tags): whether an object is used at all; only needed by the fallback to
    complete multipolygons that reach outside the area.
    """
    try:
        data = _overpass(bbox_wgs84, keys)
        print("  OpenStreetMap über Overpass geladen")
    except (requests.RequestException, ValueError) as err:
        if not api_fallback_allowed():
            raise OsmNichtErreichbar("OpenStreetMap (Overpass) ist gerade nicht erreichbar. "
                                     "Bitte später noch einmal versuchen oder ohne OSM bestellen.") from err
        print(f"  Overpass nicht erreichbar ({err}), lade über die OSM-API")
        data = _osm_api(bbox_wgs84, wanted)
    return data


def _overpass(bbox_wgs84, keys: list[str]) -> dict:
    w, s, e, n = bbox_wgs84
    bb = f"({s:.6f},{w:.6f},{n:.6f},{e:.6f})"
    parts = "".join(f'node["{k}"]{bb};way["{k}"]{bb};relation["{k}"]["type"="multipolygon"]{bb};'
                    for k in keys)
    query = f"[out:json][timeout:90];({parts});out geom;"
    r = requests.post(OVERPASS[0], data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=120)
    r.raise_for_status()
    return r.json()


def _api_get(path: str, **params) -> list[dict]:
    r = requests.get(f"{OSM_API}/{path}", params=params, headers={"User-Agent": USER_AGENT}, timeout=120)
    r.raise_for_status()
    return r.json()["elements"]


def _osm_api(bbox_wgs84, wanted: Callable[[dict[str, str]], bool]) -> dict:
    """/map call (split into quarters if the area has too many nodes), incomplete
    multipolygons completed with /relation/<id>/full, converted to "out geom" form."""
    elements: dict[tuple[str, int], dict] = {}

    def fetch(w, s, e, n, depth=0):
        try:
            for el in _api_get("map.json", bbox=f"{w:.6f},{s:.6f},{e:.6f},{n:.6f}"):
                elements[(el["type"], el["id"])] = el
        except requests.HTTPError as err:
            if err.response.status_code != 400 or depth > 3:
                raise
            mx, my = (w + e) / 2, (s + n) / 2       # too many nodes: split
            for b in ((w, s, mx, my), (mx, s, e, my), (w, my, mx, n), (mx, my, e, n)):
                fetch(*b, depth + 1)

    fetch(*bbox_wgs84)
    for (typ, oid), el in list(elements.items()):
        if (typ == "relation" and el.get("tags", {}).get("type") == "multipolygon"
                and wanted(el["tags"])
                and any(("way", m["ref"]) not in elements for m in el["members"] if m["type"] == "way")):
            try:
                for sub in _api_get(f"relation/{oid}/full.json"):
                    elements.setdefault((sub["type"], sub["id"]), sub)
            except requests.RequestException as err:
                print(f"  Fläche relation/{oid} unvollständig ({err}), übersprungen")

    nodes = {oid: el for (typ, oid), el in elements.items() if typ == "node"}
    ways = {}
    out = []
    for (typ, oid), el in elements.items():
        if typ == "way":
            geom = [{"lat": nodes[r]["lat"], "lon": nodes[r]["lon"]} for r in el["nodes"] if r in nodes]
            ways[oid] = geom
            if el.get("tags"):
                out.append({"type": "way", "id": oid, "tags": el["tags"], "geometry": geom})
        elif typ == "node" and el.get("tags"):
            out.append(el)
    for (typ, oid), el in elements.items():
        if typ == "relation" and el.get("tags", {}).get("type") == "multipolygon":
            members = [{**m, "geometry": ways[m["ref"]]} for m in el["members"]
                       if m["type"] == "way" and m["ref"] in ways]
            out.append({"type": "relation", "id": oid, "tags": el["tags"], "members": members})
    return {"elements": out, "source": "api.openstreetmap.org"}
