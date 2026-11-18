"""Measure what happens second by second, to help find moments that aren't only about words:
loudness (laughter, cheering, shouting, game sound), visual cuts/action, speech density, subtitle markers.

Usage:
  python signals.py <audio-or-video> --words runs/<id>/words.json --out runs/<id> [--visual <video>]

Writes signals.csv (one row per second) and prints:
  - a per-minute overview
  - the loudest spikes (relative to their surroundings) with what was being said
  - marker moments ([Laughter], [Applause], ...)
"""
import argparse
import csv
import re
import subprocess
from pathlib import Path

import numpy as np

from common import fmt_time, load_json, need, utf8

RATE = 8000


def loudness(path):
    raw = subprocess.run([need("ffmpeg"), "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(RATE),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    n = len(x) // RATE
    rms = np.sqrt((x[: n * RATE].reshape(n, RATE) ** 2).mean(axis=1) + 1e-10)
    return 20 * np.log10(rms)


def cuts(video):
    res = subprocess.run([need("ffmpeg"), "-v", "info", "-i", str(video), "-vf",
                          "scale=160:-2,select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"],
                         capture_output=True, text=True)
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", res.stderr)]


if __name__ == "__main__":
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--words")
    ap.add_argument("--out", required=True)
    ap.add_argument("--visual", help="video file to measure cuts/action in (slower)")
    a = ap.parse_args()

    db = loudness(a.media)
    n = len(db)
    words = (load_json(a.words, {}) or {}).get("words", []) if a.words else []
    wps = np.zeros(n)
    markers = []
    text_at = [""] * n
    for w in words:
        s = int(w["t"])
        if 0 <= s < n:
            if w.get("m"):
                markers.append((w["t"], w["w"]))
            else:
                wps[s] += 1
                text_at[s] += w["w"] + " "
    cut_rate = np.zeros(n)
    if a.visual:
        for t in cuts(a.visual):
            if int(t) < n:
                cut_rate[int(t)] += 1

    # spike = loud compared with the surrounding 30 s (laughter, cheers, shouting, explosions)
    k = 30
    pad = np.pad(db, (k, k), mode="edge")
    local = np.array([np.median(pad[i:i + 2 * k + 1]) for i in range(n)])
    spike = db - local

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "signals.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["sec", "loudness_db", "spike_db", "words", "cuts"])
        for i in range(n):
            wr.writerow([i, round(float(db[i]), 1), round(float(spike[i]), 1), int(wps[i]), int(cut_rate[i])])

    print(f"duration {fmt_time(n)}; per minute: loudness (dB), words, cuts, markers")
    for m in range(0, n, 60):
        sl = slice(m, min(m + 60, n))
        mk = sum(1 for t, _ in markers if m <= t < m + 60)
        print(f"  {fmt_time(m)}  {db[sl].mean():6.1f}  {int(wps[sl].sum()):4d}w  {int(cut_rate[sl].sum()):3d}c  {mk}m")

    order = np.argsort(-spike)
    picked = []
    for i in order:
        if spike[i] < 6 or len(picked) >= 20:
            break
        if all(abs(i - j) > 8 for j in picked):
            picked.append(int(i))
    print("\nloudest spikes (vs. surroundings), with what was said just before:")
    for i in sorted(picked):
        before = " ".join(text_at[max(0, i - 6):i + 1]).split()[-14:]
        print(f"  {fmt_time(i)}  +{spike[i]:4.1f} dB  ...{' '.join(before)}")
    if markers:
        print("\nmarkers:")
        groups = {}
        for t, w in markers:
            groups.setdefault(w, []).append(fmt_time(t))
        for w, ts in groups.items():
            print(f"  {w} x{len(ts)}: {', '.join(ts[:40])}{' ...' if len(ts) > 40 else ''}")
