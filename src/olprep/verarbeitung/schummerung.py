"""Hillshade (Schummerung) from the BEV ALS-DTM as an additional template.

Light from the north-west (azimuth 315°, 45° above the horizon), the usual
cartographic convention. 1 m pixels, grey image in the map CRS
(written as JPG + .jgw by ausgabe.bilder).
"""

from __future__ import annotations

import math

import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter

from ..quellen.gelaende import ATTR_BEV, dtm_for

AZIMUTH = 315.0
ALTITUDE = 45.0
SMOOTH_PX = 1.0             # light smoothing against single-pixel noise of the 1 m DTM

ATTRIBUTION = ATTR_BEV.replace("(Höhenlinien selbst berechnet)", "(Schummerung)")


def hillshade(epsg: int, bounds: tuple[float, float, float, float]) -> tuple[np.ndarray, rasterio.Affine]:
    """Grey uint8 image (1, H, W) and its geotransform in the map CRS."""
    dtm, transform = dtm_for(epsg, tuple(bounds))
    z = np.where(np.isfinite(dtm), dtm, np.nanmean(dtm))
    z = gaussian_filter(z, SMOOTH_PX)
    d_row, d_col = np.gradient(z)                  # pixel size 1 m, rows run southwards
    dz_east, dz_north = d_col, -d_row
    # brightness = surface normal · direction to the light (azimuth clockwise from north)
    az, alt = math.radians(AZIMUTH), math.radians(ALTITUDE)
    light = (math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt))
    shade = (-dz_east * light[0] - dz_north * light[1] + light[2]) / np.sqrt(dz_east ** 2 + dz_north ** 2 + 1)
    grey = np.clip(shade * 255, 0, 255).astype(np.uint8)
    grey[~np.isfinite(dtm)] = 255
    return grey[np.newaxis], transform
