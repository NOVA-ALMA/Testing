"""Verify PIPE-3189 decimation does not distort the ZD/telmjd weblog plot.

Checks, per TARGET field:

1. Subset property  - every decimated timestamp is an actual full-series
   timestamp (no invented/synthesised values) and endpoints are retained.
2. Range fidelity  - min/max ZD unchanged (these drive the summary stats and
   the plot's y-limits).
3. Shape fidelity  - distance from each kept point to the linear interpolation
   of the full series. This is the error introduced by *dropping* the in-between
   timestamps, so it bounds how wrong the rendered curve can be. Compared
   against the sampling interval actually achieved.
4. Image fidelity  - pixel difference between the before/after `zd_telmjd.png`
   produced by `ZDTELMJDChart`.

Usage:
    conda run -n almaPL26CM python verify_zd_decimation.py <ms_path> <before_png> <after_png>
"""
import datetime
import os
import sys

import numpy as np
from PIL import Image

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.tablereader import MeasurementSetReader
from pipeline.infrastructure.renderer import htmlrenderer

# field.time is seconds since 1858-11-17; telmjd entries are POSIX datetimes.
MJD_ORIGIN_POSIX = datetime.datetime(
    1858, 11, 17, tzinfo=datetime.timezone.utc).timestamp()

MS = (sys.argv[1] if len(sys.argv) > 1
      else casa_tools.utils.resolve(
          "pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms"))
ms = MeasurementSetReader.get_measurement_set(MS)
print("MS: %s" % MS)

data = htmlrenderer.compute_zd_telmjd_for_ms(ms)

# Recompute the *undecimated* series (what main produced) in the same process,
# so both series share one measures()/observing-time cache.
undiluted = {}
me = casa_tools.measures
me.doframe(me.observatory(ms.antenna_array.name))
epoch_dict = {'m0': {'value': 0.0, 'unit': 'd'}, 'refer': 'UTC', 'type': 'epoch'}
for field in ms.get_fields(intent='TARGET'):
    times = sorted(field.time)
    zd = []
    for t in times:
        epoch_dict['m0']['value'] = float(t) / 86400.0
        me.doframe(epoch_dict)
        zd.append(np.degrees(np.pi / 2.0
                             - me.measure(field._mdirection, 'AZELGEO')['m1']['value']))
    undiluted[field.id] = (np.array(times, dtype=float), np.array(zd))

print("=== per-field timestamp counts ===")
for fid in sorted(data):
    n_dec = len(data[fid]['zd'])
    n_full = len(undiluted[fid][1])
    print("field %-3d full=%-7d decimated=%-7d (%.1f%% kept)"
          % (fid, n_full, n_dec, 100.0 * n_dec / n_full))

print("\n=== fidelity of decimation ===")
ok = True
for fid in sorted(data):
    tf = undiluted[fid][0] + MJD_ORIGIN_POSIX          # full, POSIX seconds
    zd_full = undiluted[fid][1]
    td = np.array([t.timestamp() for t in data[fid]['telmjd']])
    zd_dec = np.array(data[fid]['zd'])

    print("field %-3d n=%-6d ZD range=%.4f deg" % (fid, len(zd_dec),
                                                   zd_full.max() - zd_full.min()))

    # 1. subset + endpoint property
    # Tolerance covers (a) float64 ulp at MJD-magnitude seconds (~1e-6 s) and
    # (b) the microsecond rounding of datetime.timedelta. Still 3 orders of
    # magnitude below the 1 s sampling interval, so it cannot mask a real miss.
    TOL = 1e-3
    # Nearest-neighbour match. np.searchsorted alone can land one slot past the
    # true match, because datetime->float conversion can put td a few ulps
    # above the exact full-series value.
    j = np.clip(np.searchsorted(tf, td), 0, len(tf) - 1)
    prev_i = np.clip(j - 1, 0, len(tf) - 1)
    idx = np.where(np.abs(tf[prev_i] - td) < np.abs(tf[j] - td), prev_i, j)
    exact = bool(np.allclose(tf[idx], td, atol=TOL))
    zd_exact = bool(exact and np.allclose(zd_full[idx], zd_dec, atol=1e-9))
    endpoints = bool(len(td) and abs(td[0] - tf[0]) < TOL
                     and abs(td[-1] - tf[-1]) < TOL)
    sorted_ok = bool(np.all(np.diff(td) > 0))
    spacing = float(np.min(np.diff(td))) if len(td) > 1 else float('nan')
    print("  [subset]  decimated pts are real full-series samples: %s" % zd_exact)
    print("  [subset]  first/last t preserved: %-5s  strictly sorted: %-5s  "
          "min spacing=%.3fs" % (endpoints, sorted_ok, spacing))
    ok &= zd_exact and endpoints and sorted_ok

    # 2. range fidelity
    dmin = abs(zd_dec.min() - zd_full.min())
    dmax = abs(zd_dec.max() - zd_full.max())
    print("  [range]   |min delta|=%.3e deg  |max delta|=%.3e deg" % (dmin, dmax))
    ok &= (dmin == 0.0 and dmax == 0.0)

    # 3. shape fidelity: error introduced by dropping the in-between samples
    zd_interp = np.interp(td, tf, zd_full)
    resid = np.abs(zd_dec - zd_interp)
    rng = zd_full.max() - zd_full.min()
    print("  [shape]   deviation from full curve: mean=%.3e max=%.3e deg "
          "(%.3f%% of ZD range)" % (resid.mean(), resid.max(),
                                    100.0 * resid.max() / rng))

if len(sys.argv) > 3:
    before_png, after_png = sys.argv[2], sys.argv[3]
    if os.path.exists(before_png) and os.path.exists(after_png):
        b = np.asarray(Image.open(before_png).convert('RGB'), dtype=np.int16)
        a = np.asarray(Image.open(after_png).convert('RGB'), dtype=np.int16)
        changed = np.any(np.abs(a - b) > 8, axis=2)
        print("\n=== zd_telmjd.png pixel comparison ===")
        print("shape: %s" % (tuple(b.shape),))
        print("pixels differing >8/255: %d of %d (%.3f%%)"
              % (changed.sum(), changed.size, 100.0 * changed.mean()))
        print("max channel diff: %d | mean channel diff: %.3f"
              % (np.abs(a - b).max(), np.abs(a - b).mean()))
    else:
        print("\nimage comparison skipped (missing %s or %s)"
              % (before_png, after_png))

print("\nRESULT: %s" % ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)