"""Profile ImportData.prepare() to measure ZD/telmjd overhead.
Run on different branches to compare. Uses a fresh MS copy per run.""" 
import cProfile, pstats, io, time, os, shutil, tempfile

from pipeline.infrastructure import casa_tools
from pipeline.infrastructure.launcher import Context
from pipeline.h.tasks.importdata.importdata import ImportData, ImportDataInputs
from pipeline.infrastructure.utils.utils import clear_time_cache

MS_SRC = casa_tools.utils.resolve(
    "pl-unittest/uid___A002_Xc46ab2_X15ae_repSPW_spw16_17_small.ms"
)
MS_BASE = os.path.basename(MS_SRC)

workdir = tempfile.mkdtemp(prefix='zd_profile_')
MS_DST = os.path.join(workdir, MS_BASE)
print(f"Copying {MS_SRC} -> {MS_DST} ...")
shutil.copytree(MS_SRC, MS_DST)
print("Done.")

os.chdir(workdir)
clear_time_cache()

context = Context()
inputs = ImportDataInputs(
    context=context, vis=MS_DST, output_dir=workdir,
    nocopy=True, datacolumns={'data': 'raw'},
)

prof = cProfile.Profile()
prof.enable()
t0 = time.time()
task = ImportData(inputs=inputs); results = task.prepare()
t1 = time.time()
prof.disable()

total = t1 - t0
print(f"\nTotal ImportData.prepare(): {total:.3f}s")
print(f"MSes: {len(results.mses)}")

s = io.StringIO()
pstats.Stats(prof, stream=s).sort_stats('cumtime').print_stats()

lines = s.getvalue().split('\n')
for tag in ('zenith', 'zd_telmjd', 'telmjd', 'set_zd', 'set_field_zd'):
    for l in lines:
        if tag in l.lower():
            print(f"  ZD: {l.strip()}")

print("\n--- Top 20 cumulative ---")
pstats.Stats(prof, stream=sys.stdout).sort_stats('cumtime').print_stats(20)

os.chdir("/")
shutil.rmtree(workdir, ignore_errors=True)
