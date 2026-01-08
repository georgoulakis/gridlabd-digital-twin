FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY appliance_pattern_generator.py .

# Set environment variables
ENV DATA_DIR=/data
ENV OUTPUT_DIR=/data/output
ENV RESULTS_DIR=/data/results
ENV SCENARIOS_DIR=/data/scenarios
ENV PATTERNS_BASE_DIR=/data/patterns
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Run uvicorn directly
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]