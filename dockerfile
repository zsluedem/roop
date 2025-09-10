# Use Ubuntu 24.04 as base image
FROM ubuntu:24.04

# Set working directory
WORKDIR /app

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system dependencies including Python 3.11
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    build-essential \
    libssl-dev \
    libffi-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    libglib2.0-0 \
    libxrender1 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python3.11
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

# Install uv package manager
RUN python3.11 -m pip install --no-cache-dir uv

# Copy dependency files first to leverage Docker cache
COPY pyproject.toml uv.lock* ./

# Install Python dependencies using uv with Python 3.11
RUN uv sync --frozen --python python3.11

# Copy the rest of the application
COPY . .

# Setup model directories and move models if they exist
RUN mkdir -p /root/.insightface/models && \
    mkdir -p /root/.opennsfw2/weights && \
    if [ -d "models/buffalo_l" ]; then mv models/buffalo_l /root/.insightface/models/; fi && \
    if [ -f "models/open_nsfw_weights.h5" ]; then mv models/open_nsfw_weights.h5 /root/.opennsfw2/weights/; fi

# Set default entry point to run redis queue consumer
CMD ["uv", "run", "python", "redis_queue_consumer.py"]
