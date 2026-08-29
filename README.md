# ffmpeg-sitter

![Version](https://img.shields.io/badge/version-2_in_development-00ffc8)
![Platform](https://img.shields.io/badge/platform-Windows_10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A small Windows installer and cleanup assistant for FFmpeg.

## Features

- **One-click install** - Download the current Gyan FFmpeg essentials build
- **Validated upgrades** - Test a staged replacement before touching the working installation
- **Automatic user PATH** - Add or remove FFmpeg without administrator access
- **Cleanup review** - Find likely standalone copies and inspect every proposed target
- **Recoverable quarantine** - Move confirmed targets with a restoration manifest instead of deleting them
- **Protected detection** - Leave copies bundled with applications such as OBS and Audacity alone
- **Code snippets** - Generate examples for pointing other applications at FFmpeg

## Install

No third-party Python packages are required. Python 3 with Tkinter is sufficient.

## Run

```powershell
python ffmpeg-sitter.py
```

## Usage

1. Select **Install FFmpeg** to install or safely replace FFmpeg under `%USERPROFILE%\ffmpeg`.
2. Select **Add to PATH** to make it available to newly opened terminals and applications.
3. Restart terminals that were already open.

The installation contains:

```text
%USERPROFILE%\ffmpeg\
  bin\
    ffmpeg.exe
    ffprobe.exe
    ffplay.exe
```

## Cleanup review

Select **Review other copies** to search the configured locations. ffmpeg-sitter displays every proposed standalone target before it acts. Application-bundled copies remain protected.

Confirmed targets move to:

```text
%LOCALAPPDATA%\ffmpeg-sitter\quarantine\<timestamp>\
```

Each quarantine contains `manifest.json`, mapping the original paths to their new locations. Nothing in cleanup review is permanently deleted.

## Development

Run the tests with:

```powershell
python -m unittest discover -s tests -v
```

Version 2 work is documented in [CHANGELOG.md](CHANGELOG.md).

## Build

```powershell
pyinstaller ffmpeg-sitter.spec
```

The configured download is the Gyan FFmpeg release essentials ZIP. Those builds currently target Windows 10 or later.

## License

MIT
