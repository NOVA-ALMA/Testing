# Fingerprinting the CASA geodetic/IERS data a regression test actually uses

PIPE-3189 · 2026-11-18 · read-only investigation in `/Users/P252012/projects/ALMA/pipeline`; nothing in the repo was changed or committed.

## TL;DR

The canary you want is a **16-character hash over the numeric column values of the four geodetic tables that `measures()` really opens, restricted to the epoch window the test covers**. It costs ~20 ms locally, it is identical on two machines with different casarundata snapshots, and it provably moves when the data moves and stays put when only the code changes.

- **Primary fingerprint** (semantic, epoch-window): `60ece9bd21e01000` — identical on the laptop (tables stamped 2026-10-21) and on eddington (`NRAO_Measures_20261026-140619`).
- **Snapshot label** (raw file bytes): laptop `3de7cb1d46f9528b`, eddington `c771551fbf49e381`. Useful for "which snapshot am I on", useless as an assertion because legitimate updates always change it.
- **Behavioural probe**: zenith distance of a fixed J2000 direction at four fixed epochs — bit-for-bit identical on both machines (CASA 6.7.4.7 macOS and 6.7.3.21 Linux).
- **Fallback for `'unknown'` versions**: `casaconfig.get_data_info(type='measures')` returns `version: 'unknown'` on the laptop (no `geodetic/readme.txt`), and VS_VERSION is `0001.0001` for every IERS table, so neither identifies the data. Use the fingerprint itself, plus VS_DATE from the table keywords (`2026-10-21/18:05` vs `2026-10-26/18:06`).

---

## 1. Which tables does `measures()` actually read?

Not the ones the existing helpers look at.

Evidence A — casacore source (`MeasTable.cc` / `MeasIERS.cc`, fetched for this investigation):

```c
const String MeasIERS::tp[MeasIERS::N_Files] = {"IERSeop97", "IERSpredict"};
...
MeasIERS::getTable(t, ..., "Observatories", "measures.observatory.directory", "geodetic");
MeasIERS::getTable(t, ..., "TAI_UTC",      "measures.tai_utc.directory",     "geodetic");
MeasIERS::getTable(t, ..., "IGRF",         "measures.igrf.directory",        "geodetic");
```

`dUT1` is served from `IERSeop97` (measured) or `IERSpredict` (when the epoch is past the last measured row). Nutation `dPsi/dEps` also come from `IERSeop97`. `IGRF` is only touched by magnetic-field measures.

Evidence B — strings in the installed binary, `casatools/__casac__/libcasa_measures.9.dylib`:

```
measures.ierseop97.directory
measures.ierspredict.directory
measures.observatory.directory
measures.tai_utc.directory
measures.igrf.directory
```

No `ierseop2000` / `ierspredict2000` entry.

Evidence C — empirical table-by-table deletion (scratch copy of the geodetic directory, `eop2000_test.py`):

| change | ZD probe result |
|---|---|
| baseline | 84.136901677069 |
| `IERSeop2000` deleted | **casatools import fails** ("measures data is not available") — it is only used by casatools' existence check |
| `IERSeop2000` dUT1 +1 s in the window | 84.136901677069 — no effect |
| `IERSpredict2000` deleted | no effect |
| `IGRF` deleted | no effect |
| `SCHED_locations` deleted | no effect |
| `IERSeop97` deleted | measures raises |
| `IERSpredict` deleted | measures raises |
| `TAI_UTC` deleted | measures raises |
| `Observatories` deleted | falls back to the default observatory, ZD 67.991084745090 |

So the four tables that matter for an AZELGEO/observatory measurement are **IERSeop97, IERSpredict, TAI_UTC, Observatories**. The pipeline's `IERSInfo` class in `pipeline/infrastructure/utils/casa_data.py` tracks `IERSpredict` + `IERSeop2000`, which is the wrong pair for a ZD canary (it is right for the PIPE-734 date-validity check).

Which *columns* move the ZD (scratch copy, one column perturbed at a time, probe at MJD 58007.24477111111):

