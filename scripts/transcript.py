"""Turn subtitles or audio into word-level timings plus a readable transcript.

Usage:
  python transcript.py subs  <file.vtt|file.srt> --out runs/<id>
  python transcript.py whisper <audio-or-video> --out runs/<id> [--model large-v3] [--lang hi]

Writes:
  words.json      {"language", "source", "words": [{"t": start, "e": end, "w": text, "m": true if a marker}]}
  transcript.txt  ~15-second paragraphs with [mm:ss] stamps, for reading and picking moments

Markers are non-speech tags in the subtitles such as [Laughter], [Applause], [Music], [हंसी].
YouTube's auto captions also write HTML codes (&gt;&gt; = a new speaker, &nbsp;) and hide every swear as "[ __ ]".
The codes are decoded and the >> speaker marks dropped; a hidden swear stays a spoken word, written "****" with
"x": true, so word counts and timings still line up (captions show it masked; censor: bleep beeps it).
"""
import argparse
import html
import re
import sys
from pathlib import Path

from common import fmt_time, save_json, utf8

TS = re.compile(r"(\d+):(\d+):(\d+)[.,](\d+)")


def secs(m):
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / (10 ** len(m[4]))


def parse_ts(text):
    m = TS.search(text)
    if m:
        return secs(m)
    m = re.search(r"(\d+):(\d+)[.,](\d+)", text)  # mm:ss.mmm
    return int(m[1]) * 60 + int(m[2]) + int(m[3]) / (10 ** len(m[3])) if m else None


def cues(text):
    """(start, end, lines) for every cue in a VTT or SRT file."""
    out = []
    # split on truly empty lines only: YouTube cues often contain a line holding a single space
    for block in re.split(r"\n\n+", text.replace("\r", "")):
        lines = block.strip().split("\n")
        idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if idx is None:
            continue
        a, b = lines[idx].split("-->")[:2]
        start, end = parse_ts(a), parse_ts(b.split()[0] if b.split() else b)
        if start is None or end is None:
            continue
        out.append((start, end, lines[idx + 1:]))
    return out


HIDDEN = "****"  # a swear YouTube's auto captions replaced with [ __ ]


def clean(w):
    """Decode HTML codes; None for things that aren't words (the >> speaker mark)."""
    w = html.unescape(w).replace("\xa0", " ").strip()
    if not w or re.fullmatch(r">+", w):
        return None
    if re.fullmatch(r"\[\s*_+\s*\]", w):
        return HIDDEN
    return w


def from_subs(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    words = []
    if "<c>" in text:
        # YouTube auto captions: each cue repeats the previous line as plain text and adds a new line whose
        # words carry their own <timestamp> tags. Only the timed lines are new.
        for start, end, lines in cues(text):
            for line in lines:
                if "<c>" not in line:
                    continue
                line = re.sub(r"\[(?:\s|&nbsp;)*_+(?:\s|&nbsp;)*\]", "[__]", line)  # keep [ __ ] as one token
                first = re.match(r"^([^<]+)", line)
                if first:
                    for w in first.group(1).split():
                        if clean(w):
                            words.append([start, clean(w)])
                for t, w in re.findall(r"<(\d+:\d+:[\d.]+)><c>([^<]*)</c>", line):
                    if clean(w):
                        words.append([parse_ts(t), clean(w)])
        # marker-only cues ([Music]) have no <c> tags
        for start, end, lines in cues(text):
            body = html.unescape(" ".join(re.sub(r"<[^>]+>", "", l) for l in lines)).replace("\xa0", " ").strip()
            # rolling captions repeat a marker in the next cue(s): one per 3 s is the real event
            if (re.fullmatch(r"\[[^\]]+\]", body) and not re.fullmatch(r"\[\s*_+\s*\]", body)
                    and not any(abs(w[0] - start) < 3 and w[1] == body for w in words)):
                words.append([start, body])
    else:
        # creator-made subtitles: spread each cue's words over its duration, weighted by length
        last = None
        for start, end, lines in cues(text):
            body = " ".join(re.sub(r"<[^>]+>", "", l).strip() for l in lines).strip()
            if not body or body == last:
                continue
            last = body
            body = re.sub(r"\[(?:\s|&nbsp;)*_+(?:\s|&nbsp;)*\]", "[__]", body)  # keep [ __ ] as one token
            toks = [c for c in (clean(t) for t in body.split()) if c]
            total = sum(len(t) + 1 for t in toks)
            acc = 0
            for tok in toks:
                words.append([start + (end - start) * acc / total, tok])
                acc += len(tok) + 1
    words.sort(key=lambda w: w[0])
    out = []
    for i, (t, w) in enumerate(words):
        nxt = words[i + 1][0] if i + 1 < len(words) else t + 0.6
        out.append({"t": round(t, 3), "e": round(min(nxt, t + 1.2), 3), "w": w,
                    **({"m": True} if re.fullmatch(r"\[[^\]]+\]", w) else {}),
                    **({"x": True} if w == HIDDEN else {})})
    return out


def from_whisper(path, model_name, lang):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper is not installed. Run: python setup.py --install --with-whisper")
    try:
        import torch  # noqa: F401  (only to check for a GPU)
        cuda = torch.cuda.is_available()
    except Exception:
        cuda = False
    try:
        model = WhisperModel(model_name, device="cuda" if cuda else "auto",
                             compute_type="float16" if cuda else "int8")
    except Exception:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(path), word_timestamps=True, vad_filter=True, language=lang or None)
    words = []
    for seg in segments:
        for w in seg.words or []:
            if w.word.strip():
                words.append({"t": round(w.start, 3), "e": round(w.end, 3), "w": w.word.strip()})
        print(f"\r  transcribed {fmt_time(seg.end)}", end="", flush=True)
    print()
    return words, info.language


def write_text(words, path):
    paras, cur, start = [], [], None
    for w in words:
        if start is None:
            start = w["t"]
        if w["t"] - start >= 15 and cur:
            paras.append(f"[{fmt_time(start)}] " + " ".join(cur))
            cur, start = [], w["t"]
        cur.append(w["w"])
    if cur:
        paras.append(f"[{fmt_time(start)}] " + " ".join(cur))
    Path(path).write_text("\n".join(paras) + "\n", encoding="utf-8")
    return len(paras)


if __name__ == "__main__":
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["subs", "whisper"])
    ap.add_argument("src")
    ap.add_argument("--out", required=True, help="run folder, e.g. ~/.video-clipper/runs/<id>")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--lang", default="")
    a = ap.parse_args()
    out = Path(a.out)
    if a.kind == "subs":
        words = from_subs(a.src)
        lang = (re.search(r"\.([a-zA-Z-]+)\.(vtt|srt)$", a.src) or [None, ""])[1]
        source = "subtitles"
    else:
        words, lang = from_whisper(a.src, a.model, a.lang)
        source = "whisper"
    save_json(out / "words.json", {"language": lang, "source": source, "words": words})
    n = write_text(words, out / "transcript.txt")
    spoken = [w for w in words if not w.get("m")]
    print(f"{len(spoken)} words, {len(words) - len(spoken)} markers, {n} paragraphs -> {out / 'transcript.txt'}")
