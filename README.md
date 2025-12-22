# Snapchat Memory Loader

A robust Python-based tool designed to download your Snapchat memories from an exported HTML history file. It automatically handles media types, extracts "Multi-Snap" ZIP archives, and synchronizes metadata (timestamps) using ExifTool to ensure your photos and videos appear in the correct chronological order in any gallery.

## Features

* **Throttled Downloading**: 5-second delay between requests to prevent IP blocking (HTTP 503).
* **Metadata Sync**: Uses ExifTool to write the original capture date from the filename into the file's EXIF/metadata headers.
* **ZIP Handling**: Automatically detects and extracts ZIP archives, applying recursive metadata updates to all contained files.
* **Auto-Resume**: Skips already downloaded files or extracted folders.
* **Detailed Logging**: Records failed downloads in `failed_downloads.log` and provides a summary report.
* **ETA Tracker**: Provides a real-time estimation of the remaining download time.

## Requirements

### 1. Python & Poetry

* **Python**: Version 3.13 or higher.
* **Poetry**: For dependency management.

### 2. External Tools

* **ExifTool**: This script requires the `exiftool` executable.
  * Download it from: [https://exiftool.org/](https://exiftool.org/)
  * Extract it and note the path to `exiftool.exe`.

### 3. Snapchat Data

* You must have your Snapchat data export (specifically `memories_history.html`).

Go to <https://accounts.snapchat.com/v2/download-my-data> and select **Export your Memories**.
You will receive a download link for a zip file containing the necessary `memories_history.html` file.

## Project Structure

```text
snapchat-memory-loader/
├── src/
│   └── snapchat_memory_loader/
│       ├── __init__.py
│       └── main.py              # The main script logic
├── configuration.json           # Local paths and settings
├── memories_history.html        # Your Snapchat export file
├── pyproject.toml               # Project dependencies (Poetry)
├── failed_downloads.log         # Auto-generated error log
└── README.md
```

## Setup & Installation

Follow these steps to prepare your environment:

1. Install Poetry: If you haven't installed Poetry yet, follow the official instructions.

1. Initialize Project: Navigate to the project root and install the required Python dependencies:

   ```shell
   poetry install
   ```

1. Configure Environment: Create a configuration.json file in the root directory. This file is excluded from version control to protect your local paths:

   ```JSON
   {
   "input_html": "memories_history.html",
   "download_folder": "P:/alessia_snaps_autoload",
   "exiftool": "D:/devtools/exiftool/exiftool-13.44_64/exiftool.exe"
   }
   ```

   *Note: Use forward slashes (/) even on Windows to avoid path escaping issues.*

1. Add Snapchat Data: Place your memories_history.html file into the project root (or update the path in configuration.json).

## Running the Script

Once everything is configured, start the automated download process:

```shell
poetry run python src/snapchat_memory_loader/main.py
```

What to expect:

* **Throttling:** The script waits 5 seconds between files to act "human" and avoid server bans.
* **ZIP Processing:** ZIP files are downloaded, renamed, extracted into folders, and then automatically deleted to save space.
* **Metadata:** Timestamps are written immediately after each download or extraction.
* **Summary:** A report will be displayed and saved to download_summary.txt once finished.
