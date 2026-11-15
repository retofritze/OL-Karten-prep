"""Orthophoto from WMTS tile services (Stadt Wien, basemap.at) as a georeferenced image.

Tiles (Web Mercator, EPSG:3857) are downloaded for a bounding box in the map CRS,
cached on disk, mosaicked and reprojected into the map CRS. The result is an RGB
array with its geotransform; ausgabe.bilder writes it as JPG + world file.
See documentation/datenquellen.md.
"""

from __future__ import annotations

import math
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np
import pyproj
import rasterio
import requests
from rasterio.errors import NotGeoreferencedWarning
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

from .netz import CACHE_DIR as _CACHE_ROOT, USER_AGENT

ORIGIN = 20037508.342789244          # half the extent of EPSG:3857
TILE = 256
CACHE_DIR = _CACHE_ROOT / "tiles"
WORKERS = 6

# One keep-alive session for all downloads (a new TLS connection per tile is slow
# and made the server drop connections in the first test)
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=WORKERS))


@dataclass(frozen=True)
class TileSource:
    key: str            # cache folder and file name
    title: str
    url: str            # {z} {y} {x}
    max_zoom: int       # highest zoom with real detail (see datenquellen.md)
    attribution: str


WIEN = TileSource(
    "wien_lb", "Orthofoto Stadt Wien (aktueller Jahrgang)",
    "https://mapsneu.wien.gv.at/wmts/lb/farbe/google3857/{z}/{y}/{x}.jpeg",
    20, "Orthofoto: Stadt Wien – data.wien.gv.at (CC BY 4.0)")
BASEMAP = TileSource(
    "basemap", "basemap.at Orthofoto",
    "https://mapsneu.wien.gv.at/basemap/bmaporthofoto30cm/normal/google3857/{z}/{y}/{x}.jpeg",
    20, "Orthofoto: basemap.at (CC BY 4.0)")
SOURCES = (WIEN, BASEMAP)       # in order of preference


class TileMissing(Exception):
    pass


def tile_size_m(z: int) -> float:
    return 2 * ORIGIN / 2 ** z


def tile_range(bounds_3857: tuple[float, float, float, float], z: int) -> tuple[range, range]:
    """Columns and rows of all tiles covering (xmin, ymin, xmax, ymax) in EPSG:3857."""
    xmin, ymin, xmax, ymax = bounds_3857
    s = tile_size_m(z)
    cols = range(math.floor((xmin + ORIGIN) / s), math.floor((xmax + ORIGIN) / s) + 1)
    rows = range(math.floor((ORIGIN - ymax) / s), math.floor((ORIGIN - ymin) / s) + 1)
    return cols, rows


def fetch_tile(src: TileSource, z: int, x: int, y: int) -> bytes:
    """Tile as JPEG bytes, from the disk cache if present. Raises TileMissing on HTTP 404."""
    cached = CACHE_DIR / src.key / str(z) / str(y) / f"{x}.jpeg"
    if cached.exists():
        return cached.read_bytes()
    url = src.url.format(z=z, x=x, y=y)
    for attempt in range(6):
        try:
            response = _session.get(url, timeout=30)
            if response.status_code == 404:
                raise TileMissing(f"{src.key} {z}/{y}/{x}")
            response.raise_for_status()
            data = response.content
            break
        except requests.RequestException:
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)        # 1, 2, 4, 8, 16 s
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


def _decode(data: bytes) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)     # plain JPEG tile
        with MemoryFile(data) as mem, mem.open() as ds:
            return ds.read((1, 2, 3))


def covers(src: TileSource, bounds_3857: tuple[float, float, float, float], z: int) -> bool:
    """Quick check with the corner and centre tiles whether the source has data here."""
    cols, rows = tile_range(bounds_3857, z)
    probes = {(c, r) for c in (cols[0], cols[-1], cols[len(cols) // 2])
              for r in (rows[0], rows[-1], rows[len(rows) // 2])}
    try:
        for c, r in probes:
            fetch_tile(src, z, c, r)
    except TileMissing:
        return False
    return True


def mosaic(src: TileSource, bounds_3857: tuple[float, float, float, float], z: int,
           workers: int = WORKERS) -> tuple[np.ndarray, rasterio.Affine]:
    """All tiles of the bounding box as one RGB array (3, H, W) in EPSG:3857."""
    cols, rows = tile_range(bounds_3857, z)
    image = np.zeros((3, len(rows) * TILE, len(cols) * TILE), dtype=np.uint8)
    jobs = [(c, r) for r in rows for c in cols]
    print(f"  {src.key}: Zoom {z}, {len(jobs)} Kacheln")
    with ThreadPoolExecutor(workers) as pool:
        for (c, r), data in zip(jobs, pool.map(lambda cr: fetch_tile(src, z, *cr), jobs)):
            i, j = (r - rows[0]) * TILE, (c - cols[0]) * TILE
            image[:, i:i + TILE, j:j + TILE] = _decode(data)
    s = tile_size_m(z)
    transform = from_origin(-ORIGIN + cols[0] * s, ORIGIN - rows[0] * s, s / TILE, s / TILE)
    return image, transform


@dataclass
class Orthofoto:
    image: np.ndarray           # uint8 RGB (3, H, W) in the map CRS
    transform: rasterio.Affine
    source: TileSource
    resolution: float           # m per pixel


def orthofoto(epsg: int, bounds: tuple[float, float, float, float],
              sources: tuple[TileSource, ...] = SOURCES) -> Orthofoto:
    """Orthophoto for bounds (xmin, ymin, xmax, ymax in EPSG:<epsg>) in the map CRS.

    Uses the first source that covers the whole area, at its highest zoom
    available there.
    """
    to_3857 = pyproj.Transformer.from_crs(epsg, 3857, always_xy=True)
    b3857 = to_3857.transform_bounds(*bounds, densify_pts=21)
    lat = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True).transform(
        (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)[1]

    for src in sources:
        for z in range(src.max_zoom, src.max_zoom - 2, -1):
            if not covers(src, b3857, z):
                continue
            try:
                image, transform = mosaic(src, b3857, z)
            except TileMissing as e:
                print(f"  {src.key}: Zoom {z} unvollständig ({e})")
                continue
            # Ground resolution of the tiles (Mercator scale 1/cos(lat)), rounded to cm
            res = round(tile_size_m(z) / TILE * math.cos(math.radians(lat)), 2)
            out, out_transform = _reproject(image, transform, epsg, bounds, res)
            return Orthofoto(out, out_transform, src, res)
    raise RuntimeError("Keine Orthofoto-Quelle deckt den Bereich ab.")


def _reproject(image: np.ndarray, transform: rasterio.Affine, epsg: int,
               bounds: tuple[float, float, float, float], res: float) -> tuple[np.ndarray, rasterio.Affine]:
    xmin, ymin, xmax, ymax = bounds
    width, height = math.ceil((xmax - xmin) / res), math.ceil((ymax - ymin) / res)
    dst_transform = from_origin(xmin, ymax, res, res)
    out = np.full((3, height, width), 255, dtype=np.uint8)
    reproject(image, out, src_transform=transform, src_crs="EPSG:3857",
              dst_transform=dst_transform, dst_crs=f"EPSG:{epsg}",
              resampling=Resampling.bilinear, src_nodata=None, dst_nodata=None)
    return out, dst_transform
