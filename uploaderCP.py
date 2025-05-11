import os
import json
import logging
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
from googleapiclient.errors import HttpError
import time
from colorama import Fore, Style, init

# Configuration and Constants

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv")
TRACKING_DIR = r"C:\Users\meetd\Desktop\YT root\Core\source code"

init(autoreset=True)

# Set up logging

logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s [%(levelname)s] %(message)s")

#Load/Save Tracking File

def extract_video_id(filename):
    """Extracts YouTube ID from filename (format: TITLE_[VIDEO_ID].mp4)"""
    try:
        # Supports both formats: "video_[ABC123].mp4" and "video_ABC123.mp4"
        base = os.path.splitext(filename)[0]
        if base.endswith("]"):
            video_id = base.split("[")[-1].rstrip("]")
        else: 
            video_id = base.split("_")[-1]

        if video_id and len(video_id) == 11:
            return video_id

    except Exception as e:
        logging.warning(f"Failed to extract ID from {filename}: {str(e)}")
        return None

def is_video_uploaded(video_id, tracking_file):
    """Checks if video ID exists in tracking file"""
    if not video_id:
        return False
    if os.path.exists(tracking_file):
        with open(tracking_file, "r") as f:
            return video_id in json.load(f)
    return False

def log_uploaded_video(video_id, tracking_file):
    """Adds YouTube video ID to tracking file"""
    os.makedirs(os.path.dirname(tracking_file), exist_ok=True)
    uploaded = set()
    if os.path.exists(tracking_file):
        with open(tracking_file, "r") as f:
            uploaded = set(json.load(f))
    uploaded.add(video_id)
    with open(tracking_file, "w") as f:
        json.dump(list(uploaded), f)    


# Function: Authenticate per Channel


def authenticate_channel(client_secrets_file, token_file):
    """Authenticates a channel with automatic token management"""
    # Ensure directories exist for token files
    os.makedirs(os.path.dirname(token_file), exist_ok=True)
    
    credentials = None
    
    # Load existing credentials if available
    if os.path.exists(token_file):
        try:
            credentials = Credentials.from_authorized_user_file(token_file, SCOPES)
            # Auto-refresh if expired
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
        except Exception as e:
            logging.error(f"Authentication failed: {str(e)}")
            logging.critical("Manual re-authentication required! Delete token file and restart.")
            raise SystemExit("Authentication failure") from e

    # First-time authentication
    if not credentials:
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
        credentials = flow.run_local_server(port=0)
        with open(token_file, "w") as token:
            token.write(credentials.to_json())

    return build("youtube", "v3", credentials=credentials)




# Function: Get Newest Video File from Folder

def get_newest_video_file(folder_path, tracking_file):
    """Scans the folder for new video files using only the tracking file"""
    video_files = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(VIDEO_EXTENSIONS):
            video_id = extract_video_id(filename)
            if video_id and not is_video_uploaded(video_id, tracking_file):
                full_path = os.path.join(folder_path, filename)
                try:
                    mod_time = os.path.getmtime(full_path)
                    video_files.append((full_path, mod_time, video_id))
                except Exception as e:
                    logging.error(f"Error accessing {filename}: {e}")
    
    if not video_files:
        return None, None
    
    video_files.sort(key=lambda x: x[1], reverse=True)
    return video_files[0][0], video_files[0][2]

# Function: Upload Video to YouTube

def upload_video(youtube, file_path, config, title, description, tags, privacy_status, category_id):
    """Uploads video"""

   # if config.get("use_filename_as_title", False):
    #    title = os.path.splitext(os.path.basename(file_path))[0]  # Filename without extension
    #else:
    #    title = config["default_title"]

    logging.info(f"Uploading video: {file_path}")
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    response = request.execute()
    video_id = response.get("id")
    logging.info(Fore.GREEN + f"Successfully uploaded video. Video ID: {video_id}")
    return video_id


# Main Function

