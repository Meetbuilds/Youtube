import yt_dlp
import random
import time
import logging
import threading
import re
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import yt_dlp
import os
import json
from pathlib import Path
from concurrent.futures import as_completed


# Configure logging
logging.basicConfig(
    filename="shorts_downloader.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Thread-safe counters
download_lock = threading.Lock()
successful_downloads = 0
failed_downloads = 0

# Auto-create history directory
HISTORY_DIR = r"C:\Users\meetd\Desktop\YT root\source code"
os.makedirs(HISTORY_DIR, exist_ok=True)

DOWNLOAD_HISTORY_FILE = r"C:\Users\meetd\Desktop\YT root\source code\download_history.log"
CHANNEL_HISTORY_FILE = r"C:\Users\meetd\Desktop\YT root\source code\channel_history.json"


# ---------------------------
# Duplicate Check
# ---------------------------
def is_video_downloaded(video_id):
    """Check if video was previously downloaded"""
    Path(DOWNLOAD_HISTORY_FILE).touch(exist_ok=True)
    with open(DOWNLOAD_HISTORY_FILE, 'r') as f:
        return video_id in f.read()

def log_downloaded_video(video_id):
    """Record downloaded video ID"""
    with open(DOWNLOAD_HISTORY_FILE, 'a') as f:
        f.write(f"{video_id}\n")

# ---------------------------
#Channel Tracker
# ---------------------------
def get_channel_id(url):
    """Extract channel ID from URL"""
    if '@' in url:  # Handle @username format
        return url.split('@')[-1].split('/')[0]
    return re.search(r'channel/([a-zA-Z0-9_-]+)', url).group(1)

def get_channel_history(channel_id):
    """Get existing video IDs for a channel"""
    if not Path(CHANNEL_HISTORY_FILE).exists():
        return []
    with open(CHANNEL_HISTORY_FILE, 'r') as f:
        history = json.load(f)
    return set(history.get(channel_id, []))

def update_channel_history(channel_id, video_ids):
    """Update channel download records"""
    history = {}
    if Path(CHANNEL_HISTORY_FILE).exists():
        with open(CHANNEL_HISTORY_FILE, 'r') as f:
            history = json.load(f)
    
    history[channel_id] = list(set(history.get(channel_id, []) + video_ids))
    
    with open(CHANNEL_HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def filter_new_videos(channel_id, video_urls):
    """Filter out tracked videos"""
    filtered = []
    for url in video_urls:
        vid = extract_video_id(url)
        if not is_video_downloaded(vid) and vid not in get_channel_history(channel_id):
            filtered.append(url)
    return filtered
# ---------------------------
# Helper Functions
# ---------------------------
def extract_video_id(url):
    """More robust ID extraction"""
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    return match.group(1) if match else None

def sanitize_filename(title):
     cleaned = re.sub(r'[^a-zA-Z0-9 \-_]', '', title)
     return cleaned[:100]
   
def validate_url(url):
    """Ensure URL is in correct format for Shorts extraction"""
    url = url.strip()
    if '/shorts/' in url.lower() or '/shorts' in url.lower():
        return url.rstrip('/')
    return f"{url.rstrip('/')}/shorts"

def fetch_video_urls(target_url, max_retries):
    """Fetch Shorts with multiple fallback strategies"""
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'match_filter': lambda info: info.get('duration', 0) <= 60,
        'ignoreerrors': True,
        'default_search': 'ytsearch',
        'cookiefile': 'cookies.txt'  # Optional: use cookies for logged-in access
    }
    
    retries = 0
    while retries < max_retries:
        try:
            user_agent = random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
            ])
            ydl_opts['http_headers'] = {'User-Agent': user_agent}

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_url, download=False)

            if not info or 'entries' not in info:
                return []

            return [entry['url'] for entry in info['entries'] if entry]
        
        except Exception as e:
            retries += 1
            logging.warning(f"Fetch error (Attempt {retries}/{max_retries}): {str(e)}")
            time.sleep(min(2 ** retries, 30) + random.uniform(0, 1))
    
    logging.error("Failed to fetch video URLs after retries.")
    return []

def get_video_range(total_shorts):
    """Get valid video range from user"""
    while True:
        print(f"\n\033[1mTotal Shorts found: {total_shorts}\033[0m")
        try:
            start = int(input("Enter starting index (0-based): "))
            end = int(input(f"Enter ending index (max {total_shorts - 1}): "))
            if 0 <= start <= end < total_shorts:
                return start, end
            print(f"\033[91mInvalid range! Must be between 0 and {total_shorts - 1}.\033[0m")
        except ValueError:
            print("\033[91mPlease enter valid numbers.\033[0m")


