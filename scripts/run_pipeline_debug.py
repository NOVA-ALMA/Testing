import argparse
import glob
import os
import pickle
import shutil

import pipeline; pipeline.initcli()
import pipeline.recipereducer

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
CONTEXT_DIR = os.path.join(SCRIPTS_DIR, "../working")


def clean_stage(stage):
    for stage_dir in glob.glob(os.path.join(CONTEXT_DIR, f"**/stage{stage}"), recursive=True):
        print(f"Removing {stage_dir}")
        shutil.rmtree(stage_dir)


def save_context(context, stage):
    path = os.path.join(CONTEXT_DIR, f"context_stage_{stage:03d}.pkl")
    with open(path, "wb") as f:
        pickle.dump(context, f)


def load_context(stage):
    path = os.path.join(CONTEXT_DIR, f"context_stage_{stage:03d}.pkl")
    with open(path, "rb") as f:
        return pickle.load(f)


def run_pipeline(vis, procedure, START_STAGE=1, EXIT_STAGE=None):
    original_dir = os.getcwd()
    os.chdir(CONTEXT_DIR)

    pipe_ = procedure.split("/")[-1].replace(".xml","")
    os.system(f"rm -rvf pipeline-{pipe_}/html/stage{START_STAGE}")
    try:
        context = load_context(START_STAGE - 1) if START_STAGE > 1 else None

        kwargs = dict(vis=vis, procedure=procedure, loglevel="debug", context=context, startstage=START_STAGE)
        if EXIT_STAGE is not None:
            kwargs["exitstage"] = EXIT_STAGE

        context = pipeline.recipereducer.reduce(**kwargs)
    except Exception as e:
        print(f"Pipeline error: {e}")
        raise
    finally:
        os.chdir(original_dir)

    if EXIT_STAGE is not None:
        save_context(context, EXIT_STAGE)
    return context

vis = ["uid___A002_X1181695_X1c6a4.asdm.sdm"]
procedure = "../rawdata/uid___A002_X1181695_X1c6a4_calimage.xml"

parser = argparse.ArgumentParser(description="Run pipeline debug script")
parser.add_argument("--start-stage", type=int, default=None, help="Stage to start the pipeline from")
parser.add_argument("--exit-stage", type=int, default=None, help="Stage to exit the pipeline at")
parser.add_argument("--clean", action="store_true", help="Remove stage output directories before re-running")
args = parser.parse_args()

start = args.start_stage
end = args.exit_stage

if start is None and end is None:
    # Full pipeline in a single call
    print("Running full pipeline")
    context = run_pipeline(vis, procedure, START_STAGE=1)

elif start is not None and end is None:
    # From start_stage to the end, single call
    print(f"Running pipeline from stage {start} to end")
    os.environ["WEBLOG_RERENDER_STAGES"] = str(start)
    context = run_pipeline(vis, procedure, START_STAGE=start)

elif start is None and end is not None:
    # From the beginning to exit_stage, stage by stage
    rerender_stages = ",".join(str(s) for s in range(1, end + 1))
    os.environ["WEBLOG_RERENDER_STAGES"] = rerender_stages
    for stage in range(1, end + 1):
        if args.clean:
            clean_stage(stage)
        print(f"Running pipeline from stage {stage} to {stage}")
        context = run_pipeline(vis, procedure, START_STAGE=stage, EXIT_STAGE=stage)

else:
    # Both provided: stage by stage with checkpointing
    rerender_stages = ",".join(str(s) for s in range(start, end + 1))
    os.environ["WEBLOG_RERENDER_STAGES"] = rerender_stages
    for stage in range(start, end + 1):
        if args.clean:
            clean_stage(stage)
        print(f"Running pipeline from stage {stage} to {stage}")
        context = run_pipeline(vis, procedure, START_STAGE=stage, EXIT_STAGE=stage)