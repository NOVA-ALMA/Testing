"""Time the weblog ZD/telmjd computation — PIPE-3189.

Measures compute_zd_telmjd_for_ms() (called from the weblog renderer) with and
without timestamp decimation. Reports the sampling interval actually present in
the MS, so SQLD (dense spectral-line) data is distinguishable from continuum.

Works on both branches: the presence of _decimate_timestamps selects the mode, so
the same script can be run against main (via PYTHONPATH to a main worktree) and
against the PIPE-3189 branch.

Usage:
    conda run -n almaPL26CM python time_weblog_zd.py [ms_path]

If ms_path is omitted, defaults to the small unittest MS. The MS is used in
place (no copy), so this is safe for multi-GB SQLD datasets. --copy is provided
for the small MS if you want an isolated copy.
"""
import argparse
import os
import shutil
import tempfile
import time

import numpy as np

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.launcher import Context
from pipeline.infrastructure.tablereader import MeasurementSetReader
from pipeline.infrastructure.renderer.htmlrenderer import (
    compute_zd_telmjd_for_ms,
)
from pipeline.infrastructure.utils.utils import clear_time_cache

# Present only on the PIPE-3189 branch.
try:
    from pipeline.infrastructure.renderer.htmlrenderer import _decimate_timestamps
    HAS_DECIMATION = True
except ImportError:
    HAS_DECIMATION = False

DEFAULT_MS = casa_tools.utils.resolve(
    "pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms"
)

p = argparse.ArgumentParser()
p.add_argument('ms', nargs='?', default=DEFAULT_MS)
p.add_argument('--runs', type=int, default=5)
p.add_argument('--copy', action='store_true',
               help='copy the MS to a temp dir first (isolate; slow for big MS)')
args = p.parse_args()

if args.copy:
    workdir = tempfile.mkdtemp(prefix='zd_weblog_timing_')
    ms_path = os.path.join(workdir, os.path.basename(args.ms))
    shutil.copytree(args.ms, ms_path)
    os.chdir(workdir)
else:
    workdir = None
    ms_path = args.ms

clear_time_cache()

ms = MeasurementSetReader.get_measurement_set(ms_path)

print("=" * 68)
print("MS: %s" % ms_path)
print("mode: %s" % ("PIPE-3189 (decimated)" if HAS_DECIMATION else "main (no decimation)"))
# Guard against a silently-wrong baseline: cwd can shadow PYTHONPATH when
# running `python -c` from inside the pipeline checkout.
import pipeline.infrastructure.renderer.htmlrenderer as _hr
print("module: %s" % _hr.__file__)
print("=" * 68)

fields = ms.get_fields(intent='TARGET')
for field in fields:
    times = field.time
    dt = np.diff(np.sort(np.asarray(times, dtype=float))) if len(times) > 1 else np.array([0.0])
    print("\nField %d (%s):" % (field.id, field.name))
    print("  Original timestamps:  %8d" % len(times))
    print("  Integration interval: min=%.4fs median=%.4fs max=%.4fs"
          % (dt.min(), np.median(dt), dt.max()))
    span = (np.max(times) - np.min(times)) if len(times) > 1 else 0.0
    if span:
        print("  Time span:            %.1f s (%.2f h)" % (span, span / 3600.0))
    if HAS_DECIMATION:
        dec = _decimate_timestamps(times)
        print("  Decimated timestamps: %8d" % len(dec))
        print("  Reduction:            %7.1f%%" % (100 * (1 - len(dec) / len(times))))
    else:
        print("  Decimation:           NOT ACTIVE (main branch)")

n_runs = args.runs
times = []
print("\nTiming compute_zd_telmjd_for_ms() x%d ..." % n_runs)
result = None
for i in range(n_runs):
    t0 = time.perf_counter()
    result = compute_zd_telmjd_for_ms(ms)
    elapsed = time.perf_counter() - t0
    times.append(elapsed)
    print("  Run %d: %8.3f s" % (i + 1, elapsed))

total_zd = sum(len(fd['zd']) for fd in result.values())
mean = sum(times) / len(times)
print("\nResults:")
print("  Mean: %8.3f s" % mean)
print("  Min:  %8.3f s" % min(times))
print("  Max:  %8.3f s" % max(times))
print("  Total ZD values: %d" % total_zd)
print("  Time per ZD: %.3f ms" % (mean / total_zd * 1000))

if workdir:
    os.chdir("/")
    shutil.rmtree(workdir, ignore_errors=True)