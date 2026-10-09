"""Consolidated fidelity evidence for PIPE-3189 (greedy vs stratified).

For each TARGET field, with the full-resolution series obtained by
monkeypatching _decimate_timestamps to identity (i.e. exactly what `main`
renders):

  mean_main      plain sample mean of the full series = what the weblog
                 displays as Avg Zenith Angle (round(..., 2))
  mean_greedy    plain sample mean of the greedy selection
  mean_strat     plain sample mean of the stratified selection
  obs_time_mean  time-weighted mean over OBSERVED time only (integrated
                 segment-wise, gaps excluded) -- the reference for "which
                 decimator preserves the intended statistic"

  shape_*        max/mean deviation of the DECIMATED curve, linearly
                 interpolated back onto the full time base, from the full
                 curve.  This is what the plot actually draws, so it is the
                 metric that matters visually.  (verify_zd_decimation.py's
                 "shape" column instead compares each retained point against
                 the full curve at that same timestamp -- since retained
                 points are exact samples that is ~0 by construction and only
                 tests determinism.)

Also reports the spacing of each selection, which is where the grid rule and
the minimum-gap rule differ.

Usage:
    conda run -n almaPL26CM python fidelity_summary.py <ms_path> <label>
"""
import sys

import numpy as np

sys.path.insert(0, '/tmp/opencode')
from greedy_impl import greedy  # noqa: E402

from pipeline.infrastructure.tablereader import MeasurementSetReader  # noqa: E402
from pipeline.infrastructure.renderer import htmlrenderer  # noqa: E402


def select(t, fn):
    """Indices of t that fn selects (fn returns timestamps)."""
    chosen = fn(t)
    idx = np.searchsorted(t, chosen)
    idx = np.clip(idx, 1, len(t) - 1)
    idx = np.where(np.abs(t[idx - 1] - chosen) <= np.abs(t[idx] - chosen),
                   idx - 1, idx)
    return np.unique(idx)


def main(ms_path, label):
    ms = MeasurementSetReader.get_measurement_set(ms_path)
    real = htmlrenderer._decimate_timestamps
    htmlrenderer._decimate_timestamps = lambda times, *a, **k: times
    full = htmlrenderer.compute_zd_telmjd_for_ms(ms)
    htmlrenderer._decimate_timestamps = real

    print('=' * 96)
    print('%s   %s' % (label, ms_path))
    print('=' * 96)
    hdr = ('%-5s %6s | %6s %6s | %8s %8s %8s | %9s %9s | %9s %9s'
           % ('fld', 'n_full', 'n_grd', 'n_str',
              'mean_main', 'greedy', 'strat',
              'g-main', 's-main', 'g-truth', 's-truth'))
    print(hdr)
    print('-' * len(hdr))

    flat = {'main': [], 'greedy': [], 'strat': []}
    for fid in sorted(full):
        z = np.asarray(full[fid]['zd'], float)
        t = np.array([x.timestamp() for x in full[fid]['telmjd']])
        dt = np.diff(t)

        # reference: time-weighted mean over observed time, integrated in
        # segments so that unobserved gaps contribute neither numerator nor
        # denominator
        obs = dt <= 1.0
        truth = float((0.5 * (z[:-1] + z[1:]) * dt)[obs].sum() / dt[obs].sum())

        ig = select(t, greedy)
        istr = select(t, lambda a: real(a))

        # shape: interpolate the decimated curve back onto the full time base
        shape = {}
        for name, idx in (('greedy', ig), ('strat', istr)):
            zi = np.interp(t, t[idx], z[idx])
            d = np.abs(zi - z)
            shape[name] = (float(d.mean()), float(d.max()))

        m_main, m_g, m_s = float(z.mean()), float(z[ig].mean()), float(z[istr].mean())
        flat['main'].append(m_main)
        flat['greedy'].append(m_g)
        flat['strat'].append(m_s)

        print('%-5d %6d | %6d %6d | %8.4f %8.4f %8.4f | %+9.4f %+9.4f | %+9.4f %+9.4f'
              % (fid, len(z), len(ig), len(istr),
                 m_main, m_g, m_s,
                 m_g - m_main, m_s - m_main, m_g - truth, m_s - truth))
        print('%-5s %6s | %6s %6s | observed-time mean %.4f' % ('', '', '', '', truth))
        print('%-5s %6s | %6s %6s | shape dev (interp onto full): greedy mean %.2e max %.2e | strat mean %.2e max %.2e deg'
              % ('', '', '', '', shape['greedy'][0], shape['greedy'][1],
                 shape['strat'][0], shape['strat'][1]))

    print()
    print('displayed Avg Zenith Angle over all TARGET fields (weblog uses round(x, 2)):')
    for key in ('main', 'greedy', 'strat'):
        v = float(np.average(flat[key]))
        print('   %-7s %.4f  ->  %.2f' % (key, v, round(v, 2)))
    print()

    # spacing of each selection, per field
    print('spacing between retained timestamps (s):')
    for fid in sorted(full):
        t = np.array([x.timestamp() for x in full[fid]['telmjd']])
        for name, fn in (('greedy', greedy), ('strat', lambda a: real(a))):
            idx = select(t, fn)
            sp = np.diff(t[idx])
            print('   fld %d %-6s n=%5d  min %.3f  p1 %.3f  p50 %.3f  p99 %.3f  max %.3f'
                  % (fid, name, len(idx), sp.min(), np.percentile(sp, 1),
                     np.percentile(sp, 50), np.percentile(sp, 99), sp.max()))
    print()
    rng = float(np.ptp(np.concatenate([np.asarray(full[f]['zd'], float)
                                       for f in sorted(full)])))
    print('ZD range over all fields: %.4f deg' % rng)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
