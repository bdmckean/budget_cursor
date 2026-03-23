# Product Requirements Document (PRD)
## Budget Cursor — AI-Powered Budget Planning Application

**Version:** 1.0  
**Last Updated:** January 2025  
**Status:** Reflects features developed to date

---

## 1. Product Overview

### 1.1 Purpose
Budget Cursor is a budget planning application that helps users analyze and categorize spending from CSV transaction exports. It uses AI (Ollama with llama3.1:8b) to suggest categories and provides tools to map transactions, review mappings, and view spending summaries across multiple files and time periods.

### 1.2 Target Users
- Individuals who export transaction data from banks/credit cards (e.g., Chase CSV exports)
- Users who want to categorize spending for budget analysis
- Single-user, local deployment scenario

### 1.3 Key Value Propositions
- **AI-assisted categorization** — Reduces manual work with intelligent suggestions
- **Multi-file support** — Process multiple CSV files; mappings persist per file
- **Progress persistence** — Resume mapping from where you left off
- **Spending insights** — Monthly and yearly totals, averages, and category breakdowns
- **Payment/transfer handling** — Correctly separates payments from spending for accurate analysis

---

## 2. Core Features (As Developed)

### 2.1 File Upload & Management
| Requirement | Description | Status |
|-------------|-------------|--------|
| CSV upload | Upload CSV files with transaction data | ✅ |
| Required headers | Date, Amount, Description (flexible column names) | ✅ |
| Validation | CSV validation with detailed error feedback | ✅ |
| Multi-file support | Support multiple uploaded files; mappings stored per filename | ✅ |
| Upload new file | Option to upload a new file without losing existing mappings | ✅ |
| Files page | View all files with mapped/total counts and completion status | ✅ |
| Load file | Switch to work on a file from the Files page (Continue button) | ✅ |

### 2.2 Mapping View
| Requirement | Description | Status |
|-------------|-------------|--------|
| Row-by-row mapping | Navigate through rows and assign categories one at a time | ✅ |
| Category selection | Click category buttons to assign; categories loaded from config | ✅ |
| AI suggestion | "Suggest" button gets LLM recommendation for current row | ✅ |
| Accept suggestion | One-click to apply suggested category | ✅ |
| Previous/Next navigation | Navigate between rows | ✅ |
| Current row display | Show transaction details (date, amount, description) | ✅ |
| Progress bar | Header shows "X / Y rows mapped" with visual progress | ✅ |
| Add category | Add new categories with spelling/capitalization correction | ✅ |
| Reset mappings | Reset all mappings for current file (with confirmation) | ✅ |

### 2.3 Auto-Map All
| Requirement | Description | Status |
|-------------|-------------|--------|
| Bulk AI categorization | Automatically map all unmapped rows using AI | ✅ |
| No overall timeout | Request runs as long as needed; no frontend abort | ✅ |
| Model-only timeout | 30-second timeout per Ollama request | ✅ |
| Progress visibility | Poll every second; progress bar and button show "X/Y mapped" | ✅ |
| Exact match first | Check previous mappings for exact match before calling LLM | ✅ |
| Save after each row | Progress persisted after each mapping for live updates | ✅ |

### 2.4 Review View
| Requirement | Description | Status |
|-------------|-------------|--------|
| Review table | Table of all mapped rows with details, amount, category | ✅ |
| Edit from review | "Edit" button navigates to mapping view with that row selected | ✅ |
| Auto-map from review | "Auto-map All Remaining" available on review page | ✅ |
| Mapped count | Shows "Total mapped: X / Y rows" | ✅ |

### 2.5 Spending Summary View
| Requirement | Description | Status |
|-------------|-------------|--------|
| Monthly breakdown | Spending per category per month (table) | ✅ |
| Spending vs payments | Separate "Spending" (excludes Payment/Transfer) and "Payments & Transfers" sections | ✅ |
| Category totals | Total column per category | ✅ |
| Month totals | Total row per month | ✅ |
| Grand total | Overall total across all months | ✅ |
| Horizontal scroll | Scroll to see all months when table is wide | ✅ |
| Per-year totals | Year total and year monthly average per category | ✅ |
| Year summary table | "Per Year Totals & Monthly Averages" section | ✅ |
| All-years total/avg | "All Total" and "All Avg/mo" columns | ✅ |
| Payments net | "Net (should cancel out)" row for payments section | ✅ |

