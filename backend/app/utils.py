# Utility functions for the budget planner application
import json
from pathlib import Path
from typing import Dict, List

# Progress file paths
PROGRESS_DIR = Path(__file__).parent.parent.parent / "progress"
PROGRESS_DIR.mkdir(exist_ok=True)
PROGRESS_FILE = PROGRESS_DIR / "mapping_progress.json"

# Mappings file paths
MAPPINGS_DIR = Path(__file__).parent.parent.parent / "mappings"
MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
MAPPINGS_FILE = MAPPINGS_DIR / "mappings.json"

# Categories file path
CATEGORIES_FILE = Path(__file__).parent.parent / "categories.json"

# Extracted text cache directory
EXTRACTED_TEXT_DIR = Path(__file__).parent.parent.parent / "extracted_text"
EXTRACTED_TEXT_DIR.mkdir(parents=True, exist_ok=True)


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
    PROGRESS_DIR.mkdir(exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(rows, f, indent=2)


def load_categories() -> List[str]:
    """Load categories from file"""
    if CATEGORIES_FILE.exists():
        try:
            with open(CATEGORIES_FILE, "r") as f:
                categories = json.load(f)
                if isinstance(categories, list) and len(categories) > 0:
                    return categories
        except (json.JSONDecodeError, IOError) as e:
            # Log error but continue to defaults
            print(f"Error loading categories from {CATEGORIES_FILE}: {e}")

    # Return default categories if file doesn't exist or is invalid
    default_categories = [
        "Food & Dining",
        "Groceries",
        "Transportation",
        "Shopping",
        "Clothing",
        "Bills & Utilities",
        "Entertainment",
        "Travel",
        "Healthcare",
        "Education",
        "Personal Care",
        "Gifts & Donations",
        "Business",
        "Income",
        "Other",
    ]
    # Only save default categories if file doesn't exist
    if not CATEGORIES_FILE.exists():
        save_categories(default_categories)
    return default_categories


def save_categories(categories: List[str]):
    """Save categories to file"""
    # Ensure parent directory exists
    CATEGORIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CATEGORIES_FILE, "w") as f:
        json.dump(categories, f, indent=2)
    # Verify file was written
    if not CATEGORIES_FILE.exists():
        raise Exception(f"Failed to save categories to {CATEGORIES_FILE}")


def load_mappings_for_file(filename: str) -> List[Dict]:
    """Load mappings for a specific file"""
    if not MAPPINGS_FILE.exists():
        return []

    try:
        with open(MAPPINGS_FILE, "r") as f:
            all_mappings = json.load(f)
            if isinstance(all_mappings, dict):
                return all_mappings.get(filename, [])
    except (json.JSONDecodeError, IOError):
        return []
    return []


def save_mappings_for_file(filename: str, rows: List[Dict]):
    """Save mappings for a specific file (replaces all mappings for that file)"""
    # Load all existing mappings
    all_mappings = {}
    if MAPPINGS_FILE.exists():
        try:
            with open(MAPPINGS_FILE, "r") as f:
                all_mappings = json.load(f)
                if not isinstance(all_mappings, dict):
                    all_mappings = {}
        except (json.JSONDecodeError, IOError):
            all_mappings = {}

    # Update mappings for this file
    all_mappings[filename] = rows

    # Save all mappings
    MAPPINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MAPPINGS_FILE, "w") as f:
        json.dump(all_mappings, f, indent=2)


def load_all_mappings() -> List[Dict]:
    """Load all mappings from all files"""
    if not MAPPINGS_FILE.exists():
        return []

    try:
        with open(MAPPINGS_FILE, "r") as f:
            all_mappings = json.load(f)
            if not isinstance(all_mappings, dict):
                return []

            # Flatten all mappings into a single list
            all_rows = []
            for filename, rows in all_mappings.items():
                if isinstance(rows, list):
                    all_rows.extend(rows)
            return all_rows
    except (json.JSONDecodeError, IOError):
        return []
    return []


def extract_text_from_file(file_path: Path, encoding: str = "utf-8") -> str | None:
    """
    Extract text from a file, using cached extracted text if available.
    Only extracts if the cached extracted text file doesn't exist or is empty.

    Args:
        file_path: Path to the source file
        encoding: File encoding (default: utf-8)

    Returns:
        Extracted text content, or None if extraction fails
    """
    if not file_path.exists():
        return None

    # Create cache file path based on source file
    cache_file = EXTRACTED_TEXT_DIR / f"{file_path.stem}_extracted.txt"

    # Check if cached extracted text exists and has content
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding=encoding) as f:
                cached_text = f.read().strip()
                if cached_text:  # Only return if cache has content
                    return cached_text
        except (IOError, UnicodeDecodeError) as e:
            print(f"Warning: Failed to read cached text from {cache_file}: {e}")
            # Continue to extract if cache read fails

    # Extract text from source file
    try:
        with open(file_path, "r", encoding=encoding) as f:
            extracted_text = f.read()

        # Save extracted text to cache
        try:
            with open(cache_file, "w", encoding=encoding) as f:
                f.write(extracted_text)
        except (IOError, UnicodeEncodeError) as e:
            print(f"Warning: Failed to save extracted text to cache {cache_file}: {e}")

        return extracted_text
    except (IOError, UnicodeDecodeError) as e:
        print(f"Error extracting text from {file_path}: {e}")
        return None

