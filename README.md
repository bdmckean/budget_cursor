# Budget Cursor

A budget planning application for analyzing and categorizing spending from CSV files. Built with Python (FastAPI) backend and React frontend, containerized with Docker.

## Features

- Upload CSV files for budget analysis
- Map each row to common budget categories
- Save progress automatically - resume mapping from where you left off
- Visual progress tracking
- Simple, intuitive one-page interface

## Prerequisites

Before you begin, ensure you have the following installed on your local machine:

- **Docker** (version 20.10 or later)
  - Download from: https://www.docker.com/products/docker-desktop/
  - Verify installation: `docker --version`
  
- **Docker Compose** (usually included with Docker Desktop)
  - Verify installation: `docker-compose --version`

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd budget_cursor
```

### 2. Start the Application with Docker

Build and start all services (backend and frontend):

```bash
docker-compose up --build
```

This command will:
- Build the Docker images for both backend and frontend
- Start the backend API server on port 18080
- Start the React frontend on port 13030
- Mount volumes for live code reloading during development

### 3. Access the Application

Once the containers are running, you can access:

- **Frontend Application**: http://localhost:13030
- **Backend API**: http://localhost:18080
- **API Documentation**: http://localhost:18080/docs (Swagger UI)

### 4. Stop the Application

To stop all running containers:

```bash
docker-compose down
```

To stop and remove volumes (clears data):

```bash
docker-compose down -v
```

## Development Workflow

### Running in Detached Mode

To run containers in the background:

```bash
docker-compose up -d
```

View logs:

```bash
docker-compose logs -f
```

View logs for a specific service:

```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Rebuilding After Code Changes

If you make changes to dependencies (e.g., update `pyproject.toml` or `package.json`):

```bash
docker-compose up --build
```

For code changes, the volumes are mounted so changes should hot-reload automatically.

### Local Development (Without Docker)

#### Backend (Python with Poetry)

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

The backend will run on http://localhost:8000

#### Frontend (React)

```bash
cd frontend
npm install
npm start
```

The frontend will run on http://localhost:3000

**Note**: When running locally, make sure to set the `REACT_APP_API_URL` environment variable or update the API_URL in `App.jsx` to point to your local backend.

## Project Structure

```
budget_cursor/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI application
│   │   ├── models.py
│   │   └── utils.py
│   ├── pyproject.toml        # Poetry dependencies
│   ├── poetry.lock           # Locked dependency versions
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main React component
│   │   ├── index.jsx
│   │   └── index.css
│   ├── public/
│   │   └── index.html
│   ├── package.json          # npm dependencies
│   ├── package-lock.json     # Locked dependency versions
│   ├── Dockerfile
│   └── .dockerignore
├── progress/
│   └── mapping_progress.json # Saved mapping progress (auto-generated)
├── docker-compose.yml        # Docker orchestration
├── .gitignore
└── README.md
```

## Usage

1. **Upload CSV File**: Click "Upload CSV File" and select your budget/spending CSV file
2. **Map Rows**: For each row, select the appropriate budget category
3. **Progress Saved**: Your progress is automatically saved to `progress/mapping_progress.json`
4. **Resume Later**: If you close the app, your progress is saved and you can resume from where you left off

## Budget Categories

The application includes these default categories:
- Food & Dining
- Transportation
- Shopping
- Bills & Utilities
- Entertainment
- Travel
- Healthcare
- Education
- Personal Care
- Gifts & Donations
- Income
- Other

## Troubleshooting

### Port Already in Use

If you get an error that ports 13030 or 18080 are already in use:

1. Stop the conflicting service, or
2. Update ports in `docker-compose.yml`:
   ```yaml
   ports:
     - "13031:3000"  # Change frontend port
     - "18081:8000"  # Change backend port
   ```

### Docker Build Fails

If the build fails, try:

```bash
# Clean up Docker cache
docker system prune -a

# Rebuild without cache
docker-compose build --no-cache
docker-compose up
```

### Backend Not Connecting

Ensure the backend is running and check logs:

```bash
docker-compose logs backend
```

### Frontend Not Loading

Check if the frontend container is running:

```bash
docker-compose ps
docker-compose logs frontend
```

### Poetry Lock File Missing

If you get errors about `poetry.lock`, generate it:

```bash
cd backend
poetry lock
```

### npm Install Issues

If frontend dependencies fail to install:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Technology Stack

- **Backend**: Python 3.11, FastAPI, Poetry
- **Frontend**: React 18, Create React App
- **Containerization**: Docker, Docker Compose

## License

See LICENSE file for details.
