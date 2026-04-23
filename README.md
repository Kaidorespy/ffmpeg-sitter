# ffmpeg-sitter

![Status](https://img.shields.io/badge/status-100%25-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![License](https://img.shields.io/badge/license-MIT-green)

One-click FFmpeg installer for Windows. Downloads, extracts, adds to PATH. Done.

## The Problem

Every time you set up a new machine:
1. Google "ffmpeg download"
2. Find the right build
3. Download 80MB zip
4. Extract somewhere
5. Add to PATH manually
6. Restart terminals
7. Repeat when you forget where you put it

## The Solution

Click a button. FFmpeg is installed and in your PATH.

## Features

- **One-click install** - Downloads latest FFmpeg release
- **Automatic PATH** - Adds to user PATH, no admin needed
- **Obliterate mode** - Find and delete stray FFmpeg copies cluttering your system
- **Protected detection** - Won't touch FFmpeg bundled with OBS, Audacity, etc.
- **Code snippets** - Generates copy-paste code to point apps at FFmpeg

## Install

No dependencies - just Python 3 and tkinter (included with Python).

## Run

```bash
python ffmpeg-sitter.py
```

## Usage

1. Click "Install FFmpeg" - downloads to `~/ffmpeg`
2. Click "Add to PATH" - makes it available everywhere
3. Restart any open terminals

### Cleanup Mode

Click "Obliterate other copies" to:
- Search your system for standalone FFmpeg installs
- Safely delete duplicates (protects app-bundled copies)
- Show code snippets to update any broken references

## Where It Installs

```
~/ffmpeg/
  bin/
    ffmpeg.exe
    ffprobe.exe
    ffplay.exe
```

## License

MIT
