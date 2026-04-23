import os
import shutil
import zipfile
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox
import urllib.request
import winreg
import subprocess

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
INSTALL_DIR = os.path.expanduser("~/ffmpeg")
BIN_DIR = os.path.join(INSTALL_DIR, "bin")

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

class FFmpegSitter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ffmpeg-sitter")
        self.root.configure(bg='#1a1a2e')
        self.root.geometry("400x230")
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
            fg='#888'
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
            text="obliterate other copies",
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
            fg='#666'
        )
        self.location.pack(pady=5)

        # Check current state
        self.root.after(100, self.check_status)

        self.root.mainloop()

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
        self.status.config(text="downloading ffmpeg (~80MB)...", fg='#ffa502')
        thread = threading.Thread(target=self._do_install)
        thread.start()

    def _do_install(self):
        try:
            # Create temp file for download
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                tmp_path = tmp.name

            # Download with progress
            def report(block, block_size, total):
                downloaded = block * block_size
                pct = min(100, int(downloaded * 100 / total)) if total > 0 else 0
                self.root.after(0, lambda: self.status.config(
                    text=f"downloading... {pct}%", fg='#ffa502'
                ))

            urllib.request.urlretrieve(FFMPEG_URL, tmp_path, report)

            self.root.after(0, lambda: self.status.config(text="extracting...", fg='#ffa502'))

            # Clean old install
            if os.path.exists(INSTALL_DIR):
                shutil.rmtree(INSTALL_DIR)

            # Extract
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                # Find the inner folder name (e.g., ffmpeg-7.0-essentials_build)
                inner_folder = zf.namelist()[0].split('/')[0]
                zf.extractall(tempfile.gettempdir())

            # Move to final location
            extracted = os.path.join(tempfile.gettempdir(), inner_folder)
            shutil.move(extracted, INSTALL_DIR)

            # Clean up
            os.unlink(tmp_path)

            self.root.after(0, lambda: self._install_done(True))

        except Exception as e:
            self.root.after(0, lambda: self._install_done(False, str(e)))

    def _install_done(self, success, error=None):
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
                current_path, _ = winreg.QueryValueEx(key, "PATH")
            except FileNotFoundError:
                current_path = ""

            # Check if already in PATH
            if BIN_DIR.lower() in current_path.lower():
                messagebox.showinfo("Already done", "ffmpeg is already in PATH!")
                return

            # Add to PATH
            new_path = f"{current_path};{BIN_DIR}" if current_path else BIN_DIR
            winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
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

                # Remove our bin dir from PATH
                path_parts = current_path.split(';')
                new_parts = [p for p in path_parts if p.lower() != BIN_DIR.lower()]
                new_path = ';'.join(new_parts)

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
        thread = threading.Thread(target=self._find_all_ffmpeg)
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
                        self.root.after(0, lambda s=searched: self.status.config(
                            text=f"searched {s} folders...", fg='#ffa502'
                        ))

                    # Skip our install location
                    if os.path.normpath(root).startswith(os.path.normpath(INSTALL_DIR)):
                        continue

                    # Look for ffmpeg.exe
                    if 'ffmpeg.exe' in files:
                        if self._is_standalone_ffmpeg(root):
                            found_safe.append(root)
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

        self.root.after(0, lambda: self._show_purge_results(found_safe, found_risky))

    def _show_purge_results(self, found_safe, found_risky):
        self.purge_btn.config(state='normal', text='obliterate all other copies')

        if not found_safe and not found_risky:
            self.status.config(text="no other ffmpeg copies found!", fg='#00ffc8')
            messagebox.showinfo(
                "ffmpeg-sitter",
                "No other ffmpeg installations found.\n\nYou're already tidy."
            )
            return

        # Build message
        msg = "ffmpeg-sitter found:\n\n"

        if found_safe:
            msg += f"STANDALONE ({len(found_safe)}) - safe to delete:\n"
            msg += "\n".join(f"  • {p}" for p in found_safe[:5])
            if len(found_safe) > 5:
                msg += f"\n  ... and {len(found_safe) - 5} more"
            msg += "\n\n"

        if found_risky:
            msg += f"BUNDLED ({len(found_risky)}) - protected:\n"
            msg += "\n".join(f"  • {p}" for p in found_risky[:3])
            if len(found_risky) > 3:
                msg += f"\n  ... and {len(found_risky) - 3} more"
            msg += "\n\n"

        if not found_safe:
            self.status.config(text=f"found {len(found_risky)} bundled (protected)", fg='#ffa502')
            messagebox.showinfo(
                "ffmpeg-sitter",
                f"Found {len(found_risky)} ffmpeg copies, but they all look like\n"
                "they belong to other programs (OBS, Audacity, etc).\n\n"
                "Leaving them alone."
            )
            return

        result = messagebox.askyesno(
            "ffmpeg-sitter // obliterate?",
            f"{msg}"
            f"DELETE THE {len(found_safe)} STANDALONE COPIES?\n\n"
            "(Your ~/ffmpeg and bundled copies are protected)",
            icon='warning'
        )

        if result:
            self._do_purge(found_safe)

    def _do_purge(self, locations):
        deleted = 0
        failed = 0

        for loc in locations:
            try:
                # Go up to find the ffmpeg folder root
                # (might be in a 'bin' subfolder)
                target = loc
                parent = os.path.dirname(loc)
                parent_name = os.path.basename(parent).lower()

                if 'ffmpeg' in parent_name:
                    target = parent

                shutil.rmtree(target)
                deleted += 1
            except Exception:
                failed += 1

        if failed:
            self.status.config(
                text=f"obliterated {deleted}, {failed} survived",
                fg='#ffa502'
            )
        else:
            self.status.config(
                text=f"obliterated {deleted} copies. cleansed.",
                fg='#00ffc8'
            )

        # Show the "fix your apps" dialog
        if deleted > 0:
            self._show_recovery_info()

    def _show_recovery_info(self):
        """Show copyable code snippets for pointing apps to the new ffmpeg"""
        win = tk.Toplevel(self.root)
        win.title("ffmpeg-sitter // recovery")
        win.configure(bg='#1a1a2e')
        win.geometry("550x420")
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
process.env.PATH = "{bin_dir_unix}:" + process.env.PATH;

# Ruby
ENV["PATH"] = "{bin_dir_unix}" + ":" + ENV["PATH"]

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


if __name__ == '__main__':
    FFmpegSitter()
