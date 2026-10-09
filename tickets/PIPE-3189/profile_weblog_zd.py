"""Profile the weblog ZD/telmjd computation — PIPE-3189.

Profiles compute_zd_telmjd_for_ms() to show where time is spent and how
decimation reduces the number of CASA measures calls. Works on both branches
(via PYTHONPATH to a main worktree for the baseline).

Usage:
    conda run -n almaPL26CM python profile_weblog_zd.py [ms_path]

MS is used in place (no copy). --copy is available for isolation.
"""
import argparse
import cProfile
import io
import os
import pstats
import shutil
import sys
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
p.add_argument('--copy', action='store_true')
args = p.parse_args()

if args.copy:
    workdir = tempfile.mkdtemp(prefix='zd_weblog_profile_')
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
# Guard against a silently-wrong baseline: cwd can shadow PYTHONPATH.
import pipeline.infrastructure.renderer.htmlrenderer as _hr
print("module: %s" % _hr.__file__)
print("=" * 68)

for field in ms.get_fields(intent='TARGET'):
    times = field.time
    print("\nField %d (%s): %d timestamps" % (field.id, field.name, len(times)))
    if HAS_DECIMATION:
        print("  decimated to %d (%.1f%% reduction)"
              % (len(_decimate_timestamps(times)),
                 100 * (1 - len(_decimate_timestamps(times)) / len(times))))
    else:
        print("  decimation: NOT ACTIVE (main branch)")

prof = cProfile.Profile()
prof.enable()
t0 = time.perf_counter()
result = compute_zd_telmjd_for_ms(ms)
total = time.perf_counter() - t0
prof.disable()

total_zd = sum(len(fd['zd']) for fd in result.values())
print("\nTotal compute_zd_telmjd_for_ms(): %.3f s" % total)
print("Total ZD values computed: %d" % total_zd)
print("Time per ZD value: %.3f ms" % (total / total_zd * 1000))

s = io.StringIO()
pstats.Stats(prof, stream=s).sort_stats('cumtime').print_stats()
lines = s.getvalue().split('\n')
print("\n--- measures calls ---")
for l in lines:
    if 'measures_doframe' in l or 'measures_measure' in l or 'decimate' in l.lower():
        print("  %s" % l.strip())

print("\n--- Top 15 cumulative ---")
pstats.Stats(prof, stream=sys.stdout).sort_stats('cumtime').print_stats(15)

if workdir:
    os.chdir("/")
    shutil.rmtree(workdir, ignore_errors=True)