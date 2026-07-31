FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (Hugging Face preference)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

WORKDIR /app

# Copy files and ensure the user owns them
COPY --chown=user . .

RUN pip install --no-cache-dir -r requirements.txt

# This ensures Telegram can write to the session file
RUN chmod 664 cloner_session.session || true

CMD ["python", "-u", "main.py"]