def download_video(video_url, download_path, max_retries):

    global successful_downloads, failed_downloads
    if not os.path.exists(download_path):
        os.makedirs(download_path, exist_ok=True)

    video_id = extract_video_id(video_url)
    
    if is_video_downloaded(video_id):
        logging.info(f"Skipping duplicate: {video_id}")
        return

    retries = 0
    actually_downloaded = False
    sanitized_title = "untitled"
    final_filename = ""
    new_path = ""

    download_opts = {
        'outtmpl': f"{download_path}/%(title)s_%(id)s.%(ext)s",        
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'ignoreerrors': False,
        'retries': max_retries,
        'fragment_retries': 3,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4'  
        }],
        'windowsfilenames': True,
        'restrictfilenames': True,
        'nooverwrites': True,
        'continuedl': True,
        'noprogress': True,
        'fixup': 'warn',
        'verbose': False
    }

    while retries < max_retries:
        try:
            user_agent = random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
            ])
            download_opts['http_headers'] = {'User-Agent': user_agent}

            with yt_dlp.YoutubeDL(download_opts) as ydl:
                # Get video info first
                info = ydl.extract_info(video_url, download=False)
                if not info:
                    raise Exception("Failed to extract video info")
                
                # Sanitize filename and prepare paths
                sanitized_title = sanitize_filename(info.get('title', 'untitled'))
                temp_filename = ydl.prepare_filename(info)  # e.g., "MyTitle_ABC123.mp4"
                base_title = sanitize_filename(info.get('title', 'untitled'))
                target_path = os.path.join(download_path, f"{base_title}.mp4")

                # Collision-safe renaming logic
                suffix = 1
                while os.path.exists(target_path):
                    target_path = os.path.join(download_path, f"{base_title} ({suffix}).mp4")
                    suffix += 1


                # Skip if already exists (race condition protection)
                if os.path.exists(new_path):
                    logging.info(f"File already exists: {new_path}")
                    actually_downloaded = True
                    break

                                   # Perform actual download
                ydl.download([video_url])

                if not os.path.exists(temp_filename):
                    raise FileNotFoundError("Download did not complete properly")

                os.replace(temp_filename, target_path)
                actually_downloaded = True


                logging.info(f"Download success: {video_url}")
                log_downloaded_video(video_id)
                break

        except Exception as e:
            retries += 1
            logging.error(f"Download attempt {retries} failed for {video_url}: {str(e)}")
            time.sleep(min(2 ** retries, 15))

    # Final verification
    if not actually_downloaded:
        expected_file = os.path.join(download_path, f"{sanitized_title}_{video_id}.mp4")
        if os.path.exists(expected_file):
            actually_downloaded = True

    # Update counters
    with download_lock:
        if actually_downloaded:
            successful_downloads += 1
        else:
            failed_downloads += 1
            logging.error(f"Permanent failure for {video_url}")

    # Cleanup temporary files
    if os.path.exists(final_filename):
        try:
            os.remove(final_filename)
        except Exception as e:
            logging.error(f"Failed to clean up temp file: {str(e)}")
    
    
if __name__ == "__main__":
    # Get user inputs
    channel_url = input("\nEnter YouTube channel URL: ").strip()
    download_path = input("Enter download path: ").strip()
    os.makedirs(download_path, exist_ok=True)
    max_threads = 5
    max_retries = 3

    # Channel tracking setup
    channel_id = get_channel_id(channel_url)
    
    # Validate URL
    def validate_url(url):
        """Ensure URL is in correct format for channel processing"""
        url = url.strip().rstrip('/')

        if '/shorts/' in url.lower():
            return url
        if '/channel/' in url or '/@' in url:
            return f"{url}/shorts" if 'shorts' not in url else url
        return f"{url}/shorts" 

    target_url = validate_url(channel_url)
    logging.info(f"Shorts downloader script started for {channel_url}")

    # Verify paths
    print(f"\n\033[1mDownload path: {os.path.abspath(download_path)}\033[0m")
    print(f"\033[1mUsing processed URL:\033[0m {target_url}")

    # Fetch video URLs
    video_urls = fetch_video_urls(target_url, max_retries)
    
    # Add debug output
    print(f"\nFound {len(video_urls)} potential shorts (before filtering)")
    logging.info(f"Initial video URLs found: {len(video_urls)}")

    # Filter for channel history
    video_urls = filter_new_videos(channel_id, video_urls)
    print(f"After filtering: {len(video_urls)} new shorts available")

    if not video_urls:
        print("\n\033[92mNo new videos found for this channel!\033[0m")
        exit()

    # Get download range
    total_shorts = len(video_urls)
    start_index, end_index = get_video_range(total_shorts)
    selected_urls = video_urls[start_index:end_index + 1]
    selected_count = len(selected_urls)

    # Final confirmation
    print(f"\n\033[1mAbout to download {selected_count} Shorts:\033[0m")
    confirm = input(f"Proceed with download? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n\033[91mDownload canceled.\033[0m")
        exit()

    successful_downloads = 0
    failed_downloads = 0

    # Start download process with enhanced monitoring
    print(f"\n\033[1mStarting download of {selected_count} Shorts...\033[0m")
    with tqdm(total=selected_count, desc="Downloading", unit="video") as pbar:
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = []
            for url in selected_urls:
                futures.append(executor.submit(
                    download_video, 
                    url,
                    # Pass explicit parameters instead of relying on globals
                    download_path,
                    max_retries
                ))
                pbar.update(0)  # Initial progress update
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Thread error: {str(e)}")
                    with download_lock:
                       failed_downloads += 1

    # Final verification
    actual_downloads = len([
        f for f in os.listdir(download_path)
        if f.endswith('.mp4') and os.path.getsize(os.path.join(download_path, f)) > 0
    ])
    
    # Display final report
    print(f"\n\033[1m{'='*40}")
    print(f"Download Summary:")
    print(f"Selected Shorts: {selected_count}")
    print(f"Reported Successes: {successful_downloads}")
    print(f"Reported Failures: {failed_downloads}")
    print(f"Actual MP4 files in directory: {actual_downloads}")
    print(f"{'='*40}\033[0m")

    logging.info(
        f"Final report - Selected: {selected_count}, "
        f"Success: {successful_downloads}, "
        f"Failed: {failed_downloads}, "
        f"Actual files: {actual_downloads}"
    )

    # Update channel history only with verified downloads
    downloaded_ids = []
    for url in selected_urls:
        vid = extract_video_id(url)
        if vid and is_video_downloaded(vid):
            downloaded_ids.append(vid)
    
    update_channel_history(channel_id, downloaded_ids)

