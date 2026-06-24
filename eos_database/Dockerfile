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

# Copy startup scripts
COPY wait-for-db.sh /app/wait-for-db.sh
COPY start.sh /app/start.sh
RUN chmod +x /app/wait-for-db.sh /app/start.sh

# Expose port (informational; on cloud hosts the app binds to $PORT)
EXPOSE 8000

# Universal entrypoint: waits for a local "db" container if DATABASE_URL
# points at one, otherwise (e.g. Neon) starts immediately and binds to $PORT.
CMD ["/app/start.sh"]
