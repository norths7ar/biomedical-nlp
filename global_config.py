# -*- coding: utf-8 -*-
# @Time    : 2025-11-21 19:07
# @Author  : Jianan Wang (jianan@insilicom.com)
# @File    : global_config.py

"""
This is the global config across all pipelines.
"""

from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT_DIR = Path(__file__).resolve().parent
DATA_SOURCE_DIR = PROJECT_ROOT_DIR.parent / "data_source"

NOVELTY_THRESHOLD = 0.9

env_path = PROJECT_ROOT_DIR / ".env"
load_dotenv(dotenv_path=env_path)

def get_paths(
    data_dir: Path,
    dataset: str,
    input_file: str,
    output_file: str,
) -> tuple[Path, Path]:
    """Return input_path and output_path for this pipeline dataset."""
    base = data_dir / dataset
    return base / input_file, base / output_file


__all__ = [
    "PROJECT_ROOT_DIR",
    "DATA_SOURCE_DIR",
    "NOVELTY_THRESHOLD",
    "get_paths",
]