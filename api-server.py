import os
from datetime import datetime
from typing import Union
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from celery import Celery
from roop.swap_worker import swap, celery_app
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "output")

app.mount("/output", StaticFiles(directory=OUTPUT_FOLDER), name="static")

allow_origins = [
    os.getenv("ALLOW_ORIGINS", None) 
] if os.getenv("ALLOW_ORIGINS") else []

allow_methods = [
    os.getenv("ALLOW_METHODS", None) 
] if os.getenv("ALLOW_METHODS") else []

allow_methods = [
    os.getenv("ALLOW_HEADERS", None) 
] if os.getenv("ALLOW_HEADERS") else []

allow_credetials = True if os.getenv("ALLOW_CREDENTIALS") =="True" else False

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,  
    allow_credentials=allow_credetials,
    allow_methods=allow_methods,  
    allow_headers=allow_methods, 
)


class SwapRequest(BaseModel):
    targetImage: str
    swapImage: str

@app.put("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload an image file and save it to the uploads directory in a date-based subfolder.
    
    Args:
        file (UploadFile): The image file to upload
        
    Returns:
        dict: Status message and filename
        
    Raises:
        HTTPException: If file is not an image or upload fails
    """
    # Validate file is an image
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail="File must be an image"
        )

    try:
        # Get current date for subfolder
        current_date = datetime.now().strftime("%Y-%m-%d")
        subfolder_path = os.path.join(UPLOAD_FOLDER, current_date)
        
        # Create uploads directory and date subfolder if they don't exist
        os.makedirs(subfolder_path, exist_ok=True)
        
        # Generate unique filename using uuid
        file_ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{file_ext}"
        filepath = os.path.join(subfolder_path, filename)

        # Save uploaded file
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)

        return {
            "message": "File uploaded successfully",
            "filename": filename,
            "path": os.path.join(current_date, filename)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        )

@app.post("/swap")
async def create_swap_task(request: SwapRequest):
    """
    Create a face swap task with the given target and swap images.
    
    Args:
        request (SwapRequest): JSON containing targetImage and swapImage paths
        
    Returns:
        dict: Task ID for tracking the swap operation
        
    Raises:
        HTTPException: If the image paths are invalid
    """
    try:
        # Validate that both images exist
        target_path = os.path.join(UPLOAD_FOLDER, request.targetImage)
        swap_path = os.path.join(UPLOAD_FOLDER, request.swapImage)
        
        if not os.path.exists(target_path) or not os.path.exists(swap_path):
            raise HTTPException(
                status_code=404,
                detail="One or both image paths not found"
            )
        
        # Start the Celery task
        task = swap.delay(target_path, swap_path)
        
        return {
            "task_id": task.id,
            "status": "processing"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating swap task: {str(e)}"
        )

@app.get("/swap/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status of a face swap task.
    
    Args:
        task_id (str): The task ID returned from the swap endpoint
        
    Returns:
        dict: Task status and result (if completed)
        
    Raises:
        HTTPException: If the task ID is invalid
    """
    try:
        task_result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": task_result.status,
        }
        
        # Add additional info based on task state
        if task_result.status == 'SUCCESS':
            response["result"] = task_result.get()
        elif task_result.status == 'FAILURE':
            response["error"] = str(task_result.result)
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking task status: {str(e)}"
        )
