"""Tests for utility functions."""
import json
import pytest
import shutil
from pathlib import Path
from app.main import load_progress, save_progress, PROGRESS_FILE


def test_load_progress_nonexistent_file(temp_progress_dir):
    """Test loading progress when file doesn't exist."""
    # Ensure file doesn't exist
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
    
    result = load_progress()
    assert result == []


def test_save_and_load_progress(temp_progress_dir):
    """Test saving and loading progress."""
    test_data = [
        {"row_index": 0, "original_data": {"col1": "val1"}, "category": "Groceries", "mapped": True},
        {"row_index": 1, "original_data": {"col1": "val2"}, "category": None, "mapped": False},
    ]
    
    save_progress(test_data)
    assert PROGRESS_FILE.exists()
    
    loaded_data = load_progress()
    assert loaded_data == test_data


def test_load_progress_invalid_json(temp_progress_dir):
    """Test loading progress when file contains invalid JSON."""
    # Write invalid JSON to file
    PROGRESS_FILE.write_text("invalid json content")
    
    result = load_progress()
    assert result == []


def test_save_progress_creates_directory(temp_progress_dir):
    """Test that save_progress creates the directory if it doesn't exist."""
    import app.main as main_module
    
    # Remove the directory
    if main_module.PROGRESS_DIR.exists():
        shutil.rmtree(main_module.PROGRESS_DIR)
    
    test_data = [{"row_index": 0, "original_data": {}, "category": None, "mapped": False}]
    save_progress(test_data)
    
    assert main_module.PROGRESS_DIR.exists()
    assert PROGRESS_FILE.exists()

