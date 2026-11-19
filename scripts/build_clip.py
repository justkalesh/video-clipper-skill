"""Combine timed words, the shot layout and the settings into one clip data file for rendering.

Usage:
  python build_clip.py --run RUN_DIR --shots shots_1.json --start 1100.25 --end 1158.9 --id 1 \
      --title "Clip title" --settings run_settings.json --out clip_1.json \
      [--captions captions_1.tokens.txt | captions_1.phrases.txt] [--emphasis "word,another"]
  python build_clip.py --run RUN_DIR --start 1100.25 --end 1158.9 --list-words
      prints the exact words a tokens file must match, one per line (time, word)

--id is the clip's rank (1 = best); the file name number comes from it. Use --rank if the id isn't a number.

Captions come from one of three places:
  (none)          the transcript's own words (fillers/stutters dropped if remove_fillers is on)
  *.tokens.txt    one caption word per line, matched 1:1 with the transcript's words in the range.
                  Use it to rewrite words while keeping their exact timing (Hinglish, fixing mishearings).
                  "-" = show nothing for that word; "*word" = emphasise it.
  *.phrases.txt   "start-end | text" per line (times in seconds or mm:ss of the ORIGINAL video).
                  Use it for translations, where words don't map 1:1; words are spread across each phrase.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

from common import PUBLIC, load_json, parse_time, save_json, utf8

WINDOW_SLACK = 0.05  # a word starting this much before the clip start still belongs to it
FILLERS = {"um", "uh", "umm", "uhh", "uhm", "er", "erm", "ah", "hmm", "mm", "mhm"}
MARKERS = {"हंसी": "laughs", "संगीत": "music", "तालियां": "applause", "हँसी": "laughs"}
SCHEMES = {"fire": "#FF2D2D", "gold": "#FFD60A", "neon": "#39FF14", "ice": "#4CC9F0", "mono": "#FFFFFF"}


def bare(w):
    return re.sub(r"[^\w']+", "", w.lower())


# censor: words masked in captions (and beeped with censor: bleep), plus anything written masked in a tokens or
# phrases file ("b***d"). Prefixes catch the usual forms ("fucking", "shitty").
SWEAR_PREFIXES = ("fuck", "motherfuck", "shit", "bullshit", "bitch", "asshole", "bastard", "cunt", "nigg",
                  "faggot", "retard", "chutiy", "bhenchod", "behenchod", "bhosd", "madarchod", "maderchod",
                  "चूतिय", "भेनचोद", "बहनचोद", "मादरचोद", "भोसड")
SWEAR_WORDS = {"dick", "dickhead", "pussy", "cock", "slut", "whore", "gaand", "gandu", "lund", "lauda", "lavda",
               "loda", "randi", "गांड", "गांडू", "लौड़ा", "लंड", "रंडी"}


def norm(w):
    """Lower-case with punctuation removed, keeping Devanagari vowel signs (a plain \\w pattern drops them)."""
    return re.sub(r"[^\wऀ-ॿ']+", "", w.lower())


def is_swear(w):
    n = norm(w)
    return bool(n) and (n in SWEAR_WORDS or n.startswith(SWEAR_PREFIXES))


def is_masked(w):
    return bool(re.search(r"\w\*+", w))


def mask(w):
    """f**k, f*****g: first and last letter kept, punctuation kept."""
    m = re.match(r"^(\W*)(.*?)(\W*)$", w)
    lead, core, trail = m.groups() if m else ("", w, "")
    if len(core) <= 2:
        return lead + core[:1] + "*" * (len(core) - 1) + trail
    return lead + core[0] + "*" * (len(core) - 2) + core[-1] + trail


def spoken_in(words, start, end):
    """The transcript words a clip covers (markers like [Laughter] excluded). Tokens files match these 1:1."""
    return [w for w in words if start - WINDOW_SLACK <= w["t"] < end and not w.get("m")]


def asset(path):
    """Copy a file the clip uses (logo, music) under the workspace's public/ folder."""
    if not path or path is True:
        return None
    src = Path(str(path)).expanduser()
    if not src.exists():
        print(f"warning: {src} not found, skipping", file=sys.stderr)
        return None
    dest = PUBLIC / "assets" / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dest)
    return f"assets/{src.name}"


