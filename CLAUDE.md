# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Roop is a discontinued AI face-swapping application that replaces faces in images and videos using deep learning models. The project includes both a standalone CLI tool and a FastAPI-based web service with Celery task processing. It uses the InsightFace library and ONNX models for face detection and swapping.

## Development Commands

### Standalone CLI Usage
- **Basic face swap**: `python run.py -s <source_image> -t <target_image> -o <output_path>`
- **Video processing**: `python run.py -s <source_image> -t <target_video> -o <output_video>`
- **Multiple faces**: `python run.py -s <source> -t <target> -o <output> --many-faces`
- **With face enhancement**: `python run.py -s <source> -t <target> -o <output> --frame-processor face_swapper face_enhancer`

### API Server Development
- **Run API server**: `make run-server` (equivalent to `ALLOW_ORIGINS=* ALLOW_METHODS=* ALLOW_HEADERS=* fastapi run --workers 4 api-server.py`)
- **Start Redis**: `make run-redis` (starts Redis container on port 6379)
- **Run Celery workers**: `make run-workers` (equivalent to `celery -A roop.swap_worker worker --loglevel=info`)

### Docker Deployment  
- **Full deployment**: `docker-compose up -d` (runs API server, Redis, Celery workers, and cron job)
- **Development with logs**: `docker-compose up` (without detached mode)

## Architecture

### Core Components
- **CLI Interface**: `run.py` - Main entry point for standalone face swapping
- **Web API**: `api-server.py` - FastAPI server with file upload and task management
- **Task Processing**: `roop/swap_worker.py` - Celery tasks for async face swapping
- **Face Processing**: `roop/processors/frame/face_swapper.py` - Core face swapping logic
- **Models**: Uses `inswapper_128.onnx` model stored in `models/` directory

### Directory Structure
- `roop/` - Core face swapping library and processors
- `models/` - ONNX models for face detection and swapping
- `uploads/` - Uploaded images organized by date (YYYY-MM-DD)
- `output/` - Generated face-swapped results
- `requirements.txt` - Main dependencies with CUDA support
- `requirements-cpu.txt` - CPU-only dependencies  
- `requirements-headless.txt` - Headless server dependencies

### API Architecture
- **Upload Endpoint**: `PUT /upload` - Accepts image files, saves with UUID names in date-based folders
- **Swap Endpoint**: `POST /swap` - Creates async face swap task, returns task ID
- **Status Endpoint**: `GET /swap/status/{task_id}` - Polls task completion status
- **Static Files**: `/output` serves generated images

### Task Processing Flow
1. Images uploaded via API and stored in `uploads/YYYY-MM-DD/`
2. Swap request creates Celery task with image paths
3. Worker executes `run.py` subprocess with appropriate arguments
4. Results saved to `output/` with task ID as filename
5. Status endpoint returns completion status and result path

### Environment Configuration
- **Redis**: `REDIS_HOST`, `REDIS_PORT`, `BROKER_DB`, `BACKEND_DB`
- **Processing**: `EXECUTION_THREADS`, `IS_FACE_ENHANCER`
- **Directories**: `UPLOAD_FOLDER`, `OUTPUT_FOLDER`
- **CORS**: `ALLOW_ORIGINS`, `ALLOW_METHODS`, `ALLOW_HEADERS`, `ALLOW_CREDENTIALS`

### Key Dependencies
- **Core**: OpenCV, InsightFace, ONNX Runtime, TensorFlow
- **Web**: FastAPI, Celery, Redis
- **ML**: PyTorch, GFPGAN (face enhancement), OpenNSFW2 (content filtering)
- **UI**: CustomTkinter (for GUI mode)

### Model Requirements
- Automatically downloads `inswapper_128.onnx` model on first run
- Models stored in `models/` directory
- CUDA support available with GPU-optimized requirements

### File Processing
- Supports images: JPG, PNG, WEBP
- Supports videos: MP4 and other common formats  
- GIF files processed with special flags: `--keep-fps --skip-audio --keep-frames`
- Automatic cleanup via cron job removes old uploads and outputs

## Important Notes

- **Project Status**: This project is discontinued and no longer receives updates
- **Security**: Includes NSFW content filtering via OpenNSFW2
- **Performance**: Single-threaded for CUDA optimization, configurable execution threads
- **Memory**: Configurable memory limits and execution providers (CPU/GPU)
- **Ethics**: Designed for legitimate use cases like character animation, includes safety measures