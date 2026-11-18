---
name: video-clipper
description: Turn any long video (a YouTube or other link, or a local file) into short clips with multi-angle layouts and word-timed captions in any language (including Hinglish), then write titles, descriptions and hashtags and optionally upload or schedule them on the user's YouTube channel. Works for every kind of video - podcasts, interviews, gaming streams, standup, vlogs, reactions, video calls, tutorials, lectures, sports, music. Use it whenever the user pastes a video link and asks for clips, shorts, reels, TikToks, highlights or "best moments", says "cut this into clips" or "make shorts from this", wants captions burned into short clips, or wants clips posted or scheduled on YouTube, even if they don't name this skill.
---

# Video Clipper

Turns one long video into finished short clips: finds the best moments, frames them for the chosen shape
(splitting the screen when several people or a facecam + gameplay are on), adds word-timed captions, writes
the post text, and can upload to YouTube.

You do the judgment work (understanding the video, picking moments, writing captions and titles, checking the
results). The scripts do the mechanical work. Keep it that way: the scripts are tested, and hand-rolled
ffmpeg/OpenCV code drifts from what the renderer expects.

**Paths.** `SKILL` = this folder. Scripts live in `SKILL/scripts/`; run them with plain `python` (not `python -I`,
which hides user-installed packages such as OpenCV). Working files go to `~/.video-clipper/`:
`runs/<video-id>/` per video (call it `RUN`) and `workspace/` (the Remotion project that renders clips).
Finished clips go to `<output_folder>/<folder>/`, one folder per source video, named "Title (Channel)".
`fetch.py info` prints that `folder` name. Call it `OUT`. Clips are named after their titles (`01 - <title>.mp4`).
Technical files live in `OUT/_data/`, so the folder stays easy to browse.

## 0. First run on a machine

```bash
python SKILL/scripts/setup.py
```
It lists what's missing. `--install` pip-installs Python packages and sets up the Remotion workspace (one-time
npm install). Add `--with-whisper` when a video has no subtitles, `--with-youtube` before the first upload.
ffmpeg and Node.js 18+ must be installed by the user; tell them how if they're missing.

## 1. Settings

`SKILL/settings.md` holds the user's choices (read it; it explains every option). Priority: what the user said
in chat for this run > settings.md > `auto` (you decide from the video). Make the run's settings file:

```bash
python SKILL/scripts/settings.py --set clip_count=3 --set orientation=square --out RUN/settings.json
```
Pass every one-off instruction from the chat as a `--set`. After step 3, replace each `auto` you can decide
with a concrete value and save again, so every later script sees real values.

**Ask first, in one message, before any analysis.** Both questions come before you download or study anything,
so the user decides how much of the work is theirs:
- **Who finds the moments** (`moment_finder`). With `ask` (in assisted mode), ask: *"Do you want to pick the
  parts yourself (send time ranges like 12:30-13:10, or describe them), or should I study the video and suggest
  the best moments?"* With `me`, ask for the ranges. With `claude`, or `ask` in autopilot, don't ask.
- **Permission to post.** If `upload_to` is `youtube` and `rights_check` is `ask`, ask whether the user may post
  clips of this video (their own content, a creator who allows clipping, or permission). Reuploading other people's
  videos gets channels copyright strikes. If the answer is no or unclear, still make the clips, but don't upload.

**When the user picks the moments**, skip the moment-finding work (signals, ranking in step 4), but still:
- fetch the transcript (captions need it)
- look at the picture (layout needs it)
- write a short profile

Map described parts ("where he talks about the cash register") to times using the transcript. Snap their
ranges to word boundaries; a few tenths of a second is fine, never more without saying so. If a range breaks
`min_length_s`/`max_length_s`, or cuts a sentence in half, say so once and suggest a fix. Their choice wins.

## 2. Get the video and its words

```bash
python SKILL/scripts/fetch.py info "<url or file>"          # id, title, length, language, subtitle tracks
python SKILL/scripts/fetch.py subs "<url>"                  # original-language subtitles -> RUN/subs.vtt
python SKILL/scripts/transcript.py subs RUN/subs.vtt --out RUN
```
- No subtitles, a local file, or `transcript_source: whisper`: use `fetch.py audio`, then
  `transcript.py whisper RUN/audio.m4a --out RUN --model <whisper_model>`.
- Download the video: with `download_mode: full`, or `auto` and a video under ~45 minutes, run
  `fetch.py video "<url>" --quality <download_quality>` now. Otherwise download only the picked ranges in step 5.
