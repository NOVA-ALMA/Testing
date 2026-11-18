"""Where does the 1.8e-3 deg deviation in Rui's filtered series come from?

Run on eddington, from the PIPE-3189 branch checkout:
  conda run -n almaPL26CM python gap_probe.py \
      --configfile=/scratch/users/pbos/probe_siteconfig.py
"""
import numpy as np

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.renderer import htmlrenderer

MS = "/scratch/users/pbos/sqld_test/uid___A002_Xf160b6_Xa57a.ms"


def rui_non_sqld_times(msmd):
    sqld = set(msmd.almaspws(sqld=True))
    if not sqld:
        return None
    ns = [i for i in range(msmd.nspw()) if i not in sqld]
    if not ns:
        return None
    return np.unique(np.concatenate(list(msmd.timesforspws(ns).values())))


with casa_tools.MSMDReader(MS) as msmd:
    nt = rui_non_sqld_times(msmd)
    for f in (3, 4, 5):
        t = np.asarray(msmd.timesforfield(f), dtype=float)
        filt = np.intersect1d(t, nt, assume_unique=True)
        strat = htmlrenderer._decimate_timestamps(t)
        for label, s in (("raw", t), ("Rui", filt), ("stratified", strat)):
            g = np.diff(s)
            order = np.argsort(g)[-5:]
            print(f"field {f} {label:<10} n={len(s):6d} gaps: max {g.max():.3f}s "
                  f"median {np.median(g):.4f}s  5 largest "
                  f"{sorted(g[order], reverse=True)}")
            print(f"    coverage {s[0]:.3f} -> {s[-1]:.3f} ({s[-1] - s[0]:.3f}s), "
                  f"gaps > 1s: {(g > 1).sum()}")
