"""Render clip data files to finished MP4s, then process the audio, save extras and check the result.

Usage:
  python render.py RUN/clip_1.json RUN/clip_2.json ... --settings RUN/settings.json --out-dir "OUT" --video-id <id>

For every clip it writes, in --out-dir (one folder per source video):
  <name>.mp4                the finished clip, named by the file_name setting (default "01 - <title>")
  <name>.jpg                cover image (if export_thumbnail)
  <name>.srt                subtitles (if export_srt)
  _data/checks/<name>.jpg   8-frame contact sheet: LOOK AT IT before calling the clip done
  _data/render_results.json one entry per clip (a re-render replaces that clip's entry)
and prints one summary line per clip (size, length, audio level, problems found).

The number in the name is the clip's rank (from build_clip.py --id / --rank), not its position in this command,
so `render.py RUN/clip_3.json` on its own still makes clip 03. Rendering a clip again overwrites its files under
the name it already has (also after organize.py renamed it). organize.py renames the files to the final post titles.

Temporary files go to workspace/out/<video-id> and workspace/build/<video-id>, so two runs at once don't collide.
"""
import argparse
import datetime
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

from common import DATA_DIR, PUBLIC, WORKSPACE, load_json, need, probe, safe_name, slug, utf8

CRF = {"draft": 28, "high": 18, "max": 14}
LOUDNESS = "I=-14:TP=-1.5:LRA=11"  # -14 LUFS is what YouTube Shorts / Reels normalise to
# speech lift for loud game sound, music or crowds: cut rumble, add presence around 3 kHz, even out the level
VOICE_BOOST = "highpass=f=90,equalizer=f=3000:t=q:w=1:g=4,acompressor=threshold=0.125:ratio=3:attack=5:release=150"


def npx():
    return shutil.which("npx") or sys.exit("npx not found: install Node.js")


def run_key(video_id, out_dir):
    return slug(video_id or Path(out_dir).name, 60) or "run"


