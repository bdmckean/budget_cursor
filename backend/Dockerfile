FROM python:3.11-slim

# Install Poetry
RUN pip install poetry==1.7.1

# Configure Poetry: Don't create virtual env, install dependencies to system
RUN poetry config virtualenvs.create false

WORKDIR /app

# Copy Poetry files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY app/ ./app/
COPY categories.json ./

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

