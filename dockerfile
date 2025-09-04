# Use Python 3.11 as base image (matches pyproject.toml requirement)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for face processing and uv
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency files first to leverage Docker cache
COPY pyproject.toml uv.lock* ./

# Install Python dependencies using uv
RUN uv sync --frozen

# Copy the rest of the application
COPY . .

# Setup model directories and move models if they exist
RUN mkdir -p /root/.insightface/models && \
    mkdir -p /root/.opennsfw2/weights && \
    if [ -d "models/buffalo_l" ]; then mv models/buffalo_l /root/.insightface/models/; fi && \
    if [ -f "models/open_nsfw_weights.h5" ]; then mv models/open_nsfw_weights.h5 /root/.opennsfw2/weights/; fi

# Set default entry point to run redis queue consumer
CMD ["uv", "run", "python", "redis_queue_consumer.py"]
