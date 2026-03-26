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
from biomedical_nlp.drug_disease.config import DATA_DIR, PIPELINE_DIR, PROMPT_DIR
from biomedical_nlp.llm_client import LLMResult, get_llm_response, clean_json_response


# ====== Step Config =======
LOGGER = init_step_logger()

MODEL = "deepseek-chat"
MAX_TOKENS = 8192
TEMPERATURE = 0.4
BATCH_SIZE = 100

PROMPT_FILE_NAME = "remove_duplicate_disease.md"
INPUT_FILE_NAME = "llm4_validate_chemical.jsonl"
OUTPUT_FILE_NAME = "llm5_duplicate_disease.jsonl"
REFERENCE_FILE_NAME = OUTPUT_FILE_NAME

llm = ChatOpenAI(model=MODEL, api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", max_tokens=MAX_TOKENS, temperature=TEMPERATURE)


def load_cache(archive_data: list[dict]) -> tuple[dict[str, dict], dict[str, set]]:
    """
    Build cache maps from an existing duplicate-disease output.

    archive_map: pmid -> full record
    idset_map:   pmid -> set of disease ids that were seen when the record was created
    """
    archive_map: dict[str, dict] = {}
    idset_map: dict[str, set] = {}

    for record in archive_data:
        pmid = record["pmid"]

        archive_map[pmid] = record

        kept = record.get("kept_entities", []) or []
        dropped = record.get("dropped_entities", []) or []
        if kept or dropped:
            try:
                idset_map[pmid] = {
                    ent["id"] for ent in (kept + dropped) if "id" in ent
                }
            except TypeError:
                # If the structure is unexpectedly wrong, skip this pmid from cache
                continue

    return archive_map, idset_map


def build_records(output_path: Path) -> set[str]:
    """Build set of completed PMIDs from existing output file."""
    records: set[str] = set()
    for item in iter_jsonl(output_path):
        if item.get("decode_error", False):
            continue
        records.add(item["pmid"])
    return records


def apply_cache_if_possible(
    pmid: str,
    diseases: list[dict],
    archive_map: dict[str, dict],
    idset_map: dict[str, set],
) -> dict | None:
    """
    Try to reuse cached duplicate-disease result for a given PMID.

    Logic mirrors v1:
    - If there is no cached record: return None.
    - If the new set of disease ids is exactly the same: reuse the whole record.
    - If the new set is a strict superset: require re-query (return None).
    - If the new set is a strict subset: reuse a filtered version of the cached record.
    """
    new_ids = {d["id"] for d in diseases if "id" in d}

    if pmid not in archive_map:
        return None  # no cache

    old_record = archive_map[pmid]
    old_ids = idset_map.get(pmid, set())

    if not old_ids:
        return None  # nothing reliable to reuse

    if new_ids == old_ids:
        LOGGER.info("PMID %s cache hit: exact match", pmid)
        return old_record

    if new_ids > old_ids:
        LOGGER.info("PMID %s new_ids larger, re-query LLM", pmid)
        return None  # force LLM

    if new_ids < old_ids:
        LOGGER.info("PMID %s new_ids smaller, reuse partial cache", pmid)
        new_record: dict = {
            k: v
            for k, v in old_record.items()
            if k
            not in (
                "has_duplicate_diseases",
                "kept_entities",
                "dropped_entities",
                "explanation",
                "replacement_map",
            )
        }

        kept = [
            e for e in old_record.get("kept_entities", []) if e.get("id") in new_ids
        ]
        dropped = [
            e for e in old_record.get("dropped_entities", []) if e.get("id") in new_ids
        ]

        # Filter replacement_map
        old_map = old_record.get("replacement_map", {}) or {}
        new_map = {
            old_id: new_id
            for old_id, new_id in old_map.items()
            if old_id in new_ids and new_id in new_ids
        }

        new_record.update(
            {
                "pmid": pmid,
                "has_duplicate_diseases": bool(dropped),
                "kept_entities": kept,
                "dropped_entities": dropped,
                "replacement_map": new_map,
                "explanation": (
                    f"Partial reuse from archive. Diseases reduced from {old_ids} "
                    f"to {new_ids}. Replacement_map and entities filtered to relevant entries."
                ),
                "decode_error": False,
            }
        )
        return new_record

    return None


def generate_input_data(articles: list[dict]) -> list[dict]:
    """
    Aggregate relation-level records into one record per PMID.

    The resulting structure is:
    {
        "pmid": str,
        "title": str,
        "abstract": str,
        "diseases": [
            {"name": disease_name, "id": disease_biokdeid}, ...
        ]
    }

    Each disease id will appear at most once per PMID.
    """
    pmid_to_articles: dict[str, dict] = {}
    seen: dict[str, set] = defaultdict(set)

    for article in articles:
        pmid = article["pmid"]

        if pmid not in pmid_to_articles:
            pmid_to_articles[pmid] = {
                "title": article.get("title") or article.get("articleTitle", ""),
                "abstract": article["abstract"],
                "diseases": [],
            }

        disease_id = article["disease_biokdeid"]
        if disease_id not in seen[pmid]:
            seen[pmid].add(disease_id)
            pmid_to_articles[pmid]["diseases"].append({
                "name": article["disease_name"],
                "id": disease_id
            })

    output: list[dict] = []
    for pmid, article_info in pmid_to_articles.items():
        output.append(
            {
                "pmid": pmid,
                "title": article_info["title"],
                "abstract": article_info["abstract"],
                "diseases": article_info["diseases"],
            }
        )

    return output


def main() -> None:
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

    article_data: list[dict] = load_jsonl(input_path)
    input_data: list[dict] = generate_input_data(article_data)
    LOGGER.info("Loaded %d articles after aggregation.", len(input_data))

    # Build cache from drug-target pipeline, if available
    reference_file = (
        PIPELINE_DIR.parent
        / "drug_target"
        / "data"
        / dataset
        / REFERENCE_FILE_NAME
    )
    if reference_file.exists():
        LOGGER.info("Building cache from drug-target pipeline: %s", reference_file)
        archive_data: list[dict] = load_jsonl(reference_file)
        archive_map, idset_map = load_cache(archive_data)
    else:
        archive_map, idset_map = {}, {}

    # Handle previous output
    if force_overwrite and output_path.exists():
        output_path.unlink()

    if output_path.exists():
        completed_pmids: set[str] = build_records(output_path)
        LOGGER.info(
            "Loaded %d completed PMIDs from %s", len(completed_pmids), output_path.name
        )
    else:
        completed_pmids = set()

    prompt_template: str = load_text(PROMPT_DIR / PROMPT_FILE_NAME)
    batch_buffer: list[dict] = []

    log_total_expected = len(input_data)
    log_counter = len(completed_pmids) + 1
    new_processed_counter = 0

    try:
        for article_info in input_data:
            pmid: str = article_info["pmid"]
            if pmid in completed_pmids:
                LOGGER.debug(
                    "Skipping article_info: %s because it has already been processed",
                    pmid,
                )
                continue

            diseases: list[dict] = article_info.get("diseases", [])
            if len(diseases) < 2:
                batch_buffer.append(
                    {
                        "pmid": pmid,
                        "has_duplicate_diseases": False,
                        "kept_entities": diseases,
                        "dropped_entities": [],
                        "replacement_map": {},
                        "explanation": "Less than 2 diseases.",
                        "decode_error": False,
                    }
                )
                LOGGER.debug(
                    "Skip %s because it has less than 2 diseases.", pmid
                )
                log_counter += 1
                continue

            # Try to use cache from drug-target pipeline
            cached = apply_cache_if_possible(pmid, diseases, archive_map, idset_map)
            if cached is not None:
                batch_buffer.append(cached)
                completed_pmids.add(pmid)
                log_counter += 1
                continue

            title: str = article_info["title"]
            abstract: str = article_info["abstract"]
            diseases_flatten: str = json.dumps(diseases, ensure_ascii=False)

            user_prompt = (
                f"Title: {title}\n\nAbstract: {abstract}\n\nDiseases: {diseases_flatten}"
            )

            LOGGER.info(
                "Querying LLM for article_info[%d/%d]: %s",
                log_counter,
                log_total_expected,
                pmid,
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
            except json.JSONDecodeError:
                response_dict = {}
                LOGGER.warning("Failed to decode JSON for PMID %s", pmid)

            if response_dict:
                response_dict["pmid"] = pmid
                response_dict.setdefault("decode_error", False)
                batch_buffer.append(response_dict)
                completed_pmids.add(pmid)
                new_processed_counter += 1
            else:
                LOGGER.error(
                    "LLM response JSON decode error for PMID %s", pmid
                )
                LOGGER.error("Raw response: %s", result.raw)

                batch_buffer.append(
                    {
                        "pmid": pmid,
                        "has_duplicate_diseases": False,
                        "kept_entities": diseases,
                        "dropped_entities": [],
                        "replacement_map": {},
                        "explanation": "LLM JSON decode error.",
                        "decode_error": True,
                    }
                )

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

        # Deduplicate output_path by pmid
        try:
            existing_output: list[dict] = load_jsonl(output_path)
            LOGGER.info(
                "Loaded %d items from %s", len(existing_output), output_path.name
            )
            input_pmids = {item["pmid"] for item in input_data}

            existing_output = [
                item for item in existing_output if item["pmid"] in input_pmids
            ]

            all_items: dict[str, dict] = {}
            for item in existing_output:
                pmid = item["pmid"]

                prev = all_items.get(pmid)

                # No previous record: add new
                if prev is None:
                    all_items[pmid] = item
                    continue

                # Previous record is valid: skip
                if prev.get("decode_error") is False:
                    prev.pop("llm_raw_response", None)
                    continue

                # Previous record is invalid: replace with current
                all_items[pmid] = item

            save_jsonl(all_items.values(), output_path)

            LOGGER.info(
                "Deduplicated output written back to %s", output_path.name
            )
            LOGGER.info("Total items: %d", len(all_items))
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error("Failed to deduplicate output: %s", exc)


if __name__ == "__main__":
    main()
