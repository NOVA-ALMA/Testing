# PIPE-3189 — weblog comparison across variants

T2-2-4 (Sky Setup) rendered for every variant with `../scripts/render_weblog_zd.py`
and compared pairwise with `../scripts/compare_weblogs.py`.
Raw output: `COMPARISON.txt`. Images: `sqld_{main,greedy,stratified}/`,
`small_ms_{main,greedy,stratified}/`.

A pixel counts as differing when any channel differs by more than 8/255.

## What is identical

For **both** measurement sets and **both** variant pairs, everything except the
Zenith-Angle plot is byte-for-byte identical:

| Artefact | SQLD | Continuum |
|---|---|---|
| `t2-2-4.html` | **identical** (3254 bytes) | **identical** (4518 bytes) |
| `azel.png` | **identical** | **identical** |
| `el_vs_time.png` | **identical** | **identical** |
| `uv_coverage.png` | **identical** | **identical** |
| `solar_el_vs_time.png` | absent in *every* variant | **identical** |
| `zd_telmjd.png` | differs by design | differs by design |

The HTML being identical matters: the page carries no ZD numbers of its own,
so the only thing that can change visually is the plot itself.

## `zd_telmjd.png` — the plot that is supposed to change

| Comparison | SQLD px (% ) | SQLD mean ch | Continuum px (%) | Continuum mean ch |
|---|---|---|---|---|
| `main` vs `greedy` | 1430 (0.465 %) | 0.336 | 6444 (2.098 %) | 2.853 |
| `main` vs `stratified` | **1373 (0.447 %)** | **0.302** | **6348 (2.066 %)** | **2.734** |
| `greedy` vs `stratified` | 702 (0.229 %) | 0.051 | 6426 (2.092 %) | 2.787 |

The stratified plot is *closer to `main`* than the greedy one is, on both
data sets — consistent with it keeping 7 % more points (3,181 vs 2,973 on
SQLD, 59 vs 55 on the continuum MS) and placing them on an exact 1 s grid
instead of greedy's 1.008 s.

The SQLD plot is much closer to `main` than the continuum one (0.447 % vs
2.066 %): at 190,080 input points the curve already saturates the 640x480
render as a solid band, so ~3,000 points reproduce it essentially exactly.
The residual difference is anti-aliasing on the marker glyphs.

`greedy` vs `stratified` on SQLD differs by only 0.051 mean channel diff —
the two decimations draw visually the same curve.

## Why thumbnails are never byte-identical

Thumbnail PNGs embed metadata recording when and from where they were made:

```
tIME              render clock
tEXt date:create  render timestamp
tEXt date:modify  render timestamp
tEXt date:timestamp
tEXt Thumb::MTime
tEXt Thumb::URI   file:///tmp/... output path
```

Everything else, including **all `IDAT` data, i.e. every pixel**, is identical —
`COMPARISON.txt` reports `IDAT identical: True` for them explicitly. So a
byte difference in a thumbnail carries no visual information.

## Reading the numbers

| | SQLD MS | Continuum MS |
|---|---|---|
| Points `main` → `stratified` | 190,080 → 3,181 | 74 → 59 |
| Pixels differing > 8/255 | 1373 (0.447 %) | 6348 (2.066 %) |
| Mean channel diff | 0.302 | 2.734 |

The underlying numeric comparison (in `../fidelity/`) is stronger than the
pixel one: ZD min/max delta is exactly `0.000e+00` on every field of both
data sets, and the drawn curve deviates from the full-resolution curve by at
most 5.2e-08 deg (SQLD) / 1.8e-07 deg (continuum), against ZD ranges of
12.67 deg and 0.031 deg respectively.

## `zd_avg` in the summary table

`zd_avg` is rendered by `t2-1_details.mako` as `round(zd_avg, 2)` and is *not*
part of this page, so it does not show up in any image above. It does change:

| | `main` | `greedy` | `stratified` |
|---|---|---|---|
| SQLD, all TARGET fields | 26.9906 → **26.99** | 26.9951 → **27.00** | 26.9815 → **26.98** |
| Continuum | 22.6893 → **22.69** | 22.6916 → **22.69** | 22.6908 → **22.69** |

On SQLD any decimation moves the second decimal; the continuum MS is
unaffected. Per field the shift is at most 0.011 deg, i.e. 0.09 % of the
12.67 deg range, and the two decimations are within 0.015 deg of each other.
See `../fidelity/*_summary.txt` for how this was measured.

## Pre-existing issue: the missing solar plot

`solar_el_vs_time.png` is absent from **every SQLD variant**. It is *not*
absent from the continuum variant, which is what makes it look like a
regression at first glance — the real cause is `plotsuntrack.py`:

```python
vis = vis.split('/')[-1]                      # plotsuntrack.py:27
with casa_tools.MSMDReader(vis) as msmd:      # opens the basename
    ...
```

The directory is stripped, so `MSMDReader` resolves the MS against the
**current working directory**. The plot renders only when the cwd happens to
contain a directory entry of that name. Reproduced with
`../debug_suntrack.py`, which shows the swallowed traceback:

```
OSError: No such file or directory: 'uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms'
```

`SunTrackChart.plot()` hides this behind a bare `except: return None`, so the
image and its whole HTML block silently disappear. That is why the plot is
present in all three continuum renders and absent from all three SQLD
renders: the continuum renders were made with the MS resolvable from the
cwd (`render_weblog_zd.py` does not `chdir`, so this depends entirely on how
the script is invoked), the SQLD ones were not. The comparison is therefore
still like-for-like — each MS is rendered with the same solar coverage in
every variant. Pre-existing and unrelated to PIPE-3189, but it should get
its own ticket: the fix is to keep the path instead of stripping it.
