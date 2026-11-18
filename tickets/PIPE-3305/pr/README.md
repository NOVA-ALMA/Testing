# PIPE-3305 implementation report

Date: 2026-11-18. Work done in a worktree of `/Users/P252012/projects/ALMA/pipeline`. The main working copy was not touched. Its uncommitted files are unchanged.

## Branch and commits

| item | value |
|---|---|
| branch | `PIPE-3305-zd-test-measures-digest` |
| base | `origin/main` at `2a803cbc8` |
| commit 1 | `bfbba6d2d11ee173bcbe610400c08212c95a7d79` — add the fingerprint helper |
| commit 2 | `81688ad7c1ccea9506dffb75ade5bcbd27c08f4d` — rewrite the ZD check |
| push | succeeded. `git ls-remote origin refs/heads/PIPE-3305-zd-test-measures-digest` returns `81688ad7c1ccea9506dffb75ade5bcbd27c08f4d` |
| patch file | `pipe-3305.patch` in this folder (304 lines, both commits) |
| PR text | `PR_DRAFT.md` in this folder. No pull request was created. No Bitbucket token is available. |

## Diff size

```
pipeline/infrastructure/renderer/zd_telmjd_test.py | 102 ++++++++++++++++++---
pipeline/infrastructure/utils/casa_data.py         |  62 +++++++++++++
pipeline/infrastructure/utils/casa_data_test.py    |  14 +++
3 files changed, 166 insertions(+), 12 deletions(-)
```

## Code added

`pipeline/infrastructure/utils/casa_data.py`

- `GEODEDIC_TABLES`, `GEODEDIC_COLUMNS`, `EPOCH_WINDOW`.
- `get_measures_fingerprint(window=EPOCH_WINDOW, geodetic_path=None)`. It hashes `struct.pack('>d', float(value))` for each value in the window. It returns 16 hex characters, or `'NOT FOUND'` when a table cannot be opened. It uses `casa_tools.TableReader` and `IERS_TABLES_PATH`. It does not call `casaconfig.get_data_info`.

`pipeline/infrastructure/renderer/zd_telmjd_test.py`

- `_ZD_LEVEL_TOL = 1e-4`, `_ZD_PATTERN_TOL = 1e-7`, `_MEASURES_FP = '60ece9bd21e01000'`.
- `_level_and_pattern(actual, expected)` returns the median offset and the largest residual.
- `test_zd_values` now checks the level and the pattern. The failure message prints both tolerances, the offset, the residual, and both fingerprints.
- `TestMeasuresData::test_fingerprint_is_recorded` warns with `warnings.warn` when the digest differs. It does not fail.
- `TestZdSeriesChecks` adds four fast tests. No measurement set is needed.
- The module docstring and the comment block now state the real numbers. The "17x tighter" text is gone.

`pipeline/infrastructure/utils/casa_data_test.py`

- Two tests for the helper: the digest format, and `'NOT FOUND'` for a missing table.

## Commands run

Python: `/Users/P252012/projects/ALMA/pipeline/.pixi/envs/default/bin/python` (CASA 6.7.4.7, measurespath `~/.casa/data`).

```
python -m pytest pipeline/infrastructure/renderer/zd_telmjd_test.py -v
python -m pytest pipeline/infrastructure/renderer/zd_telmjd_test.py pipeline/infrastructure/utils/casa_data_test.py -v
python -m ruff check pipeline/infrastructure/renderer/zd_telmjd_test.py pipeline/infrastructure/utils/casa_data.py pipeline/infrastructure/utils/casa_data_test.py
```

The full pytest output is in `test-output.txt` in this folder.

## Test counts

| run | before | after |
|---|---|---|
| `zd_telmjd_test.py` | 17 passed in 3.47 s | 22 passed in 2.25 s |
| `zd_telmjd_test.py` + `casa_data_test.py` | — | 45 passed in 3.29 s |

## Ruff counts

`ruff check` with the repo config in `pyproject.toml` (ruff 0.16.2):

| file | origin/main | branch |
|---|---|---|
| `zd_telmjd_test.py` | 6 | 5 |
| `casa_data.py` | 26 | 26 |
| `casa_data_test.py` | 24 | 24 |
| total | 32 | 31 |

No new finding. `ruff format --check` reports both files as unformatted on `origin/main` too, so the branch does not change that.

## Numbers observed

| item | value |
|---|---|
| fingerprint of the four tables, MJD 56000-61000 | `60ece9bd21e01000` |
| values hashed | 15186 |
| time for one fingerprint call | 0.018 s |
| level offset of the live run | 0.0 deg |
| worst pattern residual of the live run | 1.421e-14 deg |
| number of recorded values | 59 |
| number of adjacent pairs | 58 |
| smallest step in the series | 2.117574e-04 deg |
| largest step in the series | 5.648044e-03 deg |
| pairs the old `rel=1e-5` accepts for a neighbour pairing | 5 of 58 |
| `rel=1e-5` bound at 22.675 deg | 2.2675e-04 deg |
| `_ZD_PATTERN_TOL` as a fraction of the smallest step | 4.722e-04 |
| dUT1 change that moves a ZD by 1e-7 deg | 2.9e-05 s |

Fast-test results:

| case | level | residual | pattern check |
|---|---|---|---|
| one expected value changed by 1e-6 deg | 0.0 | 1.000e-06 | fails |
| all values shifted by 1e-6 deg | 1.000e-06 | 0.0 | passes |
| two adjacent values swapped | 0.0 | 2.118e-04 | fails |
| guard `_ZD_PATTERN_TOL < min_step/1000` | — | — | 1e-7 < 2.1176e-07, passes |

Warning path check: with `_MEASURES_FP` set to a wrong value, `test_fingerprint_is_recorded` raises a `UserWarning` under `warnings.simplefilter('error')`. With the correct value, it warns nothing.

## Things not done

- No pull request was created in Bitbucket. No credentials or REST token were found.
- `htmlrenderer.py` and other production code are unchanged.
- The `_ZDS` and `_TELMJDS` values are unchanged.
- No tolerance is widened. The per-value assertion is replaced by two checks.