### 2.6 Categories
| Requirement | Description | Status |
|-------------|-------------|--------|
| Configurable categories | Categories loaded from `categories.json` | ✅ |
| Default categories | Auto, Books, Bills & Utilities, Business, Clothing, Coffee, Education, Entertainment, Fees, Donations, Gifts, Groceries, Healthcare, Household, Income, Insurance_rebate, Interest Income, Investments, Other, Payment in, Payment out, Personal Care, Pet, Restaurants, Shopping, Subscriptions, Transfer in, Transfer out, Transportation, Travel, Unknown Income | ✅ |
| Add category | Add new categories with autocorrect (spelling, capitalization) | ✅ |
| Payment/Transfer special | Payment in/out and Transfer in/out excluded from main spending; shown in separate summary | ✅ |

### 2.7 Smart Categorization Rules
| Requirement | Description | Status |
|-------------|-------------|--------|
| Exact match from history | Match identical transactions to previous mappings | ✅ |
| Payment descriptions | "Payment Thank You" or Type=Payment → auto-map to Payment in | ✅ |
| LLM fallback | Use Ollama when no match found | ✅ |
| Category validation | Validate LLM response against allowed categories | ✅ |

### 2.8 Data Persistence
| Requirement | Description | Status |
|-------------|-------------|--------|
| Progress file | `progress/mapping_progress.json` for current session | ✅ |
| Mappings file | `backend/mappings/mappings.json` keyed by filename | ✅ |
| Merge on upload | When re-uploading, merge with existing mappings for that file | ✅ |
| Save on map | Progress and mappings saved after each manual or auto mapping | ✅ |

---

## 3. User Flows

### 3.1 First-Time Use
1. User starts app (Docker or local)
2. Clicks "Choose CSV File" or "Upload CSV File"
3. Selects bank/credit card CSV export
4. File validated; rows loaded into mapping view
5. User maps rows manually or uses "Suggest" / "Auto-map All Remaining"
6. Progress auto-saves; user can close and resume later

### 3.2 Review & Correct
1. User navigates to "Review Mappings"
2. Sees table of all mapped transactions
3. Clicks "Edit" on a row to change category
4. Redirected to mapping view with that row; selects new category
5. Can run "Auto-map All Remaining" for any unmapped rows

### 3.3 View Spending
1. User navigates to "Spending Summary"
2. Sees monthly table by category (spending excludes Payment/Transfer)
3. Sees Payments & Transfers section (should net to zero)
4. Scrolls horizontally to see all months
5. Views per-year totals and monthly averages

### 3.4 Multi-File Workflow
1. User uploads File A, maps some rows
2. User uploads File B (new file)
3. Mappings for File A persist in `mappings.json`
4. User maps File B
5. Spending summary aggregates across all files

### 3.5 Files Page & Switching Files
1. User navigates to "Files"
2. Sees table of all uploaded files with mapped/total counts
3. Sees which files are complete (green) vs incomplete (yellow badge)
4. Clicks "Continue" on a file to switch to working on it
5. File loads from saved mappings into progress; user is taken to Mapping view
6. User can now map remaining rows or review that file

---

## 4. Behavior Specifications

### 4.1 Files Page Behavior
- **Data source:** Aggregates from `mappings.json` plus current `progress` (progress overrides for the active file if newer)
- **Display:** Table with columns: File name, Mapped count, Total rows, Status, Continue button
- **Status badges:** "Complete" (green) when mapped_count == total_rows; "X remaining" (yellow) otherwise
- **Summary line:** "X of Y file(s) completely mapped"
- **Empty state:** "No files uploaded yet. Upload a CSV file to get started."
- **Continue button:** Loads file from mappings into progress, navigates to Mapping view

### 4.2 Load File Behavior
- **Endpoint:** POST `/load-file` with `{ "filename": "..." }`
- **Action:** Loads rows from `mappings.json` for that filename into `progress/mapping_progress.json`
- **Result:** That file becomes the current working file; user can map, review, or run auto-map
- **Error:** 404 if filename not found in mappings

