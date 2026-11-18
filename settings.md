# Clip Settings

This file controls how the **video-clipper** skill cuts and styles clips from any long video:
gaming streams, standup sets, podcasts, interviews, vlogs, reactions, tutorials, talks, sports,
music performances, and anything else.

Change a value, save the file, and the next run uses it. Claude reads the YAML block below before it starts.

## How settings are decided

1. **What you say in chat** for that run ("single angle this time") wins.
2. **A value set in this file** comes next.
3. **`auto`**: Claude decides after studying the video. It looks at the title and description, the transcript,
   sample frames (how many people, whether there is a facecam, gameplay, slides, a stage), the audio
   (speech, laughter, music, loud spikes) and the spoken language.
   In `assisted` mode it shows a short **video profile** with every `auto` choice before rendering, so you can
   change any of them. In `autopilot` mode it writes the profile to a log and carries on.

Lines starting with `#` are notes, not settings. Allowed values are listed in each note.

```yaml
# ─────────────────────────────── AUTOMATION ─────────────────────────────────
run_mode: assisted            # assisted  = you paste a link; it stops to confirm the clip list,
                              #             and again before anything is published
                              # autopilot = you paste a link and it does the rest: finds the moments, renders,
                              #             writes title + caption + hashtags, and uploads to your channel
log_file: out/clips/runs.md   # every run's video profile, chosen clips, titles and upload links

# ─────────────────────────────── FINDING CLIPS ──────────────────────────────
moment_finder: ask            # who decides which parts of the video become clips:
                              # ask    = Claude asks you at the start of every run
                              # me     = you give the time ranges (or describe the parts); Claude only cuts,
                              #          frames and captions them
                              # claude = Claude studies the video and suggests a ranked list
                              # (autopilot can't stop to ask, so there `ask` means `claude`)
clip_count: auto              # auto (based on video length and how many strong moments it has) | 1–20
min_length_s: 20              # shortest clip, in seconds
max_length_s: 60              # longest clip, in seconds
picking: ask                  # ask  = show a ranked list and wait for your choice
                              # auto = render the top clips without asking
clip_focus: auto              # auto = whatever the video's best moments are
                              # or any of: funny | highlight | insight | story | emotional | reaction
                              #            | tutorial_step | controversial
                              # or free text: "moments about money", "every clutch play"
moment_signals: auto          # what Claude uses to find moments:
                              # auto | transcript (what is said) | audio (laughter, cheers, loud spikes)
                              # | visual (action, scene changes) | all
hook_first: true              # a clip opens on its strongest line or moment, not a slow lead-in
self_contained: true          # a clip must make sense to someone who hasn't seen the full video
avoid_explicit: false         # true = skip moments built on sexual content, slurs or graphic violence

# ─────────────────────────────── FRAME & LAYOUT ─────────────────────────────
orientation: vertical         # vertical (9:16, Reels/Shorts/TikTok) | portrait (4:5) | square (1:1)
                              # | horizontal (16:9)
resolution: 1080              # short side in pixels: 720 | 1080 | 1440
fps: source                   # source (match the original) | 30 | 60
angle_mode: auto              # auto   = split the screen only when it helps (2+ people, facecam + gameplay,
                              #          speaker + slides); one view otherwise
                              # multi  = split whenever the frame has more than one subject
                              # single = always one view
multi_layout: auto            # how a split is arranged:
                              # auto | stack (top/bottom) | grid (2x2) | main_plus_row (one big + small ones below)
max_panels: 4                 # most views on screen at once: 1–5
single_focus: auto            # in a single view, who or what to show:
                              # auto | speaker (whoever is talking) | biggest_face | content (gameplay/slides) | center
screen_content: auto          # when part of the frame is content, not a person
                              # (gameplay, slides, a screen share, a video being watched):
                              # auto | fill (the content full frame) | with_faces (content + face views)
                              # | faces_only (ignore the content)
crop_follow: auto             # auto | smooth (the crop follows a person who moves: stage, vlog walking)
                              # | fixed (the crop stays still for each shot: seated people, webcams)
zoom_on_static: true          # slow push-in on long shots where nothing moves
seam_px: 8                    # thickness of the line between split views (0 = no line)
seam_color: "#000000"
background_fill: blur         # when the source doesn't fill the frame: blur | black

# ─────────────────────────────── CAPTIONS ───────────────────────────────────
caption_language: auto        # auto     = same language as spoken; Hindi/Urdu speech in Roman letters (Hinglish)
                              # hinglish = Hindi in Roman letters, English words kept in English
                              # english  = translate to English
                              # native   = the spoken language in its own script (e.g. Devanagari)
                              # or any language name to translate into
caption_style: karaoke        # karaoke = 2–3 words, the spoken word lights up
                              # pop     = one word at a time, big, pops in
                              # line    = plain subtitle line, no highlight
                              # boxed   = words on a solid rounded box
                              # none    = no captions
                              # auto    = Claude picks to suit the video's pace
captions_when_silent: hide    # hide = no captions over moments with no speech (gameplay, music, crowd)
                              # describe = short labels like [crowd cheers] / [music]
words_per_caption: 3          # 1–5 (pop forces 1)
max_caption_chars: 16         # longer groups get split so captions never wrap onto 2 lines
caption_case: as_spoken       # as_spoken | upper | lower
caption_position: auto        # auto = clear of faces and on-screen action (on the split line for split views)
                              # top | middle | bottom
font: "Segoe UI Black"        # any installed font or Google Font name
font_size: 108                # px at 1080 wide
remove_fillers: true          # drop "umm", "uh", repeated stutters
emphasis_words: true          # key words get the accent colour even when they aren't being spoken
emoji: off                    # off | light (at most 1 per caption, only where it fits)
censor: off                   # off | mask (f**k in captions) | bleep (also beep the audio)

# ─────────────────────────────── COLOURS ────────────────────────────────────
color_scheme: fire            # fire   = white text, red active word, black outline
                              # gold   = white text, yellow active word
                              # neon   = white text, green active word with glow
                              # ice    = white text, cyan active word
                              # mono   = all white, the active word grows instead of changing colour
                              # auto   = picked to contrast with the video's own colours
                              # custom = use the colours below
custom_colors:                # only used when color_scheme: custom
  text: "#FFFFFF"
  active: "#FF2D2D"
  outline: "#000000"
  glow: true
  title_bg: "#FFFFFF"
  title_text: "#111111"

# ─────────────────────────────── TITLE & BRANDING ───────────────────────────
title: on                     # on | off   (a short title card naming the clip)
title_language: auto          # auto (same as captions) | english | any language
title_position: top           # top | split (on the line between split views) | bottom
title_duration: full          # full = whole clip | intro = first 3 seconds only
watermark: off                # off | path to a PNG logo, e.g. assets/logo.png
watermark_position: top_right # top_left | top_right | bottom_left | bottom_right
progress_bar: off             # on = thin bar along the bottom showing time left
end_card: off                 # off | text shown for the last 1.5 s, e.g. "Full video on my channel"

# ─────────────────────────────── AUDIO ──────────────────────────────────────
normalize_loudness: true      # level every clip to the same loudness (-14 LUFS, what Reels/Shorts expect)
voice_boost: auto             # auto | on | off   (lift speech over game sound, music or crowd noise)
fade_ms: 250                  # fade in/out at the clip edges, 0 = hard cut
background_music: off         # off | path to an audio file (sits under the original audio)
music_volume: 0.08            # 0–1, only used when background_music is set

# ─────────────────────────────── SOURCE & TRANSCRIPT ────────────────────────
download_quality: 1080        # 720 | 1080 | best
download_mode: auto           # auto | sections (only the clip parts, fast) | full (whole video)
transcript_source: auto       # auto    = the platform's captions, local Whisper when there are none
                              # whisper = always transcribe locally (more accurate, slower)
whisper_model: large-v3       # small | medium | large-v3 (bigger = more accurate, slower)
spoken_language: auto         # auto | a language code (hi, en, es, ...)

# ─────────────────────────────── OUTPUT ─────────────────────────────────────
keep_source: false            # false = delete the downloaded long video once the clips are made and checked
                              #         (it's the biggest file; transcripts and clip data are kept)
                              # true  = keep it (handy if you'll cut more clips from the same video soon)
output_folder: out/clips
file_name: "{n}_{slug}"       # {n} rank, {slug} title in short form, {video_id}, {date}
export_srt: false             # also save a .srt caption file next to each clip
export_thumbnail: true        # save a cover image (best frame + title) per clip
quality: high                 # draft (fast, small) | high | max (largest files)

# ─────────────────────────────── TITLE, CAPTION & HASHTAGS ──────────────────
# Written per clip from what is said and shown in it, plus what is currently trending for that topic.
# Saved to posts.md next to the clips, and used for the upload.
post_platforms: [youtube, instagram]  # which platforms to write post text for: youtube | instagram | tiktok
metadata_language: auto       # auto (same as the clip's captions) | english | any language
trend_research: on            # on  = before writing, look up what's trending on YouTube for the clip's topic
                              #       and region (popular videos, their titles and tags, rising search terms)
                              # off = write from the clip alone
trend_region: auto            # auto (from the video's language/audience) | IN | US | GB | any country code
title_style: auto             # auto | hook (curiosity) | punchline | question | quote (best line from the clip)
                              # | descriptive (plain, searchable)
title_max_chars: 70           # Shorts titles get cut off on phones past ~40–70 characters
emoji_in_title: light         # off | light (at most 1)
description_style: auto       # auto | short (1–2 lines + hashtags) | full (hook, context, credit, hashtags)
hashtags: 4                   # how many hashtags: 0–8. YouTube shows the first 3 above the title;
                              # piling on dozens gets them ignored, so a few relevant ones work best
always_hashtags: []           # hashtags added to every clip, e.g. ["#Shorts", "#MyChannelName"]
tags: auto                    # auto (searchable keywords from the clip + trends) | off
credit_source: true           # add "Clip from: <original video title + link>" to the description
honest_titles: true           # titles and thumbnails only promise what the clip actually shows
                              # (misleading metadata breaks YouTube policy and hurts reach)

# ─────────────────────────────── PUBLISHING ─────────────────────────────────
upload_to: none               # none | youtube   (more platforms can be added later)
youtube_channel: default      # default (the account you sign in with once) | a channel name if you manage several
privacy: private              # private | unlisted | public | scheduled
schedule: off                 # off | "18:00 daily" | "every 4h from 10:00" | best_times
                              # best_times = spread uploads over the times your channel's viewers are most active
max_uploads_per_day: 3        # spreads a batch over several days instead of posting everything at once
review_before_publish: true   # true  = upload as private first and tell you; it goes public/scheduled
                              #         only after you say so
                              # false = publish or schedule straight away (what autopilot uses)
playlist: none                # none | a playlist name to add every clip to (created if missing)
category: auto                # auto | Comedy | Gaming | Entertainment | Education | People & Blogs | ...
made_for_kids: false          # YouTube requires this answer on every upload
notify_subscribers: true
altered_content: false        # true if a clip uses realistic AI-generated or altered people/scenes
rights_check: ask             # ask  = for each new link, confirm once that you may post clips of it
                              #        (the creator allows clipping, runs a clip program, or gave permission)
                              # skip = you've cleared it already; nothing is asked
```

