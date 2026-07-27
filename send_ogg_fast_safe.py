import os
import requests
from datetime import datetime
from mutagen.oggopus import OggOpus
import time
import signal
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# === CONFIG from environment variables ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID_DAY = os.getenv("CHAT_ID_DAY")
CHAT_ID_NIGHT = os.getenv("CHAT_ID_NIGHT")

CHANNELS = {
    "Hatzolah Operations": CHAT_ID_DAY,
    "Hatzolah Training": CHAT_ID_NIGHT
}

CREDIT = "@Aushatzolahbot"
ROOT_FOLDER = r"C:\Users\avrom\Desktop\scanner vetted@ converted"

# --- SETTINGS ---
MAX_RETRIES = 5
RETRY_DELAY = 2       # initial retry delay
SEND_DELAY = 0.2      # small delay per file
MAX_WORKERS = 8       # increased threads for faster sending
TESTING_MODE = True   # True = safe testing mode

stop_script = False

# === HANDLE CTRL+C ===
def signal_handler(sig, frame):
    global stop_script
    stop_script = True
    print("\n🛑 Ctrl+C detected. Stopping script gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# === FUNCTIONS ===
def get_ogg_metadata(file_path):
    try:
        audio = OggOpus(file_path)
        title = audio.get("title", ["Unknown"])[0].strip()
        date_tag = audio.get("date", ["Unknown"])[0]
        if date_tag != "Unknown" and len(date_tag) == 14:
            dt = datetime.strptime(date_tag, "%Y%m%d%H%M%S")
            timestamp = dt.strftime("%m/%d/%Y %I:%M:%S %p")
        else:
            timestamp = "Unknown"
        return title, timestamp
    except Exception as e:
        print(f"⚠️ Error reading metadata for {file_path}: {e}")
        return "Unknown", "Unknown"

def send_to_telegram(file_path, chat_id, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"
    delay = RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(file_path, "rb") as f:
                files = {"audio": (os.path.basename(file_path), f)}
                resp = requests.post(url, files=files, data={"chat_id": chat_id, "caption": caption})

            if resp.status_code == 200:
                return True
            elif resp.status_code == 429:
                print(f"⚠️ Rate limit (429), attempt {attempt}/{MAX_RETRIES} for {file_path}")
                time.sleep(delay)
                delay *= 2
            elif resp.status_code in [400, 403]:
                print(f"⚠️ Failed {file_path} | Response: {resp.status_code}, skipping")
                return False
            else:
                print(f"⚠️ Unexpected error {file_path} | Response: {resp.status_code}")
                time.sleep(delay)
                delay *= 2
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Exception sending {file_path}: {e}")
            time.sleep(delay)
            delay *= 2
    print(f"⚠️ Giving up on {file_path} after {MAX_RETRIES} attempts")
    return False

def process_ogg(file_path, index, total):
    if stop_script:
        return
    title, timestamp = get_ogg_metadata(file_path)
    chat_id = CHANNELS.get(title)
    if not chat_id:
        print(f"⚠️ No chat ID mapped for Title '{title}', skipping {file_path}")
        return
    caption = f"{title}\n{timestamp}\nCredit: {CREDIT}"
    print(f"[{index}/{total}] Processing: {file_path} | Caption: {caption.replace(chr(10), ' | ')}")
    if send_to_telegram(file_path, chat_id, caption):
        print(f"[{index}/{total}] ✅ Sent {file_path}")
    time.sleep(SEND_DELAY)

# === MAIN ===
def main():
    global stop_script
    stop_script = False  # reset every run

    all_ogg_files = []
    for root, _, files in os.walk(ROOT_FOLDER):
        for file in files:
            if file.lower().endswith(".ogg"):
                all_ogg_files.append(os.path.join(root, file))

    # Sort oldest → newest
    all_ogg_files.sort(key=lambda x: os.path.getmtime(x))
    total_files = len(all_ogg_files)

    try:
        if TESTING_MODE:
            # Safe threaded mode
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for i, f in enumerate(all_ogg_files, start=1):
                    futures.append(executor.submit(process_ogg, f, i, total_files))
                for future in as_completed(futures):
                    if stop_script:
                        break
        else:
            # Normal threaded mode
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for i, f in enumerate(all_ogg_files, start=1):
                    futures.append(executor.submit(process_ogg, f, i, total_files))
                for future in as_completed(futures):
                    if stop_script:
                        break

    except KeyboardInterrupt:
        print("\n🛑 Ctrl+C detected, stopping...")

if __name__ == "__main__":
    main()
