# Utility functions for the budget planner application
import json
from pathlib import Path
from typing import Dict, List

PROGRESS_DIR = Path(__file__).parent.parent.parent / "progress"
PROGRESS_DIR.mkdir(exist_ok=True)
PROGRESS_FILE = PROGRESS_DIR / "mapping_progress.json"

def load_progress() -> List[Dict]:
    """Load progress from file"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_progress(rows: List[Dict]):
    """Save progress to file"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(rows, f, indent=2)

