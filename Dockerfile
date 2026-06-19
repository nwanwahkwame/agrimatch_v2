FROM python:3.11-slim

# Install system dependencies required for psycopg2 compilation, GDAL, and GEOS
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Railway standard port mapping
ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
