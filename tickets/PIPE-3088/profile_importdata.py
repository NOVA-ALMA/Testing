"""Profile the importdata MS read path including ZD computation.

Profiles ObseringRunReader.get_observing_run() which is the core
of what importdata.prepare() does per MS.  This covers:

  - MS table reads (ANTENNA, FIELD, SPECTRAL_WINDOW, etc.)
  - Field.set_zd_telmjd → compute_zenith_distance (the suspected bottleneck)
  - Scan construction, state/field/source linking

This is the relevant profiler script for PIPE-3088's original complaint
(slow importdata tasks).

Usage:
    source <pipeline-env>
    python profile_importdata.py

Results are printed and also saved to /tmp/importdata.prof for
interactive inspection with snakeviz or runsnake.
"""

import cProfile
import pstats
import sys

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.tablereader import ObservingRunReader

MS_NAME = casa_tools.utils.resolve(
    "pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms"
)

profiler = cProfile.Profile()

print(f"Profiling get_observing_run on: {MS_NAME}")
sys.stdout.flush()

profiler.enable()
observing_run = ObservingRunReader.get_observing_run(MS_NAME)
profiler.disable()

# Print top 40 cumulative time consumers
print("\n=== Top 40 by cumulative time ===\n")
pstats.Stats(profiler, stream=sys.stdout).sort_stats('cumulative').print_stats(40)

print("\n=== Top 40 by total time ===\n")
pstats.Stats(profiler, stream=sys.stdout).sort_stats('time').print_stats(40)

# Save for interactive exploration
profiler.dump_stats('/tmp/importdata.prof')
print(f"\nProfile saved to /tmp/importdata.prof")
print("View with: snakeviz /tmp/importdata.prof")
