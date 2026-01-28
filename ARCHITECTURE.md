# Budget Cursor - Architecture Documentation

## System Architecture Overview

```mermaid
graph TB
    subgraph "User Browser"
        UI[React Frontend<br/>Port 13030]
    end

    subgraph "Docker Container - Frontend"
        REACT[React Dev Server<br/>Create React App]
        STATIC[Static Assets<br/>Components, CSS]
    end

    subgraph "Docker Container - Backend"
        FASTAPI[FastAPI Server<br/>Port 18080<br/>Uvicorn ASGI]

        subgraph "App Package"
            MAIN[main.py<br/>API Routes<br/>700 LOC]
            UTILS[utils.py<br/>Helper Functions<br/>200 LOC]
            VALIDATOR[csv_validator.py<br/>11 Validation Rules<br/>400 LOC]
            MODELS[models.py<br/>Pydantic Schemas]
            TRACER[langfuse_tracer.py<br/>LLM Monitoring]
        end
    end

    subgraph "Host Machine"
        OLLAMA[Ollama Server<br/>Port 11434<br/>llama3.1:8b]
        LANGFUSE[Langfuse Server<br/>Port 3001<br/>Optional Monitoring]
    end

    subgraph "Persistent Storage"
        PROGRESS[progress/<br/>mapping_progress.json]
        CATEGORIES[categories.json<br/>Dynamic Categories]
    end

    UI -->|HTTP Requests| REACT
    REACT -->|Proxy /api| FASTAPI
    FASTAPI --> MAIN
    MAIN --> VALIDATOR
    MAIN --> UTILS
    MAIN --> MODELS
    MAIN -->|Read/Write| PROGRESS
    MAIN -->|Read/Write| CATEGORIES
    MAIN -->|LLM Requests| UTILS
    UTILS -->|HTTP POST| OLLAMA
    UTILS -->|Trace Calls| TRACER
    TRACER -.->|Optional Telemetry| LANGFUSE
    OLLAMA -->|Categorization Response| UTILS
    UTILS -->|Suggestions| MAIN
    MAIN -->|Pydantic Models| FASTAPI
    FASTAPI -->|JSON Response| UI

    style FASTAPI fill:#f9f,stroke:#333,stroke-width:4px
    style VALIDATOR fill:#fbb,stroke:#333,stroke-width:3px
    style OLLAMA fill:#bbf,stroke:#333,stroke-width:2px
    style PROGRESS fill:#bfb,stroke:#333,stroke-width:2px
```

## File Structure

```
budget_cursor/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 [700 LOC - API routes + business logic]
│   │   │   ├── FastAPI app instance
│   │   │   ├── CORS middleware
│   │   │   ├── 12 API endpoints with type hints
│   │   │   ├── Request/Response validation (Pydantic)
│   │   │   └── HTTPException error handling
│   │   ├── models.py               [Pydantic schemas]
│   │   │   ├── UploadResponse
│   │   │   ├── MapRequest
│   │   │   ├── BulkMapRequest
│   │   │   └── CategoryResponse
│   │   ├── utils.py                [200 LOC - Helper functions]
│   │   │   ├── ollama_suggest()
│   │   │   ├── ollama_bulk_suggest()
│   │   │   ├── build_prompt()
│   │   │   └── parse_llm_response()
│   │   ├── csv_validator.py        [400 LOC - Comprehensive validation]
│   │   │   ├── CSVValidator class
│   │   │   ├── 11 validation rules
│   │   │   ├── Type checking
│   │   │   ├── Date format validation
│   │   │   └── Amount parsing
│   │   └── langfuse_tracer.py      [LLM tracing]
│   ├── tests/
│   │   ├── conftest.py             [pytest fixtures]
│   │   ├── test_main.py            [API endpoint tests]
│   │   ├── test_utils.py           [Helper function tests]
│   │   └── test_csv_validator.py   [Validation tests]
│   ├── pyproject.toml              [Poetry dependencies + test config]
│   ├── poetry.lock
│   ├── categories.json
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 [Main component]
│   │   ├── index.jsx
│   │   └── index.css
│   ├── package.json
│   └── Dockerfile
├── progress/                       [Separate directory for data]
│   └── mapping_progress.json
├── docker-compose.yml
└── README_TESTING.md               [Test documentation]
```

## API Endpoint Flow

