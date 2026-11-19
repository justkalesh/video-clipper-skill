# Layouts

`analyze_shots.py` splits a clip's range into shots (camera cuts / layout changes), recognises what each shot
shows, and writes panels: where each piece goes in the output (`box`) and which part of the source fills it
(`src`). Everything below can be overridden by editing the JSON.

## What it recognises

| Layout | How it's detected | Default framing (vertical) |
|---|---|---|
| `tiles` | dark divider lines split the frame into webcams (video calls, remote panels, reaction streams) | 2 → top/bottom; 3 → biggest on top + 2 below; 4 → 2×2; 5 → biggest on top + 4 small |
| `meme` / `meme+faces` | a tall portrait tile (phone video) with only thumbnail-size webcams around it | the portrait video full screen (`screen_content: with_faces` adds webcams) |
| `content_face` | a small, still face near a corner over other content (facecam over gameplay/slides) | content top 58%, face bottom 42% |
| `people` | 2+ people in one camera shot, too far apart for one crop | one head-and-shoulders crop per person, left to right |
| `single` | one person (or several close together) | one tall crop centred on the face; follows them if they move |
| `content` | no faces (gameplay, slides, scenery, B-roll) | centre crop, or the whole picture over a blurred copy if a crop would lose too much |

Horizontal output (16:9) uses side-by-side columns instead of top/bottom rows.

## How settings change it

- `angle_mode: single` → always one panel. `single_focus` picks it: `auto`/`biggest_face` = the biggest face,
  `speaker` = whoever is talking (mouth-area change minus eye-area change, so head movement doesn't count),
  `content` = the screen/meme, `center` = frame centre. With `speaker`, a shot with several people becomes one
  segment per speaker turn: activity is scored per half second, smoothed over 1.5 s, and the view only switches
  when someone else is clearly more active and the current person has had at least 2 s.
- Every shot also lists `faces` (output pixels, placed where a moving crop actually is). build_clip.py uses them
  to keep `caption_position: auto` captions off faces; delete a wrong entry if a false detection pushes captions
  somewhere odd.
- `multi_layout` forces `stack` / `grid` / `main_plus_row` instead of the default per count.
- `max_panels` caps the number of panels (the biggest webcams/faces are kept).
- `screen_content`: `fill` = only the content; `with_faces` = content + faces; `faces_only` = drop the content.
- `crop_follow`: `smooth` = always follow, `fixed` = never, `auto` = follow when a face moves more than ~6% of
  the frame width within a shot.
- `background_fill` (blur/black) is what shows around content that's shown whole (`mode: contain`).

## Reading the printed summary

```
 1102.02-  1111.56  single       co[655, 108, 486, 864]
 1119.52-  1122.85  tiles        co[272, 8, 298, 529] co[1327, 8, 298, 529] ...
 1500.10-  1508.30  single       co~[612, 0, 608, 1080]       <- ~ : the crop moves (tracking)
 1600.00-  1620.00  content      con[0, 0, 1920, 1080]        <- con: shown whole over a blurred copy
```

## Fixing a shot by hand

Each segment in the JSON looks like:
```json
{"start": 1119.52, "end": 1122.85, "layout": "tiles",
 "panels": [{"box": [0, 0, 1080, 960], "src": [272, 8, 949, 844], "mode": "cover"}, ...]}
```
- `box`: x, y, width, height in the output frame. `src`: x, y, width, height in the source video.
- The `src` aspect ratio should match the `box` aspect ratio for `cover` (otherwise the picture is cropped further).
- `mode: contain` shows the whole `src` inside the box over a blurred copy.
- `track`: `[[seconds_from_shot_start, src_x, src_y], ...]` moves the crop over time. Delete it to freeze.
- To merge two shots, delete one and stretch the other's `end`.
- To force one view for a shot, keep one panel and set its box to the whole frame.
- `faces`: `[[x, y, size], ...]` in output pixels; keep it in step with the panels you set (captions avoid them).

**A video whose layout never changes** (a facecam always in the same box over gameplay, a fixed two-camera
setup): measure the boxes once from a full-size frame, then give each clip one segment from its start to its end
with those panels. Dark cutscenes and camera cuts can make the analyzer flip layouts every second or two; a fixed
layout is steadier and still right. For facecam-over-gameplay in vertical shorts:
- the gameplay as a centre crop (`cover`), trimmed to leave out the game's own subtitles and minimap (the
  captions carry the speech)
- the facecam cropped inside its box only, above any name banner
- wide menus or maps as `contain` instead, so nothing important is cut off

## Known limits

- Faces come from OpenCV's frontal detector: profiles, heavy shadows, masks and very small faces may be
  missed. A missed face falls back to the tile centre. Check the sheets and fix by hand.
- The divider detection expects dark lines or backgrounds between webcams. Layouts with bright or patterned
  dividers look like one picture: faces then drive the framing instead.
- Tracking is smoothed over ~2 s, so very fast movement lags slightly behind.
