from pathlib import Path


# ============================================================
# BUSINESS AI GOD — CORE SETTINGS
# ============================================================

BAIG_NAME = "BUSINESS AI GOD"
BAIG_SHORT_NAME = "BAIG"
BAIG_VERSION = "0.1.0"

# Current development environment.
ENVIRONMENT = "development"

# Project root directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Main data directories.
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
KNOWLEDGE_DATA_DIR = DATA_DIR / "knowledge"
TEST_DATA_DIR = DATA_DIR / "tests"