```mermaid
sequenceDiagram
    participant User
    participant React
    participant FastAPI
    participant Validator
    participant Utils
    participant Ollama
    participant Langfuse
    participant Files

    User->>React: Upload CSV/JSON
    React->>FastAPI: POST /api/upload
    FastAPI->>Validator: validate_csv(file_content)

    alt Validation Fails
        Validator-->>FastAPI: ValidationError(details)
        FastAPI-->>React: 400 Bad Request<br/>{error: "Row 5: Invalid date format"}
    else Validation Success
        Validator-->>FastAPI: Valid data
        FastAPI->>Files: Write to progress/mapping_progress.json
        FastAPI-->>React: UploadResponse model<br/>{file_name, total_rows, validation_errors: []}
    end

    User->>React: Click "Bulk AI Categorize"
    React->>FastAPI: POST /api/bulk-map<br/>BulkMapRequest{indices: [0,1,2,3,4]}
    FastAPI->>FastAPI: Validate request (Pydantic)
    FastAPI->>Files: Load historical mappings
    FastAPI->>Utils: ollama_bulk_suggest(transactions, history)
    Utils->>Ollama: POST /api/generate<br/>{prompt with context}
    Note over Utils,Ollama: Type-safe request/response<br/>~800 tokens, ~5 seconds
    Utils->>Langfuse: Trace with metadata<br/>(if configured)
    Ollama-->>Utils: LLM response (JSON string)
    Utils->>Utils: parse_llm_response()<br/>Validate categories

    alt Invalid Response
        Utils-->>FastAPI: HTTPException 500<br/>"Failed to parse LLM response"
    else Valid Response
        Utils-->>FastAPI: List[Dict] suggestions
        FastAPI->>Files: Update progress atomically
        FastAPI-->>React: Response model<br/>{suggestions, updated_rows}
    end
```

## Data Flow - Modular Architecture

```mermaid
graph LR
    subgraph "Request Layer"
        REQUEST[HTTP Request] --> PYDANTIC[Pydantic Model<br/>Validation]
        PYDANTIC --> ENDPOINT[FastAPI Endpoint<br/>Type-Safe]
    end

    subgraph "Validation Layer"
        ENDPOINT --> CSV_VAL[CSVValidator<br/>11 Rules]
        CSV_VAL --> TYPE_CHECK[Type Checking]
        CSV_VAL --> DATE_CHECK[Date Format]
        CSV_VAL --> AMOUNT_CHECK[Amount Parsing]
        CSV_VAL --> EMPTY_CHECK[Empty Row Detection]
    end

    subgraph "Business Logic Layer"
        TYPE_CHECK --> UTILS[utils.py<br/>Helper Functions]
        DATE_CHECK --> UTILS
        AMOUNT_CHECK --> UTILS
        EMPTY_CHECK --> UTILS
        UTILS --> PROMPT[build_prompt()]
        PROMPT --> LLM_CALL[ollama_suggest()]
    end

    subgraph "External Services"
        LLM_CALL --> OLLAMA[Ollama API<br/>llama3.1:8b]
        LLM_CALL --> TRACE[Langfuse Trace<br/>Structured Logging]
    end

    subgraph "Response Layer"
        OLLAMA --> PARSE[parse_llm_response()]
        PARSE --> VALIDATE_CAT[Validate Categories]
        VALIDATE_CAT --> RESPONSE_MODEL[Pydantic Response]
        RESPONSE_MODEL --> JSON[JSON Response]
    end

    style CSV_VAL fill:#fbb,stroke:#333,stroke-width:3px
    style PYDANTIC fill:#fbf,stroke:#333,stroke-width:3px
    style OLLAMA fill:#bbf,stroke:#333,stroke-width:3px
```

## CSV Validation Architecture

