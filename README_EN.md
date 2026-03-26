# Biomedical NLP — Drug Relation Extraction Pipeline

A refactored version of a production pipeline, replacing an internal LLM framework with LangChain, for automatically extracting **drug–disease** relationships from biomedical literature.

> Currently migrated and runnable: `drug_disease`

---

## Tech Stack

| Category | Tool |
|---|---|
| Language | Python 3.11+ |
| LLM | LangChain + DeepSeek (OpenAI-compatible interface; any provider can be swapped in) |
| Data Format | JSON / JSONL (incremental writes) |
| Utilities | myutils (internal library: logging, I/O, argument parsing) |

---

## Pipeline Architecture

```
Raw literature data (PubMed)
        │
        ▼
step01  Load raw input
        │
        ▼
step02a [LLM] Detect disease name abbreviations and resolve to full names
step02b        Apply resolution results, update fields
        │
        ▼
step03a [LLM] Validate disease entities (confirm they are real diseases)
        │
        ▼
step04a [LLM] Detect chemical/drug name abbreviations and resolve to full names
step04b        Apply resolution results, update fields
        │
        ▼
step05a [LLM] Validate chemical/drug entities (confirm they are real drugs)
        │
        ▼
step06a [LLM] Detect duplicate disease entities within the same article
step06b        Apply deduplication mapping, merge duplicate entities
        │
        ▼
step07a [LLM] Detect combination therapy (multiple drugs targeting the same disease)
step07b        Apply combination therapy results, restructure relation records
        │
        ▼
step11  [LLM] Assess novelty of each drug–disease relation
        │
        ▼
step12  [LLM] Classify relation types (treatment / side effect / association / etc.)
        │
        ▼
Structured drug–disease relation data (JSONL)
```

**8 LLM calls** in total. Every step supports resume-from-checkpoint and output deduplication.

---

## Design Highlights

### 1. Unified LLM Client (`biomedical_nlp/llm_client.py`)
- Wraps LangChain `BaseChatModel` — decoupled from any specific provider
- Exponential backoff retry (up to 5 attempts: 5 → 10 → 20 → 40 → 80 s)
- Automatically extracts chain-of-thought reasoning content from reasoning models (DeepSeek-reasoner / OpenAI o-series)
- Unified cleanup of JSON markdown code fences in LLM responses

### 2. Incremental Processing + Resume from Checkpoint
- Each step writes output to JSONL in batches, preventing data loss on interruption
- On startup, rebuilds a completed-record set from any existing output file, skipping already-processed entries
- `KeyboardInterrupt` is caught gracefully, ensuring the final batch is flushed before exit

### 3. Cross-Pipeline Entity Cache Warm-Up
- Entity validation steps (step02a, step03a) pre-load cached results from the `drug_target` pipeline on startup
- LLM results for the same entity are reused across pipelines, significantly reducing redundant API calls
- Currently only `drug_disease` is available; the cross-pipeline cache takes effect when multiple pipelines are running

### 4. Runtime Dataset Switching
```bash
# Use the default dataset (configured in global_config.py)
python run_pipeline.py drug_disease

# Override dataset at runtime — no config file changes needed
python run_pipeline.py drug_disease --dataset prod

# Force re-run all steps
python run_pipeline.py drug_disease --dataset test --force_overwrite
```

---

## Project Structure

```
biomedical-nlp/
├── biomedical_nlp/
│   ├── global_config.py          # Global config: paths, API keys, dataset name
│   ├── llm_client.py             # Unified LLM call wrapper
│   └── drug_disease/
│       ├── config.py             # Pipeline-level path config
│       ├── prompt/               # LLM prompt templates (Markdown, one per step)
│       ├── step01_prepare_pipeline_input.py
│       ├── step02a_llm1_disease_abbr.py
│       ├── step02b_update_disease_name.py
│       ├── step03a_llm2_validate_disease.py
│       ├── step04a_llm3_chemical_abbr.py
│       ├── step04b_update_chemical_name.py
│       ├── step05a_llm4_validate_chemical.py
│       ├── step06a_llm5_duplicate_disease.py
│       ├── step06b_remove_duplicate_disease.py
│       ├── step07a_llm8_combination_therapy.py
│       ├── step07b_apply_combination_therapy.py
│       ├── step11_llm6_novelty.py
│       └── step12_llm7_relation_types.py
├── run_pipeline.py               # Unified pipeline entry point
└── .env                          # API keys (not committed to version control)
```

---

## Getting Started

**1. Install dependencies**
```bash
pip install langchain-openai langchain-core python-dotenv
pip install -e path/to/myutils
# myutils is the author's private utility library; contact the author to run locally,
# or refer to requirements.txt to replace with standard-library equivalents
```

**2. Configure API key**

Create `biomedical_nlp/.env`:
```
DEEPSEEK_API_KEY=your_api_key_here
```

**3. Run the pipeline**
```bash
python run_pipeline.py drug_disease
```

Debug a single step:
```bash
python biomedical_nlp/drug_disease/step02a_llm1_disease_abbr.py --dataset test --max_items 10
```

---

## Background

This project is a personal refactor of a production pipeline built at a previous employer:
- The original system relied on a proprietary internal LLM framework and private database, neither of which can be open-sourced
- This version replaces the LLM layer with LangChain + DeepSeek, and uses a sanitised public-dataset-compatible data structure
- Core business logic (entity validation, deduplication, relation classification) is consistent with the production version

*[中文版 →](README.md)*
