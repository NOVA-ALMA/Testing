import numpy as np

from pipeline.infrastructure import casa_tools

MS = '/scratch/users/pbos/sqld_test/uid___A002_Xf160b6_Xa57a.ms'

from casatools import msmetadata

print('MS      :', MS)
_meta = msmetadata()
_meta.open(MS)
print('nrows   :', _meta.nrows())

with casa_tools.TableReader(MS + '/SPECTRAL_WINDOW') as t:
    names = list(t.getcol('NAME'))
    nchan = list(t.getcol('NUM_CHAN'))
    # CHAN_FREQ is a variable-length column that trips the table reader on this
    # MS; TOTAL_BANDWIDTH is a plain scalar and sufficient for identifying SQLD.
    totbw = list(t.getcol('TOTAL_BANDWIDTH'))
print('n spw   :', len(names))
for n, c, b in zip(names, nchan, totbw):
    print('  nchan=%-6d bw=%8.1f MHz  %s' % (c, b / 1e6, n))

with casa_tools.TableReader(MS + '/OBSERVATION') as t:
    tr = np.ravel(t.getcol('TIME_RANGE')) / 86400.0
print('obs span: %.2f h  (MJD %.6f - %.6f)'
      % ((tr[1] - tr[0]) * 24, tr[0], tr[1]))

# Field-level timestamp counts and sampling, straight from the tables.
# This MS's FIELD table has no FIELD_ID column, so the row index is the field ID.
with casa_tools.TableReader(MS + '/FIELD') as t:
    field_names = [str(x) for x in t.getcol('NAME')]
with casa_tools.TableReader(MS) as t:
    fid = np.array(t.getcol('FIELD_ID'))
    times = np.array(t.getcol('TIME')) / 86400.0

print('\nfield-level sampling (all data columns):')
for f in sorted(set(fid)):
    ts = np.unique(times[fid == f])
    d = np.diff(ts) * 86400.0          # times are in days; report seconds
    name = field_names[f] if f < len(field_names) else '?'
    print('  field %-3d %-20s n_times=%-8d min_dt=%.4fs median_dt=%.4fs '
          'span=%.1f min  -> at 1s: %d pts'
          % (f, name, len(ts), d.min(), np.median(d),
             (ts[-1] - ts[0]) * 1440.0,
             int((ts[-1] - ts[0]) * 86400.0) + 1))