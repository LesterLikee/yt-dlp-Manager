# ===============================================
#  Universal Media Downloader (yt-dlp powered)
# ===============================================
# Save as: Yt_downloader.py
# ===============================================

import os, sys, subprocess, time, traceback, platform, shutil, zipfile, io, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TextColumn

# Update check for dependencies
try:
    print("🔄 Checking for updates: yt-dlp, rich, PyYAML, plyer...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp", "rich", "PyYAML", "plyer"], check=False)
except Exception as e:
    print(f"⚠️ Dependency update check failed: {e}")

# Imports after dependency update
import yt_dlp
from plyer import notification

# GUI + sound for file selection
import tkinter as tk
from tkinter import filedialog
if platform.system() == "Windows":
    import winsound

# Category manager
from category_manager import (
    load_config, save_config, manage_categories,
    pick_category_for_run, pick_folder_popup
)

# Format manager
from format_manager import choose_format_and_postprocessors, ask_subtitles_options

console = Console()

# ----------------- Auto-updater -----------------
REPO_USER = "LesterLikee"
REPO_NAME = "yt-dlp-Manager"

def check_for_update():
    config = load_config()
    local_ver = config.get("installed_version", "none")

    try:
        url = f"https://api.github.com/repos/{REPO_USER}/{REPO_NAME}/releases/latest"
        r = requests.get(url, timeout=10)
        latest_tag = r.json().get("tag_name", "unknown")

        print(f"Local version: {local_ver}, Latest version: {latest_tag}")

        # 🔹 If this is the first run, set version automatically
        if local_ver == "none" and latest_tag != "unknown":
            config["installed_version"] = latest_tag
            save_config(config)
            print(f"✅ First run detected, setting version to {latest_tag}")
            return

        # 🔹 If update available, ask user
        if latest_tag != "unknown" and latest_tag != local_ver:
            ans = input(f"\n⚠️ Update {latest_tag} available (you have {local_ver}). Update now? (y/n): ").strip().lower()
            if ans == "y":
                dl_url = f"https://github.com/{REPO_USER}/{REPO_NAME}/archive/refs/tags/{latest_tag}.zip"
                print(f"⬇️ Downloading update from {dl_url}...")
                z = zipfile.ZipFile(io.BytesIO(requests.get(dl_url).content))
                extract_dir = f"{REPO_NAME}-{latest_tag}"
                z.extractall(".")
                # copy files over
                for item in os.listdir(extract_dir):
                    src = os.path.join(extract_dir, item)
                    dst = os.path.join(os.getcwd(), item)
                    if os.path.exists(dst):
                        if os.path.isdir(dst):
                            shutil.rmtree(dst)
                        else:
                            os.remove(dst)
                    shutil.move(src, dst)
                shutil.rmtree(extract_dir)

                config["installed_version"] = latest_tag
                save_config(config)

                print("✅ Update installed. Please restart the program.")
                sys.exit(0)
    except Exception as e:
        print(f"[!] Update check failed: {e}")


# ----------------- Playlist/Profile/Post Handling -----------------
def handle_playlist(url):
    """
    Detect whether URL is a single item, playlist, or full profile/channel.
    If private, prompt user for cookies.txt and retry.
    Returns list of URLs to download.
    """
    opts = {"quiet": True, "no_warnings": True}

    def try_extract(cookies=None):
        o = dict(opts)
        if cookies:
            o["cookiefile"] = cookies
        with yt_dlp.YoutubeDL(o) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = try_extract()
    except Exception as e:
        if "login" in str(e).lower() or "private" in str(e).lower():
            console.print("[yellow]Private or restricted content detected. A cookies.txt file is required.[/yellow]")
            cookies = console.input("Enter path to cookies.txt (or press Enter to cancel): ").strip()
            if cookies and os.path.exists(cookies):
                try:
                    info = try_extract(cookies)
                except Exception as e2:
                    console.print(f"[red]Failed even with cookies: {e2}[/red]")
                    return [url]
            else:
                console.print("[red]No cookies provided, skipping private profile.[/red]")
                return []
        else:
            console.print(f"[red]Failed to extract info: {e}[/red]")
            return [url]

    # If it's a playlist/profile/channel (contains entries)
    if "entries" in info and info["entries"]:
        console.print(f"[cyan]Found collection with {len(info['entries'])} items[/cyan]")
        return [e["url"] for e in info["entries"] if e]

    # Single video/image
    return [url]

# ----------------- Download Worker -----------------
def download_worker(url, out_path, ydl_opts_base, retries, progress, task_id):
    opts = dict(ydl_opts_base)
    opts["outtmpl"] = os.path.join(out_path, "%(uploader)s", "%(title).100s.%(ext)s")
    opts["continuedl"] = True  # resume partial downloads

    # ⚡ Ensure images also get downloaded
    opts.setdefault("skip_download", False)

    def hook(d):
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0) or 0
            total = d.get("total_bytes", 0) or d.get("total_bytes_estimate", 0) or 0
            progress.update(task_id, total=total, completed=downloaded)
        elif d["status"] == "finished":
            console.print(f"[green]✅ Finished: {url}[/green]")

    opts.update({
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "logger": None,
    })

    for attempt in range(retries):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

                # ⚡ Special case: Instagram/Facebook image posts
                if info.get("ext") in ["jpg", "png", "webp"]:
                    console.print(f"[cyan]📷 Saved image post: {info.get('title','(no title)')}[/cyan]")

            return True
        except Exception as e:
            console.print(f"[red]Attempt {attempt+1}/{retries} failed: {e}[/red]")
            time.sleep(1)

    console.print(f"[red]Giving up on {url}[/red]")
    return False

