FROM python:3.11-slim

# Install system dependencies including curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and project directories
COPY . .

# Expose API port
EXPOSE 8080

# Run uvicorn server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
