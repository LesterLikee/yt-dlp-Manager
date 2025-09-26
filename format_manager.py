# ===============================================
#  format_manager.py
#  Handles format selection, audio-only, subtitles
# ===============================================

import yt_dlp
from rich.console import Console
from rich.table import Table

# Force colors even if stdout is not a tty
console = Console(force_terminal=True)


def choose_format_and_postprocessors(url):
    try:
        with console.status("[cyan]Fetching available formats... please wait[/cyan]", spinner="dots"):
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
        formats = info.get("formats", [])
    except Exception as e:
        console.print(f"[red]Failed to fetch formats: {e}[/red]")
        return "bestvideo+bestaudio/best", []

    # Split into video and audio
    video_formats = [f for f in formats if f.get("vcodec") != "none"]
    audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]

    # Add conversion choices (mp3, m4a, opus)
    conversion_options = [
        {"format_id": "conv-mp3", "ext": "mp3", "acodec": "mp3", "abr": "192", "note": "Extract & Convert"},
        {"format_id": "conv-m4a", "ext": "m4a", "acodec": "aac", "abr": "192", "note": "Extract & Convert"},
        {"format_id": "conv-opus", "ext": "opus", "acodec": "opus", "abr": "192", "note": "Extract & Convert"},
    ]
    audio_formats.extend(conversion_options)

    # Unified formats table
    all_formats = video_formats + audio_formats
    table = Table(title="Available Formats (Video + Audio + Conversions)")
    table.add_column("Idx", justify="right", width=4)
    table.add_column("format_id", width=12)
    table.add_column("ext", width=6)
    table.add_column("res/note", width=12)
    table.add_column("vcodec", width=10)
    table.add_column("acodec", width=10)
    table.add_column("abr/bitrate", width=12)
    table.add_column("fps", width=6)
    table.add_column("size", width=10)

    for i, f in enumerate(all_formats, 1):
        size = f.get("filesize") or f.get("filesize_approx")
        if size:
            size_str = f"{round(size/1024/1024,1)} MB"
        else:
            size_str = "?"

        table.add_row(
            str(i),
            str(f.get("format_id")),
            f.get("ext", ""),
            f.get("format_note") or (str(f.get("height")) + "p" if f.get("height") else f.get("note", "-")),
            f.get("vcodec", "-"),
            f.get("acodec", "-"),
            str(f.get("abr") or f.get("tbr") or "-"),
            str(f.get("fps") or "-"),
            size_str,
        )

    console.print(table)

    # Prompt
    console.print("[cyan]Options:[/cyan] "
                  "[green]B[/green]=Best (video+audio)  "
                  "[green]Index[/green]=Enter table index directly  "
                  "[green]C[/green]=Custom code  "
                  "[green]BACK[/green]=Go back")

    while True:
        choice = console.input("> ").strip().lower()

        # Best
        if choice == "b":
            return "bestvideo+bestaudio/best", []

        # Index direct (user typed number)
        if choice.isdigit():
            idxn = int(choice) - 1
            if 0 <= idxn < len(all_formats):
                fmt = all_formats[idxn]
                fmtid = str(fmt.get("format_id"))

                # Conversion entry
                if fmtid.startswith("conv-"):
                    codec = fmt["ext"]
                    postp = [{"key": "FFmpegExtractAudio", "preferredcodec": codec, "preferredquality": "192"}]
                    return "bestaudio/best", postp

                # Normal video → always merge with bestaudio
                if fmt.get("vcodec") != "none":
                    return f"{fmtid}+bestaudio/best", []

                # Pure audio
                return fmtid, []
            else:
                console.print("[yellow]Index out of range.[/yellow]")
                continue

        # Custom code
        if choice == "c":
            code = console.input("Enter custom yt-dlp format code (or BACK): ").strip()
            if code.lower() == "back" or not code:
                continue
            # Always merge with bestaudio
            return f"{code}+bestaudio/best", []

        # Back
        if choice == "back":
            return None, None

        console.print("[yellow]Unknown option[/yellow]")


def ask_subtitles_options():
    subs_opts = {}
    ch = console.input("[cyan]Download subtitles? (Y/N/B=back): [/cyan]").strip().lower()
    if ch == "y":
        lang = console.input("[cyan]Enter subtitle language code(s), comma separated (default: en): [/cyan]").strip()
        if not lang:
            lang = "en"
        langs = [l.strip() for l in lang.split(",") if l.strip()]
        subs_opts["writesubtitles"] = True
        subs_opts["writeautomaticsub"] = True
        subs_opts["subtitleslangs"] = langs
        subs_opts["subtitlesformat"] = "srt"
    elif ch == "b":
        return "back"
    return subs_opts
