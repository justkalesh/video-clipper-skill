"""Get a video's info, subtitles, audio or video, from a link (anything yt-dlp supports) or a local file.

Usage:
  python fetch.py info  <url-or-file>                        -> runs/<id>/info.json, prints the id
  python fetch.py subs  <url> [--lang hi]                     -> runs/<id>/subs.<track>.vtt, e.g. subs.hi-orig.vtt
  python fetch.py audio <url-or-file>                         -> runs/<id>/audio.<ext> (m4a, or webm on some sites)
  python fetch.py video <url-or-file> [--quality 1080]        -> workspace/public/source/<id>.mp4 (whole video)
  python fetch.py video <url> --sections "754-812,1100.5-1160" -> one file per range, cut on exact frames
Every command prints a JSON line describing what it wrote. Use the paths it prints: file names depend on the
subtitle track and the formats the site offers. For sections, pass each file's printed "offset" to
analyze_shots.py --offset (it is the exact start of the range, fractions included).

(Deleting downloads when a run is finished: see cleanup.py.)
"""
import argparse
import copy
import json
import re
import shutil
import sys
import time
from pathlib import Path

from common import PUBLIC, RUNS, load_json, need, parse_time, probe, run, save_json, slug, utf8, video_folder


def is_local(src):
    return Path(src).exists()


def local_id(path):
    """Stable per file location, so two different files that share a name don't share a run folder."""
    import hashlib
    h = hashlib.sha1(str(Path(path).resolve()).lower().encode("utf-8")).hexdigest()[:6]
    return f"local-{slug(Path(path).stem, 44)}-{h}"


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
        except Exception as e:
            text = str(e)
            if i < tries - 1 and "429" in text:  # YouTube rate-limits subtitle downloads
                wait = 20 * (i + 1)
                print(f"rate-limited, retrying in {wait}s...", file=sys.stderr, flush=True)
                time.sleep(wait)
                continue
            if i < tries - 1 and "ffmpeg exited" in text:  # a dropped stream mid-cut; usually fine on a retry
                print("ffmpeg failed on the stream, retrying...", file=sys.stderr, flush=True)
                time.sleep(5)
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
    base = spoken.split("-")[0]  # the video says "en-US", the tracks say "en" / "en-orig"
    origs = [k for k in auto if k.endswith("-orig")]
    pick = None
    # creator-made subtitles in the spoken language beat auto captions. '-orig' is the auto transcript of an audio
    # track; a video with auto-dubbed audio has one per dub language, so only the spoken language's counts, and
    # "any -orig" is used only when there is exactly one.
    for table, key, is_auto in (
        (manual, spoken, False),
        (manual, base, False),
        (manual, next((k for k in manual if base and k.startswith(base + "-")), None), False),
        (auto, f"{spoken}-orig", True),
        (auto, f"{base}-orig", True),
        (auto, origs[0] if len(origs) == 1 else None, True),
        (auto, spoken, True),
        (auto, base, True),
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
        st = Path(src).stat()
        # copy again when the file changed since the last copy (same size and time = same file)
        if not out.exists() or out.stat().st_size != st.st_size or int(out.stat().st_mtime) != int(st.st_mtime):
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
            a, b = [parse_time(x) for x in re.split(r"\s*-\s*(?=\d)", part.strip(), maxsplit=1)]
            ranges.append((a, b))
        # look the video up once (fewer requests, less risk of YouTube's rate limit), then cut every range from it
        with ydl({}) as y:
            raw = with_retry(lambda: y.extract_info(src, download=False, process=False))
        vid = raw["id"]
        for a, b in ranges:
            # one download per range, named by its start in milliseconds: the file starts exactly at `a`
            # (force_keyframes_at_cuts re-encodes the cut), and two ranges never share a file name
            ms = int(round(a * 1000))
            tmpl = str(dest / f"{vid}_{ms}").replace("%", "%%") + ".%(ext)s"
            o = dict(opts, download_ranges=u.download_range_func(None, [(a, b)]), force_keyframes_at_cuts=True,
                     outtmpl=tmpl)
            with ydl(o) as y:
                with_retry(lambda: y.process_ie_result(copy.deepcopy(raw), download=True))
            f = dest / f"{vid}_{ms}.mp4"
            files.append({"path": str(f), "offset": a, "range": [a, b], "exists": f.exists()})
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
