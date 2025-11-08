# Testing Guide

This guide explains how to run and write unit tests for the Budget Planner backend.

## Setup

Tests use `pytest` with the following dependencies:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `httpx` - HTTP client for testing FastAPI endpoints

These are installed as dev dependencies with Poetry:

```bash
cd backend
poetry install --with dev
```

## Running Tests

### Run all tests

```bash
cd backend
poetry run pytest
```

### Run with verbose output

```bash
poetry run pytest -v
```

### Run specific test file

```bash
poetry run pytest tests/test_main.py
```

### Run specific test function

```bash
poetry run pytest tests/test_main.py::test_read_root
```

### Run with coverage

```bash
poetry run pytest --cov=app --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

## Test Structure

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures and configuration
│   ├── test_main.py         # Tests for API endpoints
│   └── test_utils.py         # Tests for utility functions
```

## Writing Tests

### Test Fixtures

The `conftest.py` file provides several useful fixtures:

- `client` - FastAPI TestClient instance
- `temp_progress_dir` - Temporary directory for progress files (isolates tests)
- `sample_csv_content` - Sample CSV content string
- `sample_csv_file` - Temporary CSV file for testing

### Example Test

```python
def test_get_categories(client):
    """Test getting the list of budget categories."""
    response = client.get("/categories")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert "Groceries" in data["categories"]
```

### Testing File Uploads

```python
def test_upload_csv(client, sample_csv_file):
    """Test uploading a CSV file."""
    with open(sample_csv_file, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("test.csv", f, "text/csv")}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 3
```

### Testing JSON Endpoints

```python
def test_map_row(client, sample_csv_file, temp_progress_dir):
    """Test mapping a row to a category."""
    # Upload a file first
    with open(sample_csv_file, "rb") as f:
        client.post("/upload", files={"file": ("test.csv", f, "text/csv")})
    
    # Map a row
    response = client.post(
        "/map",
        json={"row_index": 0, "category": "Groceries"}
    )
    
    assert response.status_code == 200
    assert response.json()["row"]["category"] == "Groceries"
```

## Test Isolation

Each test uses a temporary directory for progress files (via the `temp_progress_dir` fixture), ensuring tests don't interfere with each other or with your actual progress data.

## Best Practices

1. **Use descriptive test names**: Test function names should clearly describe what they're testing
2. **One assertion per concept**: Group related assertions, but test one concept per test
3. **Use fixtures**: Leverage pytest fixtures for setup/teardown
4. **Test edge cases**: Include tests for error conditions and boundary cases
5. **Keep tests fast**: Tests should run quickly to encourage frequent execution

## Continuous Integration

To run tests in CI/CD pipelines:

```bash
cd backend
poetry install --with dev
poetry run pytest
```

