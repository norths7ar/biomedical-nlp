"""
Prepare initial input for the drug_disease pipeline.

The data has already been pre-processed upstream. This step simply loads the
raw input from the data source directory and writes it into the pipeline's
dataset folder so that subsequent steps have a consistent starting point.
"""

from myutils import init_step_logger, parse_args, load_json, save_json
from biomedical_nlp.global_config import DATA_SOURCE_DIR, DATASET_NAME, get_paths
from biomedical_nlp.drug_disease.config import DATA_DIR


# ====== Step Config ======
LOGGER = init_step_logger()

OUTPUT_FILE_NAME = "raw_input.json"


def main():
    args = parse_args()
    LOGGER.info("Args: %s", vars(args))
    force_overwrite: bool = args.force_overwrite
    dataset: str = args.dataset or DATASET_NAME

    input_file_name = f"{dataset}_raw.json"
    input_path = DATA_SOURCE_DIR / dataset / input_file_name
    _, output_path = get_paths(DATA_DIR, dataset, input_file_name, OUTPUT_FILE_NAME)

    if output_path.exists() and not force_overwrite:
        LOGGER.info("%s already exists. Skipping.", output_path.name)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = load_json(input_path)
    LOGGER.info("Loaded %d records from %s", len(data), input_path)

    save_json(data, output_path)
    LOGGER.info("Saved %d records to %s", len(data), output_path)


if __name__ == "__main__":
    main()