## What `auto` usually resolves to

These are starting points, not rules. Claude goes by what it actually sees and hears in the video,
and a video that mixes types (a gaming stream with a podcast segment) gets different choices per clip.

| What the video looks like | Layout | Finding moments | Captions |
|---|---|---|---|
| One person talking to camera (vlog, explainer, monologue) | single, `crop_follow: smooth` if they move | transcript | karaoke |
| Two or more people in one shot (studio podcast, interview, panel) | split by face when several react; the speaker alone otherwise | transcript + laughter | karaoke |
| Webcam grid (online call, remote panel, reaction stream) | split by webcam tile; the shared clip full frame | transcript + laughter | karaoke |
| Gameplay with a facecam | gameplay on top, facecam below | audio spikes + visual action + transcript | pop, hidden over silent play |
| Gameplay without a facecam | gameplay cropped to the action | visual action + audio | pop or none |
| Stage (standup, talk, performance) | single, `crop_follow: smooth` | transcript + laughter/applause | karaoke |
| Screen recording or slides (tutorial, lecture) | slides on top, presenter below if there is one | transcript (one step or idea per clip) | line |
| Sports or action footage | single on the action | visual action + crowd noise | none or describe |
| Music performance | single, follow the performer | audio (chorus, drops, solos) | none (no lyrics) |

