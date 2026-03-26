"""
LLM Step 1 — Resolve disease abbreviations.

For each relation entry, asks the LLM whether the disease mention is an
abbreviation and, if so, what the full name is.  Results are written
incrementally to a JSONL file and deduplicated on exit.
"""

import json
import sys
from pathlib import Path

from langchain_openai import ChatOpenAI
from myutils import (
    init_step_logger,
    parse_args,
    load_text,
    load_json,
    iter_jsonl,
    load_jsonl,
    add_to_jsonl,
    save_jsonl,
)
from biomedical_nlp.global_config import DATASET_NAME, DEEPSEEK_API_KEY, get_paths
from biomedical_nlp.drug_disease.config import PIPELINE_DIR, PROMPT_DIR, DATA_DIR
from biomedical_nlp.llm_client import LLMResult, get_llm_response, clean_json_response


# ====== Step Config ======
LOGGER = init_step_logger()
ENTITY_CACHE: dict[tuple, dict] = {}

MODEL = "deepseek-chat"
MAX_TOKENS = 8192
BATCH_SIZE = 100

PROMPT_FILE_NAME = "rename_disease_abbr.md"
INPUT_FILE_NAME = "raw_input.json"
OUTPUT_FILE_NAME = "llm1_disease_abbr.jsonl"

llm = ChatOpenAI(
    model=MODEL,
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
    max_tokens=MAX_TOKENS,
)


def build_entity_cache(output_path: Path) -> set[str]:
    """Populate ENTITY_CACHE from an existing output file; return processed relation IDs."""
    records: set[str] = set()
    for item in iter_jsonl(output_path):
        if item.get("decode_error", False):
            continue
        if "is_abbr" not in item:
            continue
        records.add(item["relationid"])
        key = (item["disease_biokdeid"], item["pmid"])
        ENTITY_CACHE[key] = {
            "is_abbr": item["is_abbr"],
            "full_name": item["full_name"],
            "full_name_source": item["full_name_source"],
            "confidence": item["confidence"],
        }
    return records


def main():
    args = parse_args()
    LOGGER.info("Args: %s", vars(args))
    max_items: int = args.max_items
    force_overwrite: bool = args.force_overwrite
    dataset: str = args.dataset or DATASET_NAME

    input_path, output_path = get_paths(DATA_DIR, dataset, INPUT_FILE_NAME, OUTPUT_FILE_NAME)
    article_data: list[dict] = load_json(input_path)
    valid_relationids: set[str] = {item["relationid"] for item in article_data}

    if force_overwrite and output_path.exists():
        output_path.unlink()
    if output_path.exists():
        completed_relationids = build_entity_cache(output_path)
        LOGGER.info("Loaded %d cached entity entries.", len(ENTITY_CACHE))
        LOGGER.info("Loaded %d records from %s", len(completed_relationids), output_path.name)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        completed_relationids = set()

    # Warm cache from the drug_target pipeline if it has already run on this dataset
    reference_file = (
        PIPELINE_DIR.parent / "drug_target" / "data" / dataset / OUTPUT_FILE_NAME
    )
    if reference_file.exists():
        LOGGER.info("Building cache from reference file: %s", reference_file)
        build_entity_cache(reference_file)

    prompt_template: str = load_text(PROMPT_DIR / PROMPT_FILE_NAME)
    batch_buffer: list[dict] = []
    log_total_expected = len(article_data)
    log_counter = len(completed_relationids) + 1
    new_processed_counter = 0

    try:
        for article_info in article_data:
            if article_info["relationid"] in completed_relationids:
                LOGGER.debug(
                    "Skipping %s — already processed.", article_info["relationid"]
                )
                continue

            article_info["llm_step"] = "check_disease_abbr"
            pmid = article_info["pmid"]
            entity_id = article_info["disease_biokdeid"]
            mention = article_info["disease_name"]

            if not mention:
                LOGGER.warning("Empty disease mention in %s, skipping.", pmid)
                continue

            key = (entity_id, pmid)

            if key in ENTITY_CACHE:
                LOGGER.info("Cache hit for %s", key)
                article_info.update(ENTITY_CACHE[key])
            else:
                prompt = prompt_template.format(
                    DISEASE=mention,
                    TITLE=article_info["title"],
                    ABSTRACT=article_info["abstract"],
                )
                LOGGER.info(
                    "Querying LLM for entry [%d/%d]: %s",
                    log_counter,
                    log_total_expected,
                    article_info["relationid"],
                )

                result: LLMResult = get_llm_response(
                    llm,
                    user_prompt=prompt,
                    logger=LOGGER,
                )
                response = clean_json_response(result.content)
                try:
                    response_dict = json.loads(response)
                except json.JSONDecodeError:
                    response_dict = {}

                if response_dict:
                    article_info.update(response_dict)
                    article_info["decode_error"] = False
                    ENTITY_CACHE[key] = response_dict
                    completed_relationids.add(article_info["relationid"])
                    new_processed_counter += 1
                else:
                    article_info["decode_error"] = True
                    article_info["llm_raw_response"] = response

            batch_buffer.append(article_info)
            log_counter += 1

            if max_items is not None and new_processed_counter >= max_items:
                LOGGER.info("Reached max_items limit (%d). Stopping.", max_items)
                break

            if len(batch_buffer) >= BATCH_SIZE:
                add_to_jsonl(batch_buffer, output_path)
                batch_buffer.clear()
                LOGGER.info("Flushed %d items to %s.", BATCH_SIZE, output_path.name)

    except KeyboardInterrupt:
        LOGGER.error("KeyboardInterrupt detected.")
        if batch_buffer:
            add_to_jsonl(batch_buffer, output_path)
        LOGGER.info("Graceful exit.")
        sys.exit(0)

    else:
        if batch_buffer:
            add_to_jsonl(batch_buffer, output_path)

        # Deduplicate: keep the latest valid record per relationid
        try:
            existing_output: list[dict] = load_jsonl(output_path)
            LOGGER.info("Loaded %d items for deduplication.", len(existing_output))
            all_items: dict[str, dict] = {}

            for item in existing_output:
                relationid = item.get("relationid")

                if relationid not in valid_relationids:
                    LOGGER.warning("Skipping invalid relationid: %s", relationid)
                    continue

                prev = all_items.get(relationid)
                if prev is None:
                    all_items[relationid] = item
                elif prev.get("decode_error") is False:
                    prev.pop("llm_raw_response", None)
                else:
                    all_items[relationid] = item

            save_jsonl(all_items.values(), output_path)
            LOGGER.info(
                "Deduplicated output written to %s. Total: %d items.",
                output_path.name,
                len(all_items),
            )
        except Exception as e:
            LOGGER.error("Failed to deduplicate output: %s", e)


if __name__ == "__main__":
    main()
