"""Render clip data files to finished MP4s, then level the loudness, save extras and check the result.

Usage:
  python render.py clip_1.json clip_2.json ... --settings run_settings.json --out-dir out/clips/<video-id>

For every clip it writes, in --out-dir:
  <name>.mp4          the finished clip (name from the file_name setting)
  <name>.jpg          cover image (if export_thumbnail)
  <name>.srt          subtitles (if export_srt)
  _checks/<name>.jpg  8-frame contact sheet: LOOK AT IT before calling the clip done
and prints one summary line per clip (size, length, audio level, problems found).
"""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

from common import WORKSPACE, load_json, need, probe, slug, utf8

CRF = {"draft": 28, "high": 18, "max": 14}


def npx():
    return shutil.which("npx") or sys.exit("npx not found: install Node.js")


def bundle():
    r = subprocess.run([npx(), "remotion", "bundle", "src/index.ts", "--out-dir=build"], cwd=WORKSPACE,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit("bundling the Remotion workspace failed; run scripts/setup.py")


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
    (out_dir / "_checks").mkdir(parents=True, exist_ok=True)
    tmp_dir = WORKSPACE / "out"
    tmp_dir.mkdir(exist_ok=True)

    print("bundling...", flush=True)
    bundle()
    pattern = str(s.get("file_name", "{n}_{slug}"))
    results = []
    for n, path in enumerate(a.clips, 1):
        clip = load_json(path)
        name = pattern.format(n=n, slug=slug(clip.get("title") or clip["id"]), video_id=a.video_id,
                              date=datetime.date.today().isoformat())
        tmp = tmp_dir / f"{clip['id']}.mp4"
        props = Path(path).resolve()
        wrapped = tmp_dir / f"{clip['id']}.props.json"  # the composition's props are {"data": <clip>}
        wrapped.write_text(json.dumps({"data": clip}, ensure_ascii=False), encoding="utf-8")
        cmd = [npx(), "remotion", "render", "build", "Clip", str(tmp), f"--props={wrapped}", "--timeout=240000",
               "--log=error", f"--crf={CRF.get(s.get('quality', 'high'), 18)}"]
        print(f"[{n}/{len(a.clips)}] rendering {name} ...", flush=True)
        r = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True)
        if r.returncode != 0 or not tmp.exists():
            print(r.stdout[-2000:], r.stderr[-2000:])
            results.append({"clip": name, "ok": False, "problem": "render failed"})
            continue
        final = out_dir / f"{name}.mp4"
        if s.get("normalize_loudness", True):
            # -14 LUFS is what YouTube Shorts / Reels / TikTok normalise to
            subprocess.run([need("ffmpeg"), "-v", "error", "-y", "-i", str(tmp), "-c:v", "copy",
                            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", str(final)],
                           check=True)
        else:
            shutil.copy2(tmp, final)
        tmp.unlink(missing_ok=True)

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
            subprocess.run([need("ffmpeg"), "-v", "error", "-y", "-ss", f"{dur * 0.3:.2f}", "-i", str(final),
                            "-frames:v", "1", "-q:v", "3", str(out_dir / f"{name}.jpg")], check=False)
        if s.get("export_srt", False):
            srt_of(clip, out_dir / f"{name}.srt")
        step = max(dur / 8, 0.5)
        subprocess.run([need("ffmpeg"), "-v", "error", "-y", "-i", str(final), "-vf",
                        f"fps=1/{step:.3f},scale=240:-2,tile=8x1", "-frames:v", "1",
                        str(out_dir / "_checks" / f"{name}.jpg")], check=False)
        res = {"clip": name, "file": str(final), "ok": not problems, "seconds": round(info["duration"], 1),
               "size": f"{info['width']}x{info['height']}", "mean_volume_db": vol, "problems": problems,
               "check_sheet": str(out_dir / "_checks" / f"{name}.jpg"), "data": str(props), "title": clip["title"]}
        results.append(res)
        print("   " + json.dumps(res, ensure_ascii=False), flush=True)
    log = out_dir / "render_results.json"
    old = load_json(log, [])
    log.write_text(json.dumps(old + results, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(bad)}/{len(results)} clips OK" + (f"; problems: {bad}" if bad else ""))


if __name__ == "__main__":
    main()