def main():
            
    # Channel configuration
    
    channels_config = [
        
          {
               "channel_id": "clipper645",
               "channel_url": "https://www.youtube.com/channel/UCt5CNZvZuucHT6JKsTvYTQg",
               "client_secrets_file": r"C:\Users\meetd\Desktop\YT root\auth\clipper645_client_secret.json",
               "token_file": r"C:\Users\meetd\Desktop\YT root\auth\clipper645_token.json",
               #"use_filename_as_title": False,
               "source_folder": r"C:\Users\meetd\Desktop\YT root\Media\The rookie",
               "default_title": "The Rookie #TheRookieSeason7 #Chenford #TVShow",
               "default_description": "Check out my new video on 'The Rookie'.... #CrimeDrama #PoliceDrama #TVShow #TheRookieSeason7 #Chenford #TheRookieABC",
               "tags": ["CrimeDrama", "PoliceDrama", "TVShow", "TheRookieSeason7", "Chenford", "TheRookieABC"],
               "privacy_status": "public",
               "category_id": "24"
           },
        
           {
               "channel_id": "shutterclips",
               "channel_url" : "https://www.youtube.com/channel/UCUj8fHYxqJwtwKVt8YHxMgg",
               "client_secrets_file": r"C:\Users\meetd\Desktop\YT root\auth\shutterclips_client_secret.json",
               "token_file": r"C:\Users\meetd\Desktop\YT root\auth\shutterclips_token.json",
               "source_folder": r"C:\Users\meetd\Desktop\YT root\Media\Shows - Young sheldon, BBT",
               #"use_filename_as_title": True,
               "default_title": "The Big Bang Theory #shorts # youngsheldon #BBT #TVShow",
               "default_description": "Check out my new video on 'big bang theory'.... #Drama #BBT #TVShow #youngsheldon #missy #georgie #mandy",
               "tags": ["Drama", "BBT", "TVShow", "youngsheldon", "mandy", "georgie"],
               "privacy_status": "public",
               "category_id": "24"
           },
    
           {
               "channel_id": "clipper644",
               "channel_url" : "https://www.youtube.com/channel/UCZVwI-TV4eA2HjYwoiLjefg",
               "client_secrets_file": r"C:\Users\meetd\Desktop\YT root\auth\clipper644_client_secret.json",
               "token_file": r"C:\Users\meetd\Desktop\YT root\auth\clipper644_token.json",
               "source_folder": r"C:\Users\meetd\Desktop\YT root\Media\Shows - station19, lucifer, brba, bcs, mr. inbetween",
               #"use_filename_as_title": True,
               "default_title": "Bay harbour cooker vs lawyer. #shorts #Jesse #Walter #TVShow",
               "default_description": "Check out my new video.... #Drama #jesse #TVShow #brba #bettercallsaul #Heisenberg #skyler #breakingbad",
               "tags": ["Drama", "jesse", "TVShow", "bettercallsaul", "breakingbad", "Gustavo"],
               "privacy_status": "public",
               "category_id": "24"
            },    
                
            {     
               "channel_id": "superheromania646",
               "channel_url" : "https://www.youtube.com/channel/UC_T7Wn0_bN-_tSoj2OlOB1Q",
               "client_secrets_file": r"C:\Users\meetd\Desktop\YT root\auth\superheromania646_client_secret.json",
               "token_file": r"C:\Users\meetd\Desktop\YT root\auth\superheromania646_token.json",
               "source_folder": r"C:\Users\meetd\Desktop\YT root\Media\Marvels",
               #"use_filename_as_title": True,
               "default_title": "Marvel Cinematic Universe #ironman #Tony #Superhero",
               "default_description": "Check out my new video.... #ironman #Avengers #rdj #peter #thor #spiderman #stanlee #thanos #doctorstrange #shorts #viralvideo #loki #marvel ",
               "tags": ["Tony", "Marvel", "Superhero", "Loki", "Disney", "Avengers"],
               "privacy_status": "public",
               "category_id": "24"
           }
    ]
    
    
    for config in channels_config:
 
        TRACKING_FILE = os.path.join(TRACKING_DIR, f"uploaded_videos_{config['channel_id']}.json")
        
        logging.info(f"Processing uploads for channel ({config['channel_id']}) ")
        youtube = authenticate_channel(config["client_secrets_file"], config["token_file"])
        
        # Prompt for a new folder path if all videos in the original folder are uploaded
        """while True:
            folder_uploaded = check_folder_upload_status(config["source_folder"], uploaded_videos)
            if not folder_uploaded:
                break
            logging.info(f"All videos in folder '{config['source_folder']}' have been uploaded.")
            new_folder = input("Please enter the path to another folder to process (or press Enter to skip): ").strip()
            if not new_folder:
                logging.info("No additional folder provided. Skipping to the next channel.")
                break  # Exit
            config["source_folder"] = new_folder
"""
        # Get the newest video file, ignoring already uploaded videos
        newest_video, video_id = get_newest_video_file(config["source_folder"], TRACKING_FILE)
        if newest_video is None:
            logging.warning(f"No new video found in folder: {config['source_folder']}")
            continue

        # Prepare metadata and upload
        video_filename = os.path.basename(newest_video)
        title = config['default_title'] #video_filename
        description = f"{config['default_description']}\nUploaded on: {datetime.now()}"
        tags = config["tags"]
        privacy_status = config["privacy_status"]
        categoryId = config["category_id"]
        try:
            upload_video(youtube, newest_video, config, title, description, config['tags'], config['privacy_status'], config["category_id"])
            log_uploaded_video(video_id, TRACKING_FILE)
            time.sleep(60)
        except Exception as e:
            logging.error(f"Error uploading video for channel: {e}")
        
    
    logging.info(Fore.GREEN + "Script execution completed.")

if __name__ == "__main__":
    main()