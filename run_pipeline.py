import argparse
import sys
import subprocess
from pathlib import Path
from myutils import get_logger

LOGGER = get_logger("run_pipeline", with_date=True)

VALID_PIPELINES = [
    "drug_disease",
    # "drug_protein",
    # "drug_target",
    # "clinical_trial",
]


def run_step(script_path: Path, extra_args: list[str]) -> None:
    """Run a single step script, forwarding CLI args (e.g. --dataset, --force_overwrite)."""
    try:
        subprocess.run(
            [sys.executable, "-u", str(script_path)] + extra_args,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        LOGGER.error("❌ Step %s failed (code %d)", script_path.name, e.returncode)
        sys.exit(1)


def run_pipeline(pipeline_name: str, extra_args: list[str]) -> None:
    """Run all stepXX_*.py scripts for the specified pipeline in order."""
    try:
        config_module = __import__(
            f"biomedical_nlp.{pipeline_name}.config",
            fromlist=["PIPELINE_DIR"],
        )
        pipeline_dir = config_module.PIPELINE_DIR
    except (ImportError, AttributeError) as e:
        LOGGER.error("❌ Failed to load config for pipeline '%s': %s", pipeline_name, e)
        sys.exit(1)

    step_scripts = sorted(pipeline_dir.glob("step[0-9][0-9]*_*.py"))

    if not step_scripts:
        LOGGER.error("⚠️  No step scripts found in %s", pipeline_dir)
        sys.exit(1)

    LOGGER.info("🚀 Running %s pipeline with %d steps...", pipeline_name, len(step_scripts))
    LOGGER.info("📁 Pipeline directory: %s", pipeline_dir)
    LOGGER.info("🔍 Found steps: %s", [s.name for s in step_scripts])
    LOGGER.info("")

    for script in step_scripts:
        LOGGER.info("▶️  Running %s...", script.name)
        run_step(script, extra_args)
        LOGGER.info("✅ %s completed", script.name)
        LOGGER.info("")

    LOGGER.info("🎉 Pipeline %s completed successfully!", pipeline_name)


def main():
    parser = argparse.ArgumentParser(description="Run a biomedical NLP pipeline.")
    parser.add_argument("pipeline", choices=VALID_PIPELINES, help="Pipeline to run")
    parser.add_argument("-d", "--dataset", type=str, default=None,
                        help="Override the active dataset (default: DATASET_NAME in global_config)")
    parser.add_argument("-f", "--force_overwrite", action="store_true",
                        help="Force re-run of all steps even if output already exists")
    args = parser.parse_args()

    extra_args: list[str] = []
    if args.dataset:
        extra_args += ["--dataset", args.dataset]
    if args.force_overwrite:
        extra_args.append("--force_overwrite")

    run_pipeline(args.pipeline, extra_args)


if __name__ == "__main__":
    main()
