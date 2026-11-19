# Gotchas (already hit, already solved)

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: cv2` although it's installed | ran `python -I`, which hides user site-packages | run scripts with plain `python` |
| `cv2 has no attribute CascadeClassifier` | OpenCV 5 removed the Haar face detector | `pip install "opencv-python-headless<5"` (setup.py does this) |
| `UnicodeEncodeError: 'charmap' codec` when printing Hindi | Windows console defaults to cp1252 | scripts call `utf8()`; for one-off `python -c`, add `sys.stdout.reconfigure(encoding='utf-8')` |
| `HTTP Error 429` fetching subtitles | YouTube rate-limits caption downloads, worse when fetching several languages | fetch only the original track; fetch.py retries with backoff |
| ffmpeg `drawtext` crashes with "Fontconfig error" on Windows | no fontconfig config | don't burn text with ffmpeg; Remotion draws all text |
| Choppy or stuttering motion | output fps higher than the source's (e.g. 30 fps output from a 24 fps source) | a number in `fps` is a cap (the default 30 keeps 24/25 fps sources as they are); `fps: source` always matches |
| A meme or phone video framed as a webcam | its background wasn't dark enough to read as a divider | the threshold is dark grey (< 50/255). Fix the shot by hand (references/layouts.md) |
| Dark game/film scenes split into fake "webcam tiles" | dark scenery reads as dark divider columns | dividers must also be one flat colour (std < 6); fixed in analyze_shots.py, and `single_focus: content` always shows the whole picture |
| A 5-webcam layout read as "meme" | its middle webcam is tall like a phone video | the meme rule requires every other tile to be thumbnail-sized; check `tiles` vs `meme` in the printout |
| Captions wrap onto two lines | long words in a 3-word group | lower `max_caption_chars` or `words_per_caption` |
| Caption words drift from speech | tokens file has an extra or missing line | build_clip.py prints both columns: fix where they diverge |
| Clip starts on the tail of the previous shot | the start time fell 1-5 frames before a camera cut (older versions also timed shots by counting frames after OpenCV's seek, which can be a few frames off) | analyze_shots.py now uses each frame's own timestamp; move the start to the cut time it prints |
| Video/audio out of sync in a section download | section files start on a keyframe, or the offset was rounded to whole seconds | fetch.py re-encodes the cut (`force_keyframes_at_cuts`) and prints the exact offset (fractions included); always pass it as `--offset` |
| `no frames between ...` from analyze_shots.py | START/END outside the file, usually a missing or wrong `--offset` for a section file | the message shows the part of the original the file covers |
| `npm warn install-scripts ... esbuild` during setup | npm's new script approval | harmless when setup prints `[ok] Remotion workspace`: after npm install, setup bundles the workspace once to check |
| Subtitles come back in the wrong language (e.g. `subs.ar-orig.vtt` for an English video) | videos with YouTube auto-dubbing have one `-orig` track per dub language, and the video's language (`en-US`) didn't match the track name (`en-orig`) | fetch.py matches the base language (`en`) and only guesses "any -orig" when there is exactly one |
| Transcript full of `&gt;&gt;`, `&nbsp;` and `[ __ ]` | YouTube auto captions use HTML codes, `>>` for a new speaker, and `[ __ ]` for a hidden swear | transcript.py decodes them, drops `>>`, and keeps each hidden swear as a spoken word `****` (so tokens files still line up) |
| Facecam-over-gameplay read as `people` (a split between the streamer and a game character) | the facecam check only looked at the biggest face, and a streamer moving their head failed the "stays still" test | every face is checked, and "still" allows movement up to about the face's own size |
| A gameplay video's layout flips between tiles / single / content_face every second or two | dark cutscenes and camera cuts confuse the border and face detection | when the layout never changes (a facecam always in the same box), write one segment per clip with fixed panels (references/layouts.md) |
| A shell `while read` loop over clips skips or mangles clips | ffmpeg inside the loop reads the loop's input | pass `-nostdin` to every ffmpeg in a loop |
| Crops jump between very short shots during one steady webcam layout | moving dark content (game scenes, film, test patterns) made the panel-border detection flicker, and every flicker counted as a cut | a layout change now counts as a cut only if it holds for 0.5 s (`LAYOUT_HOLD_S` in analyze_shots.py); real picture cuts still count at once |
| Two people side by side in a close-up framed as one crop between them | older face grouping merged faces within 1.5× face size | a face never joins a person already seen in the same frame; fixed in analyze_shots.py |
| A re-rendered clip came out as `01 - ...` | older render.py numbered clips by their position in the command | the number now comes from the clip's `--id` (its rank); a re-render keeps the clip's current name |
| `privacy is 'scheduled' but publish_at is empty` | a scheduled meta without a time | run `youtube_upload.py schedule` and put the time in `publish_at` |
| Remotion can't load the video (404) | the file is outside the workspace's `public/` | always fetch videos with fetch.py; local files are copied into `public/source/` |
| Upload stays private | unaudited API project | expected; see references/youtube.md |
| `quotaExceeded` | 10,000 units/day used up (~6 uploads) | wait for the reset (midnight Pacific time) or request more quota |
