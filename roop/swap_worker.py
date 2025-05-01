import os
import subprocess
from celery import Celery

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
BROKER_DB = os.getenv("BROKER_DB", "0")
BACKEND_DB = os.getenv("BACKEND_DB", "1")
EXECUTION_THREADS = int(os.getenv("EXECUTION_THREADS", "1"))
IS_FACE_ENHANCER = os.getenv("IS_FACE_ENHANCER", "false") == "true"

# Initialize Celery with Redis broker
celery_app = Celery('tasks', broker=f'redis://{REDIS_HOST}:{REDIS_PORT}/{BROKER_DB}', backend=f'redis://{REDIS_HOST}:{REDIS_PORT}/{BACKEND_DB}')

OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "output")


swap_config = {
    ".png": [],
    ".jpg": [],
    ".jpeg": [],
    ".webp": [],
    ".gif": ["--keep-fps", "--skip-audio", "--keep-frames"]
}

@celery_app.task
def swap(target_image_path: str, swap_image_path: str) -> str:
    """
    Execute the face swap process using run.py
    
    Args:
        target_image_path: Path to the target image
        swap_image_path: Path to the swap image
        
    Returns:
        str: Path to the output image
    """
    # Create output directory if it doesn't exist
    output_dir = f"./{OUTPUT_FOLDER}"
    os.makedirs(output_dir, exist_ok=True)
    # Extract extension from target image path
    _, ext = os.path.splitext(target_image_path)
    # Generate output filename using the task ID
    output_filename = f"{swap.request.id}{ext}"
    output_path = os.path.join(output_dir, output_filename)
    print(f"output_path: {output_path}, {IS_FACE_ENHANCER}")
    # Construct the command
    if IS_FACE_ENHANCER:
        cmd = [
            "python", "run.py",
            "-s", swap_image_path,
            "-t", target_image_path,
            "-o", output_path,
            "--frame-processor", "face_swapper", "face_enhancer",
            "--execution-threads", str(EXECUTION_THREADS)
        ]
    else:
        cmd = [
            "python", "run.py",
            "-s", swap_image_path,
            "-t", target_image_path,
            "-o", output_path,
            "--frame-processor", "face_swapper",
            "--execution-threads", str(EXECUTION_THREADS)
        ]
    
    additional_args = swap_config.get(ext, [])
    cmd.extend(additional_args)
    # Execute the command
    try:
        subprocess.run(cmd, check=True)
        print(f"Face swap process completed successfully for task {swap.request.id}")
        return os.path.join(OUTPUT_FOLDER, output_filename)
    except subprocess.CalledProcessError as e:
        raise Exception(f"Face swap process failed: {str(e)}")