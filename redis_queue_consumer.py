#!/usr/bin/env python3
"""
Redis Queue Consumer for Face Swap Tasks

Worker that consumes face swap tasks from Upstash Redis priority queue, downloads images,
executes face swapping using the roop CLI, and uploads results to Cloudflare R2.

Required environment variables:
- UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN: Redis connection
- R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET: Cloudflare R2 config
- R2_PUBLIC_URL: Base URL for public R2 access (optional)
- DOWNLOAD_DIR: Directory for temporary image downloads (default: ./downloads)
- OUTPUT_DIR: Directory for face swap outputs (default: ./output)
- POLL_INTERVAL: Queue polling interval in seconds (default: 1.0)
"""

import json
import os
import signal
import sys
import time
import subprocess
import tempfile
import shutil
import threading
from pathlib import Path
from typing import Dict, Optional, Any
from urllib.parse import urlparse
from uuid import uuid4
from queue import Queue

import boto3
import requests
from dotenv import load_dotenv
from upstash_redis import Redis

# Load environment variables
load_dotenv()

class RedisQueueConsumer:
    def __init__(self):
        # Redis configuration
        self.redis_url = os.getenv('UPSTASH_REDIS_REST_URL')
        self.redis_token = os.getenv('UPSTASH_REDIS_REST_TOKEN')
        
        if not self.redis_url or not self.redis_token:
            raise ValueError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN must be set")
            
        # Queue configuration
        self.queue_name = 'priority_queue'
        self.data_key = f'{self.queue_name}:data'
        self.notification_channel = 'task_notifications'
        
        # API configuration for task status updates
        self.api_base_url = os.getenv('API_BASE_URL', 'https://aifacesswap.com')
        self.worker_api_key = os.getenv('WORKER_API_KEY')
        
        if not self.worker_api_key:
            print("Warning: WORKER_API_KEY not set. Task status updates will fail.")
        else:
            print("API key configured for task status updates")
        
        # Image processing configuration
        self.download_dir = os.getenv('DOWNLOAD_DIR', './downloads')
        self.output_dir = os.getenv('OUTPUT_DIR', './output')
        
        # Cloudflare R2 configuration
        self.r2_endpoint = os.getenv('R2_ENDPOINT')
        self.r2_access_key = os.getenv('R2_ACCESS_KEY')
        self.r2_secret_key = os.getenv('R2_SECRET_KEY')
        self.r2_bucket = os.getenv('R2_BUCKET')
        self.r2_public_url = os.getenv('R2_PUBLIC_URL')
        
        if not all([self.r2_endpoint, self.r2_access_key, self.r2_secret_key, self.r2_bucket]):
            raise ValueError("R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, and R2_BUCKET must be set")
        
        # Create directories if they don't exist
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize Redis connection
        self.redis = Redis(url=self.redis_url, token=self.redis_token)
        
        # Initialize R2 client
        self.r2_client = boto3.client(
            's3',
            endpoint_url=self.r2_endpoint,
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key,
            region_name='auto'
        )
        
        # Shutdown flag
        self.shutdown_requested = False
        
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        if self.shutdown_requested:
            # Second Ctrl+C - force exit
            print(f"\n🛑 Force exit requested. Terminating immediately...")
            sys.exit(1)
        
        print(f"\n⏹️ Shutdown signal received ({signum}). Stopping worker...")
        print("   (Press Ctrl+C again to force exit)")
        self.shutdown_requested = True
        
    def download_image(self, image_path: str, filename: str) -> str:
        """
        Download image from R2 using boto3 client.
        image_path should be like '/uploads/xxxxx' or 'uploads/xxxxx'
        Returns local file path.
        """
        try:
            # Remove leading slash if present
            r2_key = image_path[1:] if image_path.startswith('/') else image_path
            
            # Download from R2 using boto3
            local_path = Path(self.download_dir) / filename
            
            with open(local_path, 'wb') as f:
                self.r2_client.download_fileobj(self.r2_bucket, r2_key, f)
                
            print(f"Downloaded from R2: {r2_key} -> {local_path}")
            return str(local_path)
            
        except Exception as e:
            raise Exception(f"Failed to download image from R2 key '{r2_key}': {e}")
            
    def run_face_swap(self, source_path: str, target_path: str, output_path: str) -> None:
        """
        Execute face swap command using subprocess.
        """
        try:
            cmd = [
                'python', 'run.py',
                '-s', source_path,
                '-t', target_path, 
                '-o', output_path,
                '--frame-processor', 'face_swapper'
            ]
            
            print(f"Executing: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=os.path.dirname(os.path.abspath(__file__))  # Run from roop directory
            )
            
            if result.returncode != 0:
                raise Exception(f"Face swap failed with exit code {result.returncode}. stderr: {result.stderr}")
                
            print(f"Face swap completed successfully: {output_path}")
            
        except subprocess.TimeoutExpired:
            raise Exception("Face swap command timed out after 5 minutes")
        except Exception as e:
            raise Exception(f"Failed to execute face swap: {e}")
            
    def upload_to_r2(self, local_path: str, task_id: str, user_id: str = None) -> str:
        """
        Upload file to Cloudflare R2 and return public URL.
        """
        try:
            # Generate R2 key with new structure: /uploads/{user_id}/outputs/{task_id}.img
            if user_id:
                r2_key = f"uploads/{user_id}/outputs/{task_id}.img"
            else:
                # Fallback for anonymous users
                r2_key = f"uploads/anonymous/outputs/{task_id}.img"
            
            # Upload to R2
            with open(local_path, 'rb') as f:
                self.r2_client.upload_fileobj(
                    f, 
                    self.r2_bucket, 
                    r2_key,
                    ExtraArgs={'ContentType': 'image/jpeg'}
                )
            
            # Generate public URL
            if self.r2_public_url:
                public_url = f"{self.r2_public_url.rstrip('/')}/{r2_key}"
            else:
                # Fallback to pre-signed URL if no public URL configured
                public_url = self.r2_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.r2_bucket, 'Key': r2_key},
                    ExpiresIn=86400  # 24 hours
                )
            
            print(f"Uploaded to R2: {r2_key} -> {public_url}")
            return public_url
            
        except Exception as e:
            raise Exception(f"Failed to upload to R2: {e}")
    
    def update_task_status(self, task_id: str, status: str, result_image_path: str = None) -> bool:
        """
        Update task status in D1 database via API endpoint.
        """
        if not self.worker_api_key:
            print("Warning: No API key configured, skipping status update")
            return False
            
        try:
            url = f"{self.api_base_url}/api/tasks/{task_id}/status"
            headers = {
                "Authorization": f"Bearer {self.worker_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {"status": status}
            if result_image_path:
                data["resultImagePath"] = result_image_path
            
            print(f"🔄 Updating task status: {task_id} -> {status}")
            print(f"   URL: {url}")
            print(f"   Data: {data}")
            
            response = requests.patch(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Task {task_id} status updated to {status}")
                return True
            else:
                print(f"❌ Failed to update task status: {response.status_code} - {response.text}")
                print(f"   Request URL: {url}")
                print(f"   Request data: {data}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating task status: {e}")
            return False
        
    def run_pubsub_consumer(self):
        """
        Main PUBSUB consumer - subscribes to notifications and processes tasks.
        This is the ONLY way the consumer works - no polling, no fallbacks.
        """
        print(f"🔔 Starting PUBSUB consumer for channel: {self.notification_channel}")
        
        # Extract base URL from Redis REST URL
        base_url = self.redis_url.rstrip('/')
        subscribe_url = f"{base_url}/subscribe/{self.notification_channel}"
        
        headers = {
            'Authorization': f'Bearer {self.redis_token}',
            'Accept': 'text/event-stream'
        }
        
        print(f"📡 Connecting to SSE endpoint: {subscribe_url}")
        
        processed_count = 0
        
        while not self.shutdown_requested:
            try:
                # Connect to Server-Sent Events endpoint
                response = requests.get(subscribe_url, headers=headers, stream=True, timeout=None)
                response.raise_for_status()
                
                print("✅ PUBSUB connection established!")
                print("🎯 Waiting for task notifications...")
                
                try:
                    for line in response.iter_lines(decode_unicode=True):
                        if self.shutdown_requested:
                            print("⏹️ Shutdown requested, closing SSE connection...")
                            break
                            
                        if line and line.startswith('data: '):
                            try:
                                # Parse SSE data format: "data: message,channel,content"
                                data = line[6:]  # Remove "data: " prefix
                                parts = data.split(',', 2)  # Split into max 3 parts
                                
                                if len(parts) >= 3 and parts[0] == 'message':
                                    channel = parts[1]
                                    message_content = parts[2]
                                    
                                    if channel == self.notification_channel:
                                        # Got a task notification - process it immediately
                                        try:
                                            notification = json.loads(message_content)
                                            task_id = notification.get('taskId', 'unknown')
                                            print(f"📩 Received notification for task: {task_id}")
                                            
                                            # Pop the task from Redis queue
                                            task = self._pop_and_process_task()
                                            
                                            if task:
                                                processed_count += 1
                                                print(f"✅ Task {task['task_id']} processed (total: {processed_count})")
                                            else:
                                                print(f"⚠️ No task found in queue for notification {task_id}")
                                                
                                        except json.JSONDecodeError:
                                            print(f"⚠️ Invalid JSON in notification: {message_content}")
                                        except Exception as e:
                                            print(f"⚠️ Error processing notification: {e}")
                                            
                                elif parts[0] == 'subscribe':
                                    print(f"📡 Subscribed to channel: {parts[1]}")
                                    
                            except Exception as e:
                                print(f"⚠️ Error parsing SSE message: {e}")
                                continue
                            
                except KeyboardInterrupt:
                    print("⏹️ KeyboardInterrupt received during SSE")
                    self.shutdown_requested = True
                    break
                finally:
                    try:
                        response.close()
                    except:
                        pass
                            
            except requests.exceptions.RequestException as e:
                print(f"⚠️ PUBSUB connection lost: {e}")
                if not self.shutdown_requested:
                    print("🔄 Retrying connection in 5 seconds...")
                    time.sleep(5)
            except Exception as e:
                print(f"⚠️ PUBSUB error: {e}")
                if not self.shutdown_requested:
                    print("🔄 Retrying connection in 5 seconds...")
                    time.sleep(5)
        
        print(f"\n🛑 Worker stopped. Total tasks processed: {processed_count}")
    
    def _pop_and_process_task(self) -> Optional[Dict[str, Any]]:
        """
        Pop task from queue and process it immediately.
        Returns task data if successful, None otherwise.
        """
        try:
            # Pop highest priority task from queue
            result = self.redis.zpopmin(self.queue_name, count=1)
            
            if not result:
                return None
                
            # Extract task ID and priority
            task_id = result[0][0]  # First item's member
            priority = result[0][1]  # First item's score
            
            # Get task data from hash
            task_data_json = self.redis.hget(self.data_key, task_id)
            
            if not task_data_json:
                print(f"⚠️ Task data not found for task ID: {task_id}")
                return None
                
            # Parse task data
            task_data = json.loads(task_data_json)
            
            # Remove task data from hash (cleanup)
            self.redis.hdel(self.data_key, task_id)
            
            # Build task object
            task = {
                'task_id': task_id,
                'priority': priority,
                'data': task_data
            }
            
            print(f"📥 Popped task: {task_id} (priority: {priority})")
            
            # Process the task (check for shutdown during processing)
            if self.shutdown_requested:
                print("⏹️ Shutdown requested during task processing")
                return task
                
            result_url = self.process_task(task)
            
            if result_url:
                print(f"🎉 Task completed with result: {result_url}")
            else:
                print("❌ Task processing failed")
                
            return task
            
        except Exception as e:
            print(f"⚠️ Error popping/processing task: {e}")
            return None
            
    def process_task(self, task: Dict[str, Any]) -> Optional[str]:
        """
        Process a face swap task: download images, run swap, upload result.
        Returns the public URL of the uploaded result or None if failed.
        """
        task_id = task['task_id']
        data = task['data']
        
        # Generate unique filenames
        unique_id = str(uuid4())[:8]
        swap_filename = f"swap_{unique_id}.jpg"
        target_filename = f"target_{unique_id}.jpg"
        output_filename = f"output_{task_id}_{unique_id}.jpeg"
        
        # File paths
        swap_path = None
        target_path = None
        output_path = str(Path(self.output_dir) / output_filename)
        
        try:
            print(f"\nProcessing Task: {task_id}")
            print(f"  Action: {data.get('action', 'unknown')}")
            print(f"  Priority: {int(task['priority'])}")
            
            # Check for shutdown before starting
            if self.shutdown_requested:
                print("⏹️ Shutdown requested, skipping task processing")
                return None
                
            # Update status to PREPARING
            self.update_task_status(task_id, "PREPARING")
            
            # Download swap image (source)
            swap_image_path = data.get('swapImage')
            if not swap_image_path:
                raise Exception("swapImage path not provided in task data")
            swap_path = self.download_image(swap_image_path, swap_filename)
            
            # Check for shutdown after download
            if self.shutdown_requested:
                print("⏹️ Shutdown requested during download")
                return None
            
            # Download target image
            target_image_path = data.get('targetImage') 
            if not target_image_path:
                raise Exception("targetImage path not provided in task data")
            target_path = self.download_image(target_image_path, target_filename)
            
            # Check for shutdown before face swap
            if self.shutdown_requested:
                print("⏹️ Shutdown requested before face swap")
                return None
            
            # Update status to PROCESSING
            self.update_task_status(task_id, "PROCESSING")
            
            # Run face swap
            print(f"Running face swap: {swap_path} -> {target_path}")
            self.run_face_swap(swap_path, target_path, output_path)
            
            # Check for shutdown after face swap
            if self.shutdown_requested:
                print("⏹️ Shutdown requested after face swap")
                return None
            
            # Upload result to R2
            print("Uploading result to R2...")
            user_id = data.get('userId')
            public_url = self.upload_to_r2(output_path, task_id, user_id)
            
            # Extract result R2 path for database
            # Convert public URL back to R2 path
            if self.r2_public_url and public_url.startswith(self.r2_public_url):
                result_r2_path = public_url.replace(self.r2_public_url.rstrip('/'), '').lstrip('/')
            else:
                # Fallback - extract from upload path pattern with new structure
                if user_id:
                    result_r2_path = f"uploads/{user_id}/outputs/{task_id}.img"
                else:
                    result_r2_path = f"uploads/anonymous/outputs/{task_id}.img"
            
            # Update status to DONE with result path
            self.update_task_status(task_id, "DONE", result_r2_path)
            
            print(f"✅ Task {task_id} completed successfully!")
            print(f"   Result URL: {public_url}")
            print(f"   Result Path: {result_r2_path}")
            
            return public_url
            
        except Exception as e:
            print(f"❌ Task {task_id} failed: {e}")
            # Update status to FAILED
            self.update_task_status(task_id, "FAILED")
            return None
            
        finally:
            # Clean up downloaded files
            for file_path in [swap_path, target_path]:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Cleaned up: {file_path}")
                    except Exception as e:
                        print(f"Failed to clean up {file_path}: {e}")
            
            # Clean up output file (optional - keep for debugging)
            # if os.path.exists(output_path):
            #     os.remove(output_path)
            
    def print_task_details(self, task: Dict[str, Any]):
        """Print task details in a structured format"""
        task_id = task['task_id']
        priority = task['priority']
        data = task['data']
        
        print(f"\nProcessing Task: {task_id}")
        print(f"  Action: {data.get('action', 'unknown')}")
        print(f"  Priority: {int(priority)}")
        print(f"  Target Image: {data.get('targetImage', 'N/A')}")
        print(f"  Swap Image: {data.get('swapImage', 'N/A')}")
        print(f"  Created: {data.get('createdTime', 'N/A')}")
        
        # Print any additional metadata
        for key, value in data.items():
            if key not in ['taskId', 'action', 'targetImage', 'swapImage', 'createdTime']:
                print(f"  {key}: {value}")
        
    def run(self):
        """Main worker - pure PUBSUB consumer"""
        print("Starting Redis Queue Consumer...")
        
        try:
            # Test Redis connection with a simple operation
            self.redis.ping()
            print("✅ Connected to Upstash Redis")
            
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            sys.exit(1)
            
        print("🚀 Running in PUBSUB-only mode. Press Ctrl+C to stop.\n")
        
        # Run the PUBSUB consumer (this is the main loop)
        self.run_pubsub_consumer()

def main():
    """Entry point"""
    try:
        consumer = RedisQueueConsumer()
        consumer.run()
    except Exception as e:
        print(f"Failed to start worker: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()