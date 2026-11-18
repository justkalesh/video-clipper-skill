"""Tidy a video's output folder: name every clip after its post title, keep only what people use at the top
level, and rebuild posts.md. Run it after the post text is written (step 8), before uploading.

Usage:  python organize.py <output_folder>/<video folder>

Result:
  <video folder>/
    01 - <post title>.mp4      the clip
    01 - <post title>.jpg      its cover image
    01 - <post title>.srt      subtitles (if made)
    posts.md                   every clip's title, description, hashtags, captions, ready to copy
    _data/                     post files (.meta.json), check sheets, render results

The number prefix keeps the clips in their ranked order. It's safe to run more than once.
"""
import json
import re
import shutil
import sys
from pathlib import Path

from common import DATA_DIR, load_json, safe_name, save_json, utf8
import posts


def unique(path, taken):
    """Avoid overwriting a different clip that happens to get the same title."""
    if str(path).lower() not in taken and not path.exists():
        return path
    stem, i = path.stem, 2
    while True:
        cand = path.with_name(f"{stem} ({i}){path.suffix}")
        if str(cand).lower() not in taken and not cand.exists():
            return cand
        i += 1


def main(folder):
    folder = Path(folder)
    data = folder / DATA_DIR
    checks = data / "checks"
    checks.mkdir(parents=True, exist_ok=True)

    # older layouts kept these at the top level
    for m in folder.glob("*.meta.json"):
        shutil.move(str(m), data / m.name)
    for f in (folder / "_checks").glob("*") if (folder / "_checks").exists() else []:
        shutil.move(str(f), checks / f.name)
    if (folder / "_checks").exists():
        shutil.rmtree(folder / "_checks", ignore_errors=True)
    if (folder / "render_results.json").exists():
        shutil.move(str(folder / "render_results.json"), data / "render_results.json")

    results = load_json(data / "render_results.json", [])
    renames, taken = {}, set()
    for n, meta_path in enumerate(sorted(data.glob("*.meta.json")), 1):
        old = meta_path.name[: -len(".meta.json")]
        meta = load_json(meta_path)
        m = re.match(r"^(\d+)", old)
        num = int(m.group(1)) if m else n
        new = f"{num:02d} - {safe_name(meta.get('title') or old)}"
        target = unique(folder / f"{new}.mp4", taken) if new != old else folder / f"{new}.mp4"
        new = target.stem
        taken.add(str(target).lower())
        if new == old:
            continue
        for ext in (".mp4", ".jpg", ".srt"):
            src = folder / f"{old}{ext}"
            if src.exists():
                src.rename(folder / f"{new}{ext}")
        if (checks / f"{old}.jpg").exists():
            (checks / f"{old}.jpg").rename(checks / f"{new}.jpg")
        meta_path.rename(data / f"{new}.meta.json")
        renames[old] = new

    for r in results:
        for old, new in renames.items():
            if r.get("clip") == old:
                r["clip"] = new
                r["file"] = str(folder / f"{new}.mp4")
                r["check_sheet"] = str(checks / f"{new}.jpg")
    if results:
        save_json(data / "render_results.json", results)

    count = posts.build(folder)
    print(json.dumps({"folder": str(folder), "renamed": renames, "clips": count}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    utf8()
    main(sys.argv[1])