def caption_words(words, start, end, captions, s, emphasis):
    window = [w for w in words if start - WINDOW_SLACK <= w["t"] < end]
    spoken = spoken_in(words, start, end)
    toks = []
    if captions and captions.endswith(".phrases.txt"):
        for line in Path(captions).read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            span, _, text = line.partition("|")
            a, b = [parse_time(x) for x in re.split(r"\s*-\s*(?=\d)", span.strip(), maxsplit=1)]
            parts = text.split()
            total = sum(len(p) + 1 for p in parts) or 1
            acc = 0
            for p in parts:
                t = a + (b - a) * acc / total
                acc += len(p) + 1
                toks.append({"t": t, "e": a + (b - a) * acc / total, "w": p.lstrip("*"), "emph": p.startswith("*")})
    elif captions:
        lines = [l.strip() for l in Path(captions).read_text(encoding="utf-8").splitlines() if l.strip()]
        lines = [l for l in lines if not l.startswith("#")]
        if len(lines) != len(spoken):
            for i in range(max(len(lines), len(spoken))):
                a = spoken[i]["w"] if i < len(spoken) else "-"
                b = lines[i] if i < len(lines) else "-"
                print(f"{i:4d} {spoken[i]['t'] if i < len(spoken) else 0:9.2f}  {a:20s} {b}")
            sys.exit(f"caption file has {len(lines)} lines but the range has {len(spoken)} words: "
                     "fix the lines where the two columns drift apart")
        for w, l in zip(spoken, lines):
            if l != "-":
                toks.append({"t": w["t"], "e": w["e"], "w": l.lstrip("*"), "emph": l.startswith("*")})
    else:
        prev = None
        for w in spoken:
            b = bare(w["w"])
            if s.get("remove_fillers", True) and (b in FILLERS or (prev is not None and b and b == prev)):
                prev = b
                continue
            prev = b
            toks.append({"t": w["t"], "e": w["e"], "w": w["w"], "emph": False})
    if toks and toks[0]["w"][:1].islower():  # a clip often starts mid-sentence in the source
        toks[0]["w"] = toks[0]["w"][0].upper() + toks[0]["w"][1:]
    emph = {bare(e) for e in emphasis.split(",") if e.strip()} if emphasis else set()
    for t in toks:
        if bare(t["w"]) in emph:
            t["emph"] = True
    bleeps = []
    if s.get("censor") in ("mask", "bleep"):
        for t in toks:
            if is_masked(t["w"]) or is_swear(t["w"]):
                t["w"] = t["w"] if is_masked(t["w"]) else mask(t["w"])
                # the word's own sound only: its end time can include the pause after it
                bleeps.append([round((t["t"] - start - 0.03) * 1000), round((min(t["e"], t["t"] + 0.7) - start) * 1000)])
    if s.get("censor") != "bleep":
        bleeps = []
    markers = []
    if s.get("captions_when_silent") == "describe":
        for w in window:
            if w.get("m") and all(abs(w["t"] - t["t"]) > 0.6 for t in toks):
                inner = w["w"].strip("[] ")
                markers.append({"t": w["t"], "w": f"[{MARKERS.get(inner, inner.lower())}]"})
    return toks, markers, [[max(a, 0), b] for a, b in bleeps if b > 0]


def paginate(toks, markers, s, start):
    style = s.get("caption_style", "karaoke")
    if style == "auto":
        style = "karaoke"
    if style == "none":
        return []
    per = {"pop": 1, "line": 7}.get(style, int(s.get("words_per_caption", 3) or 3))
    max_chars = {"pop": 99, "line": 34}.get(style, int(s.get("max_caption_chars", 16) or 16))
    gap_break = 0.6 if style == "line" else 0.35
    pages, cur = [], []
    for t in toks:
        if cur:
            chars = sum(len(x["w"]) + 1 for x in cur) + len(t["w"])
            last = re.sub(r"[^\w.,?!]+$", "", cur[-1]["w"])[-1:]  # "khatam! 💀" still ends a sentence
            if (len(cur) >= per or chars > max_chars or t["t"] - cur[-1]["e"] > gap_break
                    or last in (".", "?", "!") or (style != "line" and last == ",")):
                pages.append(cur)
                cur = []
        cur.append(t)
    if cur:
        pages.append(cur)
    ms = lambda sec: round((sec - start) * 1000)
    out = []
    for p in pages:
        out.append({"startMs": ms(p[0]["t"]), "endMs": ms(p[-1]["e"]) + 250,
                    "words": [{"text": w["w"], "startMs": ms(w["t"]), "endMs": ms(w["e"]),
                               **({"emph": True} if w.get("emph") else {})} for w in p]})
    for m in markers:
        out.append({"startMs": ms(m["t"]), "endMs": ms(m["t"]) + 1200, "marker": True,
                    "words": [{"text": m["w"], "startMs": ms(m["t"]), "endMs": ms(m["t"]) + 1200}]})
    out.sort(key=lambda p: p["startMs"])
    for a, b in zip(out, out[1:]):
        # stay up at least 0.3 s, but never past the next caption's start (that would make the next one lag)
        a["endMs"] = min(max(a["endMs"], a["startMs"] + 300), b["startMs"])
    return [p for p in out if p["endMs"] > 0]


