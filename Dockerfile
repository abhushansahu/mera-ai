FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt

# Copy application code
COPY app/ ./app/
COPY pyproject.toml .

# Create directory for ChromaDB persistence
RUN mkdir -p /app/data/chroma_db

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "-m", "app.main"]
