from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

app = FastAPI(title="Budget Planner API")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:13030"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to save progress
PROGRESS_DIR = Path(__file__).parent.parent.parent / "progress"
PROGRESS_DIR.mkdir(exist_ok=True)
PROGRESS_FILE = PROGRESS_DIR / "mapping_progress.json"


class RowMapping(BaseModel):
    row_index: int
    original_data: Dict[str, str]
    category: Optional[str] = None
    mapped: bool = False


class MappingRequest(BaseModel):
    row_index: int
    category: str


class ProgressResponse(BaseModel):
    rows: List[RowMapping]
    total_rows: int
    mapped_count: int


@app.get("/")
def read_root():
    return {"message": "Budget Planner API"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and parse CSV file"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Check for .csv extension (case-insensitive)
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"File must be a CSV file with .csv extension. Received: {file.filename}",
        )

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="File is empty")

        decoded = contents.decode("utf-8")
        csv_reader = csv.DictReader(decoded.splitlines())
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File encoding error. Please ensure the file is UTF-8 encoded",
        )

    rows = []
    for idx, row in enumerate(csv_reader):
        rows.append(
            {"row_index": idx, "original_data": row, "category": None, "mapped": False}
        )

    # Load existing progress if available
    progress_data = load_progress()
    if progress_data and len(progress_data) == len(rows):
        # Merge with existing progress
        for i, existing_row in enumerate(progress_data):
            if existing_row.get("mapped"):
                rows[i]["category"] = existing_row.get("category")
                rows[i]["mapped"] = True

    # Save initial state
    save_progress(rows)

    return {
        "message": "File uploaded successfully",
        "total_rows": len(rows),
        "rows": rows[:10],  # Return first 10 for preview
    }


@app.get("/progress")
def get_progress():
    """Get current mapping progress"""
    progress_data = load_progress()
    if not progress_data:
        return {"rows": [], "total_rows": 0, "mapped_count": 0}

    mapped_count = sum(1 for row in progress_data if row.get("mapped", False))
    return {
        "rows": progress_data,
        "total_rows": len(progress_data),
        "mapped_count": mapped_count,
    }


@app.post("/map")
def map_row(request: MappingRequest):
    """Map a row to a category"""
    progress_data = load_progress()
    if not progress_data:
        raise HTTPException(
            status_code=404, detail="No file uploaded. Please upload a CSV first."
        )

    if request.row_index >= len(progress_data):
        raise HTTPException(status_code=400, detail="Invalid row index")

    # Update the row
    progress_data[request.row_index]["category"] = request.category
    progress_data[request.row_index]["mapped"] = True

    # Save progress
    save_progress(progress_data)

    return {
        "message": "Row mapped successfully",
        "row": progress_data[request.row_index],
    }


@app.get("/categories")
def get_categories():
    """Get list of common budget categories"""
    return {
        "categories": [
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
    }


def load_progress() -> List[Dict]:
    """Load progress from file"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []


def save_progress(rows: List[Dict]):
    """Save progress to file"""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(rows, f, indent=2)
