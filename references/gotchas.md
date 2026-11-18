# Gotchas (already hit, already solved)

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: cv2` although it's installed | ran `python -I`, which hides user site-packages | run scripts with plain `python` |
| `cv2 has no attribute CascadeClassifier` | OpenCV 5 removed the Haar face detector | `pip install "opencv-python-headless<5"` (setup.py does this) |
| `UnicodeEncodeError: 'charmap' codec` when printing Hindi | Windows console defaults to cp1252 | scripts call `utf8()`; for one-off `python -c`, add `sys.stdout.reconfigure(encoding='utf-8')` |
| `HTTP Error 429` fetching subtitles | YouTube rate-limits caption downloads, worse when fetching several languages | fetch only the original track; fetch.py retries with backoff |
| ffmpeg `drawtext` crashes with "Fontconfig error" on Windows | no fontconfig config | don't burn text with ffmpeg; Remotion draws all text |
| Choppy or stuttering motion | output fps differs from the source (e.g. 30 fps output from 24 fps source) | `fps: source` (the default) |
| A meme or phone video framed as a webcam | its background wasn't dark enough to read as a divider | the threshold is dark grey (< 50/255). Fix the shot by hand (references/layouts.md) |
| Dark game/film scenes split into fake "webcam tiles" | dark scenery reads as dark divider columns | dividers must also be one flat colour (std < 6); fixed in analyze_shots.py, and `single_focus: content` always shows the whole picture |
| A 5-webcam layout read as "meme" | its middle webcam is tall like a phone video | the meme rule requires every other tile to be thumbnail-sized; check `tiles` vs `meme` in the printout |
| Captions wrap onto two lines | long words in a 3-word group | lower `max_caption_chars` or `words_per_caption` |
| Caption words drift from speech | tokens file has an extra or missing line | build_clip.py prints both columns: fix where they diverge |
| Clip starts on the tail of the previous shot | the start time fell 1-5 frames before a camera cut | move the start to the cut time printed by analyze_shots.py |
| Video/audio out of sync in a section download | section files start on a keyframe | fetch.py uses `force_keyframes_at_cuts`; always pass the printed `--offset` |
| `npm warn install-scripts ... esbuild` during setup | npm's new script approval | harmless: Remotion bundles fine (setup verifies with a bundle) |
| Remotion can't load the video (404) | the file is outside the workspace's `public/` | always fetch videos with fetch.py; local files are copied into `public/source/` |
| Upload stays private | unaudited API project | expected; see references/youtube.md |
| `quotaExceeded` | 10,000 units/day used up (~6 uploads) | wait for the reset (midnight Pacific time) or request more quota |
