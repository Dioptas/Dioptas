FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including git for Peritheos)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    git \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY client/ ./client/

# Copy initialization script
COPY wait-for-db.sh /app/wait-for-db.sh
RUN chmod +x /app/wait-for-db.sh

# Expose port
EXPOSE 8000

# Run application with wait-for-db script
CMD ["/app/wait-for-db.sh"]
