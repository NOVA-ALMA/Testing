"""IERS data canary for the ZD regression test.

Two independent checks:
  * fingerprint - sha256 of the numeric values of the rows measures() uses
  * probe       - zenith distance of a fixed direction at fixed epochs
Both are ~50 ms and need no test data.
"""
import hashlib
import math
import struct

import pytest

from pipeline.infrastructure import casa_tools

TABLES = ("IERSeop97", "IERSpredict", "TAI_UTC", "Observatories")
COLS = {"IERSeop97": ("dUT1", "x", "y"), "IERSpredict": ("dUT1", "x", "y"),
        "TAI_UTC": ("dUTC", "Offset"), "Observatories": ("Long", "Lat", "Height")}
WINDOW = (56000.0, 61000.0)
WINDOW_FP = "60ece9bd21e01000"
PROBE_MJDS = (57000.0, 58007.24477111111, 59000.0, 60967.0)
PROBE_ZD = (84.85496683766004, 84.13690167706928, 104.77194567360485, 128.6106471448433)


def measures_fingerprint(window=WINDOW):
    digest = hashlib.sha256()
    for table, cols in COLS.items():
        with casa_tools.TableReader(casa_tools.utils.resolve("geodetic/" + table)) as tab:
            mjd = None if table == "Observatories" else tab.getcol("MJD")
            for col in cols:
                vals = tab.getcol(col)
                if mjd is not None:
                    vals = [v for m, v in zip(mjd, vals) if window[0] <= m <= window[1]]
                for v in vals:
                    digest.update(struct.pack(">d", float(v)))
    return digest.hexdigest()[:16]


def probe_zd(mjds=PROBE_MJDS):
    me = casa_tools.measures
    me.doframe(me.observatory("ALMA"))
    d = me.direction("J2000", {"value": math.radians(83.6), "unit": "rad"},
                     {"value": math.radians(22.0), "unit": "rad"})
    for mjd in mjds:
        me.doframe(me.epoch("UTC", {"value": mjd, "unit": "d"}))
        yield 90.0 - math.degrees(me.measure(d, "AZELGEO")["m1"]["value"])


@pytest.mark.unit
def test_measures_snapshot_is_known():
    fp = measures_fingerprint()
    if fp != WINDOW_FP:
        pytest.fail(f"geodetic tables changed: window fingerprint {fp} "
                    f"(reference {WINDOW_FP}); re-derive the ZD reference values")


@pytest.mark.unit
def test_zd_probe():
    assert list(probe_zd()) == pytest.approx(PROBE_ZD, rel=1e-12)
