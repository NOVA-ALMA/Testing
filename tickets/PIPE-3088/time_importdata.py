"""Clean timing of ImportData.prepare() — no profiling overhead.
Run on different branches to compare. Uses a fresh MS copy per run."""
import time, os, shutil, tempfile

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.launcher import Context
from pipeline.h.tasks.importdata.importdata import ImportData, ImportDataInputs
from pipeline.infrastructure.utils.utils import clear_time_cache

MS_SRC = casa_tools.utils.resolve(
    "pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms"
)
MS_BASE = os.path.basename(MS_SRC)

workdir = tempfile.mkdtemp(prefix='zd_timing_')
MS_DST = os.path.join(workdir, MS_BASE)
shutil.copytree(MS_SRC, MS_DST)
os.chdir(workdir)

clear_time_cache()

context = Context()
inputs = ImportDataInputs(
    context=context, vis=MS_DST, output_dir=workdir,
    nocopy=True, datacolumns={'data': 'raw'},
)

t0 = time.perf_counter()
task = ImportData(inputs=inputs)
results = task.prepare()
t1 = time.perf_counter()

os.chdir("/")
shutil.rmtree(workdir, ignore_errors=True)

print(f"ImportData.prepare(): {t1-t0:.4f}s  ({len(results.mses)} MSes)")
