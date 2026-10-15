import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: parses a full multi-movement raw score (~1 min)")
