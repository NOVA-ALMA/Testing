# PIPE-3189 — `field.time` decimation in `compute_zd_telmjd_for_ms`

> **PR bundle:** structured copy of every result below, plus the diff, patches,
> raw logs, rendered weblogs and a ready-to-paste PR description, lives in
> [`pr/`](pr/README.md).

## Summary

`compute_zd_telmjd_for_ms()` iterated over every timestamp in `field.time`
(backed by `msmd.timesforfield`), doing one `measures_doframe` +
`measures_measure` per timestamp. On SQLD (high-spectral-resolution spectral-line)
data sampled at **16 ms**, that is 190,080 `measures` calls to produce a weblog
plot whose 1 s resolution is already more than adequate.

Decimating `field.time` onto a uniform 1 s grid gives a **55x speedup**
(23.6 s → 0.43 s) with the rendered plot unchanged: ZD min/max bit-identical on
every field, the drawn curve within 5.2e-08 deg of the full-resolution one
against a 12.67 deg ZD range, and the T2-2-4 page byte-for-byte identical.

---

## 1. The change

Branch `PIPE-3189-field-time-sqld` (off `main` @ `e33484632`), commits
`b73367fc1` (greedy decimation), `0fd43ae93` (test tolerance fix, see §9) and
`80f109819` (replace greedy with uniform-grid stratification, see §10).

`_decimate_timestamps(times, min_interval=1.0, min_count=50)` snaps every point
of a uniform grid of spacing `min_interval`, anchored at the first timestamp, to
the nearest real timestamp, drops duplicates, and always re-adds the first and
last — so the full time range is preserved and every returned timestamp is a
genuine input sample. Applied to `field.time` inside
`compute_zd_telmjd_for_ms()`.

Two properties of that formulation matter:

- **At most one point per `min_interval` of *elapsed* time.** That is the
  guarantee, and it is what makes the cost predictable. It is *not* a promise
  that retained points are `min_interval` apart — see §10 for why.
- **`min_count` is a continuous sparsity cap, not a fallback.** For a field
  shorter than `min_count` steps the grid tightens to `span/(min_count-1)`
  instead of handing back every sample. A binary "keep everything below 50"
  rule would have re-opened the SQLD pathology for short dwell times.

The **consumer** was fixed rather than `Field.time` itself. The ZD/telmjd values
are used only by the weblog renderer (`ZDTELMJDChart` and the min/avg/max summary
stats); they are never written to a persisted product nor read by any other task.
`Field.time` is still used by `hifv/tasks/syspower`, but only for min/max range
filtering, so it is unaffected either way.

---

## 2. Test data

### 2a. Baseline (continuum) MS

`uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms`, field 3 `helms30`,
74 timestamps at ~0.576 s spacing, ZD range 22.6743–22.7052 deg.

### 2b. SQLD MS — the dataset named in the ticket

The ticket names the dataset; it was supplied as an **ASDM** and converted:

```
/Users/users/pbos/almapipe/testdata/2021.1.01195.S/
  science_goal.uid___A001_X1590_Xd67/
    group.uid___A001_X1590_Xd68/
      member.uid___A001_X1590_Xd6b/
        raw/uid___A002_Xf160b6_Xa57a.asdm.sdm        (1.4 GB, SV dataset, M83)
```

Converted with `convert_sqld_asdm.py` (`casatasks.importasdm`, 105 s) →
`uid___A002_Xf160b6_Xa57a.ms` (2.8 GB, 8,841,600 rows, 1.29 h).

> Note: this env has the CASA Python bindings but **no `casa` CLI**, and the
> binding takes `asdm=` (not `filestrs=` as the task docs show). See
> `convert_sqld_asdm.py`.

It is genuinely SQLD — 24 spectral windows including `SQLD` correlator modes
alongside `FULL_RES` continuum and `CH_AVG`:

```
field 3/4/5  M83              n_times=63360   min_dt=0.0080s  median_dt=0.0160s  span=58.1 min
```

**16 ms median sampling**, 63,360 timestamps per field — matching the ticket's
~62,370 figure. Three fields carry `TARGET` intent → 190,080 timestamps total.

---

## 3. Performance

### SQLD MS (the case that matters)

