import os
import sys
import platform
import requests
import zipfile
import tempfile
import subprocess
from app.config import APP_VERSION, VERSION_URL


def _parse_version(v):
    return tuple(int(x) for x in v.strip().split("."))


def check_for_update() -> dict:
    try:
        # VERSION_URL is empty for now — skip silently
        if not VERSION_URL:
            return {"available": False}

        r      = requests.get(VERSION_URL, timeout=5)
        data   = r.json()
        latest = data["version"]

        if _parse_version(latest) > _parse_version(APP_VERSION):
            system = platform.system()
            url    = data["windows"]["url"] if system == "Windows" else data["macos"]["url"]
            return {
                "available":     True,
                "version":       latest,
                "release_notes": data.get("release_notes", ""),
                "url":           url
            }

        return {"available": False}

    except Exception:
        # Never crash the app because of update check
        return {"available": False}


def download_and_install(url: str, version: str, progress_cb=None):
    system = platform.system()
    suffix = ".exe" if system == "Windows" else ".zip"
    tmp    = os.path.join(tempfile.gettempdir(), f"Visara-{version}{suffix}")

    # Download file with progress
    r     = requests.get(url, stream=True, timeout=120)
    total = int(r.headers.get("content-length", 0))
    done  = 0

    with open(tmp, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
            done += len(chunk)
            if progress_cb and total:
                progress_cb(int(done / total * 100))

    # Install based on platform
    if system == "Windows":
        subprocess.Popen([tmp, "/VERYSILENT", "/NORESTART"])
        sys.exit(0)

    elif system == "Darwin":
        _install_macos(tmp)


def _install_macos(zip_path: str):
    from pathlib import Path

    tmp_dir  = tempfile.mkdtemp()
    exe      = sys.executable
    app_path = str(Path(exe).parent.parent.parent)  # Visara.app

    # Extract zip
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(tmp_dir)

    # Find .app inside extracted folder
    new_app = next(
        (os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)
         if f.endswith(".app")),
        None
    )
    if not new_app:
        return

    # Shell script that replaces app after quit
    script = f"""#!/bin/bash
sleep 2
rm -rf "{app_path}"
cp -R "{new_app}" "{app_path}"
chmod -R 755 "{app_path}"
xattr -cr "{app_path}"
open "{app_path}"
rm -rf "{tmp_dir}" "{zip_path}"
"""
    script_path = os.path.join(tempfile.gettempdir(), "visara_update.sh")
    with open(script_path, "w") as f:
        f.write(script)

    os.chmod(script_path, 0o755)
    subprocess.Popen(
        ["bash", script_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    sys.exit(0)