def caption_y(panels, faces, s, out_w, out_h):
    """caption_position: auto. Start from the default spot of a shot (the line between split views, or 80% down)
    and move to the first alternative that doesn't cover any of `faces`."""
    portrait = out_h > out_w
    scale = min(out_w, out_h) / 1080
    ys = [p["box"][1] + p["box"][3] for p in panels if p["box"][1] + p["box"][3] < out_h - 1]
    seam = min(ys, key=lambda y: abs(y - out_h / 2)) if (ys and portrait and len(panels) > 1) else None
    default = seam if seam is not None else out_h * (0.8 if portrait else 0.84)
    half = float(s.get("font_size", 108) or 108) * scale * 0.6  # half a caption line (outline included)
    title_top = s.get("title", True) and s.get("title_position", "top") == "top"
    cands = [default, out_h * 0.8, out_h * 0.88, out_h * 0.66, out_h * (0.24 if title_top else 0.16)]

    def overlap(y):
        tot = 0.0
        for cx, cy, size in faces:
            # the detector's square runs from the forehead to just under the chin; keep a little margin
            top, bottom = cy - size * 0.6, cy + size * 0.55
            tot += max(0.0, min(y + half, bottom) - max(y - half, top))
        return tot

    best = min(range(len(cands)), key=lambda i: (overlap(cands[i]) > 0, overlap(cands[i]), i))
    return round(cands[best])


def place_captions(pages, segs, s, out_w, out_h, fps):
    """One height per caption, held while it's on screen, so a caption that runs across a camera cut doesn't jump.
    It starts from the default spot of the shot the caption mostly sits in and avoids the faces of every shot it
    touches."""
    for p in pages:
        f0, f1 = p["startMs"] * fps / 1000, p["endMs"] * fps / 1000
        over = [(min(f1, x["to"]) - max(f0, x["from"]), i) for i, x in enumerate(segs)
                if min(f1, x["to"]) > max(f0, x["from"])]
        if not over:
            continue
        home = segs[max(over)[1]]
        faces = [f for _, i in over for f in segs[i].get("faces", [])]
        p["y"] = caption_y(home["panels"], faces, s, out_w, out_h)


def style_of(s):
    scheme = s.get("color_scheme", "fire")
    custom = s.get("custom_colors") or {}
    if scheme == "custom":
        text, active, outline = custom.get("text", "#FFFFFF"), custom.get("active", "#FF2D2D"), custom.get("outline", "#000000")
        glow = bool(custom.get("glow", True))
    else:
        text, active, outline = "#FFFFFF", SCHEMES.get(scheme, SCHEMES["fire"]), "#000000"
        glow = scheme != "mono"
    title_pos = s.get("title_position", "top")
    return {
        "captionStyle": {"auto": "karaoke"}.get(s.get("caption_style", "karaoke"), s.get("caption_style", "karaoke")),
        "textColor": text, "activeColor": active, "outlineColor": outline, "glow": glow,
        "monoGrow": scheme == "mono",
        "caseMode": s.get("caption_case", "as_spoken"),
        "captionPosition": s.get("caption_position", "auto"),
        "font": s.get("font", "Montserrat") or "Montserrat",
        "fontSize": float(s.get("font_size", 108) or 108),
        "titleShow": bool(s.get("title", True)),
        "titlePosition": title_pos if title_pos in ("top", "split", "bottom") else "top",
        "titleDuration": s.get("title_duration", "full"),
        "titleBg": custom.get("title_bg", "#FFFFFF"), "titleText": custom.get("title_text", "#111111"),
        "watermark": asset(s.get("watermark")),
        "watermarkPosition": s.get("watermark_position", "top_right"),
        "progressBar": bool(s.get("progress_bar", False)),
        "endCard": s.get("end_card") if isinstance(s.get("end_card"), str) and s.get("end_card") else None,
        "zoomOnStatic": bool(s.get("zoom_on_static", True)),
        "seamPx": float(s.get("seam_px", 8) or 0),
        "seamColor": s.get("seam_color", "#000000"),
        "backgroundFill": s.get("background_fill", "blur"),
        "fadeMs": float(s.get("fade_ms", 250) or 0),
        "music": asset(s.get("background_music")),
        "musicVolume": float(s.get("music_volume", 0.08) or 0.08),
    }


