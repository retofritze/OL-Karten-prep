"""Georeferencing of an OOM map: projected CRS <-> paper coordinates.

Conventions (verified against data/referenz_georef.omap, OOM 0.9.6):
- grivation = declination - meridian convergence  [degrees]
- paper coordinates in 1/1000 mm, x right, y down; paper "up" = magnetic north
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import pyproj
from pygeomag import GeoMag


def gk_epsg(lon: float) -> int:
    """MGI / Austria GK zone (M28/M31/M34) for a longitude; zone borders at 11°50' and 14°50' E."""
    if lon < 11 + 50 / 60:
        return 31254
    if lon < 14 + 50 / 60:
        return 31255
    return 31256


def decimal_year(d: date) -> float:
    start = date(d.year, 1, 1)
    length = (date(d.year + 1, 1, 1) - start).days
    return d.year + (d - start).days / length


def magnetic_declination(lat: float, lon: float, on: date, alt_km: float = 0.0) -> float:
    """Declination in degrees (east positive) from the World Magnetic Model."""
    return GeoMag().calculate(glat=lat, glon=lon, alt=alt_km, time=decimal_year(on)).d


def oom_grid_compensation(epsg: int, lat: float, lon: float) -> tuple[float, float]:
    """(convergence [deg], grid scale factor) computed exactly like OOM 0.9.6
    (Georeferencing::updateGridCompensation): 1 km baselines in a local
    stereographic WGS84 projection, mapped into the target CRS.

    OOM checks declination == round(grivation + convergence, 2) on load and
    warns otherwise, so we must use its convergence, not the analytic one.
    """
    local = pyproj.CRS.from_proj4(f"+proj=sterea +lat_0={lat} +lon_0={lon} +ellps=WGS84 +units=m")
    local_to_geo = pyproj.Transformer.from_crs(local, 4326, always_xy=True)
    geo_to_proj = pyproj.Transformer.from_crs(4326, epsg, always_xy=True)
    delta = 1000.0
    e, n, w, s = (geo_to_proj.transform(*local_to_geo.transform(x, y))
                  for x, y in ((delta / 2, 0), (0, delta / 2), (-delta / 2, 0), (0, -delta / 2)))
    d_northing_dy = (n[1] - s[1]) / delta
    d_easting_dy = (n[0] - s[0]) / delta
    d_northing_dx = (e[1] - w[1]) / delta
    d_easting_dx = (e[0] - w[0]) / delta
    convergence = math.degrees(math.atan2(d_northing_dx - d_easting_dy, d_easting_dx + d_northing_dy))
    determinant = d_easting_dx * d_northing_dy - d_northing_dx * d_easting_dy
    return convergence, math.sqrt(determinant)


@dataclass
class Georeferencing:
    epsg: int
    scale: int                  # map scale denominator, e.g. 10000
    ref_easting: float          # projected coordinates of paper origin (0, 0)
    ref_northing: float
    declination: float          # degrees, rounded as stored in the file
    grivation: float            # degrees, rounded as stored in the file
    grid_scale_factor: float
    ref_lat: float
    ref_lon: float

    @classmethod
    def create(cls, epsg: int, scale: int, ref_easting: float, ref_northing: float,
               on: date | None = None) -> "Georeferencing":
        to_wgs84 = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True)
        lon, lat = to_wgs84.transform(ref_easting, ref_northing)
        convergence, grid_scale_factor = oom_grid_compensation(epsg, lat, lon)
        # Same rounding chain as OOM's setDeclination() + load-time consistency check
        grivation = round(magnetic_declination(lat, lon, on or date.today()) - convergence, 2)
        declination = round(grivation + convergence, 2)
        return cls(epsg, scale, ref_easting, ref_northing, declination, grivation,
                   round(grid_scale_factor, 6), lat, lon)

    def to_paper(self, easting: float, northing: float) -> tuple[int, int]:
        """Projected coordinates (m) -> paper coordinates (1/1000 mm)."""
        g = math.radians(self.grivation)
        de, dn = easting - self.ref_easting, northing - self.ref_northing
        k = 1_000_000 / (self.scale * self.grid_scale_factor)   # m -> 1/1000 mm
        x = (de * math.cos(g) - dn * math.sin(g)) * k
        y = (-de * math.sin(g) - dn * math.cos(g)) * k
        return round(x), round(y)

    def lonlat_to_paper(self, lon: float, lat: float) -> tuple[int, int]:
        to_proj = pyproj.Transformer.from_crs(4326, self.epsg, always_xy=True)
        return self.to_paper(*to_proj.transform(lon, lat))