# ----------------- Path / Category Chooser -----------------
def choose_download_target(config):
    cats = config.get("categories", {})
    default_cat = config.get("default_category")
    last_used = config.get("last_used_path")

    if default_cat and default_cat in cats:
        current_label, current_path = f"[{default_cat}]", cats[default_cat]
    elif last_used:
        current_label, current_path = "[Last Used]", last_used
    else:
        current_label, current_path = "[Base Path]", config.get("download_path", os.getcwd())

    while True:
        console.print(f"\n[cyan]Current target:[/cyan] {current_label} -> [green]{current_path}[/green]")
        console.print("[cyan]Options:[/cyan] Enter=use  C=choose category  P=pick path  M=manage categories")
        choice = input("> ").strip().lower()
        if choice == "":
            config["last_used_path"] = current_path
            save_config(config)
            return current_path
        elif choice == "c":
            sel = pick_category_for_run(config)
            if sel:
                config["last_used_path"] = sel
                save_config(config)
                return sel
        elif choice == "p":
            newp = pick_folder_popup("Select download folder")
            if newp:
                config["last_used_path"] = newp
                save_config(config)
                return newp
        elif choice == "m":
            manage_categories(config)
        else:
            console.print("[yellow]Invalid choice[/yellow]")

# ----------------- MAIN -----------------
def main():
    config = load_config()

    # Menu
    while True:
        console.print("\n[cyan]=== Main Menu ===[/cyan]")
        console.print("[green]1[/green]. Manage Categories")
        console.print("[green]2[/green]. Start Downloading")
        console.print("[green]3[/green]. Exit")
        choice = input("Select option: ").strip()
        if choice == "1":
            manage_categories(config)
        elif choice == "2":
            break
        elif choice == "3":
            return

    out_path = choose_download_target(config)

    # ---------------- Link Input Options ----------------
    links = []
    console.print("\n[cyan]Link Input Options[/cyan]")
    console.print("[green]1[/green]. Paste links manually")
    console.print("[green]2[/green]. Select a .txt file")
    choice = input("Choose option: ").strip()

    if choice == "1":
        console.print("\n[cyan]Paste links (empty = finish):[/cyan]")
        while True:
            line = input("> ").strip()
            line = line.strip().strip('"').strip("'")
            if line.lower().startswith("path"):
                line = line[4:].lstrip("= :").strip().strip('"').strip("'")

            if not line:
                break
            if line.lower().endswith(".txt") and os.path.exists(line):
                with open(line, "r", encoding="utf-8") as f:
                    for l in f:
                        l = l.strip()
                        if l.startswith("http"):
                            links.extend(handle_playlist(l))
            elif line.startswith("http"):
                links.extend(handle_playlist(line))
            else:
                console.print(f"[yellow]Skipping invalid: {line}[/yellow]")

    elif choice == "2":
        root = tk.Tk()
        root.withdraw()
        if platform.system() == "Windows":
            winsound.MessageBeep()
        file_path = filedialog.askopenfilename(
            title="Select text file with links",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                for l in f:
                    l = l.strip()
                    if l.startswith("http"):
                        links.extend(handle_playlist(l))
        else:
            console.print("[yellow]No file chosen.[/yellow]")

    if not links:
        console.print("[red]No links provided.[/red]")
        return

    # Format selection
    console.print("[cyan]Preparing format selection...[/cyan]")
    fmt, postp = None, None
    while fmt is None:
        fmt, postp = choose_format_and_postprocessors(links[0])
    format_code, postprocessors = fmt, postp

    # Subtitles
    subs_opts = ask_subtitles_options()
    if subs_opts == "back":
        return

    # Thumbnail option
    thumb_choice = console.input("[cyan]Download thumbnails? (Y=normal / H=high quality / N=no): [/cyan]").strip().lower()
    thumb_opts = {}
    if thumb_choice == "y":
        thumb_opts = {"writethumbnail": True, "embedthumbnail": True}
    elif thumb_choice == "h":
        thumb_opts = {"writethumbnail": True, "embedthumbnail": True, "thumbnailsformat": "best"}
    else:
        thumb_opts = {}

    ydl_opts_base = {
        "format": format_code,
        "postprocessors": postprocessors,
        "continuedl": True,
        **subs_opts,
        **thumb_opts
    }

    retries = config.get("retries", 3)
    max_parallel = config.get("max_parallel_downloads", 2)

    console.print(f"\n[cyan]Downloading {len(links)} items, {max_parallel} parallel...[/cyan]")

    with Progress(TextColumn("[bold]{task.description}"), BarColumn(), DownloadColumn(),
                  TransferSpeedColumn(), TimeRemainingColumn(), console=console) as progress:
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = []
            for url in links:
                try:
                    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                        info = ydl.extract_info(url, download=False)
                        title = info.get("title", url)
                except Exception:
                    title = url
                task_id = progress.add_task(title, total=0)
                futures.append(executor.submit(download_worker, url, out_path, ydl_opts_base, retries, progress, task_id))
            for f in as_completed(futures):
                f.result()

    console.print("[green]✅ All downloads finished![/green]")

    try:
        notification.notify(
            title="Downloader",
            message=f"✅ {len(links)} downloads finished!",
            timeout=5
        )
    except Exception:
        pass

    try:
        if sys.platform == "win32":
            os.startfile(out_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", out_path])
        else:
            subprocess.run(["xdg-open", out_path])
    except Exception:
        pass

if __name__ == "__main__":
    check_for_update()   # Run updater first
    while True:
        try:
            main()
        except Exception as e:
            console.print(f"[red]Crash: {e}[/red]")
            traceback.print_exc()
            time.sleep(5)
            continue

        again = input("\nDo you want to start another download? (Y/N): ").strip().lower()
        if again != "y":
            break
