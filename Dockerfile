FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and drop root: the app never needs it.
COPY . .
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

# Streamlit runs every session on its own thread and glibc gives busy threads
# their own malloc arena, keeping what each frees. Two arenas: measured on
# 2026-10-08 with 4 concurrent sessions, peak 1440 -> 1286 MB, resting 946 ->
# 766 MB. It must be set before Python starts; mallopt() from app.py was tried
# and measured to do nothing (the server's threads fix the limit first).
ENV MALLOC_ARENA_MAX=2

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
