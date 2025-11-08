"""Pytest configuration and fixtures for testing the Budget Planner API."""
import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def temp_progress_dir():
    """Create a temporary directory for progress files during testing."""
    temp_dir = tempfile.mkdtemp()
    temp_progress_file = Path(temp_dir) / "mapping_progress.json"
    Path(temp_dir).mkdir(exist_ok=True)
    
    # Patch the PROGRESS_DIR and PROGRESS_FILE in the main module
    import app.main as main_module
    original_dir = main_module.PROGRESS_DIR
    original_file = main_module.PROGRESS_FILE
    
    main_module.PROGRESS_DIR = Path(temp_dir)
    main_module.PROGRESS_FILE = temp_progress_file
    
    yield temp_dir
    
    # Cleanup: restore original paths and remove temp directory
    main_module.PROGRESS_DIR = original_dir
    main_module.PROGRESS_FILE = original_file
    shutil.rmtree(temp_dir)


@pytest.fixture
def client(temp_progress_dir):
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing."""
    return """Date,Description,Amount
2024-01-01,Grocery Store,50.00
2024-01-02,Gas Station,30.00
2024-01-03,Restaurant,25.00"""


@pytest.fixture
def sample_csv_file(sample_csv_content, tmp_path):
    """Create a temporary CSV file for testing."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(sample_csv_content)
    return csv_file