| table | column | delta | ZD change (deg) |
|---|---|---|---|
| IERSeop97 | dUT1 | 1 s | −3.428e-3 |
| IERSeop97 | dUT1 | 0.001 s | −3.428e-6 |
| IERSeop97 | x | 1e-4 rad | −1.05e-8 |
| IERSeop97 | y | 1e-4 rad | +1.19e-8 |
| IERSeop97 | dPsi / dEps | 1e-3 arcsec | 0 — nutation comes from the built-in model, not these columns |
| IERSeop97 | LOD / Dx / Dy / DdUT1 | 1e-3 | 0 |
| Observatories | Long | 1e-4 deg | −8.2e-5 |
| Observatories | Lat | 1e-4 deg | −4.5e-5 |
| Observatories | Height | 100 m | −1.4e-9 |
| TAI_UTC | dUTC | 1 s | +1.3e-9 |
| TAI_UTC | Offset | 1 s | 0 |
| IERSpredict | dUT1 | 1 s | 0 (the probe epoch is inside the measured range) |

The test tolerance in `pipeline/infrastructure/renderer/zd_telmjd_test.py` is `rel=5e-10` on a ~22.67 deg ZD, i.e. ~1.1e-8 deg. Measured against that test's own 74 values, the sensitivity is 4.45e-4 deg per second of dUT1, so **a change of only ~25 µs in dUT1 breaks it** (10 µs: rel 2.0e-10, missed; 100 µs: rel 2.0e-9, detected). That is why a fingerprint is needed: the test is sensitive far beyond what a human would notice.

## 2. Why the obvious fingerprints fail

- **`table.dat`**: contains `VS_CREATE` / `VS_DATE`. Two installs with byte-identical data hash differently. Proved: `TAI_UTC/table.f0` is `fb31105cc9d64774…` on both machines while their `table.dat` differ (`79ae088cc0337e8a` vs `f0d0c99e425a6b03`). → exclude `table.dat` (and `table.info`, `table.lock`) from any hash. Opening tables read-only leaves `table.lock` untouched (verified: identical hash and mtime before and after repeated opens).
- **`casaconfig.get_data_info(type='measures')`**: on the laptop returns `{'site': 'unknown', 'version': 'unknown', 'date': '', 'age': None}` because there is no `measurespath/geodetic/readme.txt` (only `~/.casa/data/readme.txt`). Legacy/hand-copied geodetic directories have no readme at all.
- **`VS_VERSION` keyword**: `0001.0001` for every IERS table. Meaningless.
- **Whole-file hash of the four tables**: changes on *every* routine update (each update appends new rows and rewrites the predicted table), so it cannot be a pass/fail assertion — it is only a snapshot identifier.
- **Last MJD / row count**: `nrows` is a good readable companion, but a table can be re-written with the same coverage and different values.
- **File mtime**: meaningless, the tables are re-written when a snapshot is unpacked.

## 3. The two snapshots, measured

`/Users/P252012/.casa/data` (CASA 6.7.4.7, macOS) vs `/dataserver/users/almapipe/pbos/measurespath/casarundata-2026.10.27-1` on eddington (CASA 6.7.3.21, conda `almaPL26CM`).

| | laptop | eddington |
|---|---|---|
| casaconfig version | `unknown` | `NRAO_Measures_20261026-140619.ztar` (date 2026-10-27) |
| VS_DATE (IERSeop97) | 2026-10-21/18:05 | 2026-10-26/18:06 |
| IERSeop97 rows / MJD range | 23640 / 37665–61304 | 23645 / 37665–61309 |
| IERSpredict rows / MJD range | 181 / 61245–61425 | 181 / 61250–61430 |
| TAI_UTC rows / MJD range | 41 / 37300–57754 | 41 / 37300–57754 (identical) |
| Observatories rows | 59 | 59, `Long`/`Lat`/`Height` max diff 0.0 |
| raw file fingerprint | `3de7cb1d46f9528b` | `c771551fbf49e381` |
| **epoch-window fingerprint (56000–61000)** | **`60ece9bd21e01000`** | **`60ece9bd21e01000`** |
| probe ZD (4 epochs) | 84.85496683766004, 84.13690167706928, 104.77194567360485, 128.6106471448433 | identical to the last bit |
| probe dUT1 (s) | −0.4324395675212145, 0.3301612799987197, −0.25409802328795195, 0.09430709760636091 | identical |

