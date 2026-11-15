"""Georeferenced images of the map folder (templates in OOM)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio


def save_jpg(image: np.ndarray, transform: rasterio.Affine, epsg: int, path: Path) -> None:
    """uint8 image (bands, H, W) as JPG + .jgw only (no .aux.xml), the template form verified in OOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.Env(GDAL_PAM_ENABLED="NO"), \
         rasterio.open(path, "w", driver="JPEG", width=image.shape[2], height=image.shape[1],
                       count=image.shape[0], dtype="uint8", crs=f"EPSG:{epsg}", transform=transform,
                       QUALITY=90, WORLDFILE="YES") as dst:
        dst.write(image)
    path.with_suffix(".wld").replace(path.with_suffix(".jgw"))      # GDAL names it .wld
