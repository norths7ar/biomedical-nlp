from myutils import (init_step_logger, parse_args, load_jsonl, add_to_jsonl)
from biomedical_nlp.global_config import DATASET_NAME, get_paths
from biomedical_nlp.drug_disease.config import DATA_DIR

LOGGER = init_step_logger()
BATCH_SIZE = 100
INPUT_FILE_NAME = "llm3_chemical_abbr.jsonl"
OUTPUT_FILE_NAME = "stage_chemical_abbr_resolved.jsonl"
POP_FIELDS = ["is_abbr", "full_name", "full_name_source", "confidence"]

def process_item(item: dict) -> dict:
    is_abbr = item.get("is_abbr", False)
    full_name = item.get("full_name")
    if is_abbr and full_name:
        item["chemical_name"] = full_name
    for f in POP_FIELDS:
        item.pop(f, None)
    return item

def main():
    args = parse_args()
    LOGGER.info("Args: %s", vars(args))
    force_overwrite: bool = args.force_overwrite
    dataset: str = args.dataset or DATASET_NAME
    input_path, output_path = get_paths(DATA_DIR, dataset, INPUT_FILE_NAME, OUTPUT_FILE_NAME)
    data = load_jsonl(input_path)
    if force_overwrite and output_path.exists():
        output_path.unlink()
    if output_path.exists():
        completed_relationids = {x["relationid"] for x in load_jsonl(output_path)}
        LOGGER.info("Loaded %d processed items from previous run.", len(completed_relationids))
    else:
        completed_relationids = set()
    batch_buffer = []
    try:
        for item in data:
            rid = item["relationid"]
            if rid in completed_relationids:
                continue
            updated = process_item(item)
            batch_buffer.append(updated)
            if len(batch_buffer) >= 100:
                add_to_jsonl(batch_buffer, output_path)
                LOGGER.info("Flushed %d items → %s", BATCH_SIZE, output_path.name)
                batch_buffer.clear()
    except KeyboardInterrupt:
        LOGGER.warning("KeyboardInterrupt — flushing partial batch.")
    finally:
        if batch_buffer:
            add_to_jsonl(batch_buffer, output_path)
    LOGGER.info("Finished. Output → %s", output_path.name)

if __name__ == "__main__":
    main()
