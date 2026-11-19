# Video Clipper

A Claude skill that turns any long video into short, ready-to-post clips, and can post them to YouTube.

Give it a YouTube link (or any link yt-dlp supports, or a video file on your computer). It finds the best moments
(or uses the ones you choose), frames each one for the shape you want, adds word-by-word captions, writes a title,
description and hashtags for each clip, and can upload or schedule them on your channel.

It works for every kind of video: podcasts, interviews, video calls, reaction streams, gaming (with or without a
facecam), standup, vlogs, tutorials, lectures, sports and music. It doesn't assume a genre. It looks at each video
and decides.

---

## Contents

1. [What you get](#1-what-you-get)
2. [Setup](#2-setup)
3. [Using it with Claude](#3-using-it-with-claude)
4. [The flow, step by step](#4-the-flow-step-by-step)
5. [Settings](#5-settings)
6. [How it decides: the logic](#6-how-it-decides-the-logic)
7. [Using it yourself, without Claude](#7-using-it-yourself-without-claude)
8. [Files and folders](#8-files-and-folders)
9. [Limits and known issues](#9-limits-and-known-issues)
10. [Copyright, terms and licenses](#10-copyright-terms-and-licenses)

---

## 1. What you get

One folder per source video, named after it, e.g. `out/clips/Why GTA 6 Graphics Is INCREDIBLE (INTER)/`:

| File | What it is |
|---|---|
| `01 - <title>.mp4` | The finished clip, named after its post title: framed, captioned, loudness levelled for Shorts/Reels |
| `01 - <title>.jpg` | Its cover image |
| `01 - <title>.srt` | Subtitles (if `export_srt` is on) |
| `_data/01 - <title>.meta.json` | Post text and upload info: YouTube title, description, hashtags, tags; Instagram caption (and TikTok, if in `post_platforms`); pinned comment; suggested posting time |
| `posts.md` | All of that, copy-ready, for every clip, with YouTube links once uploaded |
| `_data/checks/01 - <title>.jpg` | An 8-frame contact sheet used to check the clip |
| `_data/render_results.json` | Size, length and audio level of every render |

When the clips aren't uploaded automatically, Claude also gives the full post text for every clip right in the
chat, ready to copy.

When the run is finished, everything with no further use is **deleted** (`cleanup: full`, the default):
- the long source video
- subtitles and transcripts
- analysis files and check frames
- render leftovers

The folder ends up holding only what you use: the clips, their covers and subtitles, `posts.md`, and the small
post files in `_data` that uploading needs. Set `cleanup: source` to keep transcripts for more clips later, or
`none` to keep everything.

## 2. Setup

### Install the skill

Claude Code loads skills from `~/.claude/skills/`. Clone this repository there:

```bash
# macOS / Linux
git clone https://github.com/justkalesh/video-clipper-skill.git ~/.claude/skills/video-clipper
```
```powershell
# Windows (PowerShell)
git clone https://github.com/justkalesh/video-clipper-skill.git "$env:USERPROFILE\.claude\skills\video-clipper"
```

Start a new Claude Code session afterwards. The skill shows up as `video-clipper`, and Claude uses it whenever
you ask for clips. To update it later, run `git pull` in that folder.

### Install what it needs

You need **Python 3.10+**, **ffmpeg** and **Node.js 18+** on your PATH:

| | Windows | macOS | Linux (Debian/Ubuntu) |
|---|---|---|---|
| Python | python.org installer | `brew install python` | `sudo apt install python3 python3-pip` |
| ffmpeg | `winget install ffmpeg` | `brew install ffmpeg` | `sudo apt install ffmpeg` |
| Node.js | `winget install OpenJS.NodeJS.LTS` | `brew install node` | nodejs.org or `nvm` |

Then, once, from the skill folder:

```bash
python scripts/setup.py --install                  # Python packages + the Remotion render project (a few minutes)
python scripts/setup.py --install --with-whisper   # also: transcribe videos that have no subtitles
python scripts/setup.py --install --with-youtube   # also: upload to YouTube
```

`setup.py` without flags just reports what's present and what's missing. The Python packages are also listed in
`requirements.txt` if you prefer `pip install -r requirements.txt`. On macOS/Linux the command may be `python3`.

**To post to YouTube**, connect your channel once. You create a free Google Cloud project, turn on the YouTube Data
API and sign in. Step-by-step instructions are in [`references/youtube.md`](references/youtube.md). Claude walks you
through it the first time you turn uploading on.

## 3. Using it with Claude

Paste a link and say what you want. Some examples:

- *"Make clips from this: https://youtu.be/…"*
- *"I'll pick the parts: 3:10–3:55 and 12:40–13:20. Square, yellow captions."*
- *"Find 5 clutch moments in this stream, 15–30 seconds, gameplay on top and my cam below."*
- *"Clip this and schedule the best 3 on my channel, one a day at 7 pm."*
- *"Just write titles and hashtags for the clips in out/clips, don't upload."*

At the start Claude asks, in one message:
1. **Who finds the moments.** You (send time ranges or describe the parts), or Claude (it studies the video and
   suggests a ranked list).
2. **Whether you may post clips of this video.** Only asked if uploading is on.

In **assisted** mode (the default) it also shows you:
- what it understood about the video, and the ranked moments, before rendering
- the clips and their titles, before anything is published

In **autopilot** mode it does everything without stopping.

## 4. The flow, step by step

```
 link or file
     │
     ▼
 0. ASK ─── who finds the moments? may you post this? ───────────────────────── (you answer)
     │
     ▼
 1. SETTINGS ─── settings.md + what you said in chat ──► run settings ───────── settings.py
     │
     ▼
 2. GET IT ─── info, subtitles (or Whisper), video, loudness/action signals ─── fetch.py, transcript.py, signals.py
     │
     ▼
 3. UNDERSTAND ─── reads the transcript, looks at frames ──► video profile ──── Claude
     │                 (genre, layout, language, what a great moment is,
     │                  every "auto" setting resolved)
     ▼
 4. PICK ─── ranked list of moments (or your ranges) ──► you choose ─────────── Claude (+ you)
     │
     ▼
 5. FRAME ─── shot-by-shot: what's on screen, how to lay it out ─────────────── analyze_shots.py
     │
     ▼
 6. CAPTIONS ─── caption words (as spoken / Hinglish / translated) + data file ─ Claude + build_clip.py
     │
     ▼
 7. RENDER & CHECK ─── Remotion render, loudness, cover, srt, contact sheet ──── render.py + Claude looks
     │
     ▼
 8. POST TEXT ─── trends → YouTube title/description/hashtags/tags, ──────────── trends.py + Claude, organize.py
     │                Instagram caption, pinned comment, posting time
     ▼
 9. UPLOAD ─── private for review, or scheduled/public ───────────────────────── youtube_upload.py
     │
     ▼
10. LOG, CLEAN UP, REPORT ─── log entry; delete what has no use left ────────── cleanup.py
               then: table of clips + links, decisions made, space freed;
               if not uploaded: every clip's full post text in the chat, ready to copy
```

The split of work is deliberate. **Claude does the judgment**:
- understanding the video
- choosing moments
- writing captions and titles
- checking every result by eye

**Scripts do the mechanics**:
- downloading and transcribing
- measuring
- framing maths
- rendering and uploading

They behave the same every time.

## 5. Settings

All choices live in [`settings.md`](settings.md): one block of `setting: value` lines, with the allowed values in a
note on each line. Change the word after the colon and save.

**Priority**: what you say in chat for this run > `settings.md` > `auto`.

**`auto`** means "decide from the video". Claude resolves every `auto` after studying the video and lists its
choices in the video profile. For example, a webcam panel gets split screens and a gameplay breakdown gets the whole
shot over a blurred background.

| Group | Main settings |
|---|---|
| Automation | `run_mode` (assisted / autopilot), `log_file` |
| Finding clips | `moment_finder` (ask / me / claude), `clip_count`, `min_length_s`, `max_length_s`, `picking`, `clip_focus`, `moment_signals`, `hook_first`, `self_contained`, `avoid_explicit` |
| Frame & layout | `orientation` (vertical / portrait / square / horizontal), `resolution`, `fps`, `angle_mode` (auto / multi / single), `multi_layout`, `max_panels`, `single_focus`, `screen_content`, `crop_follow`, `zoom_on_static`, `seam_px`, `background_fill` |
| Captions | `caption_language`, `caption_style` (karaoke / pop / line / boxed / none), `words_per_caption`, `max_caption_chars`, `caption_case`, `caption_position`, `font`, `font_size`, `remove_fillers`, `emphasis_words`, `emoji`, `censor`, `captions_when_silent` |
| Colours | `color_scheme` (fire / gold / neon / ice / mono / custom), `custom_colors` |
| Title & branding | `title`, `title_position`, `title_duration`, `watermark`, `progress_bar`, `end_card` |
| Audio | `normalize_loudness`, `voice_boost`, `fade_ms`, `background_music`, `music_volume` |
| Source | `download_quality`, `download_mode`, `transcript_source`, `whisper_model`, `spoken_language` |
| Output | `cleanup`, `output_folder`, `file_name`, `export_srt`, `export_thumbnail`, `quality` |
| Post text | `post_platforms`, `metadata_language`, `trend_research`, `trend_region`, `title_style`, `title_max_chars`, `hashtags`, `always_hashtags`, `tags`, `credit_source`, `honest_titles` |
| Publishing | `upload_to`, `privacy`, `schedule`, `max_uploads_per_day`, `review_before_publish`, `playlist`, `category`, `made_for_kids`, `notify_subscribers`, `altered_content`, `rights_check` |

`settings.md` also has ready-made presets (Bold karaoke, Clean subtitles, Hype, Landscape, Family-safe, Autopilot to
YouTube) and a table of what `auto` usually picks for each kind of video.

## 6. How it decides: the logic

### 6.1 Words and timings
- **Subtitles first.** `fetch.py subs` takes the creator's own subtitles in the spoken language if they exist,
  otherwise YouTube's untranslated auto captions (`-orig`). One track only, because asking for several gets
  rate-limited.
- **Word timings.** YouTube auto captions carry a timestamp per word. `transcript.py` reads those, skipping the
  "rolling" repeats where each cue repeats the previous line. Creator subtitles only have a time per line, so the
  words are spread across the line by length.
- **No subtitles** (or `transcript_source: whisper`): Whisper runs on your computer (GPU if available) and gives word
  timings directly.
- **Markers** like `[Laughter]`, `[Applause]` and `[हंसी]` are kept as markers, not words, and used as moment signals.
- Output: `words.json` (every word with its start/end) and `transcript.txt` (readable, ~15 s paragraphs with times).

### 6.2 Finding moments
Claude reads the whole transcript, plus the video's title, description and chapters. It also uses
`signals.py`, which measures, second by second:
- **loudness spikes** compared with the surrounding 30 s (laughter, cheering, shouting, explosions)
- **visual cuts and action** (`--visual`; editors cut faster around exciting moments)
- **speech density** and **marker positions**

A moment is a good clip when it has a **hook** in the first 1–2 s, **one idea**, a **payoff**, the **reaction** to
it, and a **clean ending**. Edges snap to word timings, so a clip never starts or ends mid-word. Per-genre guidance
is in [`references/picking-moments.md`](references/picking-moments.md).

### 6.3 Framing (layouts)
`analyze_shots.py` reads every frame of the clip's range at half resolution:

1. **Shots.** A new shot starts where the picture changes sharply (a camera cut) or the screen layout changes.
   Blips under 0.25 s fold into a neighbour.
2. **Tiles.** It looks for divider lines between webcams. A divider is a column or row that is dark (< 50/255) along
   92%+ of its length **and** one flat colour. The flatness check stops dark game or film scenery from being
   mistaken for dividers.
3. **What the shot is:**

| Found | Called | Typical source |
|---|---|---|
| 2+ tiles | `tiles` (`tiles_main` if one is much bigger) | video calls, remote panels, reaction streams |
| a tall portrait tile among thumbnail-sized ones | `meme` | the panel watching a phone video |
| a small, still face in a corner | `content_face` | facecam over gameplay or slides |
| 2+ similar-size faces, too far apart for one crop | `people` | studio podcast, interview, two people in one shot |
| one face (or several close together) | `single` | vlog, talking head, stage |
| no faces | `content` | gameplay, B-roll, slides, scenery |

4. **Faces.** OpenCV's face detector runs on every third frame. Detections across frames are grouped into people.
   Faces under ~55% the size of the main one are ignored: they're posters, photos and TV screens in the background.
5. **Settings decide the panels:**
   - `angle_mode: single` keeps one view (`single_focus` says which)
   - `screen_content` chooses content, faces or both
   - `max_panels` caps the count
6. **Arranging panels for the output shape** (vertical shown; horizontal uses columns instead of rows):

| Panels | Arrangement |
|---|---|
| 1 | full frame |
| 2 | top / bottom (content + facecam: content 58% top, face 42% below) |
| 3 | biggest on top, two side by side below |
| 4 | 2×2, or biggest on top + 3 below when one webcam dominates |
| 5 | biggest on top, 4 small below |

7. **Crops.**
   - **Webcams:** the largest crop of the right shape, centred on the face, with the face 42% down from the top.
   - **People sharing one shot:** a head-and-shoulders crop each.
   - **Far-away people:** a slight zoom.
   - **Content:** if a crop would keep less than 60% of the picture, it's shown whole over a blurred copy instead
     (`contain`), so the detail being talked about stays visible.
   - **Letterbox bars** are trimmed first.
8. **Following movement.** If a person moves more than ~6% of the frame width within a shot (`crop_follow: auto`),
   the crop follows them: positions are smoothed over ~2 s and written as keyframes that the renderer
   interpolates.

Every decision is written to `shots_N.json`, which can be edited by hand.

### 6.4 Captions
- **Language and script** (`caption_language: auto`):
  - speech in a Latin-script language: the transcript's words
  - Hindi/Urdu: **Hinglish** (Roman letters, English words kept in English)
  - otherwise: native script, or a translation if asked
- **Three sources of caption words:**

| Source | Use it for | How timing works |
|---|---|---|
| none | the transcript as-is | fillers ("um", "uh") and stutters dropped |
| `.tokens.txt` | rewriting words: Hinglish, fixing misheard names | one line per spoken word, so each keeps its exact time. `-` hides a word, `*word` emphasises it |
| `.phrases.txt` | translations | `start-end \| text` per line; words spread across the line |

- **Grouping into captions.** By style: karaoke/boxed use `words_per_caption` words and at most
  `max_caption_chars` characters (so a caption never wraps), pop uses 1 word, line uses about 7 words. A group
  also breaks at sentence ends, commas and pauses. Each caption stays up at least 0.3 s, but never overlaps the
  next one.
- **On screen** (Remotion, `template/src/Clip.tsx`):
  - the word being spoken lights up in the accent colour; emphasised words stay accented
  - a thick outline and drop shadow keep captions readable on any background
  - captions sit on the line between split views, or in the lower part for a single view
  - the title card sits at the top, or on the split line, falling back to the top when there's no split

### 6.5 Rendering and checks
`build_clip.py` writes one data file per clip:
- the video range, plus the shots with their panels and keyframes
- the caption groups with word timings
- the style

`render.py` bundles the Remotion project once, then renders each clip with that data. After that it:
- processes the audio: optional voice boost (`voice_boost`), beeps over censored words (`censor: bleep`), then
  background music (added after the boost, so it isn't boosted), then levels loudness to −14 LUFS (what Shorts
  and Reels normalise to) in two passes, so the level is accurate
- saves the cover image (the sharpest of five frames) and `.srt`
- **checks** size, length and audio, and makes an 8-frame contact sheet

A clip's number comes from its rank, so re-rendering one clip on its own keeps its number and file name.
Temporary files are kept per video, so two runs can render at the same time.

Claude looks at every contact sheet, checking faces, layout choice, captions over faces and wrapping. It fixes and
re-renders any clip that's off.

Frame rate defaults to **at most 30 fps**: a 60 fps source renders at 30, about twice as fast, and a 24/25 fps
source keeps its own rate, because raising it would make motion stutter.

### 6.6 Titles, descriptions, hashtags
- **Trend research** (`trend_research: on`):
  - `trends.py` searches YouTube for the clip's topic: recent popular videos in the chosen region, their titles,
    tags and hashtags.
  - It uses a YouTube API key, or your connected channel. Without either, Claude uses web search instead.
- **Title.** Claude writes it from the clip's hook in the chosen `title_style` (hook, punchline, question, quote,
  descriptive). The strongest words go in the first ~40 characters, and titles stay honest (`honest_titles`).
- **Hashtags.** `hashtags` relevant ones, the best 3 first, because YouTube shows those above the title. Then
  your `always_hashtags`. Never unrelated trending tags.
- **Description.** Short or full (`description_style`), with the credit line to the original (`credit_source`).
- **Everything else a short needs:**
  - a hook line and a comment question (call to action) in every description
  - search tags
  - a pinned comment that starts a conversation (you post and pin it yourself: the API can't pin comments)
  - a suggested posting time
  - a separate caption for each other app in `post_platforms` (Instagram Reels by default; TikTok if you add it)
- No one can guarantee a clip goes viral. The skill does the things that help: hook, title, hashtags,
  engagement prompts and timing.

### 6.7 Uploading and scheduling
- `youtube_upload.py` uses the official YouTube Data API with your own Google project. The sign-in is saved in
  `~/.video-clipper/youtube/`.
- **Schedule.**
  - `best_times`: 12:00, 18:00 and 21:00 local time
  - `"18:00 daily"`: one a day at that time
  - `"every 4h from 10:00"`: every 4 hours from 10:00
  - `max_uploads_per_day` caps each day.
- **Review gate.** With `review_before_publish: true`, everything is uploaded **private** first. It goes public
  or scheduled only after your OK.
- **Rights gate.** With `rights_check: ask`, Claude asks per link whether you may post it. If not, it makes the
  clips but doesn't upload.
- **Limits:**
  - About 6 uploads a day on the free quota.
  - A new Google project's uploads stay private until Google's free API audit.

## 7. Using it yourself, without Claude

Every step is a script you can run directly. From the skill folder (`R` = `~/.video-clipper/runs/<id>`,
`V` = `~/.video-clipper/workspace/public/source/<id>.mp4`):

```bash
# 0. once
python scripts/setup.py --install

# 1. settings for this run (add --set key=value for one-off changes)
python scripts/settings.py --set orientation=vertical --out R/settings.json

# 2. get the video, its words and signals
python scripts/fetch.py info  "https://youtu.be/VIDEO"          # prints the id
python scripts/fetch.py subs  "https://youtu.be/VIDEO"
python scripts/transcript.py subs R/subs.<lang>.vtt --out R      # -> words.json, transcript.txt
python scripts/fetch.py video "https://youtu.be/VIDEO" --quality 1080
python scripts/signals.py V --words R/words.json --out R          # loudness spikes, markers

# 3-4. read R/transcript.txt, choose a moment, e.g. 754.2 to 801.6 (seconds)

# 5. framing
python scripts/analyze_shots.py V 754.2 801.6 R/shots_1.json --settings R/settings.json

# 6. clip data (add --captions file.tokens.txt / .phrases.txt to change the words)
python scripts/build_clip.py --run R --shots R/shots_1.json --start 754.2 --end 801.6 --id 1 \
  --title "My clip title" --settings R/settings.json --out R/clip_1.json

# 7. render (several clip files at once is fine), check "out/clips/My Video (Channel)/_data/checks/", then free the space
python scripts/render.py R/clip_1.json --settings R/settings.json --out-dir "out/clips/My Video (Channel)" --video-id VIDEO
python scripts/cleanup.py VIDEO --out "out/clips/My Video (Channel)"   # when you're completely done

# 8. post text: write "out/clips/My Video (Channel)/_data/01 - My clip title.meta.json" (format in youtube_upload.py), then
python scripts/trends.py --query "topic words" --region US --shorts    # optional research
python scripts/organize.py "out/clips/My Video (Channel)"     # name clips after their titles, write posts.md

# 9. upload
python scripts/youtube_upload.py auth --client-secret client_secret.json   # once
python scripts/youtube_upload.py upload "out/clips/My Video (Channel)/01 - My clip title.mp4" --meta "out/clips/My Video (Channel)/_data/01 - My clip title.meta.json"
```

For a local file, use its path instead of the link in `fetch.py info/audio/video`. It has no subtitles, so use
`transcript.py whisper`.

To preview or tweak a clip visually, open the Remotion project in `~/.video-clipper/workspace`
(`npx remotion studio`) and load a clip data file as the composition's props.

## 8. Files and folders

```
video-clipper/                     the skill
├── SKILL.md                       the workflow Claude follows
├── README.md                      this file
├── settings.md                    your settings
├── scripts/
│   ├── setup.py                   check / install everything, prepare the render project
│   ├── settings.py                read settings.md (+ overrides) -> JSON
│   ├── fetch.py                   info, subtitles, audio, video (whole or sections); local files
│   ├── transcript.py              subtitles or Whisper -> words.json + transcript.txt
│   ├── signals.py                 loudness spikes, cuts, speech density, markers per second
│   ├── analyze_shots.py           shots, layouts, faces, crops, tracking -> shots_N.json
│   ├── build_clip.py              words + shots + settings -> clip_N.json
│   ├── render.py                  render, loudness, cover, srt, checks
│   ├── trends.py                  what's working on YouTube for a topic
│   ├── cleanup.py                 delete what a finished run no longer needs
│   ├── organize.py                name clips after their titles, tidy the folder, write posts.md
│   ├── posts.py                   all post text in one posts.md
│   ├── youtube_upload.py          connect channel, upload, publish, schedule
│   └── common.py                  shared helpers
├── template/                      the Remotion project (copied into the workspace by setup.py)
│   └── src/Clip.tsx               the clip: panels, captions, title, logo, progress bar, end card, audio
└── references/                    guides Claude reads when needed
    ├── picking-moments.md         what makes a clip work, per kind of video; where to cut
    ├── captions.md                caption language, Hinglish rules, tokens/phrases formats
    ├── layouts.md                 every layout, how settings change it, fixing a shot by hand
    ├── youtube.md                 channel setup, limits, titles/hashtags, scheduling, copyright
    └── gotchas.md                 problems already solved

~/.video-clipper/                  working files (change with the VIDEO_CLIPPER_HOME env var)
├── workspace/                     the Remotion project; public/source/ holds downloaded videos
├── runs/<video-id>/               info.json, subs, words.json, transcript.txt, signals.csv, profile.md,
│                                  settings.json, shots_N.json, captions_N.*, clip_N.json
└── youtube/                       client_secret.json, token.json (your channel sign-in), api_key.txt
```

## 9. Limits and known issues

### What has been tested

| Status | What |
|---|---|
| Tested end to end | Windows 11, Python 3.14, Node.js 24, NVIDIA laptop GPU |
| Tested sources | a Hindi webcam-panel/reaction video (2×2, 3- and 5-webcam layouts, phone memes, Hinglish captions); an English gameplay breakdown (letterboxed game footage, no facecam) |
| Tested output | vertical and square; karaoke and pop captions; fire and gold colours; title top and split; progress bar; end card; .srt; two-pass loudness levelling; voice boost; censor masking and bleeps; single-clip re-render after organize; scheduling maths and schedule checks; upload dry run; section downloads; local files; cleanup |
| Tested on test footage only | speaker focus, splitting two people in one shot, keeping captions off faces, frame-accurate shot cuts |
| Not tested yet | macOS and Linux; real YouTube uploads; Whisper transcription; facecam over gameplay and two people in one camera shot on real footage; line and boxed captions; horizontal and portrait shapes; logo, background music, translated (phrases) captions |

Reports and fixes for the untested parts are very welcome.

### Known limits

- **Faces** come from OpenCV's frontal detector. Side profiles, masks, heavy shadow and tiny faces can be missed,
  and the shot then falls back to the centre or the whole picture. Claude checks the contact sheets and fixes by
  hand.
- **"Speaker" focus** (`single_focus: speaker`) follows whoever's mouth is moving, from the picture alone (no
  audio). It holds each person at least 2 s, so very quick back-and-forth stays on one face. A face turned away
  or not detected can't be picked.
- **Caption placement** (`caption_position: auto`) moves captions off faces the detector finds. Missed faces
  (see above) can still be covered; the contact sheets show it.
- **Live streams** are not clipped while live. Clip them once they've finished.
- **Fonts**: the default is Montserrat (a Google Font), which looks the same on every OS. Google Fonts need
  internet at render time; offline, captions fall back to Segoe UI Black / Arial Black / Arial.
- **Rendering time**: about 2–3 min per 40 s clip at 24 fps, a bit more at 30 fps, and roughly 2.5× that at 60 fps.
- **Best posting times** are general peaks, not your channel's analytics.

## 10. Copyright, terms and licenses

**Your responsibility.** This tool cuts, captions and uploads video. Whether you may do that with a given video is
up to you and the rights holder, not the tool.

**Clipping other people's videos.** Posting clips of someone else's video can lead to:
- Content ID claims
- copyright strikes (three in 90 days and the channel is deleted)
- demonetisation under YouTube's "reused content" rule

The safe cases:
- your own videos
- creators who allow or pay for clipping
- written permission

The skill asks about permission before uploading, keeps uploads private for review by default, and credits the
original in every description. Captions and reframing don't make a reupload safe on their own.

**Downloading.** Videos are fetched with [yt-dlp](https://github.com/yt-dlp/yt-dlp). Downloading from YouTube and
other sites may be against their terms of service. Use it for content you have the right to download (your own
uploads, Creative Commons, permission), or give the skill a local file instead.

**Remotion's license.** Clips are rendered with [Remotion](https://www.remotion.dev). Remotion is free for
individuals, for-profit companies of up to 3 people, and non-profits. Larger companies need a paid
[company license](https://www.remotion.pro/license). This skill's MIT license doesn't cover Remotion: check
which case you're in.

**This skill** is released under the [MIT License](LICENSE).
