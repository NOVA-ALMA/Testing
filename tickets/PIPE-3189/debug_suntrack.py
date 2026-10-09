"""Reproduce the silent solar_el_vs_time failure (PIPE-3189).

SunTrackChart.plot() swallows every exception from plotsuntrack.plot_suntrack
with a bare `except:`, so a failed solar plot just silently disappears from the
weblog.  This calls plot_suntrack directly so the traceback is visible.
"""
import os
import sys
import traceback

from pipeline.infrastructure import casa_tools
import pipeline.infrastructure.renderer.htmlrenderer as _hr

MS = sys.argv[1] if len(sys.argv) > 1 else casa_tools.utils.resolve(
    "pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms")
OUT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/opencode/solar_debug.png'

print('htmlrenderer module: %s' % _hr.__file__)
print('ms                : %s' % MS)
print('figfile           : %s' % OUT)

from pipeline.infrastructure.displays import summary  # noqa: E402

_orig = summary.plotsuntrack.plot_suntrack


def _loud(*args, **kwargs):
    try:
        return _orig(*args, **kwargs)
    except BaseException:
        print('\n!!! plot_suntrack raised:', file=sys.stderr)
        traceback.print_exc()
        print('!!! args=%r kwargs=%r' % (args, kwargs), file=sys.stderr)
        raise


summary.plotsuntrack.plot_suntrack = _loud

if os.path.exists(OUT):
    os.remove(OUT)

# Drive it exactly the way the renderer does, bare except and all.
from pipeline.infrastructure.launcher import Context  # noqa: E402
from pipeline.infrastructure.tablereader import MeasurementSetReader  # noqa: E402

context = Context()
context.report_dir = os.path.dirname(OUT)
ms = MeasurementSetReader.get_measurement_set(MS)
context.observing_run.add_measurement_set(ms)

chart = summary.SunTrackChart(context, ms)
print('figfile resolved by chart: %s' % chart.figfile)
try:
    os.makedirs(os.path.dirname(chart.figfile), exist_ok=True)
except OSError:
    pass

plot = chart.plot()
print('\nSunTrackChart.plot() -> %r' % (plot,))
print('file exists: %s' % os.path.exists(chart.figfile))
if plot is None:
    print('\nSOLAR PLOT SILENTLY DROPPED (exception was swallowed by the bare except)')
    sys.exit(1)
