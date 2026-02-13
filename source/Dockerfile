FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

########################################################################################################################
# Install build + runtime deps
########################################################################################################################

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    gcc \
    libc6-dev \
 && rm -rf /var/lib/apt/lists/*

########################################################################################################################
# Create non-root user
########################################################################################################################

RUN useradd -m -s /bin/bash appuser

########################################################################################################################
# build echo-flag
########################################################################################################################
COPY echo-flag-src/echo-real-flag.c /tmp/echo-flag.c

RUN gcc -O2 -s -o /tmp/echo-flag /tmp/echo-flag.c \
 && rm -f /tmp/echo-flag.c \
 && mv /tmp/echo-flag /usr/local/bin/echo-flag \
 && chown appuser:appuser /usr/local/bin/echo-flag \
 && chmod 100 /usr/local/bin/echo-flag

########################################################################################################################
# Python app setup
########################################################################################################################
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates
COPY data ./data
COPY static ./static
RUN mkdir "./tmp"

########################################################################################################################
# Ensure app directory is owned by appuser
########################################################################################################################
RUN chown -R appuser:appuser /app

########################################################################################################################
# Switch to non-root user
########################################################################################################################

USER appuser

EXPOSE 2026

CMD ["gunicorn", "-b", "0.0.0.0:2026", "--workers", "1", "--threads", "1", "--worker-class", "sync", "app:app"]
