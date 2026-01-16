from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import csv
import json
import os
import re
import requests
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel
from autocorrect import Speller
from dotenv import load_dotenv

from .langfuse_tracer import get_tracer, initialize_tracing
from .csv_validator import (
    CSVRowValidator,
    extract_transaction_date,
    extract_amount,
)

# Load environment variables
load_dotenv()

app = FastAPI(title="Budget Planner API")

# Initialize Langfuse tracing
initialize_tracing()
tracer = get_tracer()

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

# Path to save mappings by source file
MAPPINGS_DIR = Path(__file__).parent.parent.parent / "mappings"
MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
MAPPINGS_FILE = MAPPINGS_DIR / "mappings.json"

# Path to categories file
CATEGORIES_FILE = Path(__file__).parent.parent / "categories.json"

# Path to extracted text cache directory
EXTRACTED_TEXT_DIR = Path(__file__).parent.parent.parent / "extracted_text"
EXTRACTED_TEXT_DIR.mkdir(parents=True, exist_ok=True)

# Initialize spell checker
spell = Speller(lang="en")

# Ollama configuration
# Use host.docker.internal to access host machine from Docker container
# On Linux, you may need to use the host's IP address instead
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


class RowMapping(BaseModel):
    row_index: int
    original_data: Dict[str, str]
    category: Optional[str] = None
    mapped: bool = False
    source_file: Optional[str] = None


class MappingRequest(BaseModel):
    row_index: int
    category: str


class ProgressResponse(BaseModel):
    rows: List[RowMapping]
    total_rows: int
    mapped_count: int
    current_file: Optional[str] = None


class AddCategoryRequest(BaseModel):
    category: str


class AddCategoryResponse(BaseModel):
    original: str
    corrected: str
    corrections_made: bool
    message: str


class SuggestCategoryRequest(BaseModel):
    row_index: int


class SuggestCategoryResponse(BaseModel):
    suggested_category: str
    confidence: Optional[str] = None
    reasoning: Optional[str] = None


class ResetRequest(BaseModel):
    filename: str