### 4.3 Avoid Mapping Same Entries Twice
- **On re-upload:** When a file is uploaded again, existing mappings for that file are loaded. Rows are matched by content (fingerprint or `rows_match`). Matching rows restore their previous category; no re-mapping needed.
- **On auto-map:** `find_matching_category()` checks all saved mappings across files. Identical transactions (same date, amount, description) reuse the existing category before calling the LLM.
- **Storage:** Mappings keyed by filename in `mappings.json`; progress holds current file. Both updated on each map.

### 4.4 Progress vs Mappings
- **Progress:** Current session; one file at a time; used for Mapping and Review views
- **Mappings:** Persistent; all files; used for Files page, Spending Summary, and matching on re-upload/auto-map
- **Sync:** Each map/auto-map saves to both progress and mappings for the current file

---

## 5. API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Root / API info |
| GET | `/health` | Health check |
| POST | `/upload` | Upload CSV file |
| GET | `/progress` | Get current mapping progress |
| POST | `/map` | Map a row to a category |
| GET | `/categories` | Get category list |
| POST | `/categories/add` | Add new category (with optional confirm) |
| POST | `/reset-mappings` | Reset mappings for a file |
| POST | `/suggest-category` | Get AI suggestion for a row |
| POST | `/auto-map-all` | Auto-map all unmapped rows |
| GET | `/review` | Get all mapped rows for review |
| GET | `/files` | Get list of files with mapping status (mapped/total, complete) |
| POST | `/load-file` | Load a file from saved mappings into progress |
| GET | `/spending-summary` | Get spending totals by category and month |

---

## 6. Data Model

### 6.1 Progress (Current Session)
```json
[
  {
    "row_index": 0,
    "original_data": { "Transaction Date": "...", "Amount": "...", "Description": "..." },
    "category": "Groceries",
    "mapped": true,
    "source_file": "filename.csv"
  }
]
```

### 6.2 Mappings (Persistent, Per File)
```json
{
  "filename1.csv": [ /* array of row objects same as progress */ ],
  "filename2.csv": [ /* ... */ ]
}
```

### 6.3 Files Status Response
```json
{
  "files": [
    {
      "filename": "Chase8592_Activity20250101_20251231.CSV",
      "total_rows": 850,
      "mapped_count": 850,
      "unmapped_count": 0,
      "is_complete": true
    }
  ]
}
```

### 6.4 Spending Summary Response
```json
{
  "summary": {
    "categories": {
      "Groceries": { "2025-01": 150.00, "2025-02": 200.00 },
      "Restaurants": { "2025-01": 80.00 }
    },
    "payments": {
      "Payment in": { "2025-01": 1000.00 }, "Payment out": { "2025-02": -1000.00 }
    }
  },
  "months": ["2025-01", "2025-02", ...]
}
```

---

## 7. Technical Requirements

### 7.1 Stack
- **Backend:** Python 3.11, FastAPI, Poetry
- **Frontend:** React 18, Create React App
- **AI:** Ollama with llama3.1:8b (local)
- **Containerization:** Docker, Docker Compose

### 7.2 Ports
- Frontend: 13030
- Backend: 18080
- API docs: http://localhost:18080/docs

### 7.3 Prerequisites
- Docker & Docker Compose
- Ollama running with `llama3.1:8b` model
- Optional: Langfuse for LLM tracing

### 7.4 Storage
- `progress/mapping_progress.json` — current file progress
- `backend/mappings/mappings.json` — per-file mappings
- `backend/categories.json` — category list

---

## 8. Non-Functional Requirements

| Requirement | Implementation |
|-------------|----------------|
| No overall timeout on auto-map | Removed 5-min AbortController; only 30s per Ollama call |
| Progress visibility during auto-map | 1-second polling; button shows "X/Y mapped" |
| Horizontal scroll on summary | `summary-table-container` with `overflow-x: auto` |
| Payment/transfer accuracy | Special rules + PAYMENT_CATEGORIES (Payment in/out, Transfer in/out) exclusion |

---

## 9. Out of Scope (Current Version)

- User authentication
- Database (uses JSON files)
- Async/parallel LLM calls
- Mobile-specific UI
- Export to PDF/Excel
- Budget goals or alerts
- Multi-tenant / cloud deployment

---

## 10. References

- [README.md](./README.md) — Setup and usage
- [ARCHITECTURE.md](./ARCHITECTURE.md) — Technical architecture
- [backend/README_TESTING.md](./backend/README_TESTING.md) — Testing
