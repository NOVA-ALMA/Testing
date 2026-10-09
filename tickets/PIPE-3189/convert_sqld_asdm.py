"""Convert the PIPE-3189 SQLD ASDM to an MS for benchmarking.

This env has the CASA Python bindings (casatasks) but no `casa` CLI, so
importasdm is invoked directly through casatasks.

Usage:
    conda run -n almaPL26CM python convert_sqld_asdm.py
"""
import os
import time

import casatasks

ASDM = ('/Users/users/pbos/almapipe/testdata/2021.1.01195.S/'
        'science_goal.uid___A001_X1590_Xd67/'
        'group.uid___A001_X1590_Xd68/'
        'member.uid___A001_X1590_Xd6b/'
        'raw/uid___A002_Xf160b6_Xa57a.asdm.sdm')

WORKDIR = '/scratch/users/pbos/sqld_test'
VIS = os.path.join(WORKDIR, 'uid___A002_Xf160b6_Xa57a.ms')

os.makedirs(WORKDIR, exist_ok=True)
os.chdir(WORKDIR)

if os.path.exists(VIS):
    print('MS already exists, deleting: %s' % VIS)
    import shutil
    shutil.rmtree(VIS)

print('ASDM : %s' % ASDM)
print('MS   : %s' % VIS)
t0 = time.perf_counter()
casatasks.importasdm(
    asdm=ASDM,
    vis=VIS,
    savecmds=True,
    process_flags=True,
    process_pointing=True,
    overwrite=True,
)
print('importasdm took %.1f s' % (time.perf_counter() - t0))
print('exists:', os.path.exists(VIS))