Row-by-row diff of the numeric columns (`iers_dump.json` vs `iers_dump_eddington.json`):

- IERSeop97: 23640 common MJDs, **0 differing values**; eddington has 5 extra measured rows (61305–61309).
- IERSpredict: 176 common MJDs, 170 differing dUT1 values (max 1.65e-3 s), 96 differing x, 98 differing y — the prediction window has slid forward. None of it is used for epochs ≤ 61304.
- TAI_UTC: identical.
- Observatories: identical.

Beyond the window, the two snapshots disagree in the way you would expect:

| epoch | laptop dUT1 (s) | eddington dUT1 (s) | ZD difference |
|---|---|---|---|
| 57000.0 | −0.432439568 | −0.432439568 | 0 |
| 58007.24477111111 | 0.330161280 | 0.330161280 | 0 |
| 60967.0 | 0.094307098 | 0.094307098 | 0 |
| 61304.0 | −0.010624062 | −0.010585086 | 1.54e-7 deg (0.0006″) |
| 61420.0 | −0.132870558 | −0.131769804 | 3.63e-6 deg (0.013″) |

That is the whole argument for the window-restricted fingerprint: epochs inside the window are stable across updates, epochs in the predicted tail are not.

## 4. Cost

Measured on the laptop (`/Users/P252012/projects/ALMA/pipeline/.pixi/envs/default/bin/python`), then on eddington over the network filesystem:

| step | laptop | eddington |
|---|---|---|
| raw file fingerprint (4 tables, ~5 MB) | 3–4 ms | 39–83 ms |
| semantic window fingerprint | 17–25 ms | 204–431 ms |
| coverage (nrows + last MJD) | 6–9 ms | 205–493 ms |
| 4-epoch ZD probe, first call | 34–46 ms | 87–251 ms |
| 4-epoch ZD probe, repeat in same process | 0.4 ms | — |

Full pytest run of the two canary tests: 6.2 s on the laptop, 11.3 s on eddington. The run is dominated by the casatools import and pytest startup, not by the canary: the test bodies themselves are 0.02 s + 0.03 s on the laptop and 0.25 s + 0.09 s on eddington. The longer variant in `canary_snippet.py` (adds the coverage check and the snapshot label) took 33.8 s on eddington, because the coverage scan reads the whole IERSeop97 column over the network filesystem.

## 5. Negative controls

Three cases (`negative_control2.py`, scratch copy of the geodetic directory redirected via `CASASITECONFIG`):

1. **Baseline** — both tests pass, window fingerprint `60ece9bd21e01000`.
2. **Data changed**: measured `dUT1` shifted by 1 ms in the window → raw fingerprint `ff5bd7d53e1866a2`, window fingerprint `4a869dbd947b5514`, ZD probe shifted by −3.4e-6 deg. Both canaries fire, and the message names the data.
3. **Code bug** (observatory frame never set) → fingerprints **unchanged**, ZD 67.991084745090 instead of 84.136901677069. Only the behavioural probe fires.

That is the discrimination you asked for: a changed fingerprint plus unchanged code ⇒ the reference values are stale; unchanged fingerprint plus changed ZD ⇒ the code broke.

## 6. The tested snippet

`/private/var/folders/7t/j4mr_7qd43d_ys8gzkqgj3f00000gp/T/opencode/canary_test_final.py` — passes on the laptop (CASA 6.7.4.7; 6.2 s wall time including the casatools import) and, run from the pipeline checkout on eddington (CASA 6.7.3.21, pytest 9.0.2), 2 passed in 11.3 s. Test bodies: 0.02 s and 0.03 s on the laptop, 0.25 s and 0.09 s on eddington.