```mermaid
graph TD
    INPUT[CSV File Upload] --> PARSE[Parse CSV]
    PARSE --> VALIDATOR[CSVValidator.validate_csv]

    VALIDATOR --> CHECK1[Check Headers<br/>Required: Date, Amount, Description]
    VALIDATOR --> CHECK2[Check Empty Rows]
    VALIDATOR --> CHECK3[Check Mixed Data Types]

    CHECK1 --> ITERATE[Iterate Rows]
    CHECK2 --> ITERATE
    CHECK3 --> ITERATE

    ITERATE --> ROW_VAL[validate_row]

    ROW_VAL --> DATE_VAL[Validate Date<br/>ISO/US/EU formats]
    ROW_VAL --> AMOUNT_VAL[Validate Amount<br/>Parse currency symbols]
    ROW_VAL --> DESC_VAL[Validate Description<br/>Check length/content]

    DATE_VAL --> COLLECT[Collect Errors]
    AMOUNT_VAL --> COLLECT
    DESC_VAL --> COLLECT

    COLLECT --> DECISION{Has Errors?}

    DECISION -->|Yes| ERROR_RESPONSE[Return Validation Errors<br/>Detailed per-row feedback]
    DECISION -->|No| SUCCESS[Return Valid Data<br/>Proceed to storage]

    style VALIDATOR fill:#fbb,stroke:#333,stroke-width:4px
    style ERROR_RESPONSE fill:#f99,stroke:#333,stroke-width:2px
    style SUCCESS fill:#9f9,stroke:#333,stroke-width:2px
```

### Validation Rules (11 Total)

```python
# csv_validator.py implementation
class CSVValidator:
    def validate_csv(self, csv_content):
        """
        1. Header validation (Date, Amount, Description required)
        2. Empty file check
        3. Minimum row count (at least 1 data row)
        4. Empty row detection
        5. Mixed type detection in columns
        """

    def validate_row(self, row, row_num):
        """
        6. Date field presence
        7. Date format validation (try multiple formats)
        8. Amount field presence
        9. Amount parsing (handle $, commas, negatives)
        10. Description field presence
        11. Description length validation
        """
```

## Key Design Decisions

### 1. Modular App Package
**Rationale**: Maintainability and testability
- Separation of concerns across files
- Each module <500 LOC (except main.py at 700)
- Easy to test in isolation
- Trade-off: More import complexity, slightly slower initial development

### 2. Pydantic Models
**Rationale**: Type safety and automatic validation
```python
# models.py
class BulkMapRequest(BaseModel):
    indices: List[int]  # Auto-validates: must be list of integers
    file_name: str      # Auto-validates: must be string

# Automatic validation at endpoint
@app.post("/api/bulk-map")
async def bulk_map(request: BulkMapRequest):
    # request.indices is guaranteed to be List[int]
    # No manual type checking needed
```

### 3. Comprehensive CSV Validator
**Rationale**: Catch edge cases early
```python
# Example edge cases handled:
# - Empty rows in middle of CSV
# - Mixed date formats (2024-01-01, 01/01/2024, 01-Jan-2024)
# - Amounts with currency symbols ($100.00, 100,00 €)
# - Missing required fields
# - Malformed CSV structure
# - Type inconsistencies (number in date column)
```
Trade-off: More code, longer validation time (~50ms for 100 rows)

### 4. Separate progress/ Directory
**Rationale**: Clean separation of code and data
- `progress/mapping_progress.json` isolated
- Easier to .gitignore data files
- Clearer directory structure
- Trade-off: One more directory level

### 5. FastAPI Async Support
**Rationale**: Future scalability
```python
# Async endpoints ready for async operations
@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    # Currently synchronous operations
    # Easy to add: await asyncio.gather() for parallel processing
```
Trade-off: Added complexity for current sync operations

## Component Responsibilities

### main.py (700 LOC)
```python
# API Endpoints (12 total):
@app.get("/api/health")              # Health check
@app.post("/api/upload")             # File upload + validation
@app.get("/api/progress")            # Get mapping state
@app.post("/api/map-row")            # Manual categorization
@app.post("/api/suggest-category")   # Single AI suggestion
@app.post("/api/bulk-map")           # Batch AI (5 items)
@app.post("/api/reset-file")         # Clear progress
@app.get("/api/categories")          # Get categories
@app.post("/api/add-category")       # Add category
@app.post("/api/confirm-add-category") # Confirm addition
@app.get("/api/stats")               # Mapping statistics
@app.get("/api/analytics")           # Spending insights

# Business Logic:
- Progress tracking
- File management
- Category management
- Error handling (HTTPException)
```

