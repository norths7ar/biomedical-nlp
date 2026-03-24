from pathlib import Path
from biomedical_nlp.global_config import *
from biomedical_nlp.global_config import __all__ as _parent_all

PIPELINE_DIR = Path(__file__).resolve().parent
DATA_DIR = PIPELINE_DIR / "data"
PROMPT_DIR = PIPELINE_DIR / "prompt"

__all__ = list(_parent_all)
__all__.extend([
    "PIPELINE_DIR",
    "DATA_DIR",
    "PROMPT_DIR",
])
