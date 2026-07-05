FROM python:3.11.9-slim-bookworm

# ffmpeg (and ffprobe) are required by yt-dlp/discord voice; install via apt and
# clean the package lists to keep the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Run the bot directly. The previous entrypoint used `watchmedo auto-restart`, a
# development file-watcher; process supervision belongs to the orchestrator
# (compose `restart: unless-stopped` / systemd), not a dev reloader.
ENTRYPOINT ["python", "bot.py"]
