# Changelog

All notable ffmpeg-sitter changes are recorded here.

## Version 2 - in development

### Added

- A visible `2.0-dev` marker in the window title.
- A complete scrollable review of standalone cleanup targets.
- Recoverable quarantine under `%LOCALAPPDATA%\\ffmpeg-sitter\\quarantine`.
- A JSON manifest mapping every original path to its quarantine location.
- Automated tests for PATH manipulation, cleanup targeting, deduplication, and ZIP safety.

### Changed

- Downloads are extracted into an isolated temporary directory and validated before installation.
- FFmpeg must pass `ffmpeg -version` before it can replace the existing installation.
- The existing installation is retained as a backup until its validated replacement is in place.
- Background install and search workers communicate with Tkinter through a thread-safe queue.
- Cleanup searches and installs cannot run concurrently, and workers no longer prevent app shutdown.
- PATH entries use exact normalized comparisons while preserving the registry value type.
- “Obliterate” cleanup language and behavior were replaced with recoverable quarantine.
- Recovery snippets now use platform-aware PATH separators for Node.js and Ruby.

### Fixed

- Fixed failed or malformed downloads destroying an existing working installation.
- Fixed ZIP entries being able to escape the temporary extraction directory.
- Fixed duplicate search roots producing repeated cleanup targets.
- Fixed a loose `ffmpeg.exe` on the Desktop or in Downloads targeting the entire parent folder for deletion.
- Fixed similarly prefixed PATH entries causing false “already installed” results.
- Fixed a registry handle leak when FFmpeg was already present in PATH.
- Fixed background threads directly scheduling Tkinter work during shutdown.