```python
"""IERS data canary for the ZD regression test."""
import hashlib
import math
import struct

import pytest

from pipeline.infrastructure import casa_tools

TABLES = ("IERSeop97", "IERSpredict", "TAI_UTC", "Observatories")
COLS = {"IERSeop97": ("dUT1", "x", "y"), "IERSpredict": ("dUT1", "x", "y"),
        "TAI_UTC": ("dUTC", "Offset"), "Observatories": ("Long", "Lat", "Height")}
WINDOW = (56000.0, 61000.0)                 # epochs the regression test covers
WINDOW_FP = "60ece9bd21e01000"
PROBE_MJDS = (57000.0, 58007.24477111111, 59000.0, 60967.0)
PROBE_ZD = (84.85496683766004, 84.13690167706928, 104.77194567360485, 128.6106471448433)


def measures_fingerprint(window=WINDOW):
    digest = hashlib.sha256()
    for table, cols in COLS.items():
        with casa_tools.TableReader(casa_tools.utils.resolve("geodetic/" + table)) as tab:
            mjd = None if table == "Observatories" else tab.getcol("MJD")
            for col in cols:
                vals = tab.getcol(col)
                if mjd is not None:
                    vals = [v for m, v in zip(mjd, vals) if window[0] <= m <= window[1]]
                for v in vals:
                    digest.update(struct.pack(">d", float(v)))
    return digest.hexdigest()[:16]


def probe_zd(mjds=PROBE_MJDS):
    me = casa_tools.measures
    me.doframe(me.observatory("ALMA"))
    d = me.direction("J2000", {"value": math.radians(83.6), "unit": "rad"},
                     {"value": math.radians(22.0), "unit": "rad"})
    for mjd in mjds:
        me.doframe(me.epoch("UTC", {"value": mjd, "unit": "d"}))
        yield 90.0 - math.degrees(me.measure(d, "AZELGEO")["m1"]["value"])


@pytest.mark.unit
def test_measures_snapshot_is_known():
    fp = measures_fingerprint()
    if fp != WINDOW_FP:
        pytest.fail(f"geodetic tables changed: window fingerprint {fp} "
                    f"(reference {WINDOW_FP}); re-derive the ZD reference values")


@pytest.mark.unit
def test_zd_probe():
    assert list(probe_zd()) == pytest.approx(PROBE_ZD, rel=1e-12)
```

For "which snapshot am I on" rather than "has it changed", hash `table.f0`/`table.f0i`/`table.f1` bytes instead of values — same loop, no `getcol`, ~4 ms. A longer variant of the same functions, with a `casaconfig.get_data_info` / VS_DATE fallback and an IERS-coverage check, is in `canary_snippet.py`.

## 7. Caveats

