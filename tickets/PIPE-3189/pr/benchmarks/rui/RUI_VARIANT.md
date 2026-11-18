# PIPE-3189 — Rui's "strip the SQLD timestamps" variant, measured

`PIPE-3189-strip-off-sqld-time-stamp` (Rui Xue, `88d2348d5`) changes
`pipeline/infrastructure/tablereader.py`: `FieldTable._read_table` replaces
`Field.time` with `np.intersect1d(times, non_sqld_times)`, where
`non_sqld_times` is the union of the times of all SPWs that are *not* flagged
SQLD (`msmd.almaspws(sqld=True)`).

Both variants were run on the ticket's SQLD measurement set
(`uid___A002_Xf160b6_Xa57a.ms`, 24 SPWs, 8 of them SQLD) on eddington, through
the real `compute_zd_telmjd_for_ms`, best of two runs. Scripts:
[`../scripts/rui_probe2.py`](../scripts/rui_probe2.py),
[`../scripts/gap_probe.py`](../scripts/gap_probe.py); raw output in this
directory.

## Wall clock and point counts

| variant | ZD points | wall clock |
|---|---|---|
| `main` (no decimation) | 190,080 | 33.42 s |
| **stratified (PR #2031)** | **3,181** | **9.87 s** |
| Rui (SQLD timestamps stripped) | 3,264 | 9.89 s |
| Rui + stratified | 2,980 | 9.90 s |

Building Rui's non-SQLD time union costs **0.047 s** (4,560 unique timestamps
from 16 non-SQLD SPWs), negligible next to the ~10 s of `measures` calls. The
two approaches land on the same cost; Rui's does not make it cheaper than
decimation.

## What the numbers printed in the weblog look like

`ProjectSummary` reports `zd_min`, `zd_avg`, `zd_max` over all TARGET fields.

| variant | `zd_min` (deg) | `zd_avg` (deg) | `zd_max` (deg) |
|---|---|---|---|
| `main` | 20.687818 | 26.990562 | 33.362170 |
| stratified | **20.687818** | 26.981531 | **33.362170** |
| Rui | 20.689584 | 26.989892 | 33.360406 |
| Rui + stratified | 20.689584 | 26.993136 | 33.360406 |

Rui's variant keeps the mean close to `main` (Δ 6.7e-04 deg) but moves the
extremata by **1.8e-03 deg (6.4 arcsec)**: the SQLD SPWs start 0.504 s before
the first non-SQLD sample and end 0.488 s after the last one, so the extrema
are exactly the timestamps that get dropped. Stratified keeps them bit-identical.

## Curve fidelity (decimated curve interpolated onto `main`'s time base)

| variant | max deviation (deg) | max deviation (arcsec) | mean deviation (deg) |
|---|---|---|---|
| stratified | **5.2e-08** | 0.0002 | 3.4e-09 |
| Rui | 1.77e-03 | 6.4 | 9.0e-07 |
| Rui + stratified | 1.77e-03 | 6.4 | 9.0e-07 |

The deviation is entirely at the ends of each field's series — it is the same
1.8e-03 deg as the `zd_min`/`zd_max` shift above.

## Time-series structure

Per TARGET field (raw series 63,360 timestamps, 16 ms median spacing):

| | n | median gap | max gap | span |
|---|---|---|---|---|
| raw | 63,360 | 0.0160 s | 187.792 s | 3484.832 s |
| Rui | 1,089 | 1.0080 s | 188.784 s | 3483.840 s |
| stratified | 1,060 | 0.9920 s | 187.792 s | 3484.832 s |

Stratified reproduces the raw series' gap structure exactly (same first, last
and largest gaps); Rui's shifts every gap by one sample and clips the ends.

## Side effect on `Field.time` consumers

Rui's change alters `Field.time` for **every** field, not just TARGET ones.
For this MS the first timestamp moves by +0.288…+0.504 s and the last by
−0.272…−0.488 s (fields 0, 1, 3, 4, 5: +0.504 / −0.488; field 2: +0.288 / −0.272).

`pipeline/hifa/tasks/fluxscale/qa.py:365` selects the flux-scale calibrator with

```python
min(candidate_fields, key=lambda f: f.time.min())
```

so a 0.5 s shift in `f.time.min()` can change which field that QA reports when
two candidate calibrators start within a second of each other. Not in Rui's
list of consumers; worth a regression check before that change is taken.

## Coverage edge case

`_get_non_sqld_times()` returns `None` when an MS has no non-SQLD SPWs, and
`_times_for_field()` falls back to the full time list when the intersection is
empty. For a purely SQLD observation nothing is removed, so the 16 ms
pathology (190,080 `measures` calls) survives. The decimation in PR #2031 bounds
the work regardless of SPW flags, which is why it is written at the consumer
rather than in `FieldTable`.

## Combining them

Rui + stratified is safe: the result is a genuine subset of real timestamps,
endpoints of the filtered series preserved, 2,980 points, same wall clock. It
just does not recover the extrema that Rui's filter drops, because those are
already gone before decimation runs.
