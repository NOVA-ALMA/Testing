# PIPE-3189 — benchmark results

All numbers from `scripts/time_weblog_zd.py` and `scripts/profile_weblog_zd.py`
on `eddington.desktop.astro.rug.nl` (i7-14700T, 20 cores / 28 threads, 30.7 GiB,
Rocky Linux 9.8), conda env `almaPL26CM`, casatools 6.7.3.21.

Raw logs alongside this file.

## SQLD MS — the case the ticket is about

`uid___A002_Xf160b6_Xa57a.ms`, 3 TARGET fields x 63,360 timestamps @ 16 ms.

| Metric | `main` | `greedy` | `stratified` |
|---|---|---|---|
| Timestamps used | 190,080 | 2,973 (−98.4 %) | 3,181 (−98.3 %) |
| **Mean wall clock** | **23.635 s** | **0.397 s** | **0.429 s** |
| Speedup | 1x | 59.5x | **55.1x** |
| Min / Max of runs | 23.618 / 23.652 s | 0.384 / 0.441 s | 0.402 / 0.531 s |
| Time per ZD value | 0.124 ms | 0.133 ms | 0.135 ms |

Runs: `main` x2, `greedy` x5, `stratified` x5.

Per-call cost is essentially unchanged — this is a pure reduction in the
number of `measures` calls, not a per-call optimisation. `stratified` costs
3 % more than `greedy` purely because it keeps 7 % more points (3,181 vs
2,973); per point they are identical (0.135 vs 0.133 ms).

### Against the ticket's own estimate

The ticket predicted ~90 s → ~1.5 s. Measured here: 23.6 s → 0.43 s.

The **ratio matches** (ticket 60x, measured 55–60x); absolute numbers are
~3.8x faster than the ticket's, consistent with different hardware.

## Continuum (small) MS — control

`...repSPW_spw16_17_small.ms`, field 3 `helms30`, 74 timestamps @ ~0.576 s.

| Metric | `main` | `greedy` | `stratified` |
|---|---|---|---|
| Timestamps used | 74 | 55 (−25.7 %) | 59 (−20.3 %) |
| Mean wall clock | 0.020 s | 0.018 s | 0.020 s |

Small effect, as expected: that MS already samples near 1 s, so all three
numbers are noise-level. This is the control case — the change must **not**
cost anything when the input is already at target resolution, and it does not.

## cProfile on SQLD with decimation active

| Call | `greedy` count | `greedy` cum. | `stratified` count | `stratified` cum. |
|---|---|---|---|---|
| `measures_measure` | 2,973 | 0.286 s | 3,181 | 0.325 s |
| `measures_doframe` | 2,974 | 0.062 s | 3,182 | 0.068 s |
| `_decimate_timestamps` | 3 | 0.018 s | 3 | **0.001 s** |

With `main` the corresponding `measures_measure` count is 190,080.

The profile shows the fix has moved the bottleneck exactly where it should:
`_decimate_timestamps` went from 0.018 s (2.9 % of the greedy runtime, a
Python loop over 190,080 elements) to **0.001 s (0.2 %)** once vectorised, and
what remains is irreducible — 3,181 `measures_measure` calls the weblog
actually needs. There is no further decimation-level optimisation to win;
the only way down from here is fewer points, i.e. coarser resolution than
1 s.

## Where the remaining time goes

| | `main` | `greedy` | `stratified` |
|---|---|---|---|
| `measures_measure` | 190,080 calls, ~23 s | 2,973, 0.286 s | 3,181, 0.325 s |
| `measures_doframe` | 190,081, ~1.5 s | 2,974, 0.062 s | 3,182, 0.068 s |
| decimation itself | — | 0.018 s | 0.001 s |
| everything else (matplotlib, MS I/O) | ~0.1 s | ~0.03 s | ~0.03 s |

Ratios of `measures_measure` time match ratios of point count almost exactly,
which is the sanity check that nothing else regressed.
