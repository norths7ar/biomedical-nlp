"""
Apply disease deduplication results to relation-level records.

This step consumes:
- llm5_duplicate_disease.jsonl  (which contains replacement_map)

It outputs:
- stage_duplicate_disease_removed.jsonl

Core logic:
- Build mapping (pmid, old_id) -> new_id
- Apply mapping to relation-level records
- Keep provenance via _was_mapped
- Deduplicate on (pmid, disease_id, chemical_id) preferring originals
"""

from myutils import (
    init_step_logger,
    parse_args,
    load_jsonl,
    save_jsonl,
)
from biomedical_nlp.global_config import DATASET_NAME, get_paths
from biomedical_nlp.drug_disease.config import DATA_DIR

LOGGER = init_step_logger()

INPUT_FILE_NAME = "llm5_duplicate_disease.jsonl"
RAW_RELATION_FILE = "llm4_validate_chemical.jsonl"
OUTPUT_FILE_NAME = "stage_duplicate_disease_removed.jsonl"


def build_dedup_map(duplicate_results: list[dict]) -> dict[tuple[str, str], str]:
    """
    Build mapping (pmid, old_id) -> new_id from duplicate disease step.
    Assume disease ids are always numeric → no need to skip.
    """
    mapping: dict[tuple[str, str], str] = {}

    for record in duplicate_results:
        if not record.get("has_duplicate_diseases", False):
            continue

        pmid = record["pmid"]
        rep_map = record.get("replacement_map") or {}

        for old_id, new_id in rep_map.items():
            key = (pmid, str(old_id))
            mapping[key] = str(new_id)

    LOGGER.info("Built dedup map with %d entries.", len(mapping))
    return mapping


def apply_mapping_to_relations(
    relations: list[dict],
    mapping: dict[tuple[str, str], str],
) -> list[dict]:
    """Apply replacement_map to relation-level disease_biokdeid."""
    out = []
    mapped_count = 0

    for row in relations:
        r = dict(row)
        pmid = r["pmid"]
        disease_orig: str = r["disease_biokdeid"]

        new_id = mapping.get((pmid, disease_orig))

        if new_id is not None:
            r["_was_mapped"] = True
            r["disease_original_biokdeid"] = disease_orig
            r["disease_biokdeid"] = new_id
            mapped_count += 1
        else:
            r["_was_mapped"] = False

        out.append(r)

    LOGGER.info("Applied mapping to %d relations.", mapped_count)
    return out


def dedupe_relations(relations: list[dict]) -> list[dict]:
    """
    Deduplicate relation-level rows using key (pmid, disease_id, chemical_id),
    preferring originals (i.e., _was_mapped=False).
    """
    best: dict[tuple[str, str, str], dict] = {}
    dropped = 0

    for r in relations:
        key = (
            r["pmid"],
            r["disease_biokdeid"],
            r["chemical_biokdeid"],
        )

        if key not in best:
            best[key] = r
            continue

        existing = best[key]

        # prefer original over mapped
        if existing["_was_mapped"] and not r["_was_mapped"]:
            best[key] = r
            dropped += 1
        else:
            # drop this row, since existing wins
            if r["_was_mapped"] and not existing["_was_mapped"]:
                dropped += 1

    LOGGER.info("Deduplicated by preferring original rows. Dropped %d mapped rows.", dropped)

    # clean helper fields
    cleaned = []
    for r in best.values():
        r.pop("_was_mapped", None)
        r.pop("disease_original_biokdeid", None)
        cleaned.append(r)

    return cleaned


def main():
    args = parse_args()
    dataset = args.dataset or DATASET_NAME

    # paths
    duplicate_result_path, output_path = get_paths(DATA_DIR, dataset, INPUT_FILE_NAME, OUTPUT_FILE_NAME)
    _, relation_path = get_paths(DATA_DIR, dataset, RAW_RELATION_FILE, RAW_RELATION_FILE)

    LOGGER.info("Duplicate check input: %s", duplicate_result_path)
    LOGGER.info("Raw relations input: %s", relation_path)
    LOGGER.info("Output path: %s", output_path)

    # load data
    duplicate_results = load_jsonl(duplicate_result_path)
    raw_relations = load_jsonl(relation_path)

    # build dedupe map
    dedup_map = build_dedup_map(duplicate_results)

    # apply to relation-level data
    mapped_relations = apply_mapping_to_relations(raw_relations, dedup_map)

    # dedupe final relations
    final_relations = dedupe_relations(mapped_relations)

    # save
    save_jsonl(final_relations, output_path)
    LOGGER.info("Saved %d relations to %s", len(final_relations), output_path)

    LOGGER.info("Unique pmids: %d", len({r['pmid'] for r in final_relations}))
    LOGGER.info("Unique diseases: %d", len({r['disease_biokdeid'] for r in final_relations}))
    LOGGER.info("Unique chemicals: %d", len({r['chemical_biokdeid'] for r in final_relations}))


if __name__ == "__main__":
    main()
