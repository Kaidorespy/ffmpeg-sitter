import os
import shutil
import zipfile
import tempfile
import threading
import queue
import json
import tkinter as tk
from tkinter import messagebox
import urllib.request
import winreg
import subprocess
from datetime import datetime
from pathlib import Path

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
INSTALL_DIR = os.path.expanduser("~/ffmpeg")
BIN_DIR = os.path.join(INSTALL_DIR, "bin")
APP_VERSION = "2.0-dev"
QUARANTINE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ffmpeg-sitter" / "quarantine"

# Places ffmpeg likes to hide (standalone copies)
SEARCH_LOCATIONS = [
    os.path.expanduser("~"),  # Start from user home - catch everything
    "C:/ffmpeg",
    "C:/tools",
    "C:/Program Files/ffmpeg",
    "C:/Program Files (x86)/ffmpeg",
]

# Apps that bundle ffmpeg - DON'T TOUCH
PROTECTED_APPS = {
    'obs', 'obs-studio', 'audacity', 'handbrake', 'vlc', 'imagemagick',
    'kdenlive', 'shotcut', 'davinci', 'resolve', 'premiere', 'vegas',
    'blender', 'gimp', 'krita', 'openshot', 'lightworks', 'hitfilm',
    'streamlabs', 'xsplit', 'nvidia', 'amd', 'intel', 'realtek',
    'python', 'anaconda', 'miniconda', 'conda', 'pip', 'node_modules',
    'appdata', 'programdata', 'windows', 'system32', 'syswow64',
}


def normalize_path(path):
    """Normalize a PATH entry for exact, case-insensitive comparisons."""
    path = os.path.expandvars(str(path).strip().strip('"'))
    return os.path.normcase(os.path.normpath(path)) if path else ""


def split_path(path_value):
    return [part.strip() for part in path_value.split(';') if part.strip()]


def path_contains(path_value, entry):
    target = normalize_path(entry)
    return any(normalize_path(part) == target for part in split_path(path_value))


def add_path_entry(path_value, entry):
    parts = split_path(path_value)
    if not path_contains(path_value, entry):
        parts.append(entry)
    return ';'.join(parts)


def remove_path_entry(path_value, entry):
    target = normalize_path(entry)
    return ';'.join(part for part in split_path(path_value) if normalize_path(part) != target)


def safe_zip_members(zf):
    """Reject archive entries that could escape the extraction directory."""
    for member in zf.infolist():
        path = Path(member.filename)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError(f"unsafe archive path: {member.filename}")
    return zf.infolist()


def is_within(path, parent):
    try:
        return os.path.commonpath([normalize_path(path), normalize_path(parent)]) == normalize_path(parent)
    except ValueError:
        return False


def deduplicate_paths(paths):
    """Return unique normalized paths without children of another target."""
    unique = sorted({normalize_path(path): os.path.normpath(path) for path in paths}.values(), key=len)
    result = []
    for path in unique:
        normalized = normalize_path(path)
        if not any(is_within(normalized, parent) for parent in result):
            result.append(path)
    return result


def cleanup_target(location):
    """Choose the narrowest safe target for a discovered FFmpeg executable."""
    location = Path(location)
    if 'ffmpeg' in location.name.lower():
        target = location
    elif 'ffmpeg' in location.parent.name.lower():
        target = location.parent
    else:
        target = location / 'ffmpeg.exe'

    forbidden = {normalize_path(Path.home()), normalize_path(Path(target.anchor)), normalize_path(INSTALL_DIR)}
    return None if normalize_path(target) in forbidden else str(target)

