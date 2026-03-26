import json
import sys
from pathlib import Path
from langchain_openai import ChatOpenAI
from myutils import (init_step_logger, parse_args, load_text, load_jsonl, iter_jsonl, add_to_jsonl, save_jsonl)
from biomedical_nlp.global_config import DATASET_NAME, DEEPSEEK_API_KEY, get_paths
from biomedical_nlp.drug_disease.config import DATA_DIR, PIPELINE_DIR, PROMPT_DIR
from biomedical_nlp.llm_client import LLMResult, get_llm_response, clean_json_response

LOGGER = init_step_logger()
ENTITY_CACHE: dict[tuple[str, str, str], bool] = {}
MODEL = "deepseek-chat"
MAX_TOKENS = 8192
TEMPERATURE = 0.4
BATCH_SIZE = 100
PROMPT_FILE_NAME = "validate_disease.md"
INPUT_FILE_NAME = "stage_disease_abbr_resolved.jsonl"
OUTPUT_FILE_NAME = "llm2_validate_disease.jsonl"
REFERENCE_FILE_NAME = "llm2_validate_disease.jsonl"

llm = ChatOpenAI(model=MODEL, api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", max_tokens=MAX_TOKENS, temperature=TEMPERATURE)

def build_entity_cache(output_path: Path) -> set[str]:
    records: set[str] = set()
    for item in iter_jsonl(output_path):
        if item.get("decode_error", False):
            continue
        records.add(item["relationid"])
        try:
            pmid = item["pmid"]
            entity_id = item["disease_biokdeid"]
            mention = item["disease_name"]
            valid = item.get("disease_valid", False)
            if valid is not None:
                key = (entity_id, mention, pmid)
                ENTITY_CACHE[key] = valid
        except KeyError:
            continue
    return records

def main():
    args = parse_args()
    LOGGER.info("Args: %s", vars(args))
    max_items: int = args.max_items
    force_overwrite: bool = args.force_overwrite
    dataset: str = args.dataset or DATASET_NAME
    input_path, output_path = get_paths(DATA_DIR, dataset, INPUT_FILE_NAME, OUTPUT_FILE_NAME)
    article_data: list[dict] = load_jsonl(input_path)
    valid_relationids: set[str] = {item["relationid"] for item in article_data}
    if force_overwrite and output_path.exists():
        output_path.unlink()
    if output_path.exists():
        completed_relationids = build_entity_cache(output_path)
        LOGGER.info("Loaded %d cached entity entries.", len(ENTITY_CACHE))
        LOGGER.info("Loaded %d records from %s", len(completed_relationids), output_path.name)
    else:
        completed_relationids = set()
    reference_file = PIPELINE_DIR.parent / "drug_target" / "data" / dataset / REFERENCE_FILE_NAME
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
                LOGGER.debug("Skipping article_info: %s because it has already been processed", article_info["relationid"])
                continue
            article_info["llm_step"] = "validate_disease"
            pmid = article_info["pmid"]
            entity_id = article_info["disease_biokdeid"]
            mention = article_info["disease_name"]
            if not mention:
                LOGGER.warning("Mention is not valid in %s, please check.", pmid)
                continue
            response = None
            response_dict = None
            cache_key = (entity_id, mention, pmid)
            if cache_key in ENTITY_CACHE:
                LOGGER.info("Cache hit for %s", cache_key)
                article_info["disease_valid"] = ENTITY_CACHE[cache_key]
                article_info["decode_error"] = False
                completed_relationids.add(article_info["relationid"])
            else:
                prompt = prompt_template.format(DISEASE=mention, TITLE=article_info["title"], ABSTRACT=article_info["abstract"])
                LOGGER.info("Querying LLM for article_info[%d/%d]: %s", log_counter, log_total_expected, article_info["relationid"])
                result: LLMResult = get_llm_response(llm, user_prompt=prompt, logger=LOGGER)
                response = clean_json_response(result.content)
                try:
                    response_dict = json.loads(response)
                except json.JSONDecodeError:
                    response_dict = {}
                if response_dict:
                    article_info.update(response_dict)
                    article_info["decode_error"] = False
                    ENTITY_CACHE[cache_key] = article_info["disease_valid"]
                    completed_relationids.add(article_info["relationid"])
                    new_processed_counter += 1
                else:
                    article_info["disease_valid"] = False
                    article_info["decode_error"] = True
                    article_info["llm_raw_response"] = response
            batch_buffer.append(article_info)
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
        try:
            exisitng_output: list[dict] = load_jsonl(output_path)
            LOGGER.info("Loaded %d items from %s", len(exisitng_output), output_path.name)
            all_items: dict[str, dict] = {}
            for item in exisitng_output:
                relationid = item.get("relationid")
                if relationid not in valid_relationids:
                    LOGGER.warning("Skipping invalid relationid: %s", relationid)
                    continue
                prev = all_items.get(relationid)
                if prev is None:
                    all_items[relationid] = item
                    continue
                if prev.get("decode_error") is False:
                    prev.pop("llm_raw_response", None)
                    continue
                all_items[relationid] = item
            save_jsonl(all_items.values(), output_path)
            LOGGER.info("Deduplicated output written back to %s", output_path.name)
            LOGGER.info("Total items: %d", len(all_items))
        except Exception as e:
            LOGGER.error("Failed to deduplicate output: %s", e)

if __name__ == "__main__":
    main()
