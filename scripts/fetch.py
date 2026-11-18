"""Get a video's info, subtitles, audio or video, from a link (anything yt-dlp supports) or a local file.

Usage:
  python fetch.py info  <url-or-file>                        -> runs/<id>/info.json, prints the id
  python fetch.py subs  <url> [--lang hi]                     -> runs/<id>/subs.<lang>.vtt (original-language track)
  python fetch.py audio <url-or-file>                         -> runs/<id>/audio.m4a (for Whisper / loudness)
  python fetch.py video <url-or-file> [--quality 1080]        -> workspace/public/source/<id>.mp4 (whole video)
  python fetch.py video <url> --sections "754-812,1100-1160"  -> one file per range, cut on exact frames
Every command prints a JSON line describing what it wrote.

(Deleting downloads when a run is finished: see cleanup.py.)
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from common import PUBLIC, RUNS, load_json, probe, run, save_json, slug, utf8, need, video_folder


def is_local(src):
    return Path(src).exists()


def local_id(path):
    return "local-" + slug(Path(path).stem, 50)


def ydl(opts):
    try:
        import yt_dlp
    except ImportError:
        sys.exit("yt-dlp is not installed. Run scripts/setup.py --install")
    base = {"quiet": True, "no_warnings": True, "noprogress": True}
    base.update(opts)
    return yt_dlp.YoutubeDL(base)


def with_retry(fn, tries=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # YouTube rate-limits subtitle downloads (HTTP 429)
            if "429" in str(e) and i < tries - 1:
                wait = 20 * (i + 1)
                print(f"rate-limited, retrying in {wait}s...", file=sys.stderr, flush=True)
                time.sleep(wait)
                continue
            raise


def cmd_info(src):
    if is_local(src):
        vid = local_id(src)
        p = probe(src)
        info = {"id": vid, "title": Path(src).stem, "duration": p["duration"], "local_path": str(Path(src).resolve()),
                "width": p["width"], "height": p["height"], "fps": p["fps"], "has_audio": p["audio"],
                "subtitles": [], "auto_captions": []}
    else:
        with ydl({}) as y:
            d = with_retry(lambda: y.extract_info(src, download=False))
        info = {k: d.get(k) for k in (
            "id", "title", "channel", "uploader", "upload_date", "duration", "description", "tags", "categories",
            "chapters", "language", "view_count", "like_count", "is_live", "was_live", "webpage_url", "width",
            "height", "fps", "license")}
        info["subtitles"] = sorted((d.get("subtitles") or {}).keys())
        info["auto_captions"] = sorted(k for k in (d.get("automatic_captions") or {}).keys()
                                       if k.endswith("-orig") or k in ("en", d.get("language") or ""))
        if info.get("description") and len(info["description"]) > 3000:
            info["description"] = info["description"][:3000] + " ..."
    info["folder"] = video_folder(info)  # where this video's clips go: <output_folder>/<folder>
    out = RUNS / info["id"] / "info.json"
    save_json(out, info)
    print(json.dumps({"id": info["id"], "folder": info["folder"], "info": str(out), "title": info.get("title"),
                      "duration": info.get("duration"), "language": info.get("language"),
                      "subtitles": info["subtitles"], "auto_captions": info["auto_captions"]}, ensure_ascii=False))


def cmd_subs(src, lang):
    with ydl({}) as y:
        d = with_retry(lambda: y.extract_info(src, download=False))
    vid = d["id"]
    manual = d.get("subtitles") or {}
    auto = d.get("automatic_captions") or {}
    spoken = lang or d.get("language") or ""
    pick = None
    # creator-made subtitles in the spoken language beat auto captions; '-orig' is the untranslated auto track
    for table, key, is_auto in (
        (manual, spoken, False),
        (manual, next((k for k in manual if spoken and k.startswith(spoken + "-")), None), False),
        (auto, f"{spoken}-orig", True),
        (auto, next((k for k in auto if k.endswith("-orig")), None), True),
        (auto, spoken, True),
        (manual, "en", False),
        (auto, "en", True),
        (manual, next(iter(manual), None), False),
    ):
        if key and key in table:
            pick = (key, is_auto)
            break
    if not pick:
        print(json.dumps({"id": vid, "subs": None, "note": "no subtitles; use Whisper (transcript.py whisper)"}))
        return
    key, is_auto = pick
    out_dir = RUNS / vid
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {"skip_download": True, "writesubtitles": not is_auto, "writeautomaticsub": is_auto,
            "subtitleslangs": [key], "subtitlesformat": "vtt", "outtmpl": str(out_dir / "subs.%(ext)s")}
    with ydl(opts) as y:
        with_retry(lambda: y.download([src]))
    files = sorted(out_dir.glob("subs*.vtt"), key=lambda f: f.stat().st_mtime)
    print(json.dumps({"id": vid, "subs": str(files[-1]) if files else None, "track": key, "auto": is_auto}))


def cmd_audio(src):
    if is_local(src):
        vid = local_id(src)
        out = RUNS / vid / "audio.m4a"
        out.parent.mkdir(parents=True, exist_ok=True)
        run([need("ffmpeg"), "-v", "error", "-y", "-i", src, "-vn", "-c:a", "aac", "-b:a", "128k", out])
        print(json.dumps({"id": vid, "audio": str(out)}))
        return
    with ydl({}) as y:
        vid = y.extract_info(src, download=False)["id"]
    out_dir = RUNS / vid
    opts = {"format": "bestaudio[ext=m4a]/bestaudio", "outtmpl": str(out_dir / "audio.%(ext)s")}
    with ydl(opts) as y:
        with_retry(lambda: y.download([src]))
    files = list(out_dir.glob("audio.*"))
    print(json.dumps({"id": vid, "audio": str(files[0]) if files else None}))


def cmd_video(src, quality, sections):
    dest = PUBLIC / "source"
    dest.mkdir(parents=True, exist_ok=True)
    if is_local(src):
        vid = local_id(src)
        out = dest / f"{vid}{Path(src).suffix.lower()}"
        if not out.exists():
            shutil.copy2(src, out)
        print(json.dumps({"id": vid, "files": [{"path": str(out), "offset": 0.0}]}))
        return
    q = "" if quality == "best" else f"[height<={int(quality)}]"
    # H.264 + AAC decodes everywhere (Remotion, browsers); fall back to anything if not offered
    fmt = f"bv*{q}[vcodec^=avc1]+ba[ext=m4a]/bv*{q}+ba/b{q}/bv*+ba/b"
    opts = {"format": fmt, "merge_output_format": "mp4"}
    files = []
    if sections:
        import yt_dlp.utils as u
        ranges = []
        for part in sections.split(","):
            a, b = part.split("-")
            ranges.append((float(a), float(b)))
        opts.update({"download_ranges": u.download_range_func(None, ranges), "force_keyframes_at_cuts": True,
                     "outtmpl": str(dest / "%(id)s_%(section_start)d.%(ext)s")})
        with ydl(opts) as y:
            info = with_retry(lambda: y.extract_info(src, download=True))
        vid = info["id"]
        for a, b in ranges:
            f = dest / f"{vid}_{int(a)}.mp4"
            files.append({"path": str(f), "offset": float(int(a)), "range": [a, b], "exists": f.exists()})
    else:
        opts["outtmpl"] = str(dest / "%(id)s.%(ext)s")
        with ydl(opts) as y:
            info = with_retry(lambda: y.extract_info(src, download=True))
        vid = info["id"]
        files.append({"path": str(dest / f"{vid}.mp4"), "offset": 0.0})
    manifest = RUNS / vid / "video_files.json"
    old = load_json(manifest, [])
    save_json(manifest, old + files)
    print(json.dumps({"id": vid, "files": files}))


if __name__ == "__main__":
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["info", "subs", "audio", "video"])
    ap.add_argument("src")
    ap.add_argument("--lang", default="")
    ap.add_argument("--quality", default="1080")
    ap.add_argument("--sections", default="")
    a = ap.parse_args()
    {"info": lambda: cmd_info(a.src), "subs": lambda: cmd_subs(a.src, a.lang), "audio": lambda: cmd_audio(a.src),
     "video": lambda: cmd_video(a.src, a.quality, a.sections)}[a.what]()
