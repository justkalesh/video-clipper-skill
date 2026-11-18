"""Delete everything a finished run no longer needs. Run it as the very last step.

Usage:
  python cleanup.py <video-id> --out "<output_folder>/<video folder>" [--level full|source]

  full (default)  the long source video and its audio, the whole run folder (subtitles, transcripts, word timings,
                  signals, profile, overview/range frames, shot analysis, caption files, clip data), the check sheets
                  and render results in OUT/_data, and the renderer's temporary files
  source          only the long source video and its audio

Always kept: the clips with their covers and subtitles, posts.md, the post files in OUT/_data (needed to upload,
schedule or publish later), the log file, and any logo/music you supplied. Files you pointed the skill at are never
touched: local videos are copied into the workspace and only the copy is deleted.
"""
import argparse
import json
import shutil
from pathlib import Path

from common import DATA_DIR, PUBLIC, RUNS, WORKSPACE, utf8


def size_of(p):
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def remove(p, deleted):
    if not p.exists():
        return 0
    n = size_of(p)
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    else:
        p.unlink()
    deleted.append(str(p))
    return n


def main():
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--out", help="the video's output folder (for check sheets / render results)")
    ap.add_argument("--level", choices=["full", "source"], default="full")
    a = ap.parse_args()
    deleted, freed = [], 0

    source = PUBLIC / "source"
    for f in list(source.glob(f"{a.video_id}.*")) + list(source.glob(f"{a.video_id}_*")):
        freed += remove(f, deleted)
    run = RUNS / a.video_id
    for f in run.glob("audio.*"):
        freed += remove(f, deleted)

    if a.level == "full":
        freed += remove(run, deleted)
        if a.out:
            data = Path(a.out) / DATA_DIR
            freed += remove(data / "checks", deleted)
            freed += remove(data / "render_results.json", deleted)
        # renderer leftovers: temporary renders/props and the bundle (rebuilt on every render anyway)
        freed += remove(WORKSPACE / "out", deleted)
        freed += remove(WORKSPACE / "build", deleted)

    print(json.dumps({"video_id": a.video_id, "level": a.level, "freed_mb": round(freed / 1e6, 1),
                      "deleted": deleted}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
