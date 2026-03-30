FROM python:3.14.3-slim-bookworm

# System dependencies for email parsing, image export
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpst-dev \
    pst-utils \
    libmagic1 \
    wkhtmltopdf \
    xvfb \
    fonts-dejavu-core \
    fonts-liberation \
    libesedb-utils \
    && rm -rf /var/lib/apt/lists/*

# Create a wrapper script for wkhtmltoimage with xvfb
RUN printf '#!/bin/bash\nxvfb-run -a wkhtmltoimage "$@"' > /usr/local/bin/wkhtmltoimage-xvfb \
    && chmod +x /usr/local/bin/wkhtmltoimage-xvfb

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libyara-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY app/ ./app/

RUN mkdir -p /app/data /app/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
