import os
import re
import time
import subprocess
import requests
import json
import zipfile
import shutil
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path

# --- DYNAMIC PATH RESOLUTION ---
ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = ROOT_DIR / "configuration.json"

# --- LOAD CONFIGURATION ---
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    print(f"❌ ERROR: Could not find configuration.json at {CONFIG_PATH}")
    print(f"Reason: {e}")
    exit(1)

HTML_FILE = config["input_html"]
DOWNLOAD_FOLDER = config["download_folder"]
ET_CMD = config["exiftool"]  # Can be a path or just "exiftool"
LOG_FILE = ROOT_DIR / "failed_downloads.log"
SUMMARY_FILE = ROOT_DIR / "download_summary.txt"

def check_environment():
    """Checks if required tools (ExifTool) and folders are available."""
    print("🔍 Pre-flight check...")
    
    # 1. Check ExifTool (works with absolute path or PATH variable)
    exiftool_path = shutil.which(ET_CMD)
    if exiftool_path:
        try:
            result = subprocess.run([ET_CMD, "-ver"], capture_output=True, text=True, check=True)
            print(f"   ✅ ExifTool: Ready (Version: {result.stdout.strip()})")
        except Exception as e:
            print(f"   ❌ ERROR: ExifTool found at '{exiftool_path}' but not executable: {e}")
            return False
    else:
        print(f"   ❌ ERROR: ExifTool '{ET_CMD}' not found. Ensure it is in your PATH or provided as absolute path.")
        return False

    # 2. Check Download Folder
    try:
        if not os.path.exists(DOWNLOAD_FOLDER):
            print(f"   📂 Creating download folder: {DOWNLOAD_FOLDER}")
            os.makedirs(DOWNLOAD_FOLDER)
        
        # Test write permissions
        test_file = os.path.join(DOWNLOAD_FOLDER, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print("   ✅ Download Folder: Ready and writable")
    except Exception as e:
        print(f"   ❌ ERROR: Cannot access or write to download folder: {e}")
        return False

    return True

def is_zip_file(filepath):
    """Checks if a file is actually a ZIP archive regardless of extension."""
    return zipfile.is_zipfile(filepath)

def set_metadata_from_filename(target_path, is_directory=False):
    """Uses ExifTool to sync timestamps."""
    try:
        # 1. Extract date from the name
        basename = os.path.basename(target_path)
        match = re.search(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", basename)
        if not match: return False
            
        date_str = match.group(1) # Format: 2025-11-14_11-38-59
        # Conversion for PowerShell: 11/14/2025 11:38:59
        dt_obj = datetime.strptime(date_str, "%Y-%m-%d_%H-%M-%S")
        ps_date = dt_obj.strftime("%m/%d/%Y %H:%M:%S")

        # 2. ExifTool attempt (for internal metadata in JPG/MP4)
        et_args = [ET_CMD, "-AllDates<filename", "-FileModifyDate<filename", 
                   "-overwrite_original", "-q", "-q", target_path]
        subprocess.run(et_args, stderr=subprocess.DEVNULL)

        # 3. PowerShell Fix (Forces creation and modification date under Windows)
        # Works for files AND folders, regardless of whether the format is 'valid'
        if is_directory:
            # Sets date for the folder and all files in it
            ps_cmd = (
                f'$d = "{ps_date}"; '
                f'Get-Item "{target_path}" | % {{ $_.CreationTime = $d; $_.LastWriteTime = $d }}; '
                f'Get-ChildItem "{target_path}" -Recurse | % {{ $_.CreationTime = $d; $_.LastWriteTime = $d }}'
            )
        else:
            ps_cmd = (
                f'$d = "{ps_date}"; '
                f'Get-Item "{target_path}" | % {{ $_.CreationTime = $d; $_.LastWriteTime = $d }}'
            )
        
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)

        return True
    except Exception as e:
        print(f"   ⚠️ Metadata error on {basename}: {e}")
        return False

def extract_sync_and_cleanup_zip(filepath, target_dir):
    """Extracts ZIP, syncs metadata, and deletes the ZIP file afterward."""
    try:
        folder_name = os.path.splitext(os.path.basename(filepath))[0]
        extraction_path = os.path.join(target_dir, folder_name)
        if not os.path.exists(extraction_path): 
            os.makedirs(extraction_path)
        
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            zip_ref.extractall(extraction_path)
        
        set_metadata_from_filename(extraction_path, is_directory=True)
        os.remove(filepath)
        print(f"   📦 Extracted, synced and deleted ZIP.")
        return True
    except Exception:
        return False

def log_failure(filename, url, reason):
    """Logs the failure to file and prints a message to console."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] FAILED: {filename} | {reason} | URL: {url}\n"
    
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
    
    print(f"\n   ❌ !!! DOWNLOAD FAILED !!!")
    print(f"   Filename: {filename} | Reason: {reason}\n")

def download_memories():
    if not check_environment():
        print("🛑 Aborting due to environment issues.")
        return

    stats = {"jpg": 0, "mp4": 0, "zip": 0, "skipped": 0, "errors": 0}
    
    html_path = Path(HTML_FILE)
    if not html_path.is_absolute():
        html_path = ROOT_DIR / HTML_FILE

    if not html_path.exists():
        print(f"❌ ERROR: HTML file not found at {html_path}")
        return

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    rows = soup.find_all('tr')[1:] 
    total = len(rows)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0...", "X-Snap-Route-Tag": "mem-dmd"})
    start_time = time.time()

    for i, row in enumerate(rows):
        cols = row.find_all('td')
        if len(cols) < 4: continue

        date_clean = cols[0].text.strip().replace(":", "-").replace(" ", "_").replace("_UTC", "")
        media_type_html = cols[1].text.strip().lower()
        link_tag = cols[3].find('a')

        if link_tag and 'onclick' in link_tag.attrs:
            match = re.search(r"downloadMemories\('(.+?)'", link_tag['onclick'])
            if match:
                download_url = match.group(1)
                
                ext = ".mp4" if "video" in media_type_html else ".jpg"
                filename = f"{date_clean}{ext}"
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                zip_filepath = os.path.join(DOWNLOAD_FOLDER, f"{date_clean}.zip")
                extracted_folder = os.path.join(DOWNLOAD_FOLDER, date_clean)

                if os.path.exists(filepath) or os.path.exists(extracted_folder):
                    stats["skipped"] += 1
                    continue

                elapsed = time.time() - start_time
                avg = elapsed / (stats["jpg"] + stats["mp4"] + stats["zip"] + stats["errors"] + 1)
                eta = str(timedelta(seconds=int((total - (i + 1)) * avg))) if i > 0 else "Calculating..."
                
                print(f"[{i+1}/{total}] (ETA: {eta}) Processing: {filename}")

                success, retries, last_err = False, 3, "Unknown"
                while not success and retries > 0:
                    try:
                        resp = session.get(download_url, stream=True, timeout=30)
                        if resp.status_code == 200:
                            with open(filepath, 'wb') as f:
                                for chunk in resp.iter_content(chunk_size=8192): f.write(chunk)
                            
                            if is_zip_file(filepath):
                                os.rename(filepath, zip_filepath)
                                if extract_sync_and_cleanup_zip(zip_filepath, DOWNLOAD_FOLDER):
                                    stats["zip"] += 1
                                    success = True
                            else:
                                set_metadata_from_filename(filepath)
                                if ext == ".mp4": stats["mp4"] += 1
                                else: stats["jpg"] += 1
                                success = True
                            
                            if success:
                                print("   ✅ Done")
                                time.sleep(5) 
                        else:
                            last_err = f"HTTP {resp.status_code}"
                            time.sleep(30) if resp.status_code == 503 else time.sleep(2)
                            retries -= 1
                    except Exception as e:
                        last_err = str(e); time.sleep(5); retries -= 1
                
                if not success:
                    stats["errors"] += 1
                    log_failure(filename, download_url, last_err)

    duration = str(timedelta(seconds=int(time.time() - start_time)))
    summary_text = (f"\n{'='*40}\nFINAL SUMMARY\n{'='*40}\n"
                    f"Processed: {total}\nJPEGs:     {stats['jpg']}\nMP4s:      {stats['mp4']}\n"
                    f"ZIPs:      {stats['zip']} (extracted & deleted)\nSkipped:   {stats['skipped']}\n"
                    f"Errors:    {stats['errors']}\nDuration:  {duration}\n{'='*40}")
    print(summary_text)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f: f.write(summary_text)

if __name__ == "__main__":
    download_memories()