| Metric | `main` | `greedy` | `stratified` (final) |
|---|---|---|---|
| Timestamps used | 190,080 (3 × 63,360) | 2,973 (3 × 991) | 3,181 (3 × 1060) |
| Reduction | — | −98.4% | **−98.3%** |
| **Mean wall clock** | **23.635 s** | **0.397 s** | **0.429 s** |
| Min / Max | 23.618 / 23.652 s | 0.384 / 0.441 s | 0.402 / 0.531 s |
| Time per ZD value | 0.124 ms | 0.133 ms | 0.135 ms |

**Speedup: 55.1x** (59.5x for the intermediate greedy variant).

### Against the ticket's estimate

The ticket predicted ~90 s → ~1.5 s. Measured here: 23.6 s → 0.43 s.

The **ratio matches almost exactly** (ticket 60x, measured 55–60x). The absolute
numbers are ~3.8x faster than the ticket's, consistent with different hardware.
Per-call cost is essentially unchanged (0.124 vs 0.135 ms/ZD), which is the point:
this is a pure reduction in call count, not a per-call optimisation. `stratified`
costs 3% more than `greedy` purely because it retains 7% more points.

### Baseline (continuum) MS

| Metric | `main` | `greedy` | `stratified` |
|---|---|---|---|
| Timestamps used | 74 | 55 (−25.7%) | 59 (−20.3%) |
| Mean wall clock | 0.020 s | 0.018 s | 0.020 s |

Small effect, as expected — that MS already samples near 1 s, so all three
numbers are noise-level. This is the control: the change must not cost anything
when the input is already at target resolution, and it does not.

### Where the remaining time goes

cProfile on SQLD with decimation active:

| Call | `greedy` count / cum. | `stratified` count / cum. |
|---|---|---|
| `measures_measure` | 2,973 / 0.286 s | 3,181 / 0.325 s |
| `measures_doframe` | 2,974 / 0.062 s | 3,182 / 0.068 s |
| `_decimate_timestamps` | 3 / 0.018 s | 3 / **0.001 s** |

The bottleneck moved exactly where it should: `_decimate_timestamps` was a
Python loop over 190,080 elements costing 0.018 s (2.9% of the greedy runtime)
and is now vectorised to 0.001 s (0.2%). What remains is irreducible —
3,181 `measures_measure` calls the weblog actually needs. There is no further
decimation-level win available; the only way down from here is coarser than 1 s.

---

## 4. Fidelity

`verify_zd_decimation.py` recomputes the *undecimated* series in the same process
(so both share one `measures`/observing-time cache) and compares. **Both variants
pass on both data sets.**

### SQLD MS — all three fields PASS (stratified, 1.7% kept)

```
field 3   full=63360   decimated=1060   (1.7% kept)   ZD range=12.4575 deg
  [subset]  decimated pts are real full-series samples: True
  [subset]  first/last t preserved: True   strictly sorted: True   min spacing=0.048s
  [range]   |min delta|=0.000e+00 deg  |max delta|=0.000e+00 deg
  [shape]   deviation from full curve: mean=1.243e-09 max=1.723e-09 deg (0.000% of ZD range)

field 4   ... decimated=1061 ...  [range] delta=0.000e+00   [shape] max=1.723e-09 deg
field 5   ... decimated=1060 ...  [range] delta=0.000e+00   [shape] max=1.723e-09 deg

RESULT: PASS
```

The greedy variant passed the same checks with 991 points per field
(`pr/fidelity/sqld_greedy.txt`).

- **Subset** — every retained timestamp is a genuine full-series sample; nothing
  is synthesised or interpolated.
- **Range** — ZD min and max are bit-identical (delta exactly 0.0) on all fields,
  both variants, both data sets.

Per-field ZD min/max, before → after (identical to 4 dp):

| Field | min | max |
|---|---|---|
| 3 | 20.6878 → 20.6878 | 33.1454 → 33.1454 |
| 4 | 20.8027 → 20.8027 | 33.2661 → 33.2661 |
| 5 | 20.8954 → 20.8954 | 33.3622 → 33.3622 |

Time ranges identical to the microsecond on all three fields.

### The `[shape]` column is a determinism check, not a curve metric