- **Ephemerides are a separate axis.** The geodetic fingerprint says nothing about `ephemerides/` (DE200, DE405, JPL-Horizons, SplatDefault.tbl …). The regression MS's TARGET fields have `EPHEMERIS_ID = -1` for the tested field, so planets do not enter this ZD test; if a future test uses a planet field, the fingerprint must be extended with the ephemeris files (`casa_data.get_solar_system_model_files` already does this pattern for Solar System models).
- **The dUT1 cache.** `MeasTable::dUT1` caches a thread-local value considered valid for 0.04 d (57.6 min) — verified: dUT1 at 61300.00 and 61300.02 is identical, at 61300.05 it differs. Keep probe epochs more than 0.04 d apart, and beware that a canary running in the same process as other measures-using tests can read a primed cache. The existing `tests/component/test_casa_measures_dut1_cache.py` handles this with a fresh subprocess. casacore tracks this in [issue 1545](https://github.com/casacore/casacore/issues/1545), opened by Takeshi Nakazato on 2026-11-11, where Alex Offringa says removing the cache costs about 50 ns per call and supports a pull request.
- **Predicted epochs are never reproducible.** Anything past the last measured row of IERSeop97 (61304 / 61309 here) depends on IERSpredict, which changes every update. Pin probe epochs in the past.
- **`table.dat` is a trap.** Never hash it, never use its mtime: it holds the `VS_CREATE`/`VS_DATE` stamps, so two installs of identical data have different `table.dat`. Confirmed for `TAI_UTC`, whose `table.f0` is byte-identical on both machines while `table.dat` differs only in the stamp (`2026/10/21/18:04` vs `2026/10/26/18:06`). Conversely, a `putcol` that changes values rewrites `table.f0` and leaves `table.dat` (and `VS_DATE`) untouched — so `table.dat` is neither a change detector nor a stable identity.
- **CASA version.** The probe values agreed to the last bit between 6.7.4.7 and 6.7.3.21 with the same window data, but the semantic hash depends only on the values, not the table format, so it survives a casacore format change where a byte hash would not.
- **`table.lock` / `table.lock.org`.** Excluded; opening tables read-only does not touch `table.lock` (verified: identical hash and mtime before and after 8 opens).
- **Legacy installs.** Where `measurespath` points at a directory without a `readme.txt`, `get_data_info` reports `'unknown'` and a non-empty `data_update.lock` emits SEVERE log noise on import. The fingerprint still works, since it goes through `casa_tools.utils.resolve`.
- **CASARCFILES does not work here.** Overriding aipsrc via `CASARCFILES` is ignored by this casacore build (a +100 s dUT1 shift in an aipsrc-style override produced zero ZD change); the measurespath-redirect approach is the only one that works for experiments.
- **Where to run it on eddington**: `CASASITECONFIG`/`--configfile` is needed because `~/.casa/config.py` points at a bare `measurespath` whose `ctsys.resolve('geodetic/IERSeop2000')` fails, and `data_auto_update` tries (and fails) to download 336 MB. `casaconfig` parses `--configfile` from `sys.argv`, so it works with `python script.py --configfile=…` but not with `pytest --configfile=…` (pytest rejects the flag); use `HOME=…` with a `.casa/config.py` for pytest.

## 8. Recommendation

Keep the existing hard-coded ZD values in `zd_telmjd_test.py`, but put the *data identity* next to them. The canary should be a two-level check: a **semantic fingerprint of the numeric columns of IERSeop97, IERSpredict, TAI_UTC and Observatories restricted to the epoch window the test exercises** (currently `60ece9bd21e01000`, identical on two machines five days apart in snapshot age, and it moves when the data moves), plus a **four-epoch zenith-distance probe** whose reference values are recorded alongside it. The fingerprint answers "is this the data the expected values came from?" in ~20 ms and needs no CASA computation; the probe answers "does the code produce the expected numbers from this data?". When the fingerprint differs, report the fingerprint, the VS_DATE-derived snapshot label and the IERSeop97/IERSpredict MJD coverage in the failure message and treat the reference values as needing re-derivation rather than treating it as a regression; when the fingerprint matches but the probe differs, the code is broken. Do not try to use `casaconfig`'s version string as the identifier — it is `'unknown'` on any install whose geodetic directory has no `readme.txt`, and `VS_VERSION` is `0001.0001` for every IERS table — the only usable human-readable fallback is VS_DATE from the table keywords.

## Files produced (all outside the repo)

- `canary_test_final.py` — the deliverable: the two-test canary quoted in §6, passes on both machines
- `canary_snippet.py` — the longer variant (raw fingerprint, window fingerprint, coverage, snapshot label, probe), also passes on both machines
- `canary_compact.py` — 15-line version
- `doc_snippet_check.py` — the exact snippet from §6, verified as written (`60ece9bd21e01000`, 1 passed)
- `negative_control2.py`, `column_probe.py`, `eop2000_test.py`, `zd_sensitivity.py` — the controls
- `dump_tables.py` + `iers_dump.json` / `iers_dump_eddington.json` — full numeric dump of the four tables from both machines
- `meta_dump.py`, `sensitivity_probe.py`, `tail_probe.py`, `window_fp.py`, `final_probe.py` — supporting measurements
