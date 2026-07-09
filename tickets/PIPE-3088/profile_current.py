import sys
sys.path.insert(0, '/scratch/users/pbos/pipeline')
from line_profiler import LineProfiler
from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.tablereader import MeasurementSetReader

MS_NAME = casa_tools.utils.resolve("pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms")
ms = MeasurementSetReader.get_measurement_set(MS_NAME)

from pipeline.infrastructure.renderer.htmlrenderer import compute_zd_telmjd_for_ms

lp = LineProfiler()
lp.add_function(compute_zd_telmjd_for_ms)
lp_wrapper = lp(compute_zd_telmjd_for_ms)
result = lp_wrapper(ms)
lp.print_stats(output_unit=1e-3)
