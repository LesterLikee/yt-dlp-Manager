# 📥 yt-dlp Manager --- Workflow Documentation

This project is a modular **YouTube/media downloader** built around
`yt-dlp`.\
It provides a **menu-driven console interface**, supports
**categories**, **format selection**, **parallel downloads**,
**subtitles**, **thumbnails**, and more.

------------------------------------------------------------------------

## 🗂️ File Overview

### 1. `category_manager.py`

-   Manages **download categories** and base paths.
-   Handles config (`config.yml`) with:
    -   `download_path` → default folder.
    -   `categories` → user-defined named paths (Music, Movies, etc.).
    -   `default_category` → preselected category for runs.
    -   `retries`, `max_parallel_downloads`.
-   Features:
    -   Add, rename, delete categories.
    -   Set default category.
    -   Folder picker popup (Tkinter).
    -   Sound alert on folder selection.
    -   Returns path to be used in main script.

------------------------------------------------------------------------

### 2. `format_manager.py`

-   Handles **format selection** and **subtitles**.
-   Fetches available formats from `yt-dlp`.
-   Combines **video, audio, and conversion options** into a single
    table.
-   Columns: ID, extension, resolution/note, vcodec, acodec, bitrate,
    fps, size.
-   Always merges video + audio (avoids separate raw streams).
-   Conversion options:
    -   `mp3`, `m4a`, `opus` (via postprocessor).
-   Subtitles:
    -   Ask user → language codes (default `en`).
    -   Download auto-subs + normal subs as `.srt`.

------------------------------------------------------------------------

### 3. `Yt_downloader.py`

- The **main entry point** of the project.
- Handles update-check for `yt-dlp`, `rich`, `PyYAML`, `plyer`.
- Features:
    1. **Menu system**
       - Manage categories  
       - Start downloading  
       - Exit (only when user confirms)  
    2. **Link collection**
       - Option 1 → Paste URLs one by one.  
       - Option 2 → File picker popup to choose a `.txt` file (plays system sound when dialog opens).  
       - Handles playlists (extracts entries).  
    3. **Target selection**
       - Base path, category, or custom folder.  
       - Saves `last_used_path`.  
    4. **Format selection**
       - Calls `format_manager.choose_format_and_postprocessors`.  
       - User picks best/custom/index.  
    5. **Subtitle options**
       - Prompted once per session.  
    6. **Thumbnail options**
       - `Y` = normal thumbnail.  
       - `H` = best quality thumbnail.  
       - `N` = skip thumbnails.  
    7. **Download execution**
       - Parallel downloads (`ThreadPoolExecutor`).  
       - Progress bars (`rich.progress`).  
       - Each video = one unique progress bar showing the **title** (instead of URL).  
       - Auto-resume partial downloads.  
    8. **Notifications**
       - Desktop notification when all downloads finish.  
    9. **Post-actions**
       - Auto-open folder after downloads.  
       - Script does **not close** → loops back to menu so user can run another batch.  

------------------------------------------------------------------------

## 🔄 Typical Workflow

1.  Run **`Yt_downloader.py`**

    ``` bash
    python Yt_downloader.py
    ```

2.  **Menu** → Choose option:

    -   `[1]` Manage categories\
    -   `[2]` Start downloading\
    -   `[3]` Exit

3.  **Target Path Selection**

    -   Pick a category, custom folder, or default path.

4.  **Paste Links**

    -   Paste URLs one by one, or drag-drop a `.txt` file containing
        URLs.\
    -   Playlists auto-expanded into individual items.

5.  **Format Selection**

    -   Unified format table shown.\
    -   Options: Best, Index, Custom code, Back.

6.  **Subtitles**

    -   Choose `Y/N/B`.\
    -   Input subtitle language codes (e.g., `en,hi`).

7.  **Thumbnails**

    -   Choose `Y` (normal), `H` (best quality), or `N` (skip).

8.  **Download Execution**

    -   Progress bars shown for each URL.\
    -   Resume supported (`--continuedl`).\
    -   Parallel downloads based on config (`max_parallel_downloads`).

9.  **Completion**

    -   Desktop notification pops up.\
    -   Target folder auto-opened.

------------------------------------------------------------------------

## ⚙️ Config (`config.yml`)

Example:

``` yaml
# yt-dlp Manager Downloader Config (config.yml)
download_path: "E:/Downloads"
max_parallel_downloads: 2
categories:
  Music: "E:/Media/Music"
  Movies: "E:/Media/Movies"
default_category: Music
retries: 3
```

------------------------------------------------------------------------

## ✅ Key Improvements Added

-   Unified format table (video + audio + conversions).
-   Bitrate, fps, file size estimation.
-   Always merges video + audio.
-   Resume failed downloads.
-   Queue `.txt` file support (drag & drop friendly).
-   Desktop notifications.
-   Optional thumbnail download (normal / best / none).
-   Unique progress bars (no more duplicates).

------------------------------------------------------------------------

## 🖥️ Requirements

-   Python 3.8+
-   Packages auto-installed:
    -   `yt-dlp`\
    -   `rich`\
    -   `PyYAML`\
    -   `plyer`

------------------------------------------------------------------------

## 🚀 Usage Summary

-   Flexible: works with videos, playlists, audio extraction.\
-   Configurable: categories, retries, parallelism.\
-   User-friendly: colored console UI, progress bars, notifications.
