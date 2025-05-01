# Use Python 3.10 as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

RUN apt-get update && apt-get install build-essential libssl-dev libffi-dev python3-lib2to3 python3-distutils python3-dev python3-tk ffmpeg libsm6 libxext6 -y
RUN pip install --upgrade pip
# Copy requirements first to leverage Docker cache
COPY requirements-cpu.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --no-deps -r requirements-cpu.txt

# fix torchvision import error
# https://github.com/AUTOMATIC1111/stable-diffusion-webui/issues/13985#issuecomment-1813885266
RUN sed -i 's/from torchvision.transforms.functional_tensor import rgb_to_grayscale/from torchvision.transforms.functional import rgb_to_grayscale/' /usr/local/lib/python3.10/site-packages/basicsr/data/degradations.py

# Copy the rest of the application
COPY . .

RUN mkdir -p /root/.insightface/models && mv models/buffalo_l /root/.insightface/models/ && mkdir -p /root/.opennsfw2/weights && mv models/open_nsfw_weights.h5 /root/.opennsfw2/weights/

# Expose ports for FastAPI and Redis
EXPOSE 8000

ENTRYPOINT ["/bin/bash", "-c"]
