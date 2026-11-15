"""Georeferencing: GK zone, OOM grid compensation, declination and paper coordinates.

Expected values come from files saved by OOM 0.9.6 (data/) and from the
documented test run (project.md, "Wiedereinstieg").
"""

import math
import re
from datetime import date

import pytest

from olprep.verarbeitung.georef import Georeferencing, decimal_year, gk_epsg, oom_grid_compensation

from conftest import DATA


def georef_attrs(path):
    """Attributes of <georeferencing> and its reference points from an .omap file."""
    text = path.read_text(encoding="utf-8")
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r"<georeferencing[^>]*>", text).group(0)))
    attrs.update(re.search(r'<ref_point_deg lat="(?P<lat>[^"]+)" lon="(?P<lon>[^"]+)"', text).groupdict())
    return attrs


@pytest.mark.parametrize("lon, epsg", [
    (11.40, 31254),             # Innsbruck, M28
    (11 + 50 / 60 - 1e-9, 31254),
    (11 + 50 / 60, 31255),      # zone border 11°50'
    (14.77, 31255),             # Waidhofen/Ybbs, M31
    (14 + 50 / 60, 31256),      # zone border 14°50'
    (16.42, 31256),             # Vienna, M34
])
def test_gk_zone(lon, epsg):
    assert gk_epsg(lon) == epsg


def test_decimal_year():
    assert decimal_year(date(2026, 1, 1)) == 2026.0
    assert decimal_year(date(2026, 7, 2)) == pytest.approx(2026.5, abs=0.002)


def test_grid_compensation_matches_oom_reference():
    """data/referenz_georef.omap was set up in OOM with declination 0: grivation = -convergence."""
    a = georef_attrs(DATA / "referenz_georef.omap")
    convergence, factor = oom_grid_compensation(31256, float(a["lat"]), float(a["lon"]))
    assert round(-convergence, 2) == float(a["grivation"])
    assert round(factor, 6) == float(a["grid_scale_factor"])


def test_declination_consistent_with_oom_roundtrip():
    """OOM warns on load unless declination == round(grivation + convergence, 2)."""
    a = georef_attrs(DATA / "test_stadion_roundtrip.omap")
    convergence, _ = oom_grid_compensation(31256, float(a["lat"]), float(a["lon"]))
    assert round(float(a["grivation"]) + convergence, 2) == float(a["declination"])


def test_stadion_values_on_fixed_date():
    """Documented output of make_testfile.py from 2026-11-01 on."""
    g = Georeferencing.create(31256, 10000, 6601.4, 340984.2, on=date(2026, 11, 1))
    assert (g.declination, g.grivation, g.grid_scale_factor) == (5.39, 5.33, 1.000005)
    assert g.ref_lat == pytest.approx(48.2072, abs=1e-3)
    assert g.ref_lon == pytest.approx(16.4205, abs=1e-3)


def test_to_paper():
    g = Georeferencing.create(31256, 4000, 6601.4, 340984.2, on=date(2026, 11, 1))
    assert g.to_paper(6601.4, 340984.2) == (0, 0)
    # 100 m north at 1:4000 = 25 mm on paper, turned by the grivation (paper "up" = magnetic north)
    x, y = g.to_paper(6601.4, 340984.2 + 100)
    assert math.hypot(x, y) == pytest.approx(25_000 / g.grid_scale_factor, abs=1)
    assert y < 0                                        # up on paper = negative y
    assert math.degrees(math.atan2(-x, -y)) == pytest.approx(g.grivation, abs=0.01)
