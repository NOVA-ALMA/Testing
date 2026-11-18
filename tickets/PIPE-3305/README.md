# PIPE-3305: data fingerprint for the zenith distance test

This folder holds the code and the measurements for PIPE-3305. The code runs on CASA 6.7.4.7
(macOS) and 6.7.3.21 (Linux). It needs no test data.

## The helper

```python
import hashlib
import struct

from pipeline.infrastructure import casa_tools

GEODEDIC_TABLES = ("IERSeop97", "IERSpredict", "TAI_UTC", "Observatories")
GEODEDIC_COLUMNS = {
    "IERSeop97": ("dUT1", "x", "y"),
    "IERSpredict": ("dUT1", "x", "y"),
    "TAI_UTC": ("dUTC", "Offset"),
    "Observatories": ("Long", "Lat", "Height"),
}
EPOCH_WINDOW = (56000.0, 61000.0)


def get_measures_fingerprint(window=EPOCH_WINDOW):
    """16 hex characters over the values measures() reads for a zenith distance."""
    digest = hashlib.sha256()
    for name in GEODEDIC_TABLES:
        path = casa_tools.utils.resolve("geodetic/" + name)
        with casa_tools.TableReader(path) as table:
            mjd = None if name == "Observatories" else table.getcol("MJD")
            for column in GEODEDIC_COLUMNS[name]:
                values = table.getcol(column)
                if mjd is not None:
                    values = [v for m, v in zip(mjd, values) if window[0] <= m <= window[1]]
                for value in values:
                    digest.update(struct.pack(">d", float(value)))
    return digest.hexdigest()[:16]
```

Value on two machines with different data sets: `60ece9bd21e01000`.

## Why these four tables

We deleted each table in a copy of the geodetic directory and measured the effect.

| table | effect on a zenith distance |
|---|---|
| `IERSeop97` | `measures` raises. It is required. |
| `IERSpredict` | `measures` raises. It is required. |
| `TAI_UTC` | `measures` raises. It is required. |
| `Observatories` | falls back to a default observatory. The value changes. |
| `IERSeop2000` | casatools cannot start. Its values have no effect. |
| `IERSpredict2000` | no effect |
| `IGRF` | no effect |
| `SCHED_locations` | no effect |

The pipeline class `IERSInfo` in `pipeline/infrastructure/utils/casa_data.py` reads `IERSpredict`
and `IERSeop2000`. That pair is correct for the PIPE-1231 date check. It is not correct for a
zenith distance check.

## What moves a zenith distance

Probe at MJD 58007.24477111111, ALMA observatory.

| column | change | zenith distance change (deg) |
|---|---|---|
| `IERSeop97` dUT1 | 1 s | −3.428e-3 |
| `IERSeop97` dUT1 | 1 ms | −3.428e-6 |
| `IERSeop97` x, y | 1e-4 rad | about 1e-8 |
| `Observatories` Long | 1e-4 deg | −8.2e-5 |
| `Observatories` Lat | 1e-4 deg | −4.5e-5 |
| `Observatories` Height | 100 m | −1.4e-9 |
| `TAI_UTC` dUTC | 1 s | 1.3e-9 |
| `IERSeop97` dPsi, dEps, LOD, Dx, Dy, DdUT1 | any | 0 |

The test tolerance is about 1.1e-8 deg. A dUT1 change of about 25 µs breaks it. No person can
see that. This is why we need the digest.

## Checks we ran

| change | digest | probe zenith distance |
|---|---|---|
| none | `60ece9bd21e01000` | 84.136901677069 |
| dUT1 in the window +1 ms | `4a869dbd947b5514` | 84.136898... (−3.4e-6 deg) |
| observatory frame not set | no change | 67.991084745090 |

The last row is the useful one. The data did not change. The code did.

## Rules

1. Hash `table.f0`. Do not hash `table.dat`. `table.dat` holds `VS_CREATE` and `VS_DATE`.
2. A whole-file digest changes at every update. Use it only as a label.
3. Use probe epochs in the past. Dates after the last measured row are predictions.
4. Keep probe epochs more than 0.04 d apart. casacore caches dUT1 for 0.04 d. casacore issue
   1545 discusses removing that cache.

## Files

- `canary_measures_digest.py` — the tested helper and the two tests.
- `measurements.md` — the full measurements and the caveats.
