"""Shared helpers for the video-clipper scripts."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("VIDEO_CLIPPER_HOME", Path.home() / ".video-clipper"))
WORKSPACE = HOME / "workspace"          # Remotion project (made by setup.py)
PUBLIC = WORKSPACE / "public"           # everything a clip plays must live under here
RUNS = HOME / "runs"                    # per-video working files (transcripts, shots, clip data)


def utf8():
    """Windows consoles default to cp1252; Hindi and emoji would crash print()."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def slug(text, n=40):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(text)).strip("-").lower()
    return s[:n].strip("-") or "clip"


DATA_DIR = "_data"  # inside each video's output folder: post files, check sheets, render results


def safe_name(text, n=80):
    """A readable file/folder name from a title: keeps letters (any script), digits, spaces and plain punctuation;
    drops emoji and the characters Windows/macOS forbid in names."""
    import unicodedata
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(text))
    t = re.sub(r"\s*(\.{2,}|…)\s*", " ", t)  # "INCREDIBLE.." / "wait…" read badly in a file name
    t = "".join(ch for ch in t if ord(ch) <= 0xFFFF and unicodedata.category(ch) not in ("So", "Sk", "Cs", "Co")
                and ch not in "️‍")
    t = re.sub(r"\s+", " ", t).strip().rstrip(". ")
    return t[:n].rstrip(". ") or "clip"


def video_folder(info):
    """Output folder name for a source video: 'Title (Channel)'."""
    title = info.get("title") or info.get("id") or "video"
    who = info.get("channel") or info.get("uploader")
    return safe_name(f"{title} ({who})" if who else title, 90)


def output_size(settings):
    """(width, height) of the finished clip from orientation + resolution (short side)."""
    r = int(settings.get("resolution", 1080) or 1080)
    o = settings.get("orientation", "vertical")
    even = lambda v: int(round(v / 2) * 2)
    if o == "horizontal":
        return even(r * 16 / 9), r
    if o == "square":
        return r, r
    if o == "portrait":
        return r, even(r * 5 / 4)
    return r, even(r * 16 / 9)


def need(cmd):
    path = shutil.which(cmd)
    if not path:
        sys.exit(f"'{cmd}' was not found on PATH. Run scripts/setup.py to see what's missing.")
    return path


def run(cmd, **kw):
    """Run a command, echoing it; raise with its output on failure."""
    print("$ " + " ".join(str(c) for c in cmd), flush=True)
    res = subprocess.run([str(c) for c in cmd], **kw)
    if res.returncode != 0:
        sys.exit(f"command failed ({res.returncode}): {cmd[0]}")
    return res


def probe(path):
    """Basic stream info via ffprobe."""
    out = subprocess.run(
        [need("ffprobe"), "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = any(s.get("codec_type") == "audio" for s in d.get("streams", []))
    fps = v.get("r_frame_rate", "0/1")
    num, den = (fps.split("/") + ["1"])[:2]
    return {
        "width": v.get("width"), "height": v.get("height"),
        "fps": (float(num) / float(den)) if float(den) else 0.0,
        "duration": float(d.get("format", {}).get("duration", 0) or 0),
        "audio": a,
    }


def fmt_time(sec):
    sec = max(0, sec)
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_time(text):
    """'1:02:03.5', '12:30', '754.2' -> seconds."""
    parts = [float(p) for p in str(text).strip().split(":")]
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec
