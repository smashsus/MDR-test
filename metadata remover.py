#!/usr/bin/env python3
"""
Metadata Tool — Extract / Read / Remove
Supports: JPG, PNG, WEBP, TIFF, BMP, PDF, DOCX, MP3, FLAC, OGG, M4A, MP4, MOV

Install:
    pip install Pillow pypdf python-docx mutagen pymediainfo

Usage:
    python metadata_tool.py read   <file>
    python metadata_tool.py remove <file>
    python metadata_tool.py remove <folder>
"""

import os
import sys
import json
from pathlib import Path


# ── COLORS ──────────────────────────────────────────────────────────────────

R  = "\033[91m"
G  = "\033[92m"
Y  = "\033[93m"
B  = "\033[94m"
C  = "\033[96m"
W  = "\033[97m"
DIM = "\033[2m"
RST = "\033[0m"
BOLD = "\033[1m"


# ── READ ─────────────────────────────────────────────────────────────────────

def read_image(path: Path) -> dict:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS

    img = Image.open(path)
    meta = {
        "format": img.format,
        "mode": img.mode,
        "size": f"{img.width}x{img.height}",
    }

    exif_raw = img._getexif() if hasattr(img, "_getexif") else None
    if exif_raw:
        for tag_id, val in exif_raw.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo" and isinstance(val, dict):
                gps = {GPSTAGS.get(k, k): v for k, v in val.items()}
                meta["GPS"] = gps
            else:
                try:
                    meta[str(tag)] = str(val)[:120]
                except Exception:
                    pass
    else:
        meta["EXIF"] = "none found"

    return meta


def read_pdf(path: Path) -> dict:
    from pypdf import PdfReader
    reader = PdfReader(path)
    info = reader.metadata or {}
    meta = {k.lstrip("/"): str(v) for k, v in info.items()}
    meta["pages"] = len(reader.pages)
    meta["encrypted"] = reader.is_encrypted
    return meta


def read_docx(path: Path) -> dict:
    from docx import Document
    doc = Document(path)
    p = doc.core_properties
    return {
        "author":            p.author,
        "last_modified_by":  p.last_modified_by,
        "title":             p.title,
        "subject":           p.subject,
        "description":       p.description,
        "keywords":          p.keywords,
        "category":          p.category,
        "created":           str(p.created),
        "modified":          str(p.modified),
        "revision":          p.revision,
    }


def read_audio(path: Path) -> dict:
    from mutagen import File
    from mutagen.id3 import ID3NoHeaderError
    audio = File(path)
    if audio is None:
        return {"error": "could not parse"}
    meta = {}
    for k, v in audio.tags.items() if audio.tags else []:
        try:
            meta[str(k)] = str(v)[:120]
        except Exception:
            pass
    if hasattr(audio, "info"):
        info = audio.info
        meta["duration_sec"] = round(getattr(info, "length", 0), 2)
        meta["bitrate"]      = getattr(info, "bitrate", "?")
    return meta


# ── REMOVE ───────────────────────────────────────────────────────────────────

def remove_image(path: Path) -> bool:
    from PIL import Image
    img = Image.open(path)
    clean = Image.new(img.mode, img.size)
    clean.putdata(img.getdata())
    clean.save(path)
    return True


def remove_pdf(path: Path) -> bool:
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({})
    tmp = path.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as f:
        writer.write(f)
    tmp.replace(path)
    return True


def remove_docx(path: Path) -> bool:
    from docx import Document
    doc = Document(path)
    p = doc.core_properties
    p.author = ""
    p.last_modified_by = ""
    p.title = ""
    p.subject = ""
    p.description = ""
    p.keywords = ""
    p.category = ""
    p.comments = ""
    doc.save(path)
    return True


def remove_audio(path: Path) -> bool:
    from mutagen import File
    audio = File(path)
    if audio is not None:
        audio.delete()
        audio.save()
    return True


def read_video(path: Path) -> dict:
    try:
        from pymediainfo import MediaInfo
        info = MediaInfo.parse(path)
        meta = {}
        for track in info.tracks:
            prefix = track.track_type.lower()
            for k, v in track.to_data().items():
                if v not in (None, "", "N/A") and k not in ("track_type", "kind_of_stream"):
                    meta[f"{prefix}.{k}"] = str(v)[:120]
        return meta
    except ImportError:
        # fallback: read raw atoms with struct if pymediainfo not installed
        return {"error": "install pymediainfo: pip install pymediainfo"}