def bundle(build_rel):
    r = subprocess.run([npx(), "remotion", "bundle", "src/index.ts", f"--out-dir={build_rel}"], cwd=WORKSPACE,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit("bundling the Remotion workspace failed; run scripts/setup.py")


def rank_of(clip, path, fallback):
    r = clip.get("rank")
    if isinstance(r, int) and r > 0:
        return r
    for text in (str(clip.get("id", "")), Path(path).stem):
        m = re.search(r"(\d+)$", text) or re.search(r"\d+", text)
        if m and int(m.group()) > 0:
            return int(m.group())
    return fallback


def srt_of(clip, path):
    def ts(ms):
        ms = max(0, int(ms))
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines = []
    for i, p in enumerate(clip["pages"], 1):
        lines += [str(i), f"{ts(p['startMs'])} --> {ts(p['endMs'])}", " ".join(w["text"] for w in p["words"]), ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def mean_volume(path):
    r = subprocess.run([need("ffmpeg"), "-v", "info", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "mean_volume" in line:
            return float(line.split(":")[1].split()[0])
    return None


def on(v):
    return v is True or str(v).lower() in ("on", "true", "yes")


TALK_OVER = {"content_face", "meme", "meme+faces"}  # someone talking over gameplay, a screen or another video


def boost_on(s, clip):
    """voice_boost. `auto` is meant to be decided in the video profile; if it's still auto here, boost when the
    clip shows someone talking over gameplay or another video, where that sound competes with the voice."""
    v = s.get("voice_boost", "auto")
    if str(v).lower() == "auto":
        return any(x.get("layout") in TALK_OVER for x in clip.get("segments", []))
    return on(v)


def music_of(clip):
    """background_music, mixed here (after the voice boost, so the music isn't boosted) rather than by Remotion."""
    m = (clip.get("style") or {}).get("music")
    p = PUBLIC / m if m else None
    return p if p and p.exists() else None


def audio_inputs(src, clip):
    music = music_of(clip)
    return ["-i", str(src)] + (["-stream_loop", "-1", "-i", str(music)] if music else [])


def audio_graph(s, clip, tail, has_voice=True):
    """ffmpeg -filter_complex for the clip's audio: voice boost, bleeps, background music, then `tail` (loudnorm or
    nothing). Input 0 is the rendered clip, input 1 the looped music if there is any."""
    parts, last = [], None
    bleeps = clip.get("bleeps") or []
    when = "+".join(f"between(t,{a / 1000:.3f},{b / 1000:.3f})" for a, b in bleeps)
    if has_voice:
        chain = [VOICE_BOOST] if boost_on(s, clip) else []
        if bleeps:
            chain.append(f"volume=0:enable='{when}'")
        parts.append("[0:a]" + (",".join(chain) or "anull") + "[v]")
        last = "[v]"
        if bleeps:  # ffmpeg's sine is -18 dBFS, about the level of normal speech
            parts.append(f"sine=frequency=1000:sample_rate=48000,volume=0:enable='not({when})'[b]")
            parts.append(f"{last}[b]amix=inputs=2:duration=first:normalize=0[vb]")
            last = "[vb]"
    if music_of(clip):
        st = clip.get("style") or {}
        dur = clip["durationInFrames"] / clip["fps"]
        fade = max(0.0, float(st.get("fadeMs", 250) or 0) / 1000)
        m = f"[1:a]aresample=48000,volume={float(st.get('musicVolume', 0.08) or 0.08)}"
        if not has_voice:
            m += f",atrim=0:{dur:.3f}"
        if fade:
            m += f",afade=t=in:d={fade:.3f},afade=t=out:st={max(0.0, dur - fade):.3f}:d={fade:.3f}"
        parts.append(m + "[m]")
        if last:
            parts.append(f"{last}[m]amix=inputs=2:duration=first:normalize=0[vm]")
            last = "[vm]"
        else:
            last = "[m]"
    parts.append(f"{last}{tail or 'anull'}[out]")
    return ";".join(parts)


def measure_loudness(src, s, clip, has_voice=True):
    """First loudnorm pass: the clip's measured loudness, so the second pass can level it accurately (linear)."""
    r = subprocess.run([need("ffmpeg"), "-hide_banner", "-nostats", *audio_inputs(src, clip), "-filter_complex",
                        audio_graph(s, clip, f"loudnorm={LOUDNESS}:print_format=json", has_voice), "-map", "[out]",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        return None
    j = json.loads(m.group())
    try:
        vals = [float(j[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")]
    except (KeyError, ValueError):
        return None
    if not all(math.isfinite(v) for v in vals) or vals[0] < -70:  # silence: nothing to level
        return None
    i, tp, lra, thresh, off = vals
    return (f"loudnorm={LOUDNESS}:measured_I={i}:measured_TP={tp}:measured_LRA={lra}:"
            f"measured_thresh={thresh}:offset={off}:linear=true")


def finish_audio(tmp, final, s, clip):
    level = s.get("normalize_loudness", True)
    has_voice = probe(tmp)["audio"]
    work = (has_voice and (level or boost_on(s, clip) or clip.get("bleeps"))) or music_of(clip)
    if not work:
        shutil.copy2(tmp, final)
        return
    tail = ""
    if level:
        tail = measure_loudness(tmp, s, clip, has_voice) or f"loudnorm={LOUDNESS}"
    subprocess.run([need("ffmpeg"), "-v", "error", "-y", *audio_inputs(tmp, clip), "-filter_complex",
                    audio_graph(s, clip, tail, has_voice), "-map", "0:v", "-map", "[out]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(final)], check=True)


def save_cover(final, dur, dest, work):
    """The sharpest of five frames (skips blurry motion and transition frames). The clip's own title card is in it
    when the title shows for the whole clip."""
    try:
        import cv2
    except ImportError:
        cv2 = None
    best, best_score = None, -1.0
    for i, frac in enumerate((0.2, 0.35, 0.5, 0.65, 0.8) if cv2 else (0.3,)):
        cand = work / f"cover_{i}.jpg"
        subprocess.run([need("ffmpeg"), "-v", "error", "-y", "-ss", f"{dur * frac:.2f}", "-i", str(final),
                        "-frames:v", "1", "-q:v", "2", str(cand)], check=False)
        if not cand.exists():
            continue
        score = 0.0
        if cv2:
            img = cv2.imread(str(cand), cv2.IMREAD_GRAYSCALE)
            score = float(cv2.Laplacian(img, cv2.CV_64F).var()) if img is not None else 0.0
        if score > best_score:
            best, best_score = cand, score
    if best:
        shutil.move(str(best), dest)
    for f in work.glob("cover_*.jpg"):
        f.unlink(missing_ok=True)


def main():
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--settings", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--video-id", default="")
    a = ap.parse_args()
    s = load_json(a.settings, {})
    out_dir = Path(a.out_dir)
    checks = out_dir / DATA_DIR / "checks"
    checks.mkdir(parents=True, exist_ok=True)
    key = run_key(a.video_id, out_dir)
    tmp_dir = WORKSPACE / "out" / key
    tmp_dir.mkdir(parents=True, exist_ok=True)
    build_rel = f"build/{key}"

    log = out_dir / DATA_DIR / "render_results.json"
    old = load_json(log, [])
    # a clip rendered before keeps its current name (organize.py may have renamed it to the post title)
    known = {r["data"]: r["clip"] for r in old if r.get("ok") and r.get("data") and r.get("clip")}

    print("bundling...", flush=True)
    bundle(build_rel)
    pattern = str(s.get("file_name", "{n:02d} - {title}"))
    results = []
    for i, path in enumerate(a.clips, 1):
        clip = load_json(path)
        props = str(Path(path).resolve())
        title = clip.get("title") or clip["id"]
        n = rank_of(clip, path, i)
        name = known.get(props)
        if not name or not (out_dir / f"{name}.mp4").exists():
            name = safe_name(pattern.format(n=n, title=safe_name(title), slug=slug(title), video_id=a.video_id,
                                            date=datetime.date.today().isoformat()), 110)
        tmp = tmp_dir / f"{slug(clip['id'])}.mp4"
        wrapped = tmp_dir / f"{slug(clip['id'])}.props.json"  # the composition's props are {"data": <clip>}
        # background music is mixed afterwards in finish_audio, so the voice boost and bleeps don't touch it
        render_data = dict(clip, style=dict(clip.get("style") or {}, music=None))
        wrapped.write_text(json.dumps({"data": render_data}, ensure_ascii=False), encoding="utf-8")
        cmd = [npx(), "remotion", "render", build_rel, "Clip", str(tmp), f"--props={wrapped}", "--timeout=240000",
               "--log=error", f"--crf={CRF.get(s.get('quality', 'high'), 18)}"]
        print(f"[{i}/{len(a.clips)}] rendering {name} ...", flush=True)
        r = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True)
        if r.returncode != 0 or not tmp.exists():
            print(r.stdout[-2000:], r.stderr[-2000:])
            results.append({"clip": name, "ok": False, "problem": "render failed", "data": props})
            continue
        final = out_dir / f"{name}.mp4"
        finish_audio(tmp, final, s, clip)
        tmp.unlink(missing_ok=True)
        wrapped.unlink(missing_ok=True)

        info = probe(final)
        dur = clip["durationInFrames"] / clip["fps"]
        problems = []
        if (info["width"], info["height"]) != (clip["width"], clip["height"]):
            problems.append(f"size {info['width']}x{info['height']}")
        if abs(info["duration"] - dur) > 0.4:
            problems.append(f"length {info['duration']:.1f}s, expected {dur:.1f}s")
        vol = mean_volume(final) if info["audio"] else None
        if not info["audio"]:
            problems.append("no audio")
        elif vol is not None and vol < -45:
            problems.append(f"audio nearly silent ({vol} dB)")
        if s.get("export_thumbnail", True):
            save_cover(final, dur, out_dir / f"{name}.jpg", tmp_dir)
        if s.get("export_srt", False):
            srt_of(clip, out_dir / f"{name}.srt")
        step = max(dur / 8, 0.5)
        subprocess.run([need("ffmpeg"), "-v", "error", "-y", "-i", str(final), "-vf",
                        f"fps=1/{step:.3f},scale=240:-2,tile=8x1", "-frames:v", "1",
                        str(checks / f"{name}.jpg")], check=False)
        res = {"clip": name, "file": str(final), "ok": not problems, "seconds": round(info["duration"], 1),
               "size": f"{info['width']}x{info['height']}", "mean_volume_db": vol, "problems": problems,
               "check_sheet": str(checks / f"{name}.jpg"), "data": props, "title": clip["title"], "rank": n}
        results.append(res)
        print("   " + json.dumps(res, ensure_ascii=False), flush=True)
    done = {r["data"] for r in results}
    kept = [r for r in old if r.get("data") not in done]
    log.write_text(json.dumps(kept + results, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(bad)}/{len(results)} clips OK" + (f"; problems: {bad}" if bad else ""))


if __name__ == "__main__":
    main()
