"""Files shipped with OpenOrienteering Mapper: symbol sets and OSM cross-reference tables.

Used by all layers. Today they are read from the local OOM installation (or the folder
in the environment variable OOM_SYMBOL_SETS); for the cloud they will be shipped with
the program (GPL, see project.md decision 18).
"""

from __future__ import annotations

import os
from pathlib import Path

OOM_SYMBOL_SETS = Path(os.environ.get(
    "OOM_SYMBOL_SETS", r"C:\Program Files\OpenOrienteering Mapper 0.9.6\symbol sets"))

# Symbol sets shipped with OOM 0.9.6 and their scales (Course_Design is for course setting)
SYMBOL_SETS = {
    "ISSprOM 2019": (4000,),
    "ISOM 2017-2": (10000, 15000),
    "ISMTBOM": (5000, 7500, 10000, 15000, 20000),
    "ISSkiOM 2019": (5000, 7500, 10000, 12500, 15000),
}
SCALES = sorted({s for scales in SYMBOL_SETS.values() for s in scales})

# Symbol set -> OSM cross-reference table shipped with OOM 0.9.6 (none for ISMTBOM)
CRT_FILES = {
    "ISSprOM 2019": "OSM-ISSprOM 2019.crt",
    "ISOM 2017-2": "OSM-ISOM 2017-2.crt",
    "ISSkiOM 2019": "OSM-ISSkiOM 2019.crt",
}


def default_symbol_set(scale: int) -> str:
    """Sprint for 1:4000, otherwise the forest standard where it exists."""
    for name in ("ISSprOM 2019", "ISOM 2017-2", "ISMTBOM", "ISSkiOM 2019"):
        if scale in SYMBOL_SETS[name]:
            return name
    raise ValueError(f"Kein Symbolsatz für 1:{scale}")


def symbol_set_file(name: str, scale: int) -> Path:
    """E.g. symbol_set_file('ISOM 2017-2', 10000)."""
    return OOM_SYMBOL_SETS / str(scale) / f"{name}_{scale}.omap"


def crt_file(symbol_set: str) -> Path:
    return OOM_SYMBOL_SETS / CRT_FILES[symbol_set]
