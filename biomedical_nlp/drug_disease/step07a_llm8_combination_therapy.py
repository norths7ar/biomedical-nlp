"""
LLM-based combination therapy detection step.

This step re-analyzes all chemical–disease relations within the same PMID to determine
if multiple chemicals are discussed as part of combination therapy.

Input:  stage_duplicate_disease_removed.jsonl (from step06b)
Output: llm8_combination_therapy.jsonl
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from langchain_openai import ChatOpenAI
from myutils import (
    init_step_logger,
    parse_args,
    load_text,
    load_jsonl,
    iter_jsonl,
    add_to_jsonl,
    save_jsonl,
)
from biomedical_nlp.global_config import DATASET_NAME, DEEPSEEK_API_KEY, get_paths
from biomedical_nlp.drug_disease.config import DATA_DIR, PROMPT_DIR
from biomedical_nlp.llm_client import LLMResult, get_llm_response, clean_json_response


# ====== Step Config =======
LOGGER = init_step_logger()

MODEL = "deepseek-chat"
MAX_TOKENS = 8192
TEMPERATURE = 0.4
BATCH_SIZE = 100

PROMPT_FILE_NAME = "fix_combination_therapy.md"
INPUT_FILE_NAME = "stage_duplicate_disease_removed.jsonl"
OUTPUT_FILE_NAME = "llm8_combination_therapy.jsonl"

llm = ChatOpenAI(model=MODEL, api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", max_tokens=MAX_TOKENS, temperature=TEMPERATURE)


def build_records(output_path: Path) -> set[tuple[str, str]]:
    """Build set of completed (pmid, disease_name) pairs from existing output file."""
    records: set[tuple[str, str]] = set()
    for item in iter_jsonl(output_path):
        if item.get("decode_error", False):
            continue
        pmid = item["pmid"]
        disease_name = item.get("disease_name", "")
        records.add((pmid, disease_name))
    return records


def generate_input_data(relations: list[dict]) -> list[dict]:
    """Group relations by PMID -> disease -> list of chemicals."""
    pmid_to_data: dict[str, dict] = defaultdict(
        lambda: {"title": "", "abstract": "", "diseases": defaultdict(list)}
    )
    for r in relations:
        pmid = r["pmid"]
        disease_name = r["disease_name"].lower()
        item = pmid_to_data[pmid]
        item["title"] = r.get("title", "")
        item["abstract"] = r.get("abstract", "")
        item["diseases"][disease_name].append({
            "chemical_name": r["chemical_name"].lower(),
            "relation_type": r.get("relation_type", "")
        })

    output = []
    for pmid, info in pmid_to_data.items():
        for disease_name, chems in info["diseases"].items():
            if len(chems) < 2:
                # Skip if less than 2 chemicals (no potential for combination)
                continue
            output.append({
                "pmid": pmid,
                "title": info["title"],
                "abstract": info["abstract"],
                "disease_name": disease_name,
                "chemicals": chems
            })
    return output


def main():
    args = parse_args()
    LOGGER.info("Args: %s", vars(args))
    max_items: int | None = args.max_items
    force_overwrite: bool = args.force_overwrite
    dataset: str = args.dataset or DATASET_NAME

    input_path, output_path = get_paths(
        DATA_DIR, dataset, INPUT_FILE_NAME, OUTPUT_FILE_NAME
    )
    LOGGER.info("Input path: %s", input_path)
    LOGGER.info("Output path: %s", output_path)

    if force_overwrite and output_path.exists():
        output_path.unlink()
    if output_path.exists():
        completed_pairs: set[tuple[str, str]] = build_records(output_path)
        LOGGER.info(
            "Loaded %d completed (pmid, disease) pairs from %s",
            len(completed_pairs), output_path.name
        )
    else:
        completed_pairs = set()

    relations = load_jsonl(input_path)
    input_data = generate_input_data(relations)
    LOGGER.info("Generated %d (pmid, disease) groups for LLM analysis", len(input_data))

    prompt_template: str = load_text(PROMPT_DIR / PROMPT_FILE_NAME)

    batch_buffer: list[dict] = []
    total_expected = len(input_data)
    log_counter = len(completed_pairs) + 1
    new_processed_counter = 0

    try:
        for item in input_data:
            pmid = item["pmid"]
            disease_name = item["disease_name"]
            if (pmid, disease_name) in completed_pairs:
                LOGGER.debug(
                    "Skipping PMID %s (disease %s already processed)", pmid, disease_name
                )
                continue

            chems = item["chemicals"]
            title = item["title"]
            abstract = item["abstract"]

            relation_lines = "\n".join(
                [f"{c['chemical_name']} ({c['relation_type']}) — {disease_name}" for c in chems]
            )

            user_prompt = (
                f"Title: {title}\n\nAbstract: {abstract}\n\n"
                f"Relations for disease {disease_name}:\n{relation_lines}"
            )

            LOGGER.info(
                "Querying LLM for [%d/%d] PMID %s, disease %s",
                log_counter, total_expected, pmid, disease_name
            )

            result: LLMResult = get_llm_response(
                llm,
                user_prompt=user_prompt,
                system_prompt=prompt_template,
                logger=LOGGER,
            )

            response = clean_json_response(result.content)
            try:
                response_dict: dict = json.loads(response)
                response_dict["decode_error"] = False
            except json.JSONDecodeError:
                LOGGER.warning("Failed to decode JSON for PMID %s", pmid)
                response_dict = {"decode_error": True}

            response_dict["pmid"] = pmid
            response_dict["disease_name"] = disease_name

            batch_buffer.append(response_dict)
            completed_pairs.add((pmid, disease_name))
            new_processed_counter += 1
            log_counter += 1

            if max_items is not None and new_processed_counter >= max_items:
                LOGGER.info("Reached max items limit (%d)", max_items)
                break

            if len(batch_buffer) >= BATCH_SIZE:
                add_to_jsonl(batch_buffer, output_path)
                batch_buffer.clear()
                LOGGER.info("Flushed %d items to %s", BATCH_SIZE, output_path.name)

    except KeyboardInterrupt:
        LOGGER.error("KeyboardInterrupt detected.")
        if batch_buffer:
            add_to_jsonl(batch_buffer, output_path)
        LOGGER.info("Graceful exit due to user interruption.")
        sys.exit(0)

    else:
        if batch_buffer:
            add_to_jsonl(batch_buffer, output_path)

        if not output_path.exists():
            output_path.touch()
            LOGGER.info("No combination therapy groups found. Created empty output file.")

        LOGGER.info("Finished processing. Output → %s", output_path.name)


if __name__ == "__main__":
    main()
