"""Where does the sub-grid spacing in the stratified selection come from? (PIPE-3189)

The grid guarantees at most one point per min_interval of *elapsed* time, not
a minimum separation between retained points.  This locates every retained
pair closer than 0.5 s and reports the raw sampling around it, so the claim
"the tail is the input's own irregular spacing" can be checked rather than
asserted.
"""
import sys

import numpy as np

from pipeline.infrastructure.tablereader import MeasurementSetReader  # noqa: E402
from pipeline.infrastructure.renderer import htmlrenderer  # noqa: E402

MS = sys.argv[1] if len(sys.argv) > 1 else \
    '/scratch/users/pbos/sqld_test/uid___A002_Xf160b6_Xa57a.ms'
DEC = 0.5  # report every retained pair closer than this (s)

ms = MeasurementSetReader.get_measurement_set(MS)
decimate = htmlrenderer._decimate_timestamps

for field in ms.get_fields(intent='TARGET'):
    t = np.asarray(field.time, float)
    sel = decimate(t)
    # indices of the selected timestamps in the original array
    idx = np.searchsorted(t, sel)
    idx = np.clip(idx, 1, len(t) - 1)
    idx = np.where(np.abs(t[idx - 1] - sel) <= np.abs(t[idx] - sel), idx - 1, idx)
    idx = np.unique(idx)

    sp = np.diff(t[idx])
    close = np.where(sp < DEC)[0]
    print('field %d: %d -> %d timestamps; %d retained pairs closer than %.2f s'
          % (field.id, len(t), len(idx), len(close), DEC))
    if not len(close):
        print()
        continue

    for i in close[:5]:
        a, b = idx[i], idx[i + 1]
        print('  retained %d and %d: separation %.4f s' % (a, b, sp[i]))
        lo, hi = max(0, a - 3), min(len(t), b + 4)
        print('    raw timestamps around them:')
        for j in range(lo, hi):
            mark = ' <== retained' if j in set(idx[lo:hi].tolist()) else ''
            gap = '  [GAP %.3f s]' % (t[j] - t[j - 1]) if j > lo and t[j] - t[j - 1] > 0.5 else ''
            print('      #%d  t=%.4f  dt=%.4f%s%s'
                  % (j, t[j], t[j] - t[j - 1] if j else 0.0, gap, mark))
        print()

    # how far below the grid interval does the tail reach, in bulk?
    print('  separation percentiles (s): ' + '  '.join(
        'p%d=%.3f' % (p, np.percentile(sp, p)) for p in (0, 1, 5, 25, 50, 75, 100)))
    print('  retained pairs < 0.5 s: %d of %d (%.2f%%)'
          % (len(close), len(sp), 100.0 * len(close) / len(sp)))
    print('  raw input dt percentiles (s): ' + '  '.join(
        'p%d=%.3f' % (p, np.percentile(np.diff(t), p)) for p in (0, 1, 50, 99, 100)))
    print()