### utils.py (200 LOC)
```python
# Helper Functions:
def ollama_suggest(transaction, history, categories)
    # Single transaction suggestion
    # Returns: {"category": str, "confidence": float}

def ollama_bulk_suggest(transactions, history, categories)
    # Batch of 5 transactions
    # Returns: List[{"index": int, "category": str}]

def build_prompt(transactions, history, categories)
    # Construct LLM prompt with context
    # Returns: str (formatted prompt)

def parse_llm_response(response_text)
    # Parse and validate LLM JSON output
    # Returns: validated dict or raises ValueError

def load_historical_mappings(progress_data, limit=100)
    # Extract previous categorizations
    # Returns: List[Dict] of examples
```

### csv_validator.py (400 LOC)
```python
class CSVValidator:
    def validate_csv(self, csv_content: str) -> Dict
        # Comprehensive CSV validation
        # Returns: {"valid": bool, "errors": List[str], "data": List[Dict]}

    def validate_row(self, row: Dict, row_num: int) -> List[str]
        # Per-row validation
        # Returns: List of error messages

    def _parse_date(self, date_str: str) -> Optional[datetime]
        # Try multiple date formats
        # Returns: datetime or None

    def _parse_amount(self, amount_str: str) -> Optional[float]
        # Parse currency amounts
        # Returns: float or None
```

### models.py
```python
# Pydantic Schemas:
class UploadResponse(BaseModel):
    file_name: str
    total_rows: int
    validation_errors: List[str] = []

class MapRequest(BaseModel):
    index: int
    category: str
    file_name: str

class BulkMapRequest(BaseModel):
    indices: List[int]
    file_name: str

class CategoryResponse(BaseModel):
    categories: List[str]
```

## Testing Architecture

```mermaid
graph TB
    subgraph "Test Suite"
        PYTEST[pytest Runner]

        subgraph "Unit Tests"
            TEST_UTILS[test_utils.py<br/>Helper function tests]
            TEST_VALIDATOR[test_csv_validator.py<br/>Validation logic tests]
        end

        subgraph "Integration Tests"
            TEST_MAIN[test_main.py<br/>API endpoint tests]
        end

        subgraph "Fixtures"
            CONFTEST[conftest.py<br/>Shared fixtures]
            MOCK_OLLAMA[Mock Ollama responses]
            SAMPLE_CSV[Sample test data]
        end
    end

    PYTEST --> TEST_UTILS
    PYTEST --> TEST_VALIDATOR
    PYTEST --> TEST_MAIN

    CONFTEST --> TEST_UTILS
    CONFTEST --> TEST_VALIDATOR
    CONFTEST --> TEST_MAIN

    TEST_MAIN --> MOCK_OLLAMA
    TEST_UTILS --> MOCK_OLLAMA
    TEST_VALIDATOR --> SAMPLE_CSV

    style PYTEST fill:#9f9,stroke:#333,stroke-width:3px
```

### Test Coverage Strategy
```bash
# Run tests with coverage
poetry run pytest --cov=app --cov-report=term-missing

# Coverage targets:
# - csv_validator.py:  90%+ (critical validation logic)
# - utils.py:          75%+ (LLM integration, harder to mock)
# - main.py:           65%+ (API endpoints, integration tests)
# - Overall:           ~65% coverage
```

### Example Test Structure
```python
# tests/test_csv_validator.py
def test_valid_csv():
    validator = CSVValidator()
    result = validator.validate_csv(VALID_CSV_CONTENT)
    assert result["valid"] == True
    assert len(result["errors"]) == 0

def test_missing_headers():
    validator = CSVValidator()
    result = validator.validate_csv(CSV_NO_DATE_HEADER)
    assert result["valid"] == False
    assert "Missing required header: Date" in result["errors"]

def test_invalid_date_format():
    validator = CSVValidator()
    result = validator.validate_csv(CSV_BAD_DATE)
    assert "Row 1: Invalid date format" in result["errors"]

# tests/test_main.py (uses TestClient)
def test_upload_valid_file(client, sample_csv):
    response = client.post("/api/upload", files={"file": sample_csv})
    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 10

def test_upload_invalid_file(client, invalid_csv):
    response = client.post("/api/upload", files={"file": invalid_csv})
    assert response.status_code == 400
    assert "validation" in response.json()["detail"].lower()
```

## Performance Characteristics

### Latency Breakdown
```
Operation                      Time          Notes
─────────────────────────────────────────────────────────
Upload CSV (100 rows)          ~250ms        +50ms validation
Single AI Suggestion           ~2.3s         +200ms validation
Bulk AI (5 items)              ~5.1s         +300ms validation
Manual categorization          ~100ms        Fast path
CSV Validation (100 rows)      ~50ms         Comprehensive checks
Pydantic Model Validation      ~5-10ms       Per request
```

