"""Profile the weblog ZD computation path.

Profiles compute_zd_telmjd_for_ms -- the function we optimised in
PIPE-3088 -- called during weblog rendering (T2_1DetailsRenderer
and T2_2_4Renderer).

Running this on main vs the optimised branch shows the speedup
in context.

Usage:
    source <pipeline-env>
    git checkout <branch>
    python profile_weblog_zd.py
"""

import cProfile
import pstats
import sys

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.tablereader import MeasurementSetReader
from pipeline.infrastructure.renderer.htmlrenderer import compute_zd_telmjd_for_ms

MS_NAME = casa_tools.utils.resolve(
    "pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms"
)

ms = MeasurementSetReader.get_measurement_set(MS_NAME)

profiler = cProfile.Profile()

print(f"Profiling compute_zd_telmjd_for_ms on: {MS_NAME}")
sys.stdout.flush()

profiler.enable()
result = compute_zd_telmjd_for_ms(ms)
profiler.disable()

for fid, v in result.items():
    print(f"  Field {fid}: {len(v['zd'])} timestamps")

print("\n=== Top 40 by cumulative time ===\n")
pstats.Stats(profiler, stream=sys.stdout).sort_stats('cumulative').print_stats(40)

print("\n=== Top 40 by total time ===\n")
pstats.Stats(profiler, stream=sys.stdout).sort_stats('time').print_stats(40)

profiler.dump_stats('/tmp/weblog_zd.prof')
print(f"\nProfile saved to /tmp/weblog_zd.prof")
print("View with: snakeviz /tmp/weblog_zd.prof")