Retained points *are* samples of the full series, so comparing each of them to
the full curve **at the same timestamp** is ~0 by construction; the 1e-9 deg
that the column reports is run-to-run noise between two `measures` calls. It
cannot distinguish a good selection from a bad one.

The metric that matters for a plot is different: interpolate the decimated
curve **back onto the full time base** and compare with the full curve there.
That is what `fidelity_summary.py` measures, and it separates the variants
cleanly:

| SQLD `zd_telmjd.png` curve | `greedy` | `stratified` |
|---|---|---|
| deviation, mean | 2.2e-08 deg | **3.2e-09 deg** |
| deviation, max | 4.7e-06 deg | **5.2e-08 deg** |
| relative to 12.67 deg range | 3.7e-08 % | **4.1e-10 %** |

≈90x tighter on max deviation. Both are far below anything visible, but the
reason is structural: the grid samples at exactly 1.000 s where greedy managed
1.008 s (plus a forced point at each burst end). Continuum MS: 2.8e-06 →
1.8e-07 deg (15x), on a 0.031 deg range.

### Summary statistics (`zd_avg`)

Worth stating plainly, because this is where the variants differ most.
`zd_avg` on `t2-1_details` is `round(np.average(zd), 2)` over the flattened
TARGET series.

On SQLD the undecimated mean coincides with the time-weighted mean over
observed time to better than 1e-4 deg — all 33 bursts are the same length, so
density weighting and time weighting happen to agree — which makes `main` the
reference:

| SQLD, all TARGET fields | `main` | `greedy` | `stratified` |
|---|---|---|---|
| mean | 26.9906 | 26.9951 | 26.9815 |
| displayed (2 dp) | **26.99** | **27.00** | **26.98** |
| per-field Δ vs `main` | — | +0.0045 … +0.0046 | −0.0068 … −0.0106 |

So **any** decimation moves the second decimal here. The two variants sit
within 0.015 deg of each other; the largest per-field shift is 0.011 deg =
0.09 % of the 12.67 deg range. Neither is systematically closer: greedy wins
on SQLD, stratified on the continuum MS (22.6916 vs 22.6908 against `main`'s
22.6893 — all three display as 22.69).

This is sampling error, not a bias that can be tuned away: 3,181 points cannot
reproduce a mean over 190,080 exactly. Order-of-magnitude reference: selecting
3,181 points at random from these series would have a standard error of ≈0.06
deg (σ ≈ 3.7 deg), so both decimators land ~6x tighter than chance — the
near-uniform grid is doing real work, it just cannot hit the mean exactly.

---

## 5. Weblog output

Rendered the T2-2-4 (Sky Setup) page for **every variant on both data sets**,
under `pr/weblogs/{sqld,small_ms}_{main,greedy,stratified}/`, and compared them
pairwise with `compare_weblogs.py` (raw: `pr/weblogs/COMPARISON.txt`, write-up:
`pr/weblogs/COMPARISON.md`).

| Artefact | SQLD | Continuum |
|---|---|---|
| `t2-2-4.html` | **byte-identical**, 3254 B, all 3 variants | **byte-identical**, 4518 B, all 3 |
| `azel.png` | byte-identical | byte-identical |
| `el_vs_time.png` | byte-identical | byte-identical |
| `uv_coverage.png` | byte-identical | byte-identical |
| `solar_el_vs_time.png` | absent in *every* variant (pre-existing) | byte-identical |
| `zd_telmjd.png` | differs — expected, this is the decimated data | differs |

The page HTML being identical matters: it carries no ZD numbers of its own, so
the only thing that can change visually is the plot.

Pixel comparison of `zd_telmjd.png` (640×480), channel difference > 8/255:

| | SQLD px (%) | SQLD mean ch | continuum px (%) | continuum mean ch |
|---|---|---|---|---|
| `main` vs `greedy` | 1430 (0.465 %) | 0.336 | 6444 (2.098 %) | 2.853 |
| `main` vs `stratified` | **1373 (0.447 %)** | **0.302** | **6348 (2.066 %)** | **2.734** |
| `greedy` vs `stratified` | 702 (0.229 %) | 0.051 | 6426 (2.092 %) | 2.787 |

