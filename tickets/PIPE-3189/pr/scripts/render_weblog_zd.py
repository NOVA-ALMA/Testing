"""Render the T2-2-4 (Sky Setup) weblog page before/after decimation (PIPE-3189).

Renders the page embedding the Zenith Angle vs. Telescope MJD scatter plot
produced by compute_zd_telmjd_for_ms(), so the visual output can be compared
between main and the PIPE-3189 branch.

Usage:
    conda run -n almaPL26CM python render_weblog_zd.py <output_dir> [ms_path]

MS is used in place (no copy) — important for multi-GB SQLD datasets. The
output_dir is wiped first so a failed run cannot leave a stale/empty page behind
(the renderers skip any page whose file already exists).
"""
import os
import shutil
import sys
import traceback

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.launcher import Context
from pipeline.infrastructure.tablereader import MeasurementSetReader
from pipeline.infrastructure.renderer import htmlrenderer

try:
    from pipeline.infrastructure.renderer.htmlrenderer import _decimate_timestamps
    HAS_DECIMATION = True
except ImportError:
    HAS_DECIMATION = False

DEFAULT_MS = casa_tools.utils.resolve(
    "pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms"
)

output_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'weblog_out')
ms_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MS

if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
os.makedirs(output_dir, exist_ok=True)

print("=" * 68)
print("MS  : %s" % ms_path)
print("out : %s" % output_dir)
print("mode: %s" % ("PIPE-3189 (decimated)" if HAS_DECIMATION else "main (no decimation)"))
# Guard against a silently-wrong baseline: cwd can shadow PYTHONPATH.
import pipeline.infrastructure.renderer.htmlrenderer as _hr
print("module: %s" % _hr.__file__)
print("=" * 68)

context = Context()
context.report_dir = output_dir

ms = MeasurementSetReader.get_measurement_set(ms_path)
context.observing_run.add_measurement_set(ms)

# T2_2_4Renderer.get_display_context() calls utils.contains_single_dish(context),
# which inspects context.results[0]. A bare Context() has no results, so seed a
# placeholder whose repr is not an SD result (i.e. single-dish interferometer).
context.results.append(type('ImportDataResults', (), {})())

html_path = os.path.join(output_dir, 'session%s' % ms.session,
                         ms.basename, 't2-2-4.html')
zd_plot = os.path.join(output_dir, 'session%s' % ms.session,
                       ms.basename, 'zd_telmjd.png')

try:
    htmlrenderer.T2_2_4Renderer.render(context)
except Exception:
    traceback.print_exc()
    print("RENDER FAILED", file=sys.stderr)

# Report what actually made it to disk, rather than assuming success.
for label, path in (('html', html_path), ('zd_telmjd.png', zd_plot)):
    if os.path.exists(path):
        print("%-14s %9d bytes  %s" % (label, os.path.getsize(path), path))
    else:
        print("%-14s MISSING      %s" % (label, path))

data = htmlrenderer.compute_zd_telmjd_for_ms(ms)
raw_counts = {f.id: len(f.time) for f in ms.get_fields(intent='TARGET')}
for field_id in sorted(data):
    zd = data[field_id]['zd']
    telmjd = data[field_id]['telmjd']
    print("\nField %d:" % field_id)
    print("  timestamps:    %d (of %d raw)"
          % (len(zd), raw_counts.get(field_id, len(zd))))
    print("  ZD min/max:    %.4f / %.4f deg" % (min(zd), max(zd)))
    print("  ZD mean:       %.4f deg" % (sum(zd) / len(zd)))
    print("  Time range:    %s to %s" % (telmjd[0], telmjd[-1]))

if not os.path.exists(html_path) or os.path.getsize(html_path) == 0:
    sys.exit(1)