- Measure what happens second by second (loudness spikes = laughter, cheers, shouting, game action):
  `signals.py <audio or video> --words RUN/words.json --out RUN`. Add `--visual <video>` when moments are
  visual (gaming, sports, action) and the full video is downloaded.

## 3. Understand the video (the video profile)

Read `RUN/transcript.txt` in full: it is your main view of the content. Also read `RUN/info.json` (title,
description, chapters, tags) and the signals summary, and look at the picture: make a contact sheet of the
whole video and view it.
```bash
ffmpeg -v error -y -i VIDEO -vf "fps=1/30,scale=320:-2,tile=6x6" -frames:v 1 RUN/overview.jpg
```
(Pick the fps so the sheet covers the whole video; make several sheets for long videos.)

Then write `RUN/profile.md`, 5 to 10 lines:
- what kind of video it is and who is in it
- how it looks on screen: one camera / several / webcam grid / facecam over gameplay / stage / slides
- the spoken language, and the caption language you'll use
- what a great moment looks like in this video
- every `auto` setting and what you resolved it to

Don't assume a genre from one signal: a "podcast" may be a gaming stream with a talk segment. Decide per clip
when the video mixes formats. `references/picking-moments.md` has per-genre guidance.

## 4. Pick the moments

(If the user gave the ranges themselves, go straight to step 5 with their ranges.)

Read `references/picking-moments.md` before the first pick. In short:
- Respect `min_length_s` / `max_length_s`, `clip_count`, `clip_focus`, `avoid_explicit`.
- `hook_first`: start on the line or action that makes someone stop scrolling, not on the run-up to it.
- `self_contained`: a stranger must get it without the full video. Include the setup a punchline needs.
- End after the payoff plus the reaction to it (the laugh, the "no way"), before the next topic starts.
- Snap both ends to word timings from `RUN/words.json`: never start or end mid-word.
- Clips that are mostly something the creator is reacting to (a meme, someone else's video, a match broadcast)
  carry extra copyright risk: prefer moments where the creator's own talk is the value.

Present a ranked list: `# | start-end | length | working title | opening line | why it works`.
With `picking: ask`, show the list (and the profile) and wait. With `picking: auto`, take the top ones.

## 5. Frame each clip

If the video wasn't downloaded in full, fetch only the picked ranges, padded by 2 s:
`fetch.py video "<url>" --sections "1098-1161,1407-1448"`. Each file's offset is printed. Pass it as `--offset`.

```bash
python SKILL/scripts/analyze_shots.py VIDEO START END RUN/shots_1.json --settings RUN/settings.json [--offset O]
```
It prints one line per shot: the layout it chose (tiles, meme, content_face, people, single, content) and the
crops (`~` = the crop follows a moving person). Check it against the picture:
```bash
ffmpeg -v error -y -ss START -t LENGTH -i VIDEO -vf "fps=1/2,scale=320:-2,tile=6x5" -frames:v 1 RUN/range_1.jpg
```
If a shot is framed wrong (a face missed, a meme mistaken for a webcam), edit that shot's `panels` in the JSON.
`references/layouts.md` explains every layout and how to fix common misreads.

## 6. Captions

Decide the caption words per clip. `references/captions.md` has the rules and the file formats:
- **Same language and script as spoken**: use the transcript's words, no file needed. Add a `.tokens.txt` only to
  fix misheard words (names, brands, slang).
- **Hindi/Urdu speech, Hinglish captions** (the `auto` result for Hindi): write a `.tokens.txt`, one Roman-script
  word per transcript word, with English words kept in English.
- **Translated captions**: write a `.phrases.txt` with timed lines.

Write a short title for the on-screen title card, in the caption language. Then:
```bash
python SKILL/scripts/build_clip.py --run RUN --shots RUN/shots_1.json --start S --end E --id 1 \
  --title "On-screen title" --settings RUN/settings.json --out RUN/clip_1.json [--captions RUN/captions_1.tokens.txt]
```
A word-count mismatch prints both columns side by side: fix the lines where they drift and run it again.

## 7. Render and check

```bash
python SKILL/scripts/render.py RUN/clip_1.json RUN/clip_2.json --settings RUN/settings.json \
  --out-dir "OUT" --video-id <video-id>
```
It renders, levels loudness, saves cover images and subtitle files if enabled, and writes a contact sheet per
clip to `OUT/_data/checks/`. **Open every check sheet** (read the image) before calling a clip done. Look for:
- faces cut off or off-centre
- a split screen where one view would be better, or the reverse
- captions covering faces
- captions wrapping onto two lines

Fix the shots JSON or the settings, rebuild that one clip and render it again. Problems in the summary line
(wrong size, no audio, wrong length) must be fixed, not reported.

(Don't delete anything yet: re-cuts need the source and the run files. Cleanup is the last step.)

## 8. Titles, descriptions, hashtags

For each finished clip write `OUT/_data/<clip file name>.meta.json` (format in `scripts/youtube_upload.py`), with
post text for every platform in `post_platforms`. Every clip gets the full set a short needs to perform:
- a scroll-stopping **title** (YouTube), a **description** that opens on a hook line and ends with a comment
  question (the call to action), and the credit line
- **hashtags**: a few relevant ones, the strongest first
- **search tags**: keywords people actually type
- a **pinned comment** that starts a conversation
- a **suggested posting time**
- an **Instagram Reels caption** and a **TikTok caption**, each written for that app (see `references/youtube.md`)

Read `references/youtube.md` for how to write them. In short:
- With `trend_research: on`, run `trends.py --query "<clip topic>" --region <trend_region> --shorts` for each
  topic. Exit code 2 means no API access: use web search for what's trending instead.
- Title: the clip's hook in at most `title_max_chars` characters, in `metadata_language`, front-loaded,
  and honest. `honest_titles` is about reach as well as rules: viewers who feel tricked swipe away and YouTube
  notices.
- Description: shaped by `description_style`. Add the credit line when `credit_source` is on.
- Hashtags: `hashtags` of them, put the most important 3 first, add `always_hashtags`. Use only relevant ones.

Then tidy the folder: `python SKILL/scripts/organize.py "OUT"`. It renames every clip (and its cover and subtitles)
to `NN - <post title>`, keeps the ranked order, moves the post files to `_data/`, and writes `posts.md` with all
the post text. Upload with the renamed paths it prints.

## 9. Upload (only when `upload_to: youtube`)

- `youtube_upload.py whoami`. If no channel is connected, walk the user through the one-time setup in
  `references/youtube.md`. They do the Google sign-in themselves; never handle their password.
- Publish times: `youtube_upload.py schedule --count N --settings RUN/settings.json`. Put the time into each
  meta's `publish_at` when `privacy: scheduled`.
- `review_before_publish: true`: upload everything as private, give the user the links, and wait for an OK
  before running `youtube_upload.py publish <id>` (or `--at <time>`). With `false`, upload with the final privacy.
- `youtube_upload.py upload <mp4> --meta <meta.json>` per clip. Respect `max_uploads_per_day`. The free API
  quota allows about 6 uploads a day, and new API projects can only upload private videos until Google audits them.
- Run `posts.py "OUT"` again so posts.md shows the links.

## 10. Finish

Append a short entry to `log_file`: the video, the profile, each clip (time range, title, file, upload link)
and anything that needed a manual fix. Write the log **before** cleaning up, because the profile lives in the run
folder.

**Clean up** (`cleanup` setting, unless `none`). Do it once the clips are final: every check passed, uploads done,
and in assisted mode the user has seen the clips and wants no re-cuts.
```bash
python SKILL/scripts/cleanup.py <video-id> --out "OUT" --level full     # or --level source
```
`full` deletes everything with no further use:
- the long video and its audio
- the run folder: subtitles, transcripts, word timings, signals, profile, overview/range frames, shots, caption
  files, clip data
- the check sheets and render results
- the renderer's temporary files

It keeps:
- the clips with their covers and subtitles
- `posts.md`
- the post files in `OUT/_data` (needed to upload, schedule or publish later)
- the log

It never touches a file the user pointed at; a local video is copied into the workspace and only the copy is deleted.

Then report to the user:
- a table of the clips: title, length, file, link
- what you decided for the `auto` settings
- anything that still needs their attention
- how much space the cleanup freed

**When nothing was uploaded automatically** (`upload_to: none`, or the upload was skipped), the user posts by
hand, so put the complete post text for every clip in the reply itself, ready to copy. Don't make them open
files for it. Per clip:
- YouTube title, description (hashtags included) and tags
- the Instagram caption and the TikTok caption
- the pinned comment and the suggested time

Use one copyable code block per field. Also point to `posts.md`, which holds the same text.

## Reference files

- `references/picking-moments.md`: what makes a clip work, per kind of video; where to cut
- `references/captions.md`: caption language and script, Hinglish rules, tokens/phrases file formats
- `references/layouts.md`: what each layout is, how the analyzer decides, fixing misreads by hand
- `references/youtube.md`: channel setup, quotas, scheduling, titles/hashtags that perform, copyright
- `references/gotchas.md`: problems already hit and their fixes (read when something fails)
