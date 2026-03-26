import json
import sys
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
BATCH_SIZE = 100

PROMPT_FILE_NAME = "relation_types.md"
INPUT_FILE_NAME = "llm6_novelty.jsonl"
OUTPUT_FILE_NAME = "llm7_relation_types.jsonl"

llm = ChatOpenAI(model=MODEL, api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", max_tokens=MAX_TOKENS)


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
        completed_relationids = {e["relationid"] for e in iter_jsonl(output_path)}
        LOGGER.info("Loaded %d records from %s", len(completed_relationids), output_path.name)
    else:
        completed_relationids = set()

    prompt_template: str = load_text(PROMPT_DIR / PROMPT_FILE_NAME)
    batch_buffer: list[dict] = []
    log_total_expected = len(article_data)
    log_counter = len(completed_relationids) + 1
    new_processed_counter = 0

    try:
        for article_info in article_data:
            if article_info["relationid"] in completed_relationids:
                LOGGER.debug(
                    "Skipping article_info: %s because it has already been processed",
                    article_info["relationid"],
                )
                continue

            if article_info.get("novelty", False) is False:
                LOGGER.debug(
                    "Skipping %s because it's not novel",
                    article_info["relationid"],
                )
                log_counter += 1
                continue

            article_info["llm_step"] = "relation_types"

            response = None
            response_dict = None

            title = article_info.get("title") or article_info.get("articleTitle", "")
            abstract = article_info.get("abstract", "")
            disease = article_info.get("disease_name", "")
            chemical = article_info.get("chemical_name", "")
            user_prompt = f"Title: {title}\n\nAbstract: {abstract}\n\nChemical: {chemical}\n\nDisease: {disease}"

            LOGGER.info(
                "Querying LLM for article_info[%d/%d]: %s",
                log_counter,
                log_total_expected,
                article_info["relationid"],
            )

            result: LLMResult = get_llm_response(
                llm,
                user_prompt=user_prompt,
                system_prompt=prompt_template,
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
                completed_relationids.add(article_info["relationid"])
                new_processed_counter += 1
            else:
                article_info["relation_type"] = "unknown"
                article_info["decode_error"] = True
                LOGGER.error(
                    "LLM response JSON decode error for %s",
                    article_info["relationid"],
                )
                LOGGER.error(
                    "Raw response: %s",
                    result.raw,
                )

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

        # Deduplicate output_path by relationid
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

                # No previous record: add new
                if prev is None:
                    all_items[relationid] = item
                    continue

                # Previous record is valid: skip
                if prev.get("decode_error") is False:
                    prev.pop("llm_raw_response", None)
                    continue

                # Previous record is invalid: replace with current
                all_items[relationid] = item

            save_jsonl(all_items.values(), output_path)

            LOGGER.info("Deduplicated output written back to %s", output_path.name)
            LOGGER.info("Total items: %d", len(all_items))
        except Exception as e:
            LOGGER.error("Failed to deduplicate output: %s", e)


if __name__ == "__main__":
    main()
