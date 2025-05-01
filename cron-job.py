import os
from datetime import datetime, timedelta
import time
import shutil
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler()]  # This ensures logs go to stdout
)

class FolderCleaner:
    def __init__(self, root_path, output_path, days_threshold=7):
        self.root_path = root_path
        self.output_path = output_path
        self.days_threshold = days_threshold

    def is_old_folder(self, folder_name):
        try:
            # Try to parse the folder name as a date (year-month-day format)
            folder_date = datetime.strptime(folder_name, "%Y-%m-%d")
            current_date = datetime.now()
            age = current_date - folder_date
            return age.days > self.days_threshold
        except ValueError:
            # If folder name isn't in the expected date format, skip it
            logging.warn(f"getting unexpected folder name {folder_name}")
            return False

    def is_old_file(self, file_path):
        try:
            # Get file creation time (or last modified time as fallback)
            file_time = os.path.getctime(file_path)
            file_datetime = datetime.fromtimestamp(file_time)
            current_date = datetime.now()
            age = current_date - file_datetime
            return age.days > self.days_threshold
        except Exception as e:
            logging.error(f"Error checking file age: {str(e)}")
            return False

    def clean_old_files(self):
        try:
            # List all files in the output directory
            for item in os.listdir(self.output_path):
                item_path = os.path.join(self.output_path, item)
                
                # Check if it's a file and is old enough to delete
                if os.path.isfile(item_path) and self.is_old_file(item_path):
                    logging.info(f"Removing old file: {item_path}")
                    os.remove(item_path)
                    logging.info(f"Successfully removed file: {item_path}")
        except Exception as e:
            logging.error(f"Error during file cleanup: {str(e)}")

    def clean_old_folders(self):
        try:
            # List all items in the root directory
            for item in os.listdir(self.root_path):
                item_path = os.path.join(self.root_path, item)
                
                # Check if it's a directory and matches our date format
                if os.path.isdir(item_path) and self.is_old_folder(item):
                    logging.info(f"Removing old folder: {item_path}")
                    shutil.rmtree(item_path)
                    logging.info(f"Successfully removed: {item_path}")
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")

def main():
    # Configure these parameters
    ROOT_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")  # Replace with your folder path
    OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "output")  # Replace with your output folder path
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 3600))  # Check every hour (in seconds)
    DAYS_THRESHOLD = int(os.getenv("DAYS_THRESHOLD", 7))    # Remove folders older than 7 days

    cleaner = FolderCleaner(ROOT_FOLDER, OUTPUT_FOLDER, DAYS_THRESHOLD)
    
    logging.info(f"Starting folder cleanup service for: {ROOT_FOLDER}")
    logging.info(f"Also monitoring output folder: {OUTPUT_FOLDER}")
    logging.info(f"Will remove items older than {DAYS_THRESHOLD} days")

    while True:
        logging.info("Running cleanup check...")
        cleaner.clean_old_folders()
        cleaner.clean_old_files()
        logging.info(f"Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
