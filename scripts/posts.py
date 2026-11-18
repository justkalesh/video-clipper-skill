"""Collect every clip's post text (its .meta.json in _data/) into one readable, copy-ready posts.md.

Usage:  python posts.py <output_folder>/<video folder>
"""
import sys
from pathlib import Path

from common import DATA_DIR, load_json, probe, utf8


def tags_line(tags):
    return " ".join(h if h.startswith("#") else "#" + h for h in tags or [])


def block(text):
    return ["```", (text or "").strip(), "```", ""]


def metas_in(folder):
    folder = Path(folder)
    return sorted((folder / DATA_DIR).glob("*.meta.json")) or sorted(folder.glob("*.meta.json"))


def build(folder):
    folder = Path(folder)
    metas = metas_in(folder)
    lines = [f"# Posts: {folder.name}", "",
             "Everything below is ready to copy. Hashtags are already in each description/caption.", ""]
    for i, m in enumerate(metas, 1):
        meta = load_json(m)
        video = folder / m.name.replace(".meta.json", ".mp4")
        length = f"{probe(video)['duration']:.0f}s" if video.exists() else "?"
        yt = meta.get("youtube")
        status = "not uploaded"
        if yt:
            when = f", goes live {yt['publish_at']}" if yt.get("publish_at") else ""
            status = f"[{yt['url']}]({yt['url']}) ({yt['privacy']}{when})"
        desc = (meta.get("description") or "").strip()
        tl = tags_line(meta.get("hashtags"))
        if tl and tl.split()[0].lower() not in desc.lower():
            desc = f"{desc}\n\n{tl}"
        lines += [f"## {video.stem}", "",
                  f"**File:** {video.name} · **Length:** {length} · **YouTube:** {status}"
                  + (f" · **Post at:** {meta['best_time']}" if meta.get("best_time") else ""), "",
                  "**YouTube title**", *block(meta.get("title")),
                  "**YouTube description**", *block(desc),
                  "**YouTube tags** (paste into the Tags box)", *block(", ".join(meta.get("tags") or []))]
        for name, p in (meta.get("platforms") or {}).items():
            cap = (p.get("caption") or "").strip()
            ht = tags_line(p.get("hashtags"))
            if ht and ht.split()[0].lower() not in cap.lower():
                cap = f"{cap}\n\n{ht}"
            lines += [f"**{name.capitalize()} caption**", *block(cap)]
        if meta.get("pinned_comment"):
            lines += ["**Pinned comment**", *block(meta["pinned_comment"])]
    (folder / "posts.md").write_text("\n".join(lines), encoding="utf-8")
    return len(metas)


if __name__ == "__main__":
    utf8()
    n = build(sys.argv[1])
    print(f"{n} clips -> {Path(sys.argv[1]) / 'posts.md'}")
