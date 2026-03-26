from pathlib import Path

from biomedical_nlp.global_config import DATASET_NAME, DEEPSEEK_API_KEY, NOVELTY_THRESHOLD

PIPELINE_DIR = Path(__file__).resolve().parent
DATA_DIR = PIPELINE_DIR / "data"
PROMPT_DIR = PIPELINE_DIR / "prompt"
