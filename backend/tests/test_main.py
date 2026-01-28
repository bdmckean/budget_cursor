"""Unit tests for the Budget Planner API endpoints."""
import json
from fastapi.testclient import TestClient


def test_read_root(client: TestClient):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Budget Planner API"}


def test_get_categories(client: TestClient):
    """Test getting the list of categories."""
    response = client.get("/categories")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert isinstance(data["categories"], list)
    assert "Groceries" in data["categories"]
    assert "Clothing" in data["categories"]
    assert "Business" in data["categories"]


def test_get_progress_empty(client: TestClient):
    """Test getting progress when no file has been uploaded."""
    response = client.get("/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["rows"] == []
    assert data["total_rows"] == 0
    assert data["mapped_count"] == 0


def test_upload_csv(client: TestClient, sample_csv_file):
    """Test uploading a CSV file."""
    with open(sample_csv_file, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("test.csv", f, "text/csv")}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "File uploaded successfully"
    assert data["total_rows"] == 3
    assert len(data["rows"]) == min(10, data["total_rows"])
    assert data["rows"][0]["row_index"] == 0
    assert "Date" in data["rows"][0]["original_data"]
    assert data["rows"][0]["mapped"] is False


def test_upload_non_csv_file(client: TestClient, tmp_path):
    """Test uploading a non-CSV file should fail."""
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("This is not a CSV file")
    
    with open(txt_file, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("test.txt", f, "text/plain")}
        )
    
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_map_row(client: TestClient, sample_csv_file):
    """Test mapping a row to a category."""
    # First upload a CSV
    with open(sample_csv_file, "rb") as f:
        client.post("/upload", files={"file": ("test.csv", f, "text/csv")})
    
    # Map the first row
    response = client.post(
        "/map",
        json={"row_index": 0, "category": "Groceries"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Row mapped successfully"
    assert data["row"]["category"] == "Groceries"
    assert data["row"]["mapped"] is True
    assert data["row"]["row_index"] == 0


def test_map_row_invalid_index(client: TestClient, sample_csv_file):
    """Test mapping a row with an invalid index."""
    # First upload a CSV
    with open(sample_csv_file, "rb") as f:
        client.post("/upload", files={"file": ("test.csv", f, "text/csv")})
    
    # Try to map a non-existent row
    response = client.post(
        "/map",
        json={"row_index": 999, "category": "Groceries"}
    )
    
    assert response.status_code == 400
    assert "Invalid row index" in response.json()["detail"]


def test_map_row_no_file_uploaded(client: TestClient):
    """Test mapping a row when no file has been uploaded."""
    response = client.post(
        "/map",
        json={"row_index": 0, "category": "Groceries"}
    )
    
    assert response.status_code == 404
    assert "No file uploaded" in response.json()["detail"]


def test_get_progress_after_upload(client: TestClient, sample_csv_file):
    """Test getting progress after uploading a file."""
    # Upload CSV
    with open(sample_csv_file, "rb") as f:
        client.post("/upload", files={"file": ("test.csv", f, "text/csv")})
    
    # Get progress
    response = client.get("/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 3
    assert data["mapped_count"] == 0
    assert len(data["rows"]) == 3


def test_get_progress_after_mapping(client: TestClient, sample_csv_file):
    """Test getting progress after mapping some rows."""
    # Upload CSV
    with open(sample_csv_file, "rb") as f:
        client.post("/upload", files={"file": ("test.csv", f, "text/csv")})
    
    # Map two rows
    client.post("/map", json={"row_index": 0, "category": "Groceries"})
    client.post("/map", json={"row_index": 1, "category": "Transportation"})
    
    # Get progress
    response = client.get("/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 3
    assert data["mapped_count"] == 2
    assert data["rows"][0]["mapped"] is True
    assert data["rows"][0]["category"] == "Groceries"
    assert data["rows"][1]["mapped"] is True
    assert data["rows"][1]["category"] == "Transportation"
    assert data["rows"][2]["mapped"] is False


def test_progress_persistence(client: TestClient, sample_csv_file, temp_progress_dir):
    """Test that progress is saved and can be retrieved."""
    import app.utils as utils_module
    
    # Upload CSV
    with open(sample_csv_file, "rb") as f:
        client.post("/upload", files={"file": ("test.csv", f, "text/csv")})
    
    # Map a row
    client.post("/map", json={"row_index": 0, "category": "Groceries"})
    
    # Verify progress file exists and has correct content
    assert utils_module.PROGRESS_FILE.exists()
    with open(utils_module.PROGRESS_FILE, "r") as f:
        progress_data = json.load(f)
    
    assert len(progress_data) == 3
    assert progress_data[0]["mapped"] is True
    assert progress_data[0]["category"] == "Groceries"