def main():
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--shots")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--id", default="clip")
    ap.add_argument("--rank", type=int)
    ap.add_argument("--list-words", action="store_true")
    ap.add_argument("--settings")
    ap.add_argument("--captions")
    ap.add_argument("--emphasis", default="")
    ap.add_argument("--out")
    a = ap.parse_args()
    start, end = parse_time(a.start), parse_time(a.end)
    words = load_json(Path(a.run) / "words.json")["words"]
    if a.list_words:
        for w in spoken_in(words, start, end):
            print(f"{w['t']:9.2f}  {w['w']}")
        return
    if not (a.shots and a.settings and a.out):
        sys.exit("--shots, --settings and --out are required (except with --list-words)")
    s = load_json(a.settings, {})
    shots = load_json(a.shots)

    src_path = Path(shots["source"]["path"]).resolve()
    try:
        rel = src_path.relative_to(PUBLIC.resolve()).as_posix()
    except ValueError:
        sys.exit(f"{src_path} is not inside {PUBLIC}; fetch videos with fetch.py so Remotion can read them")
    offset = float(shots.get("offset", 0.0))
    src_fps = float(shots["source"]["fps"]) or 30
    fps_set = s.get("fps", "source")
    # a number is a cap: never invent frames (24 -> 30 stutters), only drop them (60 -> 30 renders twice as fast)
    fps = round(src_fps) if fps_set in ("source", None, "") else min(int(fps_set), round(src_fps))
    dur = round((end - start) * fps)

    segs = []
    for x in shots["segments"]:
        f0 = max(round((x["start"] - start) * fps), 0)
        f1 = min(round((x["end"] - start) * fps), dur)
        if f1 <= f0:
            continue
        panels = []
        for p in x["panels"]:
            q = {"box": p["box"], "src": p["src"], "mode": p.get("mode", "cover")}
            if p.get("track"):
                seen, keys = set(), []
                for sec, kx, ky in p["track"]:
                    fr = round(sec * fps)
                    if fr not in seen:
                        seen.add(fr)
                        keys.append([fr, kx, ky])
                q["track"] = keys
            panels.append(q)
        segs.append({"from": f0, "to": f1, "layout": x["layout"], "panels": panels, "faces": x.get("faces") or []})
    if not segs:
        sys.exit("no shots overlap the clip range: re-run analyze_shots.py for this range")
    segs[0]["from"] = 0
    segs[-1]["to"] = dur
    for x, y in zip(segs, segs[1:]):
        y["from"] = x["to"]

    toks, markers, bleeps = caption_words(words, start, end, a.captions, s, a.emphasis)
    pages = paginate(toks, markers, s, start)
    out_w, out_h = shots["out"]["w"], shots["out"]["h"]
    if s.get("caption_position", "auto") == "auto":
        place_captions(pages, segs, s, out_w, out_h, fps)
    for x in segs:
        x.pop("faces", None)
    m = re.search(r"\d+", a.id)
    rank = a.rank or (int(m.group()) if m else None)
    clip = {
        "id": a.id, "rank": rank, "title": a.title, "fps": fps, "width": out_w, "height": out_h,
        "src": rel, "sourceW": shots["source"]["w"], "sourceH": shots["source"]["h"],
        "startFrame": round((start - offset) * fps), "durationInFrames": dur,
        "segments": segs, "pages": pages, "bleeps": bleeps, "style": style_of(s),
        "meta": {"start": start, "end": end},
    }
    save_json(a.out, clip)
    print(f"{a.id}: {dur / fps:.1f}s, {out_w}x{out_h}@{fps}, {len(segs)} shots, {len(pages)} caption groups"
          + (f", {len(bleeps)} bleeps" if bleeps else ""))
    for p in pages[:6]:
        print(f"  {p['startMs'] / 1000:6.2f}  " + " ".join(w["text"] for w in p["words"]))


if __name__ == "__main__":
    main()
