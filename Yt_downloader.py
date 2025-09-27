# ===============================================
#  Universal Media Downloader (yt-dlp powered)
# ===============================================
# Save as: Yt_downloader.py
# ===============================================

import os, sys, subprocess, time, traceback, platform, shutil, zipfile, io, importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TextColumn

console = Console()

# ----------------- Dependency Manager -----------------
def ensure_deps():
    deps = {
        "yt_dlp": "yt-dlp",
        "rich": "rich",
        "yaml": "PyYAML",
        "plyer": "plyer",
        "requests": "requests",
    }
    missing = []
    for module, pkg in deps.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pkg)

    # Install missing ones (show logs)
    if missing:
        print(f"⬇️ Installing missing packages: {', '.join(missing)} ...")
        subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=False)
    else:
        print("✅ All required packages are installed.")

    # Check outdated packages
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--outdated", "--format=freeze"],
        capture_output=True, text=True
    )
    outdated = [line.split("==")[0] for line in result.stdout.strip().splitlines() if line]
    needs_update = [pkg for pkg in deps.values() if pkg in outdated]

    if needs_update:
        ans = input(f"⚠️ Updates available for: {', '.join(needs_update)}. Update now? (y/n): ").strip().lower()
        if ans == "y":
            print("🔄 Updating dependencies...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-U"] + needs_update)
            print("✅ Dependencies updated.")
    else:
        print("✅ All dependencies are up to date.")

# ----------------- FFmpeg (Full) check & install/update -----------------
def check_ffmpeg_full():
    try:
        # Verify ffmpeg and ffprobe exist
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("✅ FFmpeg (full) is installed and working.")

        # Try checking upgrade on Windows
        if platform.system() == "Windows":
            result = subprocess.run(
                ["winget", "upgrade", "ffmpeg", "--accept-source-agreements", "--accept-package-agreements"],
                capture_output=True, text=True
            )
            if "No applicable update found" not in result.stdout:
                ans = input("⚠️ FFmpeg update available. Update now? (y/n): ").strip().lower()
                if ans == "y":
                    print("🔄 Updating FFmpeg...")
                    subprocess.run(
                        ["winget", "upgrade", "ffmpeg",
                         "--accept-source-agreements", "--accept-package-agreements"]
                    )
                    print("✅ FFmpeg updated.")
                else:
                    print("⏭️ Skipped FFmpeg update.")
            else:
                print("✅ FFmpeg is up to date.")

    except Exception:
        print("⚠️ FFmpeg (full) not found.")
        if platform.system() == "Windows":
            print("⬇️ Installing FFmpeg (full)...")
            subprocess.run(
                ["winget", "install", "ffmpeg",
                 "--accept-source-agreements", "--accept-package-agreements"]
            )
        else:
            print("⚠️ Please install FFmpeg manually from: https://ffmpeg.org/download.html")

# Run deps check before imports
ensure_deps()

# Imports after dependency check
check_ffmpeg_full()
import yt_dlp
import requests
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

# ----------------- Auto-updater -----------------
REPO_USER = "LesterLikee"
REPO_NAME = "yt-dlp-Manager"

def check_for_update():
    config = load_config()
    local_ver = config.get("installed_version")

    try:
        url = f"https://api.github.com/repos/{REPO_USER}/{REPO_NAME}/releases/latest"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        latest_tag = r.json().get("tag_name", "unknown")

        # First run or missing key
        if not local_ver and latest_tag != "unknown":
            config["installed_version"] = latest_tag
            save_config(config)
            print(f"✅ First run detected, set version to {latest_tag}")
            return

        # Update available
        if latest_tag != "unknown" and latest_tag != local_ver:
            ans = input(f"\n⚠️ Update {latest_tag} available (you have {local_ver or 'none'}). Update now? (y/n): ").strip().lower()
            if ans == "y":
                dl_url = f"https://github.com/{REPO_USER}/{REPO_NAME}/archive/refs/tags/{latest_tag}.zip"
                print(f"⬇️ Downloading update from {dl_url}...")

                # Download zip
                zip_path = "update.zip"
                with open(zip_path, "wb") as f:
                    f.write(requests.get(dl_url).content)

                # Extract to temp folder
                extract_dir = f"update_tmp_{latest_tag}"
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(extract_dir)

                # Find actual repo folder inside extracted
                inner_dir = next(d for d in os.listdir(extract_dir) if d.startswith(REPO_NAME))

                # Copy files to current folder (overwrite)
                src_path = os.path.join(extract_dir, inner_dir)
                for item in os.listdir(src_path):
                    s = os.path.join(src_path, item)
                    d = os.path.join(os.getcwd(), item)
                    if os.path.exists(d):
                        if os.path.isdir(d):
                            shutil.rmtree(d)
                        else:
                            os.remove(d)
                    shutil.move(s, d)

                # Cleanup
                os.remove(zip_path)
                shutil.rmtree(extract_dir)

                # Save new version
                config["installed_version"] = latest_tag
                save_config(config)

                print("✅ Update installed. Please restart the program.")
                sys.exit(0)
        else:
            print("✅ Up to date.")

    except Exception as e:
        print(f"[!] Update check failed: {e}")

