FROM python:3.11-slim

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source directory
COPY app/ ./app/

# Port exposure
EXPOSE 8000

# Set environment defaults inside container
ENV PYTHONUNBUFFERED=1
ENV DATABASE_FILE=/app/data/stock_tracker.db
ENV REPORTS_DIR=/app/reports

# Run FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
