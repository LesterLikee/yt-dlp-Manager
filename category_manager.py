# ===============================================
#  Category Manager (called from main script)
# ===============================================

import os
import sys
import yaml
from rich.console import Console
from rich.table import Table

# ----------- GLOBALS & CONFIG ----------- #
console = Console()
CONFIG_FILE = "config.yml"

DEFAULT_CONFIG = {
    "download_path": os.path.expanduser(os.getcwd()),
    "max_parallel_downloads": 2,
    "categories": {},  # name -> path
    "default_category": None,
    "retries": 3
}

CONFIG_COMMENTS = """# Universal Downloader Config (config.yml)
# download_path: Default folder where files will be saved if no category is chosen
# max_parallel_downloads: Number of files to download in parallel
# categories: Named categories (example)
#   Music: /path/to/music
#   Movies: /path/to/movies
# default_category: Name of the category to use by default (optional)
# retries: Number of retry attempts for failed downloads
"""

# ----------- CONFIG HANDLING ----------- #
def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        console.log("[yellow]No config found, created default config.yml[/yellow]")
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            # fill missing keys with defaults
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        console.log(f"[red]Failed to load config: {e} — using defaults[/red]")
        return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(CONFIG_COMMENTS)
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        console.log(f"[red]Failed to save config: {e}[/red]")

# ----------- UTIL: sound and folder popup ----------- #
def play_sound():
    try:
        if sys.platform == "win32":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
    except Exception:
        pass

def pick_folder_popup(title="Select folder"):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        play_sound()
        path = filedialog.askdirectory(title=title)
        root.update()
        root.destroy()
        if path:
            return os.path.abspath(path)
    except Exception as e:
        console.log(f"[red]Folder chooser failed: {e}[/red]")
    return None

# ----------- CATEGORY MANAGER ----------- #
def manage_categories(config: dict):
    """Interactive category manager: add/rename/delete/set default."""
    while True:
        cats: dict = config.get("categories", {})
        table = Table(title="Categories", show_lines=False)
        table.add_column("Index", width=6)
        table.add_column("Name")
        table.add_column("Path")
        items = list(cats.items())
        for i, (n, p) in enumerate(items, 1):
            table.add_row(str(i), n, p)
        console.print(table)
        console.print("Options: [A]dd  [R]ename  [D]elete  [S]et default  [B]ack")
        choice = input("Choice: ").strip().lower()
        if choice == "a":
            name = input("Category name: ").strip()
            if not name:
                console.log("[yellow]Name empty, canceled.[/yellow]")
                continue
            new_path = pick_folder_popup(f"Select folder for category '{name}'")
            if not new_path:
                console.log("[yellow]No folder chosen, canceled.[/yellow]")
                continue
            cats[name] = new_path
            config["categories"] = cats
            save_config(config)
            console.log(f"[green]Added category {name} -> {new_path}[/green]")
        elif choice == "r":
            idx = input("Enter category index to rename: ").strip()
            if not idx.isdigit():
                console.log("[yellow]Invalid index.[/yellow]"); continue
            idx = int(idx) - 1
            if idx < 0 or idx >= len(items):
                console.log("[yellow]Index out of range.[/yellow]"); continue
            old_name, old_path = items[idx]
            new_name = input(f"New name for '{old_name}' (leave empty to cancel): ").strip()
            if not new_name:
                console.log("[yellow]Canceled.[/yellow]"); continue
            cats[new_name] = cats.pop(old_name)
            config["categories"] = cats
            if config.get("default_category") == old_name:
                config["default_category"] = new_name
            save_config(config)
            console.log(f"[green]Renamed {old_name} -> {new_name}[/green]")
        elif choice == "d":
            idx = input("Enter category index to delete: ").strip()
            if not idx.isdigit():
                console.log("[yellow]Invalid index.[/yellow]"); continue
            idx = int(idx) - 1
            if idx < 0 or idx >= len(items):
                console.log("[yellow]Index out of range.[/yellow]"); continue
            name_to_del = items[idx][0]
            confirm = input(f"Delete '{name_to_del}'? Type YES to confirm: ").strip()
            if confirm == "YES":
                cats.pop(name_to_del, None)
                if config.get("default_category") == name_to_del:
                    config["default_category"] = None
                config["categories"] = cats
                save_config(config)
                console.log(f"[green]Deleted category {name_to_del}[/green]")
            else:
                console.log("[yellow]Delete canceled.[/yellow]")
        elif choice == "s":
            idx = input("Enter category index to set as default: ").strip()
            if not idx.isdigit():
                console.log("[yellow]Invalid index.[/yellow]"); continue
            idx = int(idx) - 1
            if idx < 0 or idx >= len(items):
                console.log("[yellow]Index out of range.[/yellow]"); continue
            default_name = items[idx][0]
            config["default_category"] = default_name
            save_config(config)
            console.log(f"[green]Default category set to {default_name}[/green]")
        elif choice == "b":
            return
        else:
            console.log("[yellow]Unknown option.[/yellow]")

# ----------- PATH / CATEGORY CHOOSING ----------- #
def choose_base_path(config: dict) -> str:
    base = config.get("download_path") or os.getcwd()
    while True:
        console.print(f"\nCurrent base download path: [cyan]{base}[/cyan]")
        console.print("Press [Enter] to keep, type C to change path, M to manage categories.")
        choice = input("> ").strip().lower()
        if choice == "":
            return base
        if choice == "c":
            new = pick_folder_popup("Select download base folder")
            if new:
                config["download_path"] = new
                save_config(config)
                console.log(f"[green]Saved new base path -> {new}[/green]")
                return new
            else:
                console.log("[yellow]No folder chosen, keeping previous path.[/yellow]")
                return base
        if choice == "m":
            manage_categories(config)
            base = config.get("download_path") or base
            continue
        console.log("[yellow]Unknown choice — Enter = keep, C = change, M = manage categories[/yellow]")

def pick_category_for_run(config: dict):
    cats: dict = config.get("categories", {}) or {}
    default_name = config.get("default_category")
    if default_name and default_name in cats:
        console.print(f"\nDefault category: [green]{default_name}[/green] -> {cats[default_name]}")
        use = input("Use default? (Enter = yes, N = no): ").strip().lower()
        if use == "" or use != "n":
            return cats[default_name]
    if not cats:
        ans = input("No categories defined. Type 'Y' to add one now, Enter to skip: ").strip().lower()
        if ans == "y":
            manage_categories(config)
            cats = config.get("categories", {}) or {}
            if cats:
                pass
            else:
                return None
        else:
            return None
    items = list(cats.items())
    console.print("\nAvailable categories:")
    for i, (n, p) in enumerate(items, 1):
        console.print(f" {i}. {n} -> {p}")
    console.print("Enter index, NEW to create, or Enter to skip.")
    choice = input("> ").strip()
    if choice == "":
        return None
    if choice.lower() == "new":
        manage_categories(config)
        return pick_category_for_run(config)
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(items):
            return items[idx][1]
    console.log("[yellow]Invalid category selection. Using base path.[/yellow]")
    return None
