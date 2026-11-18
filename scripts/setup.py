"""Check (and optionally install) everything the skill needs, and prepare the Remotion workspace.

Usage:
  python setup.py                 # report what's there / missing; refresh the workspace's source files
  python setup.py --install       # also pip-install missing Python packages and run npm install
  python setup.py --install --with-whisper --with-youtube

The workspace lives in ~/.video-clipper/workspace (override with the VIDEO_CLIPPER_HOME env var).
"""
import argparse
import hashlib
import importlib
import shutil
import subprocess
import sys

from common import HOME, PUBLIC, RUNS, SKILL_DIR, WORKSPACE, utf8

REQUIRED = {  # import name -> pip spec
    "yt_dlp": "yt-dlp",
    "cv2": "opencv-python-headless<5",  # OpenCV 5 dropped the Haar face detector
    "numpy": "numpy",
}
WHISPER = {"faster_whisper": "faster-whisper"}
YOUTUBE = {
    "googleapiclient": "google-api-python-client",
    "google_auth_oauthlib": "google-auth-oauthlib",
    "google_auth_httplib2": "google-auth-httplib2",
}


def has_module(name):
    try:
        mod = importlib.import_module(name)
    except Exception:
        return False
    if name == "cv2":
        return hasattr(mod, "CascadeClassifier")
    return True


def pip_install(specs):
    if specs:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", *specs], check=False)


def sync_workspace(install):
    tpl = SKILL_DIR / "template"
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for sub in ("source", "assets"):
        (PUBLIC / sub).mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    for f in tpl.rglob("*"):
        if f.is_file():
            dest = WORKSPACE / f.relative_to(tpl)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
    pkg_hash = hashlib.sha1((tpl / "package.json").read_bytes()).hexdigest()
    stamp = WORKSPACE / ".installed"
    installed = (WORKSPACE / "node_modules").exists() and stamp.exists() and stamp.read_text() == pkg_hash
    if not installed and install:
        npm = shutil.which("npm")
        if not npm:
            print("  npm not found: install Node.js 18+ first")
            return False
        print("  running npm install in the workspace (one time, a few minutes)...", flush=True)
        r = subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=WORKSPACE)
        if r.returncode == 0:
            stamp.write_text(pkg_hash)
            installed = True
    return installed


def main():
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--with-whisper", action="store_true")
    ap.add_argument("--with-youtube", action="store_true")
    a = ap.parse_args()

    rows = []
    for tool in ("ffmpeg", "ffprobe", "node", "npm", "npx"):
        rows.append((tool, bool(shutil.which(tool)), "required"))

    groups = [(REQUIRED, "required")]
    if a.with_whisper or a.install:
        groups.append((WHISPER, "optional: transcribe videos without subtitles"))
    if a.with_youtube or a.install:
        groups.append((YOUTUBE, "optional: upload to YouTube"))
    for group, why in groups:
        missing = [spec for name, spec in group.items() if not has_module(name)]
        if a.install and missing and (group is REQUIRED or a.with_whisper and group is WHISPER
                                      or a.with_youtube and group is YOUTUBE):
            pip_install(missing)
        for name, spec in group.items():
            rows.append((spec, has_module(name), why))

    ws_ok = sync_workspace(a.install)
    rows.append((f"Remotion workspace ({WORKSPACE})", ws_ok, "required"))

    print("\nvideo-clipper setup")
    for name, ok, why in rows:
        print(f"  [{'ok' if ok else '--'}] {name}  ({why})")
    missing_required = [n for n, ok, why in rows if not ok and why == "required"]
    if missing_required:
        print("\nMissing required pieces:", ", ".join(missing_required))
        print("Run: python setup.py --install   (ffmpeg / Node.js must be installed separately)")
        sys.exit(1)
    print(f"\nReady. Working files go to {HOME}")


if __name__ == "__main__":
    main()
