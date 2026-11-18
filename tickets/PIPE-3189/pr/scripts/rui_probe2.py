"""PIPE-3189 follow-up: curve fidelity + Field.time.min() side effects.

Run on eddington, from the PIPE-3189 branch checkout:
  conda run -n almaPL26CM python rui_probe2.py \
      --configfile=/scratch/users/pbos/probe_siteconfig.py
"""
import time

import numpy as np

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure import tablereader
from pipeline.infrastructure.renderer import htmlrenderer

MS = "/scratch/users/pbos/sqld_test/uid___A002_Xf160b6_Xa57a.ms"
get_ms = tablereader.MeasurementSetReader.get_measurement_set


def rui_non_sqld_times(msmd):
    """Exactly the helper in PIPE-3189-strip-off-sqld-time-stamp."""
    sqld = set(msmd.almaspws(sqld=True))
    if not sqld:
        return None
    ns = [i for i in range(msmd.nspw()) if i not in sqld]
    if not ns:
        return None
    return np.unique(np.concatenate(list(msmd.timesforspws(ns).values())))


orig_read_table = tablereader.FieldTable._read_table
orig_decimate = htmlrenderer._decimate_timestamps


def rui_read_table(msmd):
    rows = orig_read_table(msmd)
    nt = rui_non_sqld_times(msmd)
    out = []
    for r in rows:
        if nt is not None:
            filtered = np.intersect1d(r[3], nt, assume_unique=True)
            r = list(r)
            r[3] = filtered if len(filtered) > 0 else r[3]
        out.append(tuple(r))
    return out


def run(label, decimate, read_table):
    htmlrenderer._decimate_timestamps = decimate
    tablereader.FieldTable._read_table = read_table
    best = None
    try:
        for _ in range(2):
            t0 = time.perf_counter()
            ms = get_ms(MS)
            res = htmlrenderer.compute_zd_telmjd_for_ms(ms)
            dt = time.perf_counter() - t0
            best = dt if best is None else min(best, dt)
    finally:
        htmlrenderer._decimate_timestamps = orig_decimate
        tablereader.FieldTable._read_table = orig_read_table
    n = sum(len(v["zd"]) for v in res.values())
    print(f"  {label:<22} {n:7d} ZD points   {best:8.3f} s")
    return res


print("real compute_zd_telmjd_for_ms, wall clock (best of 2)")
main_res = run("main (raw)", lambda t: t, orig_read_table)
strat_res = run("stratified (PR)", orig_decimate, orig_read_table)
rui_res = run("Rui (SQLD stripped)", lambda t: t, rui_read_table)
both_res = run("Rui + stratified", orig_decimate, rui_read_table)


def arr(x):
    if len(x) and hasattr(x[0], "timestamp"):
        return np.asarray([v.timestamp() for v in x], dtype=float)
    return np.asarray(x, dtype=float)


print("\ncurve fidelity vs main (decimated curve interpolated onto main's time base)")
for label, res in (("stratified", strat_res), ("Rui", rui_res), ("Rui+strat", both_res)):
    for f in sorted(main_res):
        zd_full = arr(main_res[f]["zd"])
        t_full = arr(main_res[f]["telmjd"])
        zd = arr(res[f]["zd"])
        t = arr(res[f]["telmjd"])
        dev = np.abs(np.interp(t_full, t, zd) - zd_full)
        print(f"  {label:<11} field {f}: max {dev.max():.3e} deg "
              f"({dev.max() * 3600:.2f} arcsec), mean {dev.mean():.3e} deg")

print("\nrange stats used by the weblog (min/max/mean of zd)")
for label, res in (("main", main_res), ("stratified", strat_res),
                   ("Rui", rui_res), ("Rui+strat", both_res)):
    all_zd = [z for f in sorted(res) for z in arr(res[f]["zd"])]
    all_t = [t for f in sorted(res) for t in arr(res[f]["telmjd"])]
    print(f"  {label:<11} all TARGET fields: zd_min {min(all_zd):.6f} "
          f"zd_avg {np.average(all_zd):.6f} zd_max {max(all_zd):.6f} "
          f"telmjd_avg {np.average(all_t):.6f} (n={len(all_zd)})")
    for f in sorted(main_res):
        zd = arr(res[f]["zd"])
        print(f"  {label:<11} field {f}: min {zd.min():.6f} max {zd.max():.6f} "
              f"mean {zd.mean():.6f}")

print("\nField.time endpoints and first-observation selection (hifa fluxscale QA)")
with casa_tools.MSMDReader(MS) as msmd:
    for r in orig_read_table(msmd):
        fid = r[0]
        t = arr(r[3])
        nt = rui_non_sqld_times(msmd)
        filtered = arr(np.intersect1d(t, nt, assume_unique=True)) if nt is not None else t
        print(f"  field {fid}: raw n={len(t)} first {t[0]:.3f} last {t[-1]:.3f} | "
              f"Rui n={len(filtered)} first {filtered[0]:.3f} last {filtered[-1]:.3f} "
              f"| first-obs shift {filtered[0] - t[0]:+.3f} s "
              f"last shift {filtered[-1] - t[-1]:+.3f} s")

print("\npure-SQLD fallback behaviour (Rui's _get_non_sqld_times on an MS with no non-SQLD spw)")
print("  sqld-only -> returns None -> _times_for_field falls back to the full 63k list")
