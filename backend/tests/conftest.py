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
    
    # Patch the progress and mapping paths in the utils module
    import app.utils as utils_module
    original_progress_dir = utils_module.PROGRESS_DIR
    original_progress_file = utils_module.PROGRESS_FILE
    original_mappings_dir = utils_module.MAPPINGS_DIR
    original_mappings_file = utils_module.MAPPINGS_FILE
    
    utils_module.PROGRESS_DIR = Path(temp_dir) / "progress"
    utils_module.PROGRESS_DIR.mkdir(exist_ok=True)
    utils_module.PROGRESS_FILE = utils_module.PROGRESS_DIR / "mapping_progress.json"
    
    utils_module.MAPPINGS_DIR = Path(temp_dir) / "mappings"
    utils_module.MAPPINGS_DIR.mkdir(exist_ok=True)
    utils_module.MAPPINGS_FILE = utils_module.MAPPINGS_DIR / "mappings.json"
    
    yield temp_dir
    
    # Cleanup: restore original paths and remove temp directory
    utils_module.PROGRESS_DIR = original_progress_dir
    utils_module.PROGRESS_FILE = original_progress_file
    utils_module.MAPPINGS_DIR = original_mappings_dir
    utils_module.MAPPINGS_FILE = original_mappings_file
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


@pytest.fixture
def wise_csv_content():
    """Wise/TransferWise export format CSV for testing."""
    return '''ID,Status,Direction,"Created on","Finished on","Source fee amount","Source fee currency","Target fee amount","Target fee currency","Source name","Source amount (after fees)","Source currency","Target name","Target amount (after fees)","Target currency","Exchange rate",Reference,Batch,"Created by",Category,Note
TRANSFER-1,COMPLETED,OUT,"2025-12-15 15:05:00","2025-12-15 15:05:21",0.00,EUR,,,"Brian McKean",400.0,EUR,"Blanca Diago",400.0,EUR,1.0,Vet,,"Brian McKean",General,
TRANSFER-2,COMPLETED,IN,"2025-12-08 17:35:15","2025-12-08 17:35:22",0.00,USD,,,"USAA SAV-INTRNT",2000.00,USD,"Brian McKean",2000.0,USD,1.0,TRANSFER,,"Brian McKean","Money added",
'''


@pytest.fixture
def wise_csv_file(wise_csv_content, tmp_path):
    """Create a temporary Wise-format CSV file for testing."""
    csv_file = tmp_path / "wise_2025.csv"
    csv_file.write_text(wise_csv_content)
    return csv_file


