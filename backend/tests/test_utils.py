"""Tests for utility functions."""
import json
import pytest
import shutil
from pathlib import Path
import app.utils as utils_module
from app.utils import load_progress, save_progress


def test_load_progress_nonexistent_file(temp_progress_dir):
    """Test loading progress when file doesn't exist."""
    # Ensure file doesn't exist
    if utils_module.PROGRESS_FILE.exists():
        utils_module.PROGRESS_FILE.unlink()
    
    result = load_progress()
    assert result == []


def test_save_and_load_progress(temp_progress_dir):
    """Test saving and loading progress."""
    test_data = [
        {"row_index": 0, "original_data": {"col1": "val1"}, "category": "Groceries", "mapped": True},
        {"row_index": 1, "original_data": {"col1": "val2"}, "category": None, "mapped": False},
    ]
    
    save_progress(test_data)
    assert utils_module.PROGRESS_FILE.exists()
    
    loaded_data = load_progress()
    assert loaded_data == test_data


def test_load_progress_invalid_json(temp_progress_dir):
    """Test loading progress when file contains invalid JSON."""
    # Write invalid JSON to file
    utils_module.PROGRESS_FILE.write_text("invalid json content")
    
    result = load_progress()
    assert result == []


def test_save_progress_creates_directory(temp_progress_dir):
    """Test that save_progress creates the directory if it doesn't exist."""
    
    # Remove the directory
    if utils_module.PROGRESS_DIR.exists():
        shutil.rmtree(utils_module.PROGRESS_DIR)
    
    test_data = [{"row_index": 0, "original_data": {}, "category": None, "mapped": False}]
    save_progress(test_data)
    
    assert utils_module.PROGRESS_DIR.exists()
    assert utils_module.PROGRESS_FILE.exists()

