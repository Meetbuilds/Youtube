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

init(autoreset=True)

# Set up logging

logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s [%(levelname)s] %(message)s")

# Function: Load/Save Tracking File

def load_uploaded_videos(tracking_file):
    """Loads the list of uploaded videos from the tracking file."""
    if os.path.exists(tracking_file):
        with open(tracking_file, "r") as f:
            return set(json.load(f))
    return set()

"""Saves list of uploaded videos to tracking file."""
def save_uploaded_videos(uploaded_videos, tracking_file):
    with open(tracking_file, "w") as f:
         json.dump(list(uploaded_videos), f)


# Function: Authenticate per Channel

# ------------------------------
# Function: Authenticate per Channel (FIXED)
# ------------------------------

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



# Function: Check Folder Upload Status

def check_folder_upload_status(folder_path, uploaded_videos):
    """Checks if all videos in the folder have been uploaded."""
    folder_videos = [
        filename for filename in os.listdir(folder_path)
        if filename.lower().endswith(VIDEO_EXTENSIONS)
    ]
    not_uploaded = [video for video in folder_videos if video not in uploaded_videos]
    
    if not_uploaded:
        logging.info(f"{len(not_uploaded)} videos in folder '{folder_path}' are not uploaded yet.")
        return False
    logging.info(f"All videos in folder '{folder_path}' have been uploaded.")
    return True


# Function: Get Newest Video File from Folder

def get_newest_video_file(folder_path, uploaded_videos):
    """Scans the folder for new video files and returns the newest file."""
    video_files = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(VIDEO_EXTENSIONS) and filename not in uploaded_videos:
            full_path = os.path.join(folder_path, filename)
            try:
                mod_time = os.path.getmtime(full_path)
                video_files.append((full_path, mod_time))
            except Exception as e:
                logging.error(f"Error getting creation time for {full_path}: {e}")
    if not video_files:
        return None
    video_files.sort(key=lambda x: x[1], reverse=True)
    return video_files[0][0]


# Function: Upload Video to YouTube

def upload_video(youtube, file_path, config, title, description, tags, privacy_status, category_id):
    """Uploads video"""

    if config.get("use_filename_as_title", False):
        title = os.path.splitext(os.path.basename(file_path))[0]  # Filename without extension
    else:
        title = config["default_title"]

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
               "use_filename_as_title": False,
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
               "use_filename_as_title": True,
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
               "use_filename_as_title": True,
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
               "use_filename_as_title": True,
               "default_title": "Marvel Cinematic Universe #ironman #Tony #Superhero",
               "default_description": "Check out my new video.... #ironman #Avengers #rdj #peter #thor #spiderman #stanlee #thanos #doctorstrange #shorts #viralvideo #loki #marvel ",
               "tags": ["Tony", "Marvel", "Superhero", "Loki", "Disney", "Avengers"],
               "privacy_status": "public",
               "category_id": "24"
           }
    ]
    
    
    for config in channels_config:

       # config["client_secrets_file"] = f"C:/Users/meetd/Desktop/YT root/auth/{config['channel_id']}_client_secret.json"
       # config["token_file"] = f"C:/Users/meetd/Desktop/YT root/auth/{config['channel_id']}_token.json"

        channel_id = config["channel_url"].split("/")[-1]
        TRACKING_FILE = f"uploaded_videos_{channel_id}.json"
        uploaded_videos = load_uploaded_videos(TRACKING_FILE)

        logging.info(f"Processing uploads for channel '{config['channel_id']}' ")
        youtube = authenticate_channel(config["client_secrets_file"], config["token_file"])
        
        # Prompt for a new folder path if all videos in the original folder are uploaded
        while True:
            folder_uploaded = check_folder_upload_status(config["source_folder"], uploaded_videos)
            if not folder_uploaded:
                break
            logging.info(f"All videos in folder '{config['source_folder']}' have been uploaded.")
            new_folder = input("Please enter the path to another folder to process (or press Enter to skip): ").strip()
            if not new_folder:
                logging.info("No additional folder provided. Skipping to the next channel.")
                break  # Exit
            config["source_folder"] = new_folder

        # Get the newest video file, ignoring already uploaded videos
        newest_video = get_newest_video_file(config["source_folder"], uploaded_videos)
        if newest_video is None:
            logging.warning(f"No new video found in folder: {config['source_folder']}")
            continue

        # Prepare metadata and upload
        video_filename = os.path.basename(newest_video)
        title = config['default_title']
        description = f"{config['default_description']}\nUploaded on: {datetime.now()}"
        tags = config["tags"]
        privacy_status = config["privacy_status"]
        categoryId = config["category_id"]
        try:
            upload_video(youtube, newest_video, config, title, description, tags, privacy_status, config["category_id"])
            uploaded_videos.add(video_filename)
            time.sleep(60)
        except Exception as e:
            logging.error(f"Error uploading video for channel: {e}")
        

              # Save updated tracking data
        save_uploaded_videos(uploaded_videos, TRACKING_FILE)
    
    logging.info(Fore.GREEN + "Script execution completed.")

if __name__ == "__main__":
    main()