# ----------------- Playlist/Profile/Post Handling -----------------
def handle_playlist(url):
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

    if "entries" in info and info["entries"]:
        console.print(f"[cyan]Found collection with {len(info['entries'])} items[/cyan]")
        return [e["url"] for e in info["entries"] if e]

    return [url]

# ----------------- Download Worker -----------------
def download_worker(url, out_path, opts, retries, progress=None, task_id=None):
    try:
        retries = int(retries)
    except Exception:
        retries = 3

    for attempt in range(retries):
        try:
            def hook(d):
                if d["status"] == "downloading" and progress and task_id:
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    downloaded = d.get("downloaded_bytes", 0)

                    progress.update(
                        task_id,
                        total=total or None,
                        completed=downloaded,
                        description=f"{d.get('filename', url)}",
                    )

                elif d["status"] == "finished" and progress and task_id:
                    progress.update(task_id, completed=1, total=1)
                    progress.console.print(f"[green]✅ Finished:[/green] {d.get('filename', url)}")

            ydl_opts = {
                **opts,
                "outtmpl": os.path.join(out_path, "%(title)s.%(ext)s"),
                "progress_hooks": [hook],
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True

        except Exception as e:
            console.print(f"[red]Attempt {attempt+1}/{retries} failed: {e}[/red]")
            time.sleep(1)

    console.print(f"[red]❌ Giving up on {url} after {retries} attempts[/red]")
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

    # ---------------- Link Input ----------------
    links = []
    console.print("\n[cyan]Link Input Options[/cyan]")
    console.print("[green]1[/green]. Paste links manually")
    console.print("[green]2[/green]. Select a .txt file")
    choice = input("Choose option: ").strip()

    if choice == "1":
        console.print("\n[cyan]Paste links (empty = finish):[/cyan]")
        while True:
            line = input("> ").strip().strip('"').strip("'")
            if not line:
                break
            if line.lower().endswith(".txt") and os.path.exists(line):
                with open(line, "r", encoding="utf-8") as f:
                    for l in f:
                        l = l.strip()
                        if l.startswith("http"):
                            try:
                                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                                    info = ydl.extract_info(l, download=False)
                                    console.print(f"[green]🎞️ Found:[/green] {info.get('title', l)}")
                            except Exception:
                                console.print(f"[blue]🔗 Using link:[/blue] {l}")
                            links.extend(handle_playlist(l))
            elif line.startswith("http"):
                try:
                    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                        info = ydl.extract_info(line, download=False)
                        console.print(f"[green]🎞️ Found:[/green] {info.get('title', line)}")
                except Exception:
                    console.print(f"[blue]🔗 Using link:[/blue] {line}")
                links.extend(handle_playlist(line))
            else:
                console.print(f"[yellow]Skipping invalid: {line}[/yellow]")

    elif choice == "2":
        root = tk.Tk(); root.withdraw()
        if platform.system() == "Windows": winsound.MessageBeep()
        file_path = filedialog.askopenfilename(title="Select text file with links", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if file_path and os.path.exists(file_path):
            console.print("[cyan]Loading links from file, please wait...[/cyan]")
            with open(file_path, "r", encoding="utf-8") as f:
                for l in f:
                    l = l.strip()
                    if l.startswith("http"):
                        try:
                            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                                info = ydl.extract_info(l, download=False)
                                console.print(f"[green]🎞️ Found:[/green] {info.get('title', l)}")
                        except Exception:
                            console.print(f"[blue]🔗 Using link:[/blue] {l}")
                        links.extend(handle_playlist(l))
        else:
            console.print("[yellow]No file chosen.[/yellow]")

    if not links:
        console.print("[red]No links provided.[/red]")
        return

    # ---------------- Format Selection ----------------
    console.print("[cyan]Preparing format selection...[/cyan]")
    fmt, postp = None, None
    while fmt is None:
        fmt, postp = choose_format_and_postprocessors(links[0])

    format_code, postprocessors = fmt, postp
    subs_opts = ask_subtitles_options()
    if subs_opts == "back": return
    thumb_choice = console.input("[cyan]Download thumbnails? (Y=normal / H=high quality / N=no): [/cyan]").strip().lower()
    if thumb_choice == "y":
        thumb_opts = {"writethumbnail": True, "embedthumbnail": True}
    elif thumb_choice == "h":
        thumb_opts = {"writethumbnail": True, "embedthumbnail": True, "thumbnailsformat": "best"}
    else:
        thumb_opts = {}

    ydl_opts_base = {"format": format_code, "postprocessors": postprocessors, "continuedl": True, **subs_opts, **thumb_opts}

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
                # 🔹 No more 0-byte bars, just clean indefinite bar
                task_id = progress.add_task(title, total=None)
                futures.append(executor.submit(download_worker, url, out_path, ydl_opts_base, retries, progress, task_id))
            for f in as_completed(futures):
                f.result()

    console.print("[green]✅ All downloads finished![/green]")

    try:
        notification.notify(title="Downloader", message=f"✅ {len(links)} downloads finished!", timeout=5)
    except Exception:
        pass

    try:
        if sys.platform == "win32": os.startfile(out_path)
        elif sys.platform == "darwin": subprocess.run(["open", out_path])
        else: subprocess.run(["xdg-open", out_path])
    except Exception:
        pass

if __name__ == "__main__":
    check_for_update()
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
