#!/usr/bin/env python3
"""
NSFW Content Checker

Tests images and videos using the same OpenNSFW2 model that roop uses to filter content.
Threshold: 0.85 (same as roop's MAX_PROBABILITY)
"""

import sys
import os
from roop.predictor import predict_image, predict_video, MAX_PROBABILITY
import opennsfw2

def is_video_file(path: str) -> bool:
    """Check if file is a video based on extension."""
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.gif'}
    return os.path.splitext(path.lower())[1] in video_extensions

def check_nsfw_image(image_path: str) -> None:
    """Check if an image is flagged as NSFW content."""
    try:
        probability = predict_image(image_path)
        is_nsfw = probability > MAX_PROBABILITY
        
        print(f"Image: {image_path}")
        print(f"NSFW probability: {probability:.4f}")
        print(f"Threshold: {MAX_PROBABILITY}")
        print(f"Result: {'❌ BLOCKED (NSFW)' if is_nsfw else '✅ ALLOWED'}")
        print()
        
    except Exception as e:
        print(f"Error processing image '{image_path}': {e}")

def check_nsfw_video(video_path: str) -> None:
    """Check if a video is flagged as NSFW content."""
    try:
        # Get detailed frame analysis like roop does
        _, probabilities = opennsfw2.predict_video_frames(video_path=video_path, frame_interval=100)
        
        max_prob = max(probabilities) if probabilities else 0.0
        is_nsfw = any(prob > MAX_PROBABILITY for prob in probabilities)
        flagged_frames = sum(1 for prob in probabilities if prob > MAX_PROBABILITY)
        
        print(f"Video: {video_path}")
        print(f"Frames analyzed: {len(probabilities)} (every 100th frame)")
        print(f"Highest NSFW probability: {max_prob:.4f}")
        print(f"Frames flagged as NSFW: {flagged_frames}/{len(probabilities)}")
        print(f"Threshold: {MAX_PROBABILITY}")
        print(f"Result: {'❌ BLOCKED (NSFW)' if is_nsfw else '✅ ALLOWED'}")
        print()
        
    except Exception as e:
        print(f"Error processing video '{video_path}': {e}")

def check_nsfw(file_path: str) -> None:
    """Check if a file (image or video) is flagged as NSFW content."""
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist")
        return
    
    if is_video_file(file_path):
        check_nsfw_video(file_path)
    else:
        check_nsfw_image(file_path)

def main():
    if len(sys.argv) < 2:
        print("Usage: python nsfw_check.py <file_path1> [file_path2] ...")
        print("       python nsfw_check.py /path/to/image.jpg")
        print("       python nsfw_check.py /path/to/video.mp4")
        print("       python nsfw_check.py *.jpg *.mp4")
        print()
        print("Supports images and videos. Videos are sampled every 100 frames.")
        sys.exit(1)
    
    file_paths = sys.argv[1:]
    
    print(f"Checking {len(file_paths)} file(s) for NSFW content...")
    print(f"Using OpenNSFW2 model with threshold {MAX_PROBABILITY}")
    print("-" * 60)
    
    for file_path in file_paths:
        check_nsfw(file_path)

if __name__ == "__main__":
    main()