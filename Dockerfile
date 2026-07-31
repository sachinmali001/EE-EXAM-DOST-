
FROM python:3.10-slim

# Install system dependencies if needed for ffmpeg/opencv
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

WORKDIR /app
COPY --chown=user . .

RUN pip install --no-cache-dir -r requirements.txt

RUN chmod 664 cloner_session.session || true

EXPOSE 8080

CMD ["python", "-u", "main.py"]
