"""BEV ALS terrain model (DTM, 1 m), read directly from the BEV cloud-optimised GeoTIFFs.

See documentation/datenquellen.md.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pyproj
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds

from .netz import USER_AGENT

BEV_DTM = "https://data.bev.gv.at/download/ALS/DTM/{date}/ALS_DTM_CRS3035RES50000mN{n}E{e}.tif"
BEV_DATE = "20250915"           # newest "Stichtag" of the BEV ALS-DTM (checked 2026-11-02)
BEV_TILE = 50_000
PAD_M = 30                      # extra DTM around the area against smoothing edge effects

ATTR_BEV = "Geländemodell (Höhenlinien selbst berechnet): BEV – Bundesamt für Eich- und Vermessungswesen (CC BY 4.0)"


def _read_dtm(epsg: int, bounds: tuple[float, float, float, float]) -> tuple[np.ndarray, rasterio.Affine]:
    """1 m DTM for bounds (map CRS), assembled from the BEV COG tiles by range requests."""
    xmin, ymin, xmax, ymax = bounds
    width, height = math.ceil(xmax - xmin), math.ceil(ymax - ymin)
    dst_transform = from_origin(xmin, ymax, 1.0, 1.0)
    dtm = np.full((height, width), np.nan, dtype=np.float32)

    b3035 = pyproj.Transformer.from_crs(epsg, 3035, always_xy=True).transform_bounds(
        *bounds, densify_pts=21)
    pad = 5     # m, room for the bilinear kernel
    env = rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                       CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_USERAGENT=USER_AGENT)
    with env:
        for n in range(int(b3035[1] // BEV_TILE) * BEV_TILE, int(b3035[3]) + 1, BEV_TILE):
            for e in range(int(b3035[0] // BEV_TILE) * BEV_TILE, int(b3035[2]) + 1, BEV_TILE):
                url = BEV_DTM.format(date=BEV_DATE, n=n, e=e)
                with rasterio.open("/vsicurl/" + url) as ds:
                    tb = ds.bounds
                    win_bounds = (max(b3035[0] - pad, tb.left), max(b3035[1] - pad, tb.bottom),
                                  min(b3035[2] + pad, tb.right), min(b3035[3] + pad, tb.top))
                    win = from_bounds(*win_bounds, ds.transform).round_offsets().round_lengths()
                    src = ds.read(1, window=win)
                    reproject(src, dtm, src_transform=ds.window_transform(win), src_crs=ds.crs,
                              src_nodata=ds.nodata, dst_transform=dst_transform,
                              dst_crs=f"EPSG:{epsg}", dst_nodata=np.nan,
                              resampling=Resampling.bilinear, init_dest_nodata=False)
                print(f"  Geländemodell BEV {BEV_DATE}: Kachel N{n} E{e}")
    return dtm, dst_transform


@lru_cache(maxsize=2)
def dtm_for(epsg: int, bounds: tuple[float, float, float, float]) -> tuple[np.ndarray, rasterio.Affine]:
    """DTM for the map area plus PAD_M, read once and shared by contours and hillshade.
    The returned array must not be modified."""
    padded = (bounds[0] - PAD_M, bounds[1] - PAD_M, bounds[2] + PAD_M, bounds[3] + PAD_M)
    return _read_dtm(epsg, padded)