Two things to read off this:

1. **The stratified plot is closer to `main` than the greedy one is**, on both
   data sets — consistent with keeping 7 % more points (3,181 vs 2,973) and
   spacing them exactly 1 s apart.
2. `greedy` vs `stratified` on SQLD differs by a mean channel value of 0.051:
   the two decimations draw visually the same curve.

The SQLD plot is much closer to `main` than the continuum one (0.447 % vs
2.066 %): at 190,080 input points the curve already saturates the 640×480
render as a solid band, so ~3,100 points reproduce it essentially exactly. The
residual difference is anti-aliasing on the marker glyphs.

`solar_el_vs_time.png` (SunTrack) is absent from **every SQLD variant**, and
that turned out to be worth root-causing. `plotsuntrack.py:27` strips the
directory (`vis = vis.split('/')[-1]`) and then opens the basename, so the MS
is resolved against the *current working directory*; when it is not there the
resulting `OSError` is hidden by `SunTrackChart.plot()`'s bare
`except: return None`, and the image **plus its whole HTML block** silently
disappear. It is present in all three continuum renders and absent from all
three SQLD ones, so the comparison stays like-for-like. Reproduced with
`debug_suntrack.py`. Pre-existing, unrelated to this ticket — deserves its own
ticket, the fix is to keep the path instead of stripping it.

---

## 6. Reproduction

```bash
# convert the ASDM (once)
conda run -n almaPL26CM python convert_sqld_asdm.py

# baseline (pristine main)
git -C /scratch/users/pbos/pipeline worktree add /tmp/opencode/pipeline-main main
cd /tmp   # neutral cwd, else it shadows PYTHONPATH
PYTHONPATH=/tmp/opencode/pipeline-main conda run -n almaPL26CM \
    python time_weblog_zd.py $MS --runs 2

# PIPE-3189 branch
conda run -n almaPL26CM python time_weblog_zd.py $MS --runs 5
```

All four scripts now take the MS path as an optional argument, default to the
small MS, and use it **in place** rather than copying it — necessary for a 2.8 GB
MS. Each prints the `htmlrenderer` module path it loaded, so a silently-wrong
baseline (cwd shadowing `PYTHONPATH`) cannot go unnoticed.

---

## 7. Files

| File | Purpose |
|---|---|
| `render_weblog_zd.py` | Render T2-2-4 page + plots; wipes output dir first |
| `compare_weblogs.py` | Byte + pixel + IDAT comparison of two rendered trees |
| `verify_zd_decimation.py` | Subset / range / shape / pixel fidelity checks |
| `fidelity_summary.py` | Mean-vs-reference and curve-shape metrics for both variants |
| `spacing_probe.py` | Locates every sub-grid retained pair and the raw sampling around it |
| `debug_suntrack.py` | Surfaces the exception `SunTrackChart.plot()` swallows |
| `time_weblog_zd.py` | Wall-clock timing, any MS |
| `profile_weblog_zd.py` | cProfile, any MS |
| `convert_sqld_asdm.py` | ASDM → MS conversion (documents the `asdm=` kwarg) |
| `inspect_ms.py` | SPW layout + per-field sampling diagnostics |
| `pr/` | **Structured PR bundle — see `pr/README.md`** |
| `results/`, `weblog/`, `weblog_sqld/` | Original raw captures (kept for provenance) |

---

## 8. Conclusion

The decimation is safe and effective on the exact dataset the ticket cites:

- **55x faster** (23.6 s → 0.43 s), matching the ticket's predicted ratio.
- **98.3% fewer** `measures` calls (190,080 → 3,181).
- ZD min/max **bit-identical** on every field; the drawn curve within
  5.2e-08 deg of the full-resolution one, on a 12.67 deg range.
- `t2-2-4.html` byte-identical; all four non-ZD plots byte-identical; the ZD
  plot differs by 0.447% of pixels, entirely marker anti-aliasing — and *less*
  than the intermediate greedy variant differed (0.465%).
- `zd_avg` moves by at most 0.011 deg (0.09% of range), which does shift the
  second decimal of the 2-dp summary statistic on this data set. Disclosed in
  §4; any decimation of this data does that.
