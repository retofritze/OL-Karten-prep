"""Contour lines for a map area: ready-made from Stadt Wien or computed from the BEV ALS-DTM.

Rule (documentation/project.md, decision 8): use the city's 1 m contours where they
are good and fit (whole area inside Vienna, whole-metre interval), otherwise compute
them from the 1 m BEV terrain model. See documentation/datenquellen.md.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import contourpy
import numpy as np
import requests
from scipy.ndimage import gaussian_filter
from shapely.geometry import LineString, box
from shapely.ops import linemerge

from ..quellen import wien
from ..quellen.gelaende import ATTR_BEV, BEV_DATE, dtm_for
from ..quellen.wien import ATTR_WIEN

# Generalisation, in mm on paper (scaled with the map scale)
SMOOTH_MM = 0.3                 # Gaussian sigma applied to the DTM
SIMPLIFY_MM = 0.05              # Douglas-Peucker tolerance
MIN_LENGTH_MM = 2.5             # shorter lines (tiny knolls, fragments) are dropped


@dataclass
class Contour:
    line: LineString        # map CRS (metres)
    height: float
    index: bool             # Zählkurve


@dataclass
class ContourResult:
    contours: list[Contour]
    attribution: str
    note: str               # how the lines were made, for QUELLEN.txt


def _is_multiple(value: float, step: float) -> bool:
    q = value / step
    return abs(q - round(q)) < 1e-6


def contours(epsg: int, bounds: tuple[float, float, float, float], interval: float,
             index_interval: float, scale: int) -> ContourResult:
    whole_metres = float(interval).is_integer() and float(index_interval).is_integer()
    if epsg == 31256 and whole_metres and wien.inside_vienna(bounds):
        try:
            return _wien(bounds, interval, index_interval, scale)
        except (requests.RequestException, RuntimeError) as e:
            print(f"  Wiener Höhenlinien nicht verfügbar ({e}), rechne selbst")
    return _from_dtm(epsg, bounds, interval, index_interval, scale)


# --- ready-made lines of Stadt Wien ------------------------------------------

def _wien(bounds, interval, index_interval, scale) -> ContourResult:
    by_level: dict[int, list] = defaultdict(list)
    for level, line in wien.contour_lines(bounds):      # whole metres above Wiener Null
        if _is_multiple(level, interval):
            by_level[level].append(line)
    result = []
    for level, parts in by_level.items():
        merged = linemerge(parts)                       # rejoin lines cut at the 2.5 km tiles
        for line in _finish(merged, bounds, scale):
            result.append(Contour(line, float(level), _is_multiple(level, index_interval)))
    print(f"  Höhenlinien Stadt Wien: {len(result)} Linien, {interval:g} m, Zählkurve {index_interval:g} m")
    return ContourResult(result, ATTR_WIEN,
                         f"Höhenlinien {interval:g} m, Zählkurven {index_interval:g} m, fertige Linien der "
                         f"Stadt Wien. Höhen über Wiener Null (= 156,68 m ü. Adria).")


# --- computed from the BEV ALS-DTM -------------------------------------------

def _smooth(dtm: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian smoothing that ignores NaN (normalised convolution)."""
    valid = np.isfinite(dtm)
    num = gaussian_filter(np.where(valid, dtm, 0.0), sigma)
    den = gaussian_filter(valid.astype(np.float32), sigma)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[~valid] = np.nan
    return out


def _from_dtm(epsg, bounds, interval, index_interval, scale) -> ContourResult:
    dtm, t = dtm_for(epsg, tuple(bounds))
    if not np.isfinite(dtm).any():
        raise RuntimeError("Keine Höhendaten für diesen Bereich")
    z = _smooth(dtm, SMOOTH_MM * scale / 1000)
    # pixel centres
    x = t.c + 0.5 + np.arange(z.shape[1])
    y = t.f - 0.5 - np.arange(z.shape[0])
    gen = contourpy.contour_generator(x, y, np.ma.masked_invalid(z),
                                      line_type=contourpy.LineType.Separate)
    lo, hi = np.nanmin(z), np.nanmax(z)
    result = []
    for level in np.arange(math.ceil(lo / interval) * interval, hi, interval):
        level = round(float(level), 3)
        for xy in gen.lines(level):
            if len(xy) < 2:
                continue
            for line in _finish(LineString(xy), bounds, scale):
                result.append(Contour(line, level, _is_multiple(level, index_interval)))
    print(f"  Höhenlinien berechnet: {len(result)} Linien, {interval:g} m, Zählkurve {index_interval:g} m, "
          f"Höhen {lo:.0f}–{hi:.0f} m")
    return ContourResult(result, ATTR_BEV,
                         f"Höhenlinien {interval:g} m, Zählkurven {index_interval:g} m, selbst berechnet "
                         f"aus dem BEV ALS-Geländemodell 1 m (Stichtag {BEV_DATE[:4]}-{BEV_DATE[4:6]}-"
                         f"{BEV_DATE[6:]}), geglättet. Höhen über Adria (EVRF2000).")


# --- common ------------------------------------------------------------------

def _finish(geom, bounds, scale) -> list[LineString]:
    """Clip to the area, simplify and drop short pieces."""
    m_per_mm = scale / 1000
    clipped = geom.intersection(box(*bounds))
    parts = getattr(clipped, "geoms", [clipped])       # Multi-/GeometryCollection or single
    out = []
    for part in parts:
        if not isinstance(part, LineString) or part.is_empty:
            continue
        part = part.simplify(SIMPLIFY_MM * m_per_mm)
        if part.length >= MIN_LENGTH_MM * m_per_mm:
            out.append(part)
    return out