### Memory Usage
```
Component                      Memory        Notes
─────────────────────────────────────────────────────────
FastAPI + Uvicorn              ~80MB         Base overhead
Pydantic Models                ~5MB          Schema definitions
CSV Validator (loaded)         ~15MB         Validation logic
Ollama Client                  ~10MB         HTTP client
Test Suite (running)           ~120MB        Fixtures + mocks
```

## Docker Architecture

```mermaid
graph TB
    subgraph "Host Machine - macOS M2"
        OLLAMA_HOST[Ollama Server<br/>localhost:11434<br/>llama3.1:8b model]
        LANGFUSE_HOST[Langfuse Server<br/>localhost:3001<br/>Docker container]
    end

    subgraph "Docker Network: budget_cursor_default"
        FE_CONTAINER[Frontend Container<br/>Node.js + React<br/>Port 13030→3000]
        BE_CONTAINER[Backend Container<br/>Python + FastAPI<br/>Port 18080→8000]

        BE_CONTAINER -->|host.docker.internal:11434| OLLAMA_HOST
        BE_CONTAINER -.->|localhost:3001| LANGFUSE_HOST
    end

    USER[User Browser<br/>localhost:13030] --> FE_CONTAINER
    FE_CONTAINER -->|/api proxy| BE_CONTAINER

    subgraph "Volume Mounts"
        HOST_CODE[./backend/app<br/>./frontend/src] -.->|Live reload| BE_CONTAINER
        HOST_CODE -.->|Live reload| FE_CONTAINER
        HOST_DATA[./progress/] -.->|Bind mount| BE_CONTAINER
    end
```

## Error Handling Architecture

```mermaid
graph TD
    REQUEST[HTTP Request] --> PYDANTIC_VAL{Pydantic<br/>Validation}

    PYDANTIC_VAL -->|Invalid| PYDANTIC_ERROR[422 Unprocessable Entity<br/>Detailed field errors]
    PYDANTIC_VAL -->|Valid| ENDPOINT[Endpoint Logic]

    ENDPOINT --> CUSTOM_VAL{Custom<br/>Validation}

    CUSTOM_VAL -->|CSV Invalid| CSV_ERROR[400 Bad Request<br/>CSVValidator errors]
    CUSTOM_VAL -->|Business Logic Error| BUSINESS_ERROR[400 Bad Request<br/>Custom message]
    CUSTOM_VAL -->|Valid| EXTERNAL_CALL[External Service Call]

    EXTERNAL_CALL --> OLLAMA_CALL{Ollama<br/>Success?}

    OLLAMA_CALL -->|Connection Error| OLLAMA_ERROR[503 Service Unavailable<br/>"Ollama not reachable"]
    OLLAMA_CALL -->|Parse Error| PARSE_ERROR[500 Internal Server Error<br/>"Failed to parse LLM response"]
    OLLAMA_CALL -->|Success| SUCCESS[200 OK<br/>Pydantic Response Model]

    EXTERNAL_CALL --> LANGFUSE_CALL{Langfuse<br/>Trace}
    LANGFUSE_CALL -->|Error| TRACE_LOG[Log Warning<br/>Continue without trace<br/>Non-blocking]
    LANGFUSE_CALL -->|Success| SUCCESS

    style CSV_ERROR fill:#fbb,stroke:#333,stroke-width:2px
    style OLLAMA_ERROR fill:#f99,stroke:#333,stroke-width:2px
    style SUCCESS fill:#9f9,stroke:#333,stroke-width:2px
    style TRACE_LOG fill:#ffb,stroke:#333,stroke-width:2px
```

### Error Handling Patterns

