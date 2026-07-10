"""Time compute_zd_telmjd_for_ms from the pipeline code.

Check out any branch and run this — it times whatever implementation
is in htmlrenderer right now.

Usage:
    source <pipeline-env>
    python time_pipeline_zd.py
"""

import timeit

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.tablereader import MeasurementSetReader
from pipeline.infrastructure.renderer.htmlrenderer import compute_zd_telmjd_for_ms

MS_NAME = casa_tools.utils.resolve(
    "pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms"
)

ms = MeasurementSetReader.get_measurement_set(MS_NAME)

# Warmup
result = compute_zd_telmjd_for_ms(ms)
for fid, v in result.items():
    print(f"  Field {fid}: {len(v['zd'])} timestamps, "
          f"zd range [{min(v['zd']):.6f}, {max(v['zd']):.6f}] deg")
print()

N = 200
t = timeit.timeit(lambda: compute_zd_telmjd_for_ms(ms), number=N)
print(f"{t/N*1e3:.3f} ms  ({t:.3f}s for {N} runs)")