## Presets

Copy one of these over the matching lines above for a quick change of look.

| Preset | What changes |
|---|---|
| **Bold karaoke** | `caption_style: karaoke`, `color_scheme: fire`, `title_position: split` |
| **Clean subtitles** | `caption_style: line`, `color_scheme: mono`, `angle_mode: single`, `zoom_on_static: false` |
| **Hype** | `caption_style: pop`, `caption_case: upper`, `color_scheme: gold`, `emoji: light`, `progress_bar: on` |
| **Landscape** | `orientation: horizontal`, `angle_mode: single`, `caption_position: bottom`, `title: off` |
| **Family-safe** | `avoid_explicit: true`, `censor: bleep` |
| **Autopilot to YouTube** | `run_mode: autopilot`, `picking: auto`, `upload_to: youtube`, `privacy: scheduled`, `schedule: best_times`, `review_before_publish: false` |

## Saying it in chat instead

You don't need to edit this file for a one-off change. Things like these work as overrides:

- "find 5 clutch moments from this stream, 15–30 seconds, gameplay on top and my cam below"
- "cut my standup set into clips that each end on a punchline, English captions in yellow"
- "3 clips from this lecture, square, plain subtitles, no title"
- "make it single angle and all caps this time"
- "clip this link and post the best 3 on my channel, one a day at 7 pm"
- "just write titles and hashtags for the clips in out/clips, don't upload"
