FROM python:3.11-slim

WORKDIR /app

# ffmpeg is required for Reels rendering; keep the image otherwise slim.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend code + bundled assets (fonts; music is synthesized at first boot).
COPY app ./app
COPY assets ./assets

EXPOSE 8000

# Cap glibc malloc arenas — this app is thread-heavy (render jobs, schedulers) and
# the default (8 × CPUs) fragments RSS badly on small instances. 2 keeps memory tight.
ENV MALLOC_ARENA_MAX=2 PYTHONUNBUFFERED=1

# Render injects $PORT; default to 8000 locally. --proxy-headers so request URLs
# resolve as https behind Render's TLS proxy (used for the Instagram redirect URI).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
