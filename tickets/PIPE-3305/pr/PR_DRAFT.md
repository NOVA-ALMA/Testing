# Pull request draft

**Title:** PIPE-3305: check the level and the pattern of the zenith-distance series

**Source branch:** `PIPE-3305-zd-test-measures-digest`
**Target branch:** `main`
**Reviewers:** Rui Xue, Federico Montesino Pouzols, Takeshi Nakazato, Patrick Sheehan

## Description

This PR changes one test file and adds one helper function. No production pipeline code changes. `htmlrenderer.py` is not touched. The recorded `_ZDS` values stay the same.

The helper in `pipeline/infrastructure/utils/casa_data.py`:

- `get_measures_fingerprint(window, geodetic_path)` returns a 16-character sha256 digest.
- The digest covers the numeric values of the four geodetic tables that `measures()` reads: `IERSeop97`, `IERSpredict`, `TAI_UTC`, `Observatories`.
- The digest covers the columns that move a zenith distance: `dUT1`, `x`, `y`, `dUTC`, `Offset`, `Long`, `Lat`, `Height`.
- The digest is limited to MJD 56000 to 61000. It reads `table.f0` values only, never `table.dat`.
- A missing table gives `"NOT FOUND"`, like `IERSInfo` does.

The test `test_zd_values` now has two checks instead of one:

- Level: `abs(median(actual - expected)) < 1e-4` deg (`_ZD_LEVEL_TOL`).
- Pattern: `max(abs(actual - expected - offset)) < 1e-7` deg (`_ZD_PATTERN_TOL`).

Two new test classes need no measurement set:

- `TestMeasuresData` warns when the running fingerprint differs from `_MEASURES_FP`. It uses `warnings.warn`. It does not fail.
- `TestZdSeriesChecks` tests the level and pattern logic on the recorded series.

## Why

The recorded values come from one CASA `measures` snapshot. That data changes every week.

Measured facts (CASA 6.7.4.7 on macOS, and CASA 6.7.3.21 with `NRAO_Measures_20261026-140619`):

| item | value |
|---|---|
| shift of every value after one data update | -2.1e-08 deg, spread 9.8e-10 deg |
| drift of consecutive differences | at most 5.6e-10 deg |
| fingerprint of the window values | `60ece9bd21e01000` on both machines |
| fingerprint of the raw files | different on the two machines, because `table.dat` carries `VS_CREATE` and `VS_DATE` |

The tolerance on this assertion grew four times in four months: `rel=1e-10` (2026-07-10), `rel=5e-10` (2026-07-31, PIPE-3088), `rel=1e-5` (PR #2031).

`rel=1e-5` is 2.27e-04 deg at 22.675 deg. The smallest step in the recorded series is 2.1176e-04 deg. So `rel=1e-5` accepts a zenith distance paired with the neighbouring timestamp for 5 of the 58 adjacent pairs. `test_telmjd_exact` pins the timestamps with `==`, so nothing else catches that.

The new checks separate the two problems:

- the level drifts with the data, so the level check allows 1e-4 deg;
- the shape of the series does not drift, so the pattern check allows 1e-7 deg, which is 2000 times smaller than the smallest step.

## Testing

Commands run in the worktree, with the pixi environment:

1. `<pixi python> -m pytest pipeline/infrastructure/renderer/zd_telmjd_test.py -v` → 22 passed in 2.25 s.
2. `<pixi python> -m pytest pipeline/infrastructure/renderer/zd_telmjd_test.py pipeline/infrastructure/utils/casa_data_test.py -v` → 45 passed in 3.29 s.
3. `<pixi python> -m ruff check pipeline/infrastructure/renderer/zd_telmjd_test.py pipeline/infrastructure/utils/casa_data.py` → 31 findings. The same command on `origin/main` gives 32 findings. Per file: `zd_telmjd_test.py` 6 → 5, `casa_data.py` 26 → 26, `casa_data_test.py` 24 → 24. No new finding.

Numbers from the live run on this machine:

- fingerprint: `60ece9bd21e01000`, computed in 0.018 s over 15186 values;
- level offset: 0.0 deg;
- worst pattern residual: 1.421e-14 deg.

Numbers from the new fast tests:

- one value changed by 1e-6 deg: level 0.0, residual 1.000e-06 → pattern check fails;
- all values shifted by 1e-6 deg: level 1.000e-06, residual 0.0 → pattern check passes;
- two adjacent values swapped: level 0.0, residual 2.118e-04 → pattern check fails;
- guard: `_ZD_PATTERN_TOL` (1e-7) is below the smallest step divided by 1000 (2.1176e-07).

Negative control: the same swap passes the old `rel=1e-5` assertion. It fails the new pattern check.

## Known limits

- The digest covers the geodetic tables only. It says nothing about the ephemerides.
- The digest is limited to MJD 56000-61000. Rows past the last measured `IERSeop97` row are predictions. Predictions change with every update.
- Never hash `table.dat`. It holds the `VS_CREATE` and `VS_DATE` stamps of an install.
- casacore caches `dUT1` for 0.04 d. For the 73.75 s test series the effect is at most 2.7e-09 deg. See casacore issue 1545.
- The level check absorbs a uniform shift. A uniform data change will not trip the pattern check. It trips the level check only above 1e-4 deg.
- The fingerprint check warns. It does not fail the test. A maintainer must re-record `_ZDS` when the digest changes and the pattern also moves.

## Questions for reviewers

Patrick Sheehan: is MJD 56000 to 61000 the right window, and is the four-table list
(`IERSeop97`, `IERSpredict`, `TAI_UTC`, `Observatories`) the right one for the work of the
Measures Data Working Group? On this installation `IERSeop2000` and `IERSeop97` agree exactly
on `dUT1`, `x` and `y` for all 5001 rows in the window, and both cover MJD 37665 to 61304. So
a switch to the 2000 series would not change the digest today. It would change it if the two
tables ever disagree, or if `measures()` starts reading a different table.

## Links

- Jira: https://open-jira.nrao.edu/browse/PIPE-3305
- Measurements and the reference helper: https://github.com/NOVA-ALMA/Testing/tree/main/tickets/PIPE-3305
- casacore issue 1545: https://github.com/casacore/casacore/issues/1545
- Earlier PR: #2031 (PIPE-3189)

## Checklist

- [x] No production code change.
- [x] The recorded `_ZDS` values are unchanged.
- [x] No tolerance is widened. The per-value comparison is replaced, not relaxed.
- [x] New tests run without a measurement set.
- [x] No new ruff findings.
- [x] The failure message names the offset, the residual, and both fingerprints.
