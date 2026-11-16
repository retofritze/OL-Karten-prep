"""Open data of the City of Vienna (WFS): city boundary and ready-made 1 m contour lines.

See documentation/datenquellen.md.
"""

from __future__ import annotations

import requests
from shapely.geometry import box, shape

from .netz import USER_AGENT

WFS = "https://data.wien.gv.at/daten/geo"


def _wfs(type_name: str, bbox: tuple[float, float, float, float] | None = None) -> dict:
    params = {"service": "WFS", "version": "1.1.0", "request": "GetFeature",
              "typeName": type_name, "srsName": "EPSG:31256", "outputFormat": "json"}
    if bbox:
        params["bbox"] = ",".join(f"{v:.1f}" for v in bbox) + ",EPSG:31256"
    r = requests.get(WFS, params=params, headers={"User-Agent": USER_AGENT}, timeout=120)
    r.raise_for_status()
    data = r.json()
    total = data.get("totalFeatures")
    if isinstance(total, int) and total != len(data["features"]):
        raise RuntimeError(f"WFS lieferte nur {len(data['features'])} von {total} Objekten")
    return data


def inside_vienna(bounds: tuple[float, float, float, float]) -> bool:
    """True if the area (EPSG:31256) lies completely inside the city boundary."""
    city = shape(_wfs("ogdwien:LANDESGRENZEOGD")["features"][0]["geometry"])
    return city.contains(box(*bounds))


def contour_lines(bounds: tuple[float, float, float, float]) -> list[tuple[int, object]]:
    """(height above Wiener Null in whole metres, shapely line) for each contour piece in the
    area (EPSG:31256). Lines are cut at the city's 2.5 km tiles."""
    data = _wfs("ogdwien:HOEHENLINIEOGD", bounds)
    return [(f["properties"]["HOEHE_WIEN"], shape(f["geometry"])) for f in data["features"]]
