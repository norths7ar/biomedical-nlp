"""
Combine LLM combination detection results with base relations.

Input:
  1. stage_duplicate_disease_removed.jsonl (from step06b)
  2. llm8_combination_therapy.jsonl (from step07a)

Output:
  stage_combination_therapy_applied.jsonl
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

BASE_RELATION_FILE = "stage_duplicate_disease_removed.jsonl"
LLM_COMBINATION_FILE = "llm8_combination_therapy.jsonl"
OUTPUT_FILE_NAME = "stage_combination_therapy_applied.jsonl"


def normalize_name(name: str) -> str:
    """Normalize chemical/disease names for matching."""
    return name.strip().lower()


def reformat_base_relations(base_rels: list[dict]) -> dict[tuple[str, str], dict[str, dict]]:
    """
    Build a mapping: (pmid, disease_name) -> {chemical_name: relation_dict}
    """
    rel_map: dict[tuple[str, str], dict[str, dict]] = {}
    for r in base_rels:
        pmid = r["pmid"]
        disease = r["disease_name"].lower()
        chemical = r["chemical_name"].lower()
        key = (pmid, disease)
        if key not in rel_map:
            rel_map[key] = {}
        rel_map[key][chemical] = r
    return rel_map


def build_combination_map(llm_results: list[dict]) -> dict[tuple[str, str], dict]:
    """
    Build a mapping: (pmid, disease_name) -> valid combinations and single drugs
    """
    combo_map = {}
    for r in llm_results:
        pmid = r.get("pmid")
        disease = r.get("disease_name", "").lower()
        if not pmid or not disease:
            continue

        if r.get("has_combination", False) is False:
            continue  # skip no-combo entries

        valid_chems = {
            "combination_tuples": [],
            "single_drug_names": []
        }

        for g in r.get("combination_groups", []):
            drugs = [normalize_name(d) for d in g.get("drugs", [])]
            valid_chems["combination_tuples"].append(tuple(drugs))

        for s in r.get("single_drug_relations", []):
            valid_chems["single_drug_names"].append(normalize_name(s["drug"]))

        combo_map[(pmid, disease)] = valid_chems

    return combo_map


def main():
    args = parse_args()
    LOGGER.info("Args: %s", vars(args))
    dataset = args.dataset or DATASET_NAME

    # Get paths
    _, base_relation_path = get_paths(DATA_DIR, dataset, BASE_RELATION_FILE, BASE_RELATION_FILE)
    _, llm_combination_path = get_paths(DATA_DIR, dataset, LLM_COMBINATION_FILE, LLM_COMBINATION_FILE)
    _, output_path = get_paths(DATA_DIR, dataset, OUTPUT_FILE_NAME, OUTPUT_FILE_NAME)

    LOGGER.info("Base relations input: %s", base_relation_path)
    LOGGER.info("LLM combination input: %s", llm_combination_path)
    LOGGER.info("Output path: %s", output_path)

    base_relations = reformat_base_relations(load_jsonl(base_relation_path))
    combo_map = build_combination_map(load_jsonl(llm_combination_path))

    output = []

    # Iterate through all base relations and apply combination info
    for key, base_rel in base_relations.items():
        pmid, disease = key
        if (pmid, disease) not in combo_map:
            # No combinations detected, keep all original relations
            output.extend(base_rel.values())
            continue

        valid_chems = combo_map[(pmid, disease)]

        # Handle combinations
        for i, combo in enumerate(valid_chems["combination_tuples"], start=1):
            combo_name = " + ".join(sorted(combo)) + " (combination)"

            # Create a new combination relation
            for drug in combo:
                if drug in base_rel:
                    new_rel = base_rel[drug].copy()
                    new_rel["chemical_name"] = combo_name
                    old_chemical_id = new_rel["chemical_biokdeid"]
                    new_rel["chemical_biokdeid"] = ""  # Empty out the ID for combinations
                    # Modify relationid to remove the old drug's ID
                    relation_nodes: list[str] = new_rel["relationid"].split(".")
                    if old_chemical_id in relation_nodes:
                        relation_nodes.remove(old_chemical_id)
                    relation_nodes.append(f"COMBO{i}")
                    new_rel["relationid"] = ".".join(relation_nodes)

                    output.append(new_rel)

        # Handle single drugs
        for drug in valid_chems["single_drug_names"]:
            if drug in base_rel:
                rel = base_rel[drug].copy()
                output.append(rel)

    save_jsonl(output, output_path)
    LOGGER.info("Saved %d updated relations to %s", len(output), output_path.name)

    # Deduplicate output_path by relationid
    try:
        existing_output: list[dict] = load_jsonl(output_path)
        LOGGER.info("Loaded %d items from %s", len(existing_output), output_path.name)
        all_items: dict[str, dict] = {}
        for item in existing_output:
            # If the relationid is new, add it to the output
            if item["relationid"] not in all_items:
                all_items[item["relationid"]] = item

        save_jsonl(all_items.values(), output_path)

        LOGGER.info("Deduplicated output written back to %s", output_path.name)
        LOGGER.info("Total items: %d", len(all_items))
    except Exception as e:
        LOGGER.error("Failed to deduplicate output: %s", e)


if __name__ == "__main__":
    main()
