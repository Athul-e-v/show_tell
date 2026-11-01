# Use Python 3.12 as the base image
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Copy dependency list
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy FastAPI application code
COPY app/ ./app/

# Create non-root user
RUN useradd --create-home appuser

# Run application as non-root user
USER appuser

# Document service port
EXPOSE 8001

# Start FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