def remove_video(path: Path) -> bool:
    """Strip metadata using ffmpeg (must be installed)."""
    import subprocess
    import shutil

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found — install it: pkg install ffmpeg (Termux) or apt install ffmpeg")

    tmp = path.with_name(path.stem + "_clean" + path.suffix)
    cmd = [
        "ffmpeg", "-y", "-i", str(path),
        "-map_metadata", "-1",   # strip all metadata
        "-c", "copy",            # no re-encode, just copy streams
        str(tmp)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-300:])
    tmp.replace(path)
    return True


# ── DISPATCH ─────────────────────────────────────────────────────────────────

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}
PDF_EXT   = {".pdf"}
DOCX_EXT  = {".docx"}
AUDIO_EXT = {".mp3", ".flac", ".ogg", ".m4a"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

ALL_EXT = IMAGE_EXT | PDF_EXT | DOCX_EXT | AUDIO_EXT | VIDEO_EXT

READERS = {
    **{e: read_image for e in IMAGE_EXT},
    **{e: read_pdf   for e in PDF_EXT},
    **{e: read_docx  for e in DOCX_EXT},
    **{e: read_audio for e in AUDIO_EXT},
    **{e: read_video for e in VIDEO_EXT},
}

REMOVERS = {
    **{e: remove_image for e in IMAGE_EXT},
    **{e: remove_pdf   for e in PDF_EXT},
    **{e: remove_docx  for e in DOCX_EXT},
    **{e: remove_audio for e in AUDIO_EXT},
    **{e: remove_video for e in VIDEO_EXT},
}


# ── DISPLAY ──────────────────────────────────────────────────────────────────

def print_meta(path: Path, meta: dict):
    print(f"\n{BOLD}{C}── {path.name}{RST}")
    if not meta:
        print(f"  {DIM}no metadata found{RST}")
        return
    max_k = max(len(k) for k in meta)
    for k, v in meta.items():
        val_color = W if v and str(v) not in ("", "None", "0") else DIM
        print(f"  {Y}{k:<{max_k}}{RST}  {val_color}{v}{RST}")


def banner():
    print(f"""
{BOLD}{W}┌─────────────────────────────────┐
│       Metadata Tool v1.0        │
│  extract · read · remove        │
└─────────────────────────────────┘{RST}""")


# ── MAIN ─────────────────────────────────────────────────────────────────────

def cmd_read(target: Path):
    files = [target] if target.is_file() else list(target.rglob("*"))
    files = [f for f in files if f.is_file() and f.suffix.lower() in ALL_EXT]

    if not files:
        print(f"{R}No supported files found.{RST}")
        return

    for f in files:
        ext = f.suffix.lower()
        reader = READERS.get(ext)
        try:
            meta = reader(f)
            print_meta(f, meta)
        except Exception as e:
            print(f"\n{R}Error reading {f.name}: {e}{RST}")

    print()


def cmd_remove(target: Path):
    files = [target] if target.is_file() else list(target.rglob("*"))
    files = [f for f in files if f.is_file() and f.suffix.lower() in ALL_EXT]

    if not files:
        print(f"{R}No supported files found.{RST}")
        return

    print(f"\n{DIM}Found {len(files)} file(s){RST}\n")
    ok = err = skip = 0

    for f in files:
        ext = f.suffix.lower()
        remover = REMOVERS.get(ext)
        if not remover:
            print(f"  {DIM}[~] skipped   {f.name}{RST}")
            skip += 1
            continue
        try:
            remover(f)
            print(f"  {G}[✓] cleaned   {RST}{f.name}")
            ok += 1
        except Exception as e:
            print(f"  {R}[✗] failed    {f.name} — {e}{RST}")
            err += 1

    print(f"\n{G}{ok} cleaned{RST}  {R}{err} failed{RST}  {DIM}{skip} skipped{RST}\n")


def usage():
    print(f"""
{Y}Usage:{RST}
  python metadata_tool.py read   <file or folder>
  python metadata_tool.py remove <file or folder>

{Y}Examples:{RST}
  python metadata_tool.py read   photo.jpg
  python metadata_tool.py read   ./downloads
  python metadata_tool.py remove photo.jpg
  python metadata_tool.py remove ./photos

{Y}Supported:{RST}
  Images   — jpg jpeg png webp tiff bmp
  PDF      — pdf
  Document — docx
  Audio    — mp3 flac ogg m4a
""")


def main():
    banner()

    if len(sys.argv) < 3:
        usage()
        sys.exit(1)

    cmd    = sys.argv[1].lower()
    target = Path(sys.argv[2])

    if not target.exists():
        print(f"{R}Not found: {target}{RST}")
        sys.exit(1)

    if cmd == "read":
        cmd_read(target)
    elif cmd == "remove":
        cmd_remove(target)
    else:
        print(f"{R}Unknown command: {cmd}{RST}")
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