class FFmpegSitter:
    def __init__(self):
        self.ui_queue = queue.Queue()
        self.closing = False
        self.root = tk.Tk()
        self.root.title(f"ffmpeg-sitter {APP_VERSION}")
        self.root.configure(bg='#1a1a2e')
        self.root.geometry("420x250")
        self.root.resizable(False, False)

        # Title
        tk.Label(
            self.root,
            text="ffmpeg-sitter",
            font=("Consolas", 18, "bold"),
            bg='#1a1a2e',
            fg='#00ffc8'
        ).pack(pady=15)

        # Status
        self.status = tk.Label(
            self.root,
            text="checking for ffmpeg...",
            font=("Consolas", 10),
            bg='#1a1a2e',
            fg='#888',
            wraplength=390
        )
        self.status.pack(pady=5)

        # Buttons frame
        self.btn_frame = tk.Frame(self.root, bg='#1a1a2e')
        self.btn_frame.pack(pady=15)

        # Install button
        self.install_btn = tk.Button(
            self.btn_frame,
            text="install ffmpeg",
            font=("Consolas", 11, "bold"),
            bg='#00ffc8',
            fg='#1a1a2e',
            activebackground='#00d4aa',
            relief='flat',
            command=self.install,
            cursor='hand2',
            width=14
        )
        self.install_btn.pack(side='left', padx=5)

        # Add to PATH button
        self.path_btn = tk.Button(
            self.btn_frame,
            text="add to PATH",
            font=("Consolas", 11, "bold"),
            bg='#16213e',
            fg='#00ffc8',
            activebackground='#1a1a3e',
            relief='flat',
            command=self.add_to_path,
            cursor='hand2',
            width=14
        )
        self.path_btn.pack(side='left', padx=5)

        # Bottom buttons frame (destructive actions)
        self.bottom_frame = tk.Frame(self.root, bg='#1a1a2e')
        self.bottom_frame.pack(pady=5)

        # PURGE button
        self.purge_btn = tk.Button(
            self.bottom_frame,
            text="review other copies",
            font=("Consolas", 9),
            bg='#ff4757',
            fg='white',
            activebackground='#ff6b7a',
            relief='flat',
            command=self.purge,
            cursor='hand2'
        )
        self.purge_btn.pack(side='left', padx=5)

        # UNINSTALL button
        self.uninstall_btn = tk.Button(
            self.bottom_frame,
            text="uninstall ffmpeg",
            font=("Consolas", 9),
            bg='#ff4757',
            fg='white',
            activebackground='#ff6b7a',
            relief='flat',
            command=self.uninstall,
            cursor='hand2'
        )
        self.uninstall_btn.pack(side='left', padx=5)

        # Location label
        self.location = tk.Label(
            self.root,
            text="",
            font=("Consolas", 9),
            bg='#1a1a2e',
            fg='#666',
            wraplength=390
        )
        self.location.pack(pady=5)

        # Check current state
        self.root.after(100, self.check_status)
        self.root.after(50, self._process_ui_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.root.mainloop()

    def _process_ui_queue(self):
        try:
            while True:
                action, payload = self.ui_queue.get_nowait()
                if action == 'status':
                    text, color = payload
                    self.status.config(text=text, fg=color)
                elif action == 'install_done':
                    self._install_done(*payload)
                elif action == 'purge_results':
                    self._show_purge_results(*payload)
        except queue.Empty:
            pass
        if not self.closing:
            self.root.after(50, self._process_ui_queue)

    def close(self):
        self.closing = True
        self.root.destroy()

    def check_status(self):
        # Check if in PATH
        ffmpeg_in_path = shutil.which('ffmpeg')

        # Check our install location
        our_ffmpeg = os.path.join(BIN_DIR, "ffmpeg.exe")
        have_ours = os.path.exists(our_ffmpeg)

        if ffmpeg_in_path:
            self.status.config(text="ffmpeg found in PATH", fg='#00ffc8')
            self.location.config(text=f"location: {ffmpeg_in_path}")
            self.install_btn.config(text="reinstall", bg='#16213e', fg='#00ffc8')
        elif have_ours:
            self.status.config(text="ffmpeg installed (not in PATH)", fg='#ffa502')
            self.location.config(text=f"location: {BIN_DIR}")
            self.install_btn.config(text="reinstall", bg='#16213e', fg='#00ffc8')
            self.path_btn.config(bg='#00ffc8', fg='#1a1a2e')
        else:
            self.status.config(text="ffmpeg not found", fg='#ff4757')
            self.location.config(text="click install to download")

    def install(self):
        self.install_btn.config(state='disabled', text='downloading...')
        self.status.config(text="downloading ffmpeg (~100MB)...", fg='#ffa502')
        self.purge_btn.config(state='disabled')
        self.uninstall_btn.config(state='disabled')
        thread = threading.Thread(target=self._do_install, daemon=True)
        thread.start()

    def _do_install(self):
        try:
            with tempfile.TemporaryDirectory(prefix='ffmpeg-sitter-') as temp_dir:
                temp_path = Path(temp_dir)
                archive_path = temp_path / 'ffmpeg.zip'
                extract_dir = temp_path / 'extracted'

                def report(block, block_size, total):
                    downloaded = block * block_size
                    pct = min(100, int(downloaded * 100 / total)) if total > 0 else 0
                    self.ui_queue.put(('status', (f"downloading... {pct}%", '#ffa502')))

                urllib.request.urlretrieve(FFMPEG_URL, archive_path, report)
                self.ui_queue.put(('status', ("validating download...", '#ffa502')))

                with zipfile.ZipFile(archive_path, 'r') as zf:
                    members = safe_zip_members(zf)
                    zf.extractall(extract_dir, members=members)

                bin_candidates = [
                    path.parent for path in extract_dir.rglob('ffmpeg.exe')
                    if path.parent.joinpath('ffprobe.exe').exists()
                ]
                if not bin_candidates:
                    raise RuntimeError("archive did not contain ffmpeg.exe and ffprobe.exe")

                staged_root = bin_candidates[0].parent
                check = subprocess.run(
                    [str(bin_candidates[0] / 'ffmpeg.exe'), '-version'],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=15
                )
                if check.returncode != 0:
                    raise RuntimeError("downloaded ffmpeg failed its version check")

                backup_dir = Path(f"{INSTALL_DIR}.backup")
                install_dir = Path(INSTALL_DIR)
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                if install_dir.exists():
                    os.replace(install_dir, backup_dir)
                try:
                    shutil.move(str(staged_root), install_dir)
                except Exception:
                    if backup_dir.exists() and not install_dir.exists():
                        os.replace(backup_dir, install_dir)
                    raise
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)

            self.ui_queue.put(('install_done', (True, None)))

        except Exception as e:
            self.ui_queue.put(('install_done', (False, str(e))))

    def _install_done(self, success, error=None):
        self.purge_btn.config(state='normal')
        self.uninstall_btn.config(state='normal')
        if success:
            self.status.config(text="ffmpeg installed!", fg='#00ffc8')
            self.location.config(text=f"location: {BIN_DIR}")
            self.install_btn.config(state='normal', text='reinstall', bg='#16213e', fg='#00ffc8')
            self.path_btn.config(bg='#00ffc8', fg='#1a1a2e')
        else:
            self.status.config(text=f"failed: {error[:30]}", fg='#ff4757')
            self.install_btn.config(state='normal', text='retry')

    def add_to_path(self):
        try:
            if not os.path.exists(BIN_DIR):
                messagebox.showerror("Error", "Install ffmpeg first!")
                return

            # Get current user PATH
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
                0,
                winreg.KEY_ALL_ACCESS
            )
            try:
                try:
                    current_path, value_type = winreg.QueryValueEx(key, "PATH")
                except FileNotFoundError:
                    current_path, value_type = "", winreg.REG_EXPAND_SZ

                if path_contains(current_path, BIN_DIR):
                    messagebox.showinfo("Already done", "ffmpeg is already in PATH!")
                    return

                winreg.SetValueEx(key, "PATH", 0, value_type, add_path_entry(current_path, BIN_DIR))
            finally:
                winreg.CloseKey(key)

            # Notify system of change
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x1A
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")

            self.status.config(text="added to PATH! restart terminals", fg='#00ffc8')
            self.path_btn.config(bg='#16213e', fg='#00ffc8', text="done!")

        except Exception as e:
            messagebox.showerror("ffmpeg-sitter", f"Failed to modify PATH: {e}")

    def uninstall(self):
        # Check if there's anything to uninstall
        have_ours = os.path.exists(os.path.join(BIN_DIR, "ffmpeg.exe"))

        if not have_ours:
            messagebox.showinfo("ffmpeg-sitter", "Nothing to uninstall.\n\nNo ffmpeg found at ~/ffmpeg")
            return

        # Confirm
        result = messagebox.askyesno(
            "ffmpeg-sitter // uninstall",
            "This will:\n\n"
            f"• Delete {INSTALL_DIR}\n"
            "• Remove ffmpeg from your PATH\n\n"
            "Continue?",
            icon='warning'
        )

        if not result:
            return

        errors = []

        # Remove from PATH first
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
                0,
                winreg.KEY_ALL_ACCESS
            )

            try:
                current_path, _ = winreg.QueryValueEx(key, "PATH")

                new_path = remove_path_entry(current_path, BIN_DIR)

                if new_path != current_path:
                    winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)

                    # Notify system of change
                    import ctypes
                    HWND_BROADCAST = 0xFFFF
                    WM_SETTINGCHANGE = 0x1A
                    ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment")

            except FileNotFoundError:
                pass  # No PATH set, nothing to remove
            finally:
                winreg.CloseKey(key)

        except Exception as e:
            errors.append(f"PATH removal: {e}")

        # Delete the ffmpeg folder
        try:
            shutil.rmtree(INSTALL_DIR)
        except Exception as e:
            errors.append(f"Folder deletion: {e}")

        # Update UI
        if errors:
            self.status.config(text="partially uninstalled (see errors)", fg='#ffa502')
            messagebox.showwarning(
                "ffmpeg-sitter",
                "Uninstall completed with errors:\n\n" + "\n".join(errors)
            )
        else:
            self.status.config(text="ffmpeg uninstalled", fg='#00ffc8')
            self.location.config(text="")
            messagebox.showinfo("ffmpeg-sitter", "ffmpeg has been uninstalled.\n\nRestart any open terminals.")

        # Refresh state
        self.install_btn.config(text="install ffmpeg", bg='#00ffc8', fg='#1a1a2e')
        self.path_btn.config(text="add to PATH", bg='#16213e', fg='#00ffc8')
        self.check_status()

    def purge(self):
        self.purge_btn.config(state='disabled', text='hunting...')
        self.status.config(text="searching for ffmpeg copies...", fg='#ffa502')
        self.install_btn.config(state='disabled')
        self.uninstall_btn.config(state='disabled')
        thread = threading.Thread(target=self._find_all_ffmpeg, daemon=True)
        thread.start()

    def _is_standalone_ffmpeg(self, path):
        """Check if this looks like a standalone ffmpeg install, not bundled"""
        path_lower = path.lower()

        # Check if path contains any protected app names
        for protected in PROTECTED_APPS:
            if protected in path_lower:
                return False

        # Check if this is in a folder that looks like ffmpeg
        # (standalone installs are usually in folders named ffmpeg-something)
        path_parts = path_lower.replace('\\', '/').split('/')
        for part in path_parts:
            if 'ffmpeg' in part:
                return True

        # If it's directly in Downloads/Desktop with ffmpeg.exe, probably standalone
        if any(loc.lower() in path_lower for loc in ['downloads', 'desktop']):
            return True

        return False

    def _find_all_ffmpeg(self):
        found_safe = []  # Definitely standalone
        found_risky = []  # Might be bundled
        searched = 0

        for base in SEARCH_LOCATIONS:
            if not os.path.exists(base):
                continue

            try:
                for root, dirs, files in os.walk(base):
                    searched += 1
                    if searched % 500 == 0:
                        self.ui_queue.put(('status', (f"searched {searched} folders...", '#ffa502')))

                    # Skip our install location
                    if is_within(root, INSTALL_DIR) or is_within(root, QUARANTINE_DIR):
                        dirs.clear()
                        continue

                    # Look for ffmpeg.exe
                    if 'ffmpeg.exe' in files:
                        if self._is_standalone_ffmpeg(root):
                            target = cleanup_target(root)
                            if target:
                                found_safe.append(target)
                        else:
                            found_risky.append(root)

                    # Don't go too deep
                    depth = root.replace(base, '').count(os.sep)
                    if depth > 5:
                        dirs.clear()

                    # Skip obvious system folders
                    dirs[:] = [d for d in dirs if d.lower() not in PROTECTED_APPS]

            except PermissionError:
                continue
            except Exception:
                continue

        self.ui_queue.put(('purge_results', (deduplicate_paths(found_safe), deduplicate_paths(found_risky))))

    def _show_purge_results(self, found_safe, found_risky):
        self.purge_btn.config(state='normal', text='review other copies')
        self.install_btn.config(state='normal')
        self.uninstall_btn.config(state='normal')

        if not found_safe and not found_risky:
            self.status.config(text="no other ffmpeg copies found!", fg='#00ffc8')
            messagebox.showinfo(
                "ffmpeg-sitter",
                "No other ffmpeg installations found.\n\nYou're already tidy."
            )
            return

        if not found_safe:
            self.status.config(text=f"found {len(found_risky)} bundled (protected)", fg='#ffa502')
            messagebox.showinfo(
                "ffmpeg-sitter",
                f"Found {len(found_risky)} ffmpeg copies, but they all look like\n"
                "they belong to other programs (OBS, Audacity, etc).\n\n"
                "Leaving them alone."
            )
            return

        review = tk.Toplevel(self.root)
        review.title("ffmpeg-sitter // cleanup review")
        review.configure(bg='#1a1a2e')
        review.geometry("680x400")
        review.transient(self.root)
        review.grab_set()

        tk.Label(
            review,
            text=f"Review {len(found_safe)} standalone target{'s' if len(found_safe) != 1 else ''}",
            font=("Consolas", 12, "bold"), bg='#1a1a2e', fg='#ffa502'
        ).pack(pady=(15, 5))
        tk.Label(
            review,
            text=f"{len(found_risky)} app-bundled location{'s' if len(found_risky) != 1 else ''} protected",
            font=("Consolas", 9), bg='#1a1a2e', fg='#888'
        ).pack(pady=(0, 10))

        list_frame = tk.Frame(review, bg='#1a1a2e')
        list_frame.pack(fill='both', expand=True, padx=15)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        targets = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, font=("Consolas", 9),
            bg='#0d1117', fg='#ffffff', selectbackground='#16213e'
        )
        targets.pack(fill='both', expand=True)
        scrollbar.config(command=targets.yview)
        for path in found_safe:
            targets.insert('end', path)

        tk.Label(
            review,
            text="Nothing is deleted: targets move to a dated quarantine folder.",
            font=("Consolas", 9), bg='#1a1a2e', fg='#00ffc8'
        ).pack(pady=8)
        buttons = tk.Frame(review, bg='#1a1a2e')
        buttons.pack(pady=(0, 15))
        tk.Button(
            buttons, text="move to quarantine", font=("Consolas", 10, "bold"),
            bg='#ffa502', fg='#1a1a2e', relief='flat', cursor='hand2',
            command=lambda: (review.destroy(), self._do_purge(found_safe))
        ).pack(side='left', padx=5)
        tk.Button(
            buttons, text="cancel", font=("Consolas", 10), bg='#16213e',
            fg='#ffffff', relief='flat', cursor='hand2', command=review.destroy
        ).pack(side='left', padx=5)

    def _do_purge(self, locations):
        moved = 0
        failed = 0
        quarantine = QUARANTINE_DIR / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        quarantine.mkdir(parents=True, exist_ok=False)
        manifest = []

        for index, loc in enumerate(locations, start=1):
            try:
                target = Path(loc)
                if not target.exists():
                    raise FileNotFoundError(target)
                destination = quarantine / f"{index:02d}-{target.name}"
                shutil.move(str(target), destination)
                manifest.append({"original": str(target), "quarantined": str(destination)})
                moved += 1
            except Exception as error:
                manifest.append({"original": str(loc), "error": str(error)})
                failed += 1

        (quarantine / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

        if failed:
            self.status.config(
                text=f"quarantined {moved}, {failed} failed",
                fg='#ffa502'
            )
        else:
            self.status.config(
                text=f"quarantined {moved} copies safely",
                fg='#00ffc8'
            )

        if moved > 0:
            self._show_recovery_info(quarantine)

    def _show_recovery_info(self, quarantine=None):
        """Show copyable code snippets for pointing apps to the new ffmpeg"""
        win = tk.Toplevel(self.root)
        win.title("ffmpeg-sitter // recovery")
        win.configure(bg='#1a1a2e')
        win.geometry("550x460")
        win.resizable(False, False)

        tk.Label(
            win,
            text="some apps might need directions",
            font=("Consolas", 12, "bold"),
            bg='#1a1a2e',
            fg='#ffa502'
        ).pack(pady=10)

        tk.Label(
            win,
            text="point them here:",
            font=("Consolas", 10),
            bg='#1a1a2e',
            fg='#888'
        ).pack()

        # Path display with copy button
        path_frame = tk.Frame(win, bg='#1a1a2e')
        path_frame.pack(pady=5, padx=20, fill='x')

        path_var = tk.StringVar(value=BIN_DIR)
        path_entry = tk.Entry(
            path_frame,
            textvariable=path_var,
            font=("Consolas", 10, "bold"),
            bg='#0d1117',
            fg='#ffffff',
            relief='flat',
            state='readonly',
            width=45,
            readonlybackground='#0d1117'
        )
        path_entry.pack(side='left', padx=(0, 5))

        def copy_path():
            win.clipboard_clear()
            win.clipboard_append(BIN_DIR)
            copy_btn.config(text="copied!")
            win.after(1500, lambda: copy_btn.config(text="copy"))

        copy_btn = tk.Button(
            path_frame,
            text="copy",
            font=("Consolas", 9),
            bg='#00ffc8',
            fg='#1a1a2e',
            relief='flat',
            command=copy_path,
            cursor='hand2'
        )
        copy_btn.pack(side='left')

        # Code snippets
        tk.Label(
            win,
            text="or paste into your code:",
            font=("Consolas", 10),
            bg='#1a1a2e',
            fg='#888'
        ).pack(pady=(15, 5))

        snippets = tk.Text(
            win,
            font=("Consolas", 9),
            bg='#16213e',
            fg='#00ffc8',
            relief='flat',
            height=14,
            width=60,
            wrap='none'
        )
        snippets.pack(padx=20, pady=5)

        bin_dir_unix = BIN_DIR.replace('\\', '/')
        rust_line = '.env("PATH", format!("' + bin_dir_unix + ';{}", env::var("PATH").unwrap()))'
        code = f'''# Python
import os
os.environ["PATH"] = r"{BIN_DIR}" + os.pathsep + os.environ["PATH"]

# Node.js
process.env.PATH = "{bin_dir_unix}" + require("path").delimiter + process.env.PATH;

# Ruby
ENV["PATH"] = "{bin_dir_unix}" + File::PATH_SEPARATOR + ENV["PATH"]

# Rust (std::process::Command)
{rust_line}

# Bash / Terminal (add to .bashrc)
export PATH="{bin_dir_unix}:$PATH"

# PowerShell (add to $PROFILE)
$env:PATH = "{BIN_DIR};" + $env:PATH'''

        snippets.insert('1.0', code)
        snippets.config(state='disabled')

        tk.Label(
            win,
            text="(or just click 'add to PATH' and restart your apps)",
            font=("Consolas", 9),
            bg='#1a1a2e',
            fg='#666'
        ).pack(pady=10)

        if quarantine:
            tk.Label(
                win,
                text=f"quarantine manifest: {quarantine / 'manifest.json'}",
                font=("Consolas", 8), bg='#1a1a2e', fg='#888', wraplength=510
            ).pack(pady=(0, 8))


if __name__ == '__main__':
    FFmpegSitter()