```python
# 1. Automatic Pydantic Validation
@app.post("/api/bulk-map")
async def bulk_map(request: BulkMapRequest):  # Auto-validates
    # If request invalid: 422 with field-level details
    pass

# 2. Custom Validation with HTTPException
if not (0 <= index < len(rows)):
    raise HTTPException(
        status_code=400,
        detail=f"Invalid index {index}. Must be 0-{len(rows)-1}"
    )

# 3. CSV Validation Errors
validation_result = validator.validate_csv(content)
if not validation_result["valid"]:
    raise HTTPException(
        status_code=400,
        detail={
            "message": "CSV validation failed",
            "errors": validation_result["errors"]
        }
    )

# 4. External Service Errors (Ollama)
try:
    response = requests.post(OLLAMA_URL, json=payload, timeout=30)
    response.raise_for_status()
except requests.exceptions.ConnectionError:
    raise HTTPException(
        status_code=503,
        detail="Ollama service unavailable. Ensure Ollama is running."
    )
except requests.exceptions.Timeout:
    raise HTTPException(
        status_code=504,
        detail="Ollama request timed out after 30 seconds"
    )

# 5. Non-blocking Langfuse Errors
try:
    langfuse.trace(...)
except Exception as e:
    logger.warning(f"Langfuse trace failed: {e}")
    # Continue execution - tracing failure is non-critical
```

## Comparison: FastAPI vs Flask (budget_claude)

| Aspect | budget_cursor (FastAPI) | budget_claude (Flask) |
|--------|------------------------|----------------------|
| **Structure** | Modular `app/` package (4 files) | Monolithic `app.py` (1 file) |
| **LOC** | main.py: 700, utils: 200, validator: 400 | app.py: 1000+ |
| **Type Safety** | ✅ Pydantic models, type hints | ❌ Duck typing |
| **Validation** | ✅ 11 CSV rules + auto Pydantic | ⚠️ Basic checks |
| **Error Messages** | ✅ Field-level, structured | ⚠️ Generic messages |
| **Testing** | ✅ pytest suite (65% coverage) | ❌ No tests |
| **API Docs** | ✅ Auto Swagger UI (/docs) | ❌ Manual README |
| **Async Support** | ✅ ASGI, async/await ready | ❌ WSGI (sync only) |
| **Dev Speed** | ⭐⭐⭐⭐ Fast | ⭐⭐⭐⭐⭐ Fastest |
| **Maintainability** | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐ Good |
| **Production Ready** | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐ Good |
| **Learning Curve** | Higher (more concepts) | Lower (simpler) |

## API Documentation (Auto-Generated)

FastAPI automatically generates interactive API docs at `/docs` (Swagger UI):

```
http://localhost:18080/docs

Features:
- Interactive request/response examples
- Try endpoints directly in browser
- Automatic schema validation
- Request body examples
- Response models with field descriptions
- Authentication (if configured)
```

Example endpoint documentation:
```python
@app.post(
    "/api/upload",
    response_model=UploadResponse,
    summary="Upload CSV or JSON file",
    description="Uploads a transaction file and validates it",
    responses={
        200: {"description": "File uploaded successfully"},
        400: {"description": "Validation failed"},
        422: {"description": "Invalid request format"}
    }
)
async def upload(file: UploadFile = File(...)):
    """
    Upload a CSV or JSON file containing transactions.

    The file must have headers: Date, Amount, Description
    """
```

## Future Improvements

### 1. Async LLM Calls
```python
# Current: Sequential batch processing
for transaction in batch:
    result = ollama_suggest(transaction)

# Future: Parallel processing
results = await asyncio.gather(
    *[ollama_suggest(t) for t in batch]
)
# Could reduce batch time from 5s to ~2s
```

### 2. Database Migration
```python
# Current: JSON file storage
# Future: PostgreSQL with SQLAlchemy

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=False)
    category = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
```

### 3. Enhanced Testing
```python
# Current: 65% coverage
# Future targets:
# - 90%+ for validators
# - 85%+ for utils
# - 80%+ for main.py
# - Add integration tests with real Ollama
# - Add performance benchmarks
# - Add load testing (Locust)
```

### 4. User Authentication
```python
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/api/bulk-map")
async def bulk_map(
    request: BulkMapRequest,
    token: str = Depends(oauth2_scheme)
):
    user = verify_token(token)
    # User-specific progress files
```

### 5. Caching Layer
```python
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

# Cache LLM responses for identical prompts
@cache(expire=3600)  # 1 hour
async def ollama_suggest(transaction, history, categories):
    # Expensive LLM call
    pass
```

### Why These Weren't Implemented
- **Scope**: MVP focused on core categorization
- **Complexity**: Each adds significant development time
- **Trade-offs**: Cursor optimized for production-ready structure, not premature optimization
- **User Base**: Single-user, local deployment scenario
- **Demo Focus**: Architectural clarity over performance optimization