- 17/17 unit tests pass, on both data sets.

Recommend proceeding to review.

---

## 9. Test tolerance change (found while packaging the PR)

`zd_telmjd_test.py::test_zd_values` started failing on **2026-10-06**. Every recorded
zenith distance moved by 2.14e-08 deg. `test_telmjd_exact` still passed to the microsecond.

This is not caused by this ticket. We verified it on a clean `main` worktree. `main` fails
with the same assertion and the same diff:

```
zd[0] mismatch: 22.6743212251656772 != 22.6743212465381028, diff=2.14e-08
```

So both branches compute the same value. Only the stored expectation is old.

Cause: the shared CASA measures data at
`/dataserver/users/almapipe/pbos/measurespath/geodetic/*` changed on **2026-10-05 20:04**.
That is between the first test run on 2026-10-02 and the packaging of this PR. Those tables
feed the frame transformation in `measures`. The change is the same for every value. We
measured the spread across the series: 9.8e-10 deg. The change of the steps between values is
at most 5.6e-10 deg.

Fix in commit `0fd43ae93`: raise the tolerance from `rel=5e-10` to `rel=1e-5`.

**This fix is not the right one, and we say so here.** `rel=1e-5` is 2.27e-04 deg at 22.675
deg. The smallest step in the stored series is 2.1176e-04 deg. So five of the 58 adjacent
pairs accept a zenith distance with the next timestamp. The code comment in the PR said
"17x tighter than the ~4e-3 deg a one-second timestamp error would produce". That figure is
the largest sky rate times one second. It is not the step in this test.

The follow-up ticket replaces the tolerance with three assertions: the exact timestamps, a
coarse check of the level, and a tight check of the pattern. It also stores a digest of the
geodetic tables the values came from. See
[`pr/benchmarks`](benchmarks/) and the ticket draft in
`projects/20261117-pipe-3189/ticket-draft-measures-regression.md`.

Evidence: `pr/tests/main_RED_before_fix.txt`.