@app.post("/auto-map-all")
def auto_map_all():
    """Auto-map all unmapped rows using AI suggestions"""
    # Create a trace for bulk operation
    trace = tracer.create_trace(
        name="auto_map_all", metadata={"endpoint": "/auto-map-all"}
    )

    try:
        progress_data = load_progress()
        if not progress_data:
            if trace:
                tracer.add_span(
                    trace,
                    name="no_progress_error",
                    output_text="No file uploaded",
                    metadata={"error": True},
                )
            raise HTTPException(
                status_code=404, detail="No file uploaded. Please upload a CSV first."
            )

        unmapped_rows = [
            (idx, row) for idx, row in enumerate(progress_data) if not row.get("mapped")
        ]

        if not unmapped_rows:
            if trace:
                tracer.add_span(
                    trace,
                    name="all_mapped",
                    output_text="No unmapped rows",
                    metadata={"unmapped_count": 0},
                )
            return {
                "message": "All rows are already mapped",
                "mapped_count": 0,
                "total_unmapped": 0,
            }

        categories = load_categories()
        previous_mappings = [
            row for row in progress_data if row.get("mapped") and row.get("category")
        ][-10:]  # Get last 10 examples

        if trace:
            tracer.add_span(
                trace,
                name="bulk_operation_start",
                metadata={
                    "total_unmapped": len(unmapped_rows),
                    "context_mappings": len(previous_mappings),
                },
            )

        mapped_count = 0
        errors = []
        current_filename = (
            progress_data[0].get("source_file") if progress_data else None
        )

        for idx, row in unmapped_rows:
            row_data = row.get("original_data", {})

            # First check for exact match
            matching_category = find_matching_category(row_data)
            if matching_category:
                progress_data[idx]["category"] = matching_category
                progress_data[idx]["mapped"] = True
                mapped_count += 1
            else:
                # Use AI suggestion
                row_trace = tracer.create_trace(
                    name="process_row", metadata={"row_index": idx}
                )
                try:
                    prompt = build_suggestion_prompt(
                        row_data, categories, previous_mappings
                    )
                    suggested_category = call_ollama(prompt, trace=row_trace)
                    progress_data[idx]["category"] = suggested_category
                    progress_data[idx]["mapped"] = True
                    mapped_count += 1

                    # Add to previous mappings for next iterations
                    previous_mappings.append(
                        {
                            "original_data": row_data,
                            "category": suggested_category,
                            "mapped": True,
                        }
                    )
                    if len(previous_mappings) > 10:
                        previous_mappings.pop(0)
                except Exception as e:
                    errors.append(f"Row {idx + 1}: {str(e)}")
                finally:
                    if row_trace:
                        tracer.end_trace(row_trace)

            # Save progress after each mapping so frontend can show updates
            save_progress(progress_data)

            # Save mappings for current file after each mapping
            if current_filename:
                save_mappings_for_file(current_filename, progress_data)

        if trace:
            tracer.add_span(
                trace,
                name="bulk_operation_complete",
                output_text=f"Auto-mapped {mapped_count} rows",
                metadata={
                    "total_processed": len(unmapped_rows),
                    "successful": mapped_count,
                    "failed": len(errors),
                },
            )

        return {
            "message": f"Auto-mapped {mapped_count} rows",
            "mapped_count": mapped_count,
            "total_unmapped": len(unmapped_rows),
            "errors": errors if errors else None,
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        if tracer.is_enabled():
            try:
                tracer.client.flush()
            except Exception:
                pass
        raise
    except Exception as e:
        if trace:
            tracer.add_span(
                trace,
                name="exception",
                input_text=type(e).__name__,
                output_text=str(e),
                metadata={"error": True},
            )
        if tracer.is_enabled():
            try:
                tracer.client.flush()
            except Exception:
                pass
        raise
    finally:
        if trace:
            tracer.end_trace(trace)
        # Flush the trace
        if tracer.is_enabled():
            try:
                tracer.client.flush()
            except Exception:
                pass


@app.get("/review")
def get_review_data():
    """Get all mapped rows for review"""
    progress_data = load_progress()
    if not progress_data:
        return {"rows": [], "total_rows": 0, "mapped_count": 0}

    mapped_rows = [
        {**row, "row_index": idx}
        for idx, row in enumerate(progress_data)
        if row.get("mapped")
    ]

    return {
        "rows": mapped_rows,
        "total_rows": len(progress_data),
        "mapped_count": len(mapped_rows),
    }


@app.get("/")
def read_root():
    return {"message": "Budget Planner API"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and parse CSV file"""
    # Trace user interaction: file upload
    trace = tracer.create_trace(
        name="user_upload_file",
        metadata={"endpoint": "/upload", "filename": file.filename or "unknown"},
    )

    try:
        if not file.filename:
            if trace:
                tracer.add_span(
                    trace,
                    name="error",
                    output_text="No file provided",
                    metadata={"error": True},
                )
                tracer.end_trace(trace)
            raise HTTPException(status_code=400, detail="No file provided")

        # Check for .csv extension (case-insensitive)
        if not file.filename.lower().endswith(".csv"):
            if trace:
                tracer.add_span(
                    trace,
                    name="error",
                    output_text="Invalid file type",
                    metadata={"error": True},
                )
                tracer.end_trace(trace)
            raise HTTPException(
                status_code=400,
                detail=f"File must be a CSV file with .csv extension. Received: {file.filename}",
            )

        contents = await file.read()
        if not contents:
            if trace:
                tracer.add_span(
                    trace,
                    name="error",
                    output_text="File is empty",
                    metadata={"error": True},
                )
                tracer.end_trace(trace)
            raise HTTPException(status_code=400, detail="File is empty")

        try:
            decoded = contents.decode("utf-8")
            csv_reader = csv.DictReader(decoded.splitlines())

            # Check if CSV has headers but no data rows
            if not csv_reader.fieldnames:
                if trace:
                    tracer.add_span(
                        trace,
                        name="error",
                        output_text="CSV file has no headers",
                        metadata={"error": True},
                    )
                    tracer.end_trace(trace)
                raise HTTPException(
                    status_code=400,
                    detail="CSV file appears to be empty or has no headers. Please check your file.",
                )

            # Initialize CSV validator with headers
            validator = CSVRowValidator(csv_reader.fieldnames)
        except UnicodeDecodeError:
            if trace:
                tracer.add_span(
                    trace,
                    name="error",
                    output_text="Encoding error",
                    metadata={"error": True},
                )
                tracer.end_trace(trace)
            raise HTTPException(
                status_code=400,
                detail="File encoding error. Please ensure the file is UTF-8 encoded",
            )

        rows = []
        skipped_count = 0
        total_rows_read = 0
        for idx, row in enumerate(csv_reader):
            total_rows_read += 1
            # Skip rows that are not fully populated
            if not validator.is_row_valid(row):
                skipped_count += 1
                continue

            rows.append(
                {
                    "row_index": len(rows),  # Use sequential index after filtering
                    "original_data": row,
                    "category": None,
                    "mapped": False,
                    "source_file": file.filename,  # Store source file name
                }
            )

        # If all rows were skipped, return a helpful error
        if total_rows_read > 0 and len(rows) == 0:
            if trace:
                tracer.add_span(
                    trace,
                    name="all_rows_skipped",
                    output_text=f"All {total_rows_read} rows were incomplete",
                    metadata={
                        "error": True,
                        "total_rows": total_rows_read,
                        "skipped": skipped_count,
                    },
                )
                tracer.end_trace(trace)
            raise HTTPException(
                status_code=400,
                detail=f"All {total_rows_read} row(s) in the file were incomplete and skipped. Each row needs: a valid date, an amount, and a description. Please check your CSV file format.",
            )

        # Check if file was already uploaded (duplicate detection)
        existing_mappings = load_mappings_for_file(file.filename)
        file_already_uploaded = len(existing_mappings) > 0

        if file_already_uploaded:
            if trace:
                tracer.add_span(
                    trace,
                    name="duplicate_file_detected",
                    output_text=f"File {file.filename} was previously uploaded",
                    metadata={
                        "existing_rows": len(existing_mappings),
                        "new_rows": len(rows),
                    },
                )

        if existing_mappings:
            # Merge with existing mappings by matching original_data content
            for row in rows:
                row_data = row.get("original_data", {})
                # Find matching existing mapping by content
                for existing_row in existing_mappings:
                    existing_data = existing_row.get("original_data", {})
                    if rows_match(row_data, existing_data) and existing_row.get(
                        "mapped"
                    ):
                        row["category"] = existing_row.get("category")
                        row["mapped"] = True
                        break

        # Merge with existing mappings instead of replacing
        if existing_mappings:
            # Create a map of existing rows by fingerprint for efficient lookup
            existing_by_fingerprint = {}
            for existing_row in existing_mappings:
                existing_data = existing_row.get("original_data", {})
                fingerprint = generate_row_fingerprint(existing_data)
                if fingerprint:
                    existing_by_fingerprint[fingerprint] = existing_row

            # Match new rows with existing ones
            matched_count = 0
            for row in rows:
                row_data = row.get("original_data", {})
                fingerprint = generate_row_fingerprint(row_data)

                if fingerprint and fingerprint in existing_by_fingerprint:
                    existing_row = existing_by_fingerprint[fingerprint]
                    if existing_row.get("mapped"):
                        row["category"] = existing_row.get("category")
                        row["mapped"] = True
                        matched_count += 1
                else:
                    # Try fallback matching for rows without valid fingerprint
                    for existing_row in existing_mappings:
                        existing_data = existing_row.get("original_data", {})
                        if rows_match(row_data, existing_data) and existing_row.get(
                            "mapped"
                        ):
                            row["category"] = existing_row.get("category")
                            row["mapped"] = True
                            matched_count += 1
                            break

        # Save initial state to progress (for current session)
        save_progress(rows)

        # Merge mappings instead of replacing - preserve existing mappings for rows not in new upload
        merge_mappings_for_file(file.filename, rows, existing_mappings)

        # Count mapped and unmapped rows
        mapped_count = sum(1 for row in rows if row.get("mapped", False))
        unmapped_count = len(rows) - mapped_count

        if trace:
            tracer.add_span(
                trace,
                name="upload_success",
                output_text=f"Uploaded {len(rows)} rows, skipped {skipped_count} incomplete rows",
                metadata={
                    "total_rows": len(rows),
                    "mapped_count": mapped_count,
                    "unmapped_count": unmapped_count,
                    "skipped_count": skipped_count,
                    "file_already_uploaded": file_already_uploaded,
                    "filename": file.filename,
                },
            )
            tracer.end_trace(trace)

        message = "File uploaded successfully"
        if file_already_uploaded:
            message += f" (file was previously uploaded - {mapped_count} existing mappings restored)"
        if skipped_count > 0:
            message += f". Skipped {skipped_count} incomplete row(s)."

        return {
            "message": message,
            "total_rows": len(rows),
            "mapped_count": mapped_count,
            "unmapped_count": unmapped_count,
            "skipped_count": skipped_count,
            "file_already_uploaded": file_already_uploaded,
            "rows": rows[:10],  # Return first 10 for preview
            "source_file": file.filename,
        }
    except HTTPException:
        if trace:
            tracer.end_trace(trace)
        raise
    except Exception as e:
        if trace:
            tracer.add_span(
                trace,
                name="exception",
                output_text=str(e),
                metadata={"error": True, "error_type": type(e).__name__},
            )
            tracer.end_trace(trace)
        raise


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
    # Trace user interaction: manual row mapping
    trace = tracer.create_trace(
        name="user_map_row",
        metadata={
            "endpoint": "/map",
            "row_index": request.row_index,
            "category": request.category,
        },
    )

    try:
        progress_data = load_progress()
        if not progress_data:
            if trace:
                tracer.add_span(
                    trace,
                    name="error",
                    output_text="No file uploaded",
                    metadata={"error": True},
                )
            raise HTTPException(
                status_code=404, detail="No file uploaded. Please upload a CSV first."
            )

        if request.row_index >= len(progress_data):
            if trace:
                tracer.add_span(
                    trace,
                    name="error",
                    output_text="Invalid row index",
                    metadata={"error": True},
                )
            raise HTTPException(status_code=400, detail="Invalid row index")

        row_data = progress_data[request.row_index].get("original_data", {})

        # Update the row
        progress_data[request.row_index]["category"] = request.category
        progress_data[request.row_index]["mapped"] = True

        # Save progress
        save_progress(progress_data)

        # Save mappings for the current file
        # Get the current file name from progress metadata or use a default
        current_filename = (
            progress_data[0].get("source_file") if progress_data else None
        )
        if current_filename:
            save_mappings_for_file(current_filename, progress_data)

        if trace:
            tracer.add_span(
                trace,
                name="mapping_success",
                output_text=f"Mapped row {request.row_index} to {request.category}",
                metadata={
                    "row_index": request.row_index,
                    "category": request.category,
                    "row_data": str(row_data)[:200],  # Truncate for metadata
                },
            )
            tracer.end_trace(trace)

        return {
            "message": "Row mapped successfully",
            "row": progress_data[request.row_index],
        }
    except Exception as e:
        if trace:
            tracer.add_span(
                trace,
                name="exception",
                output_text=str(e),
                metadata={"error": True, "error_type": type(e).__name__},
            )
            tracer.end_trace(trace)
        raise


@app.get("/categories")
def get_categories():
    """Get list of budget categories from file"""
    categories = load_categories()
    return {"categories": categories}


@app.post("/reset-mappings")
def reset_mappings(request: ResetRequest):
    """Reset (clear) all mappings for a specific file"""
    if not request.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

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

    # Remove mappings for this file
    if request.filename in all_mappings:
        del all_mappings[request.filename]

        # Save updated mappings
        MAPPINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MAPPINGS_FILE, "w") as f:
            json.dump(all_mappings, f, indent=2)

    # Also clear current progress if it's for this file
    progress_data = load_progress()
    if progress_data and progress_data[0].get("source_file") == request.filename:
        # Reset all mappings in current progress
        for row in progress_data:
            row["category"] = None
            row["mapped"] = False
        save_progress(progress_data)

    return {
        "message": f"Mappings reset for file: {request.filename}",
        "filename": request.filename,
    }


@app.post("/categories/add")
def add_category(request: AddCategoryRequest, confirm: Optional[str] = Query(None)):
    """Add a new category with spelling and capitalization checking"""
    # Convert string query parameter to boolean
    confirm_bool = False
    if confirm is not None:
        confirm_bool = str(confirm).lower() in ("true", "1", "yes")

    original_category = request.category.strip()

    if not original_category:
        raise HTTPException(status_code=400, detail="Category cannot be empty")

    # Load existing categories
    categories = load_categories()

    # Check if category already exists (case-insensitive)
    if any(cat.lower() == original_category.lower() for cat in categories):
        raise HTTPException(
            status_code=400,
            detail=f"Category '{original_category}' already exists",
        )

    # Check spelling and capitalization
    corrected_category, corrections_made = check_and_correct_category(original_category)

    # If corrections were made and not confirmed, return correction info without adding
    if corrections_made and not confirm_bool:
        return {
            "original": original_category,
            "corrected": corrected_category,
            "corrections_made": True,
            "message": "Corrections needed. Please confirm.",
            "categories": categories,
        }

    # Add the corrected category
    category_to_add = corrected_category if corrections_made else original_category
    categories.append(category_to_add)
    categories.sort()  # Keep sorted alphabetically

    # Save categories back to file
    save_categories(categories)

    message = "Category added successfully"
    if corrections_made:
        message = f"Category added: '{category_to_add}'"

    return {
        "original": original_category,
        "corrected": category_to_add,
        "corrections_made": False,  # Already confirmed and added
        "message": message,
        "categories": categories,
    }


@app.post("/suggest-category")
def suggest_category(request: SuggestCategoryRequest):
    """Get LLM suggestion for category based on row data and previous mappings"""
    # Create a trace for this operation
    trace = tracer.create_trace(
        name="suggest_category", metadata={"endpoint": "/suggest-category"}
    )

    try:
        progress_data = load_progress()
        if not progress_data:
            if trace:
                tracer.add_span(
                    trace,
                    name="no_progress_error",
                    output_text="No file uploaded",
                    metadata={"error": True},
                )
            raise HTTPException(
                status_code=404, detail="No file uploaded. Please upload a CSV first."
            )

        if request.row_index >= len(progress_data):
            if trace:
                tracer.add_span(
                    trace,
                    name="invalid_index_error",
                    output_text=f"Invalid row index: {request.row_index}",
                    metadata={"error": True, "row_index": request.row_index},
                )
            raise HTTPException(status_code=400, detail="Invalid row index")

        current_row = progress_data[request.row_index]
        row_data = current_row.get("original_data", {})

        if trace:
            tracer.add_span(
                trace,
                name="parse_request",
                metadata={
                    "row_index": request.row_index,
                    "description": row_data.get("description", ""),
                },
            )

        # First, check if we have a matching entry from previous mappings
        matching_category = find_matching_category(row_data)
        if matching_category:
            if trace:
                tracer.add_span(
                    trace,
                    name="matching_category_found",
                    output_text=f"Found matching category: {matching_category}",
                    metadata={
                        "category": matching_category,
                        "source": "previous_mappings",
                    },
                )
            return {
                "suggested_category": matching_category,
                "confidence": "high",
                "reasoning": "Based on a previous mapping of the same transaction",
            }

        # Get categories
        categories = load_categories()

        # Get previous mappings as examples (last 10 mapped rows)
        previous_mappings = [
            row for row in progress_data if row.get("mapped") and row.get("category")
        ][-10:]  # Get last 10 examples

        if trace:
            tracer.add_span(
                trace,
                name="load_context",
                metadata={
                    "categories_count": len(categories),
                    "previous_mappings_count": len(previous_mappings),
                },
            )

        # Build prompt
        prompt = build_suggestion_prompt(row_data, categories, previous_mappings)

        if trace:
            tracer.add_span(
                trace,
                name="build_prompt",
                output_text=f"Prompt built ({len(prompt)} chars)",
                metadata={"prompt_length": len(prompt)},
            )

        # Call Ollama only if no match found
        try:
            suggested_category = call_ollama(prompt, trace=trace)
            if trace:
                tracer.add_span(
                    trace,
                    name="categorization_success",
                    output_text=f"Categorized as: {suggested_category}",
                    metadata={"category": suggested_category},
                )
            if trace:
                tracer.end_trace(trace)
            return {
                "suggested_category": suggested_category,
                "confidence": "medium",  # Could be enhanced with LLM confidence
                "reasoning": "Based on similar transactions and available categories",
            }
        except Exception as e:
            if trace:
                tracer.add_span(
                    trace,
                    name="ollama_error",
                    input_text=type(e).__name__,
                    output_text=str(e),
                    metadata={"error": True},
                )
                tracer.end_trace(trace)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get LLM suggestion: {str(e)}. Make sure Ollama is running with model {OLLAMA_MODEL}.",
            )
    except HTTPException:
        if trace:
            tracer.end_trace(trace)
        raise
    except Exception as e:
        if trace:
            tracer.add_span(
                trace,
                name="exception",
                input_text=type(e).__name__,
                output_text=str(e),
                metadata={"error": True},
            )
            tracer.end_trace(trace)
        raise


@app.get("/spending-summary")
def spending_summary():
    """Return spending totals per category per month, grouped by file."""
    # Include current progress in addition to saved mappings
    # This ensures we see mappings that are in progress
    current_progress = load_progress()
    if current_progress:
        # Save current progress to mappings if it has a source file
        current_filename = (
            current_progress[0].get("source_file") if current_progress else None
        )
        if current_filename:
            save_mappings_for_file(current_filename, current_progress)

    summary, months = calculate_spending_summary()
    return {"summary": summary, "months": months}


def build_suggestion_prompt(
    row_data: Dict, categories: List[str], previous_mappings: List[Dict]
) -> str:
    """Build prompt for LLM category suggestion"""

    # Format row data
    row_info = "\n".join([f"  - {key}: {value}" for key, value in row_data.items()])

    # Format categories
    categories_list = ", ".join(categories)

    # Format previous mappings as examples
    examples_text = ""
    if previous_mappings:
        examples_text = "\n\nHere are some examples of previous mappings:\n"
        for mapping in previous_mappings:
            mapping_data = mapping.get("original_data", {})
            mapping_category = mapping.get("category", "")
            mapping_info = ", ".join([f"{k}: {v}" for k, v in mapping_data.items()])
            examples_text += (
                f"- Transaction: {mapping_info} → Category: {mapping_category}\n"
            )

    prompt = f"""You are a budget categorization assistant. Your task is to suggest the most appropriate budget category for a transaction.

Available categories:
{categories_list}

Current transaction to categorize:
{row_info}
{examples_text}

Based on the transaction details and the examples provided, suggest the most appropriate category from the list above.

IMPORTANT: 
- Return ONLY the category name exactly as it appears in the list above
- Do not include any explanation, reasoning, or additional text
- If the transaction doesn't clearly fit any category, suggest "Other"
- Use the examples to understand the pattern of how similar transactions are categorized

Category:"""

    return prompt


def call_ollama(prompt: str, trace=None) -> str:
    """Call Ollama API to get category suggestion"""
    url = f"{OLLAMA_URL}/api/generate"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,  # Lower temperature for more consistent results
            "top_p": 0.9,
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        # Extract the suggested category from the response
        suggested = result.get("response", "").strip()

        # Log the LLM generation
        if trace:
            tracer.add_generation(
                trace,
                name="ollama_categorization",
                model=OLLAMA_MODEL,
                input_text=prompt,
                output_text=suggested,
                usage={
                    "prompt_tokens": result.get("prompt_eval_count", 0),
                    "completion_tokens": result.get("eval_count", 0),
                },
                metadata={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "ollama_url": OLLAMA_URL,
                },
            )

        # Clean up the response - remove any extra text
        # The prompt asks for only the category name
        suggested = suggested.split("\n")[0].strip()
        suggested = suggested.replace("Category:", "").strip()

        # Validate it's one of our categories (case-insensitive)
        categories = load_categories()
        for cat in categories:
            if cat.lower() == suggested.lower():
                if trace:
                    tracer.add_span(
                        trace,
                        name="validation_success",
                        output_text=f"Validated category: {cat}",
                        metadata={"category": cat},
                    )
                return cat

        # If not found, try to find closest match or return "Other"
        if trace:
            tracer.add_span(
                trace,
                name="validation_fallback",
                input_text=f"Invalid category: {suggested}",
                output_text="Using 'Other'",
                metadata={"suggested": suggested},
            )
        return "Other"

    except requests.exceptions.ConnectionError as e:
        if trace:
            tracer.add_span(
                trace,
                name="connection_error",
                output_text=f"Failed to connect to {OLLAMA_URL}",
                metadata={
                    "error": True,
                    "error_type": "ConnectionError",
                    "details": str(e),
                },
            )
        raise Exception(
            f"Cannot connect to Ollama at {OLLAMA_URL}. Make sure Ollama is running."
        )
    except requests.exceptions.Timeout as e:
        if trace:
            tracer.add_span(
                trace,
                name="timeout_error",
                output_text="Ollama request timed out",
                metadata={"error": True, "error_type": "Timeout", "details": str(e)},
            )
        raise Exception("Ollama request timed out. The model may be loading.")
    except Exception as e:
        if trace:
            tracer.add_span(
                trace,
                name="unexpected_error",
                input_text=type(e).__name__,
                output_text=str(e),
                metadata={"error": True, "error_type": type(e).__name__},
            )
        raise Exception(f"Error calling Ollama: {str(e)}")


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


def merge_mappings_for_file(
    filename: str, new_rows: List[Dict], existing_rows: List[Dict]
):
    """
    Merge new rows with existing mappings, preserving existing mappings for rows not in new upload.
    This prevents losing mappings when re-uploading a file.
    """
    if not existing_rows:
        # No existing mappings, just save new rows
        save_mappings_for_file(filename, new_rows)
        return

    # Create fingerprint maps for efficient lookup
    new_by_fingerprint = {}
    for row in new_rows:
        row_data = row.get("original_data", {})
        fingerprint = generate_row_fingerprint(row_data)
        if fingerprint:
            new_by_fingerprint[fingerprint] = row

    existing_by_fingerprint = {}
    for row in existing_rows:
        row_data = row.get("original_data", {})
        fingerprint = generate_row_fingerprint(row_data)
        if fingerprint:
            existing_by_fingerprint[fingerprint] = row

    # Start with new rows (they take precedence)
    merged_rows = {fp: row.copy() for fp, row in new_by_fingerprint.items()}

    # Add existing rows that aren't in the new upload (preserve old mappings)
    for fingerprint, existing_row in existing_by_fingerprint.items():
        if fingerprint not in merged_rows:
            merged_rows[fingerprint] = existing_row

    # Convert back to list (fingerprints are just for deduplication)
    # Use new_rows as base, but preserve order
    final_rows = []
    seen_fingerprints = set()

    # Add all new rows first
    for row in new_rows:
        row_data = row.get("original_data", {})
        fingerprint = generate_row_fingerprint(row_data)
        if fingerprint:
            seen_fingerprints.add(fingerprint)
        final_rows.append(row)

    # Add existing rows that weren't in new upload
    for existing_row in existing_rows:
        existing_data = existing_row.get("original_data", {})
        fingerprint = generate_row_fingerprint(existing_data)
        if fingerprint and fingerprint not in seen_fingerprints:
            final_rows.append(existing_row)
            seen_fingerprints.add(fingerprint)

    # Save merged mappings
    save_mappings_for_file(filename, final_rows)


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


def normalize_value(value: str) -> str:
    """Normalize a value for comparison (lowercase, strip whitespace)"""
    if not isinstance(value, str):
        value = str(value)
    return value.lower().strip()


def generate_row_fingerprint(row_data: Dict) -> str:
    """
    Generate a fingerprint/hash for a row based on key identifying fields.
    Uses date, amount, and description to create a unique identifier.
    """
    # Extract key fields for fingerprinting
    date = extract_transaction_date(row_data)
    amount = extract_amount(row_data)

    # Get description - find first non-date, non-amount field
    description = ""
    for key, value in row_data.items():
        key_lower = key.lower()
        if "date" in key_lower:
            continue
        if any(
            token in key_lower
            for token in ["amount", "debit", "credit", "value", "charge"]
        ):
            continue
        if value and str(value).strip():
            description = str(value).strip()
            break

    # Create fingerprint from key fields
    date_str = date.strftime("%Y-%m-%d") if date else ""
    amount_str = f"{amount:.2f}" if amount is not None else ""
    desc_str = normalize_value(description) if description else ""

    # Create hash from combined fields
    fingerprint_str = f"{date_str}|{amount_str}|{desc_str}"
    return hashlib.md5(fingerprint_str.encode("utf-8")).hexdigest()


def rows_match(row1: Dict, row2: Dict) -> bool:
    """
    Check if two row data dictionaries match.
    Uses fingerprint for more reliable matching that works even if column order changes.
    """
    # First try fingerprint matching (more reliable)
    fingerprint1 = generate_row_fingerprint(row1)
    fingerprint2 = generate_row_fingerprint(row2)
    if fingerprint1 == fingerprint2 and fingerprint1:  # Non-empty fingerprint
        return True

    # Fallback to exact field matching (for backward compatibility)
    normalized1 = {k: normalize_value(v) for k, v in row1.items()}
    normalized2 = {k: normalize_value(v) for k, v in row2.items()}

    # Check if all keys match
    if set(normalized1.keys()) != set(normalized2.keys()):
        return False

    # Check if all values match
    for key in normalized1.keys():
        if normalized1[key] != normalized2[key]:
            return False

    return True


def find_matching_category(row_data: Dict) -> Optional[str]:
    """Find a matching category from previous mappings"""
    # Load all previous mappings
    all_mappings = load_all_mappings()

    # Look for exact matches
    for mapping in all_mappings:
        if not mapping.get("mapped") or not mapping.get("category"):
            continue

        mapping_data = mapping.get("original_data", {})
        if rows_match(row_data, mapping_data):
            return mapping.get("category")

    return None


def extract_text_from_file(file_path: Path, encoding: str = "utf-8") -> Optional[str]:
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


def calculate_spending_summary() -> Tuple[Dict[str, Dict], List[str]]:
    """Aggregate spending totals per category per month across all files."""
    # Load both saved mappings and current progress
    all_mappings = load_all_mappings()

    # Also include current progress to catch in-progress mappings
    current_progress = load_progress()
    if current_progress:
        # Merge current progress with saved mappings (current progress takes precedence)
        current_filename = (
            current_progress[0].get("source_file") if current_progress else None
        )
        if current_filename:
            # Replace any existing mappings for this file with current progress
            all_mappings = [
                m for m in all_mappings if m.get("source_file") != current_filename
            ]
            all_mappings.extend(current_progress)

    # Aggregate across all files - single summary structure
    summary: Dict[str, Dict] = {"categories": {}}
    months_set = set()

    for mapping in all_mappings:
        if not mapping.get("mapped") or not mapping.get("category"):
            continue

        row_data = mapping.get("original_data", {})
        amount = extract_amount(row_data)
        if amount is None:
            continue

        transaction_date = extract_transaction_date(row_data)
        if transaction_date:
            month_key = transaction_date.strftime("%Y-%m")
        else:
            month_key = "Unknown"

        category = mapping.get("category")

        # Normalize amount based on category:
        # - Income: normalize to negative (money coming in)
        # - Expenses: normalize to positive (money going out)
        if category == "Income":
            # Income should be negative (money coming in)
            normalized_amount = -abs(amount)
        else:
            # Expenses should be positive (money going out)
            normalized_amount = abs(amount)

        if normalized_amount == 0:
            continue

        months_set.add(month_key)

        # Aggregate directly into categories (no file grouping)
        category_summary = summary["categories"].setdefault(category, {})
        category_summary[month_key] = (
            category_summary.get(month_key, 0.0) + normalized_amount
        )

    # Round values for presentation
    for month_totals in summary["categories"].values():
        for month_key, value in month_totals.items():
            month_totals[month_key] = round(value, 2)

    months_list = sorted(months_set)
    return summary, months_list


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
    # Only save defaults if file doesn't exist (not if it's invalid)
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


def check_and_correct_category(category: str) -> Tuple[str, bool]:
    """
    Check spelling and capitalization of a category.
    Returns (corrected_category, corrections_made)
    """
    corrections_made = False
    corrected = category

    # Split category into words (handle &, -, etc.)
    # Preserve special characters like &, -, etc.
    words = re.split(r"(\s+|&|-)", category)

    corrected_words = []
    for word in words:
        if not word.strip() or word in ["&", "-", " "]:
            # Preserve separators and spaces
            corrected_words.append(word)
            continue

        # Check spelling for each word
        corrected_word = spell(word)
        if corrected_word.lower() != word.lower():
            corrections_made = True
            corrected_words.append(corrected_word)
        else:
            corrected_words.append(word)

    corrected = "".join(corrected_words)

    # Fix capitalization: Title Case for each word
    # Handle special cases like "&" and "-"
    corrected = title_case_category(corrected)

    # Check if capitalization changed
    if corrected != category:
        corrections_made = True

    return corrected, corrections_made


def title_case_category(category: str) -> str:
    """
    Apply proper title case to category.
    Handles special cases like "&", "-", and common words.
    """
    # Words that should remain lowercase (except at start)
    lowercase_words = {"and", "or", "the", "of", "in", "on", "at", "to", "for"}

    # Split by spaces, &, and - while preserving separators
    parts = re.split(r"(\s+|&|-)", category)
    result = []

    for i, part in enumerate(parts):
        if not part.strip() or part in ["&", "-", " "]:
            result.append(part)
            continue

        # First word or after separator: always capitalize
        # Otherwise: lowercase if in lowercase_words list
        if i == 0 or (i > 0 and parts[i - 1] in [" ", "&", "-"]):
            result.append(part.capitalize())
        elif part.lower() in lowercase_words:
            result.append(part.lower())
        else:
            result.append(part.capitalize())

    return "".join(result)
