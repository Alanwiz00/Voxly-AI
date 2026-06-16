FROM python:3.12-slim

WORKDIR /app

# System fonts for Pillow text rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

RUN mkdir -p /data /data/img_tmp /data/img_cache

CMD ["python", "agent.py"]