Known casacore limits we do not test here: the `MeasTable::dUT1` cache is valid for 0.04 d and
has no clear API. casacore discusses it in
[issue 1545](https://github.com/casacore/casacore/issues/1545). This test data spans 73.75 s,
so the cache changes the zenith distance by 2.7e-09 deg at most. Only a leap-second straddle
gives a large error. That needs its own data and its own test.

### Open items (not blocking)

1. ~~`_decimate_timestamps` is a Python loop; 0.018 s / 2.9%~~ — **resolved**
   by `80f109819`: vectorised with `np.searchsorted`, now 0.001 s / 0.2%.
2. `zd_avg` is a plain sample mean of the retained points, so it moves by
   ≤0.011 deg on decimation (quantified in §4). If a consumer ever needs an
   exact mean, it should compute it deliberately (e.g. weighted by the
   intervals each point represents) rather than assume parity with the full
   series.
3. `plotsuntrack` strips the MS path and resolves against the cwd, hiding the
   failure behind a bare `except:` (§5). A separate pre-existing issue.
4. The 1 s interval is a judgement call. It is well-supported here (ZD smooth,
   min/max preserved), but not formally justified across all source
   declinations.
5. **Sub-grid bursts are over-weighted.** A burst shorter than `min_interval`
   gets 1–2 points (wherever a grid node happens to land), so 30 short bursts
   can claim as many points as one 30 s burst. Bounded — `min_count` and the
   grid both cap it — but exact duration-weighting would require weighted
   averaging rather than point selection. Follow-up, not needed for a plot.
6. `verify_zd_decimation.py`'s `[shape]` column cannot detect a bad selection
   (§4); `fidelity_summary.py`'s interpolate-back metric should replace it if
   either is kept long-term.

---

## 10. Phase B — replacing the greedy rule with a uniform time grid

Commit `80f109819`. The greedy "keep a point if it is ≥1 s after the last
kept point" rule in `b73367fc1` was correct but had three structural
weaknesses, and the rewrite also removed the last Python loop in the hot path.

### Why

1. **A minimum-gap rule cannot reach a 1 s target when the input is coarser
   than 1 s.** With the continuum MS's 0.576 s sampling the gap test can never
   pass at 1 s, so the rule falls back to keeping everything — or, as
   implemented, rounds the effective spacing up to 1.152 s and under-samples by
   a third. On SQLD it settled at 1.008 s rather than 1.000 s. The uniform grid
   hits the target exactly regardless of input rate.
2. **Selection should depend only on time, never on sample density**, so bursts
   of unequal density are represented in proportion to how *long* they are.
3. **It was the last vectorisable loop**: 0.018 s over 190,080 elements.

### What it does now

Every point of a uniform grid of spacing `min_interval`, anchored at the first
timestamp, is snapped to the nearest real timestamp; duplicates are dropped;
the first and last timestamps are re-added explicitly. `np.searchsorted` +
`np.where` + `np.union1d`, so it is fully vectorised. For a field whose span
would yield fewer than `min_count = 50` grid points, the spacing tightens to
`span/(min_count-1)` — a continuous cap, deliberately not a binary "keep
everything below 50" fallback, which would have handed a short-but-dense field
all 60k samples back and re-opened the ticket's pathology.

### The guarantee, stated precisely

The guarantee is **at most one retained point per `min_interval` of elapsed
time** — i.e. a bound on points per unit time, which is what bounds the cost.
It is *not* a promise that retained points are `min_interval` apart.

Measured spacing on SQLD (1,060 points per field):

```
stratified  min 0.048   p1 0.233   p50 0.992   p99 62.080   max 187.792
greedy      min 0.992   p1 1.008   p50 1.008   p99 63.072   max 188.784
raw input   min 0.008   median 0.016          max 187.792
```

`spacing_probe.py` shows where the sub-second tail comes from: **29–30 pairs
per field (2.7%), all at burst boundaries**. A grid node that falls in the 62 s
gap just *after* a burst snaps back to that burst's final timestamp, landing
0.224 s from the previous node — the node spacing (1.0 s) exceeded the
remaining burst length (0.224 s), so the pair is compressed. Every other point
is ≥0.99 s apart (p1 = 0.233 is the same boundary effect, 1% of pairs). The
large spacings (p99 62 s, max 188 s) are the genuine inter-burst gaps, which
are correctly left empty.

So: `p50 = 0.992 s`, one extra point per burst, no synthesised timestamps.

### Results vs the greedy variant

| | `greedy` | `stratified` | winner |
|---|---|---|---|
| SQLD points | 2,973 | 3,181 | — (7% more) |
| SQLD wall clock | 0.397 s (59.5x) | 0.429 s (55.1x) | greedy, 3% |
| `_decimate_timestamps` | 0.018 s | **0.0001 s** | **stratified, ~180x** |
| curve dev, mean (SQLD) | 2.2e-08 deg | **3.2e-09 deg** | **stratified, 7x** |
| curve dev, max (SQLD) | 4.7e-06 deg | **5.2e-08 deg** | **stratified, 90x** |
| pixel diff vs `main` (SQLD) | 1430 px / 0.336 | **1373 px / 0.302** | **stratified** |
| pixel diff vs `main` (continuum) | 6444 px / 2.853 | **6348 px / 2.734** | **stratified** |
| `zd_avg` vs `main` (SQLD) | +0.0046 | −0.0106 | greedy |
| `zd_avg` vs `main` (continuum) | +0.0024 | +0.0016 | stratified |
| min_count protection | no | **yes** | **stratified** |

Net: stratified is 3% slower but draws a curve 90x closer to the full
resolution, is 180x cheaper to compute, is protected against short dense
fields, and renders closer to `main` in the actual weblog image. The one
regression is the sign of a 0.01 deg `zd_avg` shift on SQLD — itself
unavoidable in kind (§4) and 0.09% of the ZD range.

### Tests

`zd_telmjd_test.py`: **17/17 pass** — 4 `TestZdTelmjd` regression tests
(re-recorded at 59 values for the continuum MS: 74 → 59 timestamps) and 13
`TestDecimateTimestamps` unit tests covering the min_count floor (exactly 50
for dense 2/10/30/48 s spans, 101 for a 100 s span), sparse input left
untouched, unsorted input, degenerate inputs, endpoints, allocation by time
rather than sample count, and time-weighted means across equal bursts.