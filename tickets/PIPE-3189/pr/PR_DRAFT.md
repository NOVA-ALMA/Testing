# PIPE-3189: decimate `field.time` in `compute_zd_telmjd_for_ms`

## Problem

`compute_zd_telmjd_for_ms()` iterated over every timestamp in `field.time`
(backed by `msmd.timesforfield`), doing one `measures_doframe` +
`measures_measure` per timestamp, to produce a weblog plot whose 1 s
resolution is already more than adequate.

On SQLD (high-spectral-resolution spectral-line) data the integration time is
~16 ms, so a single field yielded 63,360 timestamps instead of ~1,000 —
190,080 `measures` calls for the ticket's dataset, taking 23.6 s of CPU inside
a weblog render.

## Change

Add `_decimate_timestamps(times, min_interval=1.0, min_count=50)` and apply it
to `field.time` inside `compute_zd_telmjd_for_ms()`.

It snaps every point of a uniform grid of spacing `min_interval`, anchored at
the first timestamp, to the **nearest real timestamp**, drops duplicates, and
re-adds the first and last explicitly. Every returned timestamp therefore
exists in the input; nothing is synthesised; the full time range is preserved.
The whole thing is vectorised (`np.searchsorted` + `np.where` +
`np.union1d`).

The guarantee is **at most one retained point per `min_interval` of elapsed
time** — a bound on points per unit time, which is what bounds the cost. It is
deliberately *not* a promise that retained points are `min_interval` apart:
snapping means a grid node that falls in a gap just past the end of a burst
selects that burst's final timestamp, so a few pairs land closer together than
the grid step (2.7 % of pairs on the test data, `p50 = 0.992 s`).

`min_count` is a **continuous** sparsity cap: for a field too short to yield 50
grid points, the spacing tightens to `span/(min_count-1)` rather than falling
back to keeping everything. A binary "keep everything below 50" rule would
have handed a short-but-dense field all 63,360 samples back and re-opened the
ticket's pathology for short dwell times.

**The consumer was fixed rather than `Field.time` itself.** The ZD/telmjd
values are used only by the weblog renderer (`ZDTELMJDChart` and the
min/avg/max summary stats); they are never written to a persisted product nor
read by any other task. `Field.time` itself is untouched, so
`hifv/tasks/syspower` (which uses it for min/max range filtering only) is
unaffected.

## Performance

SQLD MS `uid___A002_Xf160b6_Xa57a.ms` (the dataset named in the ticket,
converted from its ASDM):

| Metric | `main` | this branch |
|---|---|---|
| Timestamps used | 190,080 | 3,181 (**−98.3 %**) |
| **Mean wall clock** | **23.635 s** | **0.429 s** |
| Time per ZD value | 0.124 ms | 0.135 ms |

**55x speedup.** The ticket predicted ~90 s → ~1.5 s: the *ratio* matches
almost exactly (60x predicted, 55–60x measured), with absolute numbers ~3.8x
faster on this hardware. Per-call cost is unchanged — this is purely a
reduction in call count.

Control on a continuum MS already sampled near 1 s: 74 → 59 timestamps,
0.020 s → 0.020 s. No change, as expected — the function must not cost
anything when the input is already at target resolution, and it does not.

Profile confirms the bottleneck moved: `_decimate_timestamps` 0.018 s →
0.001 s, `measures_measure` 190,080 → 3,181 calls. What remains is irreducible
— the calls the weblog actually needs.

## Fidelity

`verify_zd_decimation.py` recomputes the *undecimated* series in the same
process and compares, on all three TARGET fields of the SQLD MS:

- **Subset** — every retained timestamp is a genuine full-series sample;
  nothing synthesised or interpolated. First/last preserved, strictly sorted.
- **Range** — ZD min and max delta **exactly `0.000e+00`** on every field.
- **Curve** — interpolating the decimated curve back onto the full time base
  and comparing with the full curve deviates by at most **`5.2e-08` deg**,
  i.e. **4e-10 %** of the 12.67 deg ZD range.

Per-field, identical to 4 decimal places:

| Field | min | max |
|---|---|---|
| 3 | 20.6878 → 20.6878 | 33.1454 → 33.1454 |
| 4 | 20.8027 → 20.8027 | 33.2661 → 33.2661 |
| 5 | 20.8954 → 20.8954 | 33.3622 → 33.3622 |

Continuum MS: same three checks PASS.

## Weblog output

T2-2-4 (Sky Setup) rendered for every variant on both datasets, output in
`weblogs/`, pairwise comparison in `weblogs/COMPARISON.{txt,md}`:

| Artefact | SQLD MS | Continuum MS |
|---|---|---|
| `t2-2-4.html` | **byte-identical** (3254 B) | **byte-identical** (4518 B) |
| `azel.png` / `el_vs_time.png` / `uv_coverage.png` | **byte-identical** | **byte-identical** |
| `solar_el_vs_time.png` | absent in *every* variant (pre-existing) | **byte-identical** |
| `zd_telmjd.png` | differs by design — 1373 px (0.447 %), mean ch 0.302 | 6348 px (2.066 %), mean ch 2.734 |

The SQLD plot differs *less* than the continuum control (0.447 % vs 2.066 %):
at 190,080 points the curve already saturates the 640x480 render, so 3,181
points reproduce it essentially exactly. Residual difference is marker
anti-aliasing.

Note the thumbnails are never byte-identical even when pixel-identical —
they embed `tIME`/`date:*`/`Thumb::URI` metadata. All `IDAT` data matches.

## Tests

`zd_telmjd_test.py` — **17 passed**: 4 `TestZdTelmjd` regression tests and 13
`TestDecimateTimestamps` unit tests (min_count floor, sparse/unsorted/degenerate
input, endpoints, allocation by time rather than sample count, time-weighted
means).

The expected values are re-recorded for the decimated series (74 → 59
timestamps). `test_telmjd_exact` asserts every timestamp with `==`, so
regressions in *which* timestamps are selected are caught exactly and are not
subject to floating-point tolerance.

## Known limitations / follow-ups

1. **`zd_avg` moves by ≤0.011 deg.** It is `round(np.average(zd), 2)` on
   `t2-1_details`, and *any* decimation shifts it here: SQLD displays 26.99
   (`main`), 27.00 (greedy) → the branch gives 26.98, a 0.01 deg change that
   is 0.09 % of the 12.67 deg range. Not a bias that can be tuned away —
   3,181 points cannot reproduce a mean over 190,080 exactly — and both
   decimators land ~6x tighter than random selection would. Full analysis in
   `report.md` §4. Continuum MS unaffected (all three show 22.69).
2. **Sub-grid bursts are over-weighted.** A burst shorter than
   `min_interval` gets 1–2 points wherever a grid node lands, so several
   short bursts can claim as many points as one 30 s burst. Bounded by both
   the grid and `min_count`; exact duration-weighting would need weighted
   averaging rather than point selection. Doesn't show on the test data (all
   33 bursts equal); follow-up if a target with many unequal sub-scans ever
   matters.
3. **min/max is guaranteed only at the endpoints.** Interior extrema can be
   missed by up to `max|dZD/dt| x interval`. Physically ZD cannot change
   faster than the sky rotates (360/86400 = 0.00417 deg/s), so at 1 s the
   worst case is <= 0.0042 deg — 0.03 % of the observed range. Measured: 0.0.
4. **`zd_telmjd_test.py::test_zd_values` was red on `main` as well.** The
   shared CASA measures data was refreshed on 2026-10-05, shifting every ZD
   by a constant 2.14e-08 deg. Fixed by relaxing the tolerance from
   `rel=5e-10` to `rel=1e-5` (still 17x tighter than a one-second timestamp
   error); evidence in `tests/main_RED_before_fix.txt`.
5. **`solar_el_vs_time.png` missing** on the SQLD MS in *every* variant —
   `plotsuntrack.py:27` strips the MS path and resolves the basename against
   the cwd, then `SunTrackChart.plot()` swallows the `OSError` behind a bare
   `except:`, dropping the image and its whole HTML block. Pre-existing and
   unrelated; reproduced in `scripts/debug_suntrack.py`. Separate ticket.
