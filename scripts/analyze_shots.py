"""Work out, shot by shot, what is on screen in a time range and how to lay it out in the output frame.

Usage:
  python analyze_shots.py <video> <start_sec> <end_sec> <out.json> --settings run/settings.json [--offset 0]
  (start/end are times in the ORIGINAL video; --offset is where this file starts, for section downloads)

What it recognises per shot:
  tiles        webcams separated by dark divider lines (video calls, remote panels, reaction streams)
  meme         a tall phone video with only thumbnail webcams around it
  content_face a small static face in a corner over other content (facecam over gameplay / slides)
  people       two or more people in one camera shot
  single       one person (the crop can follow them as they move)
  content      no faces (gameplay, slides, scenery)

Each shot becomes panels: {"box": output rect, "src": source rect, "mode": cover|contain, "track": [[sec, x, y]...]}.
Edit the JSON by hand if a shot needs a different framing; build_clip.py reads it as-is.
"""
import argparse
import math

import cv2
import numpy as np

from common import load_json, output_size, save_json, utf8

utf8()
ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("start", type=float)
ap.add_argument("end", type=float)
ap.add_argument("out")
ap.add_argument("--settings")
ap.add_argument("--offset", type=float, default=0.0)
A = ap.parse_args()
S = load_json(A.settings, {}) if A.settings else {}


def opt(key, default):
    v = S.get(key, default)
    return default if v in (None, "") else v


OUT_W, OUT_H = output_size(S)
PORTRAIT = OUT_H >= OUT_W
ANGLE = opt("angle_mode", "auto")
ARRANGE = opt("multi_layout", "auto")
MAX_PANELS = max(1, int(opt("max_panels", 4)))
FOCUS = opt("single_focus", "auto")
SCREEN = opt("screen_content", "auto")
FOLLOW = opt("crop_follow", "auto")

cap = cv2.VideoCapture(A.video)
FPS = cap.get(cv2.CAP_PROP_FPS) or 30
W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
SC = 2 if W >= 1280 else 1  # analyse at half resolution for speed
w2, h2 = W // SC, H // SC
cap.set(cv2.CAP_PROP_POS_MSEC, (A.start - A.offset) * 1000)
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
if cascade.empty():
    raise SystemExit("OpenCV has no Haar face detector (OpenCV 5 removed it). pip install 'opencv-python-headless<5'")

DARK, FULL = 50, 0.92  # dividers are black; meme backgrounds are dark grey (~45)


def runs(mask, min_len):
    out, start = [], None
    for i, v in enumerate(np.append(mask, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_len:
                out.append((start, i))
            start = None
    return out


FLAT = 6  # real dividers / backgrounds are one flat colour; dark game or film scenery has texture and noise


def tiles_of(gray):
    d = gray < DARK
    col_div = (d.mean(axis=0) > FULL) & (gray.std(axis=0) < FLAT)
    tiles = []
    for x0, x1 in runs(~col_div, w2 * 0.08):
        sub = gray[:, x0:x1]
        row_div = ((sub < DARK).mean(axis=1) > FULL) & (sub.std(axis=1) < FLAT)
        for y0, y1 in runs(~row_div, h2 * 0.08):
            tiles.append((x0 * SC, y0 * SC, x1 * SC, y1 * SC))
    return tiles or [(0, 0, W, H)]


def tile_kind(tiles):
    if len(tiles) >= 2:
        for t in tiles:
            w, h = t[2] - t[0], t[3] - t[1]
            if w / h < 0.75 and h > H * 0.8 and all(o[3] - o[1] < H * 0.3 for o in tiles if o is not t):
                return "meme"
        return "tiles"
    return "open"  # one picture filling the frame (maybe letterboxed): decided by faces later


def signature(tiles):
    return tuple(round(v / 40) for t in tiles for v in t)


# ---------------------------------------------------------------- pass 1: read frames
tiles_per, diffs, grays = [], [], {}
prev = None
nframes = int((A.end - A.start) * FPS)
for i in range(nframes):
    ok, f = cap.read()
    if not ok:
        break
    g = cv2.cvtColor(cv2.resize(f, (w2, h2)), cv2.COLOR_BGR2GRAY)
    tiles_per.append(tiles_of(g))
    small = cv2.resize(f, (96, 54)).astype(np.float32)
    diffs.append(0.0 if prev is None else float(np.abs(small - prev).mean()))
    prev = small
    if i % 3 == 0:
        grays[i] = g
nframes = len(tiles_per)

# ---------------------------------------------------------------- pass 2: shots
cuts = [0]
for i in range(1, nframes):
    if signature(tiles_per[i]) != signature(tiles_per[i - 1]) or diffs[i] > 38:
        cuts.append(i)
cuts.append(nframes)
shots, carry = [], None
for a, b in zip(cuts, cuts[1:]):
    if b - a < 6:  # transition frames: fold into the previous shot (or the next one, at the very start)
        if shots:
            shots[-1][1] = b
        else:
            carry = a if carry is None else carry
        continue
    shots.append([carry if carry is not None else a, b])
    carry = None
if not shots:
    shots = [[0, nframes]]


def faces_in(g, region, min_frac=0.06):
    x0, y0, x1, y1 = (v // SC for v in region)
    sub = g[y0:y1, x0:x1]
    if sub.size == 0:
        return []
    m = max(12, int(min(sub.shape) * min_frac))
    found = cascade.detectMultiScale(sub, 1.1, 6, minSize=(m, m))
    return [((x0 + fx + fw / 2) * SC, (y0 + fy + fh / 2) * SC, fw * SC) for fx, fy, fw, fh in found]


def clusters_in(region, idx):
    """Group face detections across frames into people: [{cx, cy, size, seen, pts: [(frame, cx, cy)]}]."""
    cl = []
    for i in idx:
        for cx, cy, s in faces_in(grays[i], region):
            best = None
            for c in cl:
                if abs(cx - c["cx"]) < max(c["size"] * 1.5, W * 0.08) and abs(cy - c["cy"]) < c["size"] * 2:
                    best = c
                    break
            if best is None:
                best = {"cx": cx, "cy": cy, "size": s, "seen": 0, "pts": []}
                cl.append(best)
            n = best["seen"]
            best["cx"] = (best["cx"] * n + cx) / (n + 1)
            best["cy"] = (best["cy"] * n + cy) / (n + 1)
            best["size"] = (best["size"] * n + s) / (n + 1)
            best["seen"] = n + 1
            best["pts"].append((i, cx, cy))
    need = max(2, int(len(idx) * 0.25))
    cl = sorted([c for c in cl if c["seen"] >= need], key=lambda c: -c["size"])
    # faces much smaller than the main one are posters, photos or a TV in the background, not another person
    return [c for c in cl if c["size"] >= cl[0]["size"] * 0.55] if cl else []


def content_box(tile, idx):
    """Trim letterbox / pillarbox bars inside a tile."""
    x0, y0, x1, y1 = tile
    g = grays[idx[len(idx) // 2]][y0 // SC:y1 // SC, x0 // SC:x1 // SC] >= 28
    rows = np.where(g.mean(axis=1) > 0.05)[0]
    cols = np.where(g.mean(axis=0) > 0.05)[0]
    if not len(rows) or not len(cols):
        return list(tile)
    return [x0 + int(cols[0]) * SC, y0 + int(rows[0]) * SC, x0 + (int(cols[-1]) + 1) * SC, y0 + (int(rows[-1]) + 1) * SC]


# ---------------------------------------------------------------- framing helpers
def fit_rect(region, focus, aspect, face_y=0.42, height=None):
    """A rect of the given aspect inside region, centred on focus (face at face_y of the height)."""
    x0, y0, x1, y1 = region
    rw, rh = x1 - x0, y1 - y0
    h = min(height or rh, rh)
    w = h * aspect
    if w > rw:
        w, h = rw, rw / aspect
    x = min(max(focus[0] - w / 2, x0), x1 - w)
    y = min(max(focus[1] - h * face_y, y0), y1 - h)
    return [round(x), round(y), round(w), round(h)]


def content_panel(region, aspect):
    """Cover-crop if that keeps most of the picture, otherwise show it whole over a blurred copy."""
    x0, y0, x1, y1 = region
    rw, rh = x1 - x0, y1 - y0
    keep = min(1.0, (rh * aspect) / rw) if rw / rh > aspect else min(1.0, (rw / aspect) / rh)
    if keep < 0.6:
        return {"src": [x0, y0, rw, rh], "mode": "contain"}
    return {"src": fit_rect(region, ((x0 + x1) / 2, (y0 + y1) / 2), aspect, 0.5), "mode": "cover"}


def face_panel(region, person, aspect, tight):
    size = person["size"]
    rh = region[3] - region[1]
    height = None
    if tight:  # several people share one shot: head-and-shoulders crop per person
        height = max(size * 3.2, rh * 0.35)
    elif size < rh * 0.12:  # far away (stage, wide shot): zoom in a little
        height = max(size * 6, rh * 0.75)
    return {"src": fit_rect(region, (person["cx"], person["cy"]), aspect, 0.42, height), "mode": "cover",
            "_person": person, "_region": region, "_height": height}


def boxes(k, kind):
    """Output rects for k panels."""
    Wo, Ho = OUT_W, OUT_H
    if k <= 1:
        return [[0, 0, Wo, Ho]]
    arr = ARRANGE
    if kind == "content_face" and k == 2:
        if PORTRAIT:
            hc = round(Ho * 0.58)
            return [[0, 0, Wo, hc], [0, hc, Wo, Ho - hc]]
        wc = round(Wo * 0.62)
        return [[0, 0, wc, Ho], [wc, 0, Wo - wc, Ho]]
    if arr == "auto":
        arr = {2: "stack", 3: "main_plus_row", 4: "grid"}.get(k, "main_plus_row")
        if kind == "tiles_main":  # one webcam clearly bigger than the rest: keep it big
            arr = "main_plus_row"
    if arr == "stack":
        if PORTRAIT:
            hs = [round(Ho * i / k) for i in range(k + 1)]
            return [[0, hs[i], Wo, hs[i + 1] - hs[i]] for i in range(k)]
        ws = [round(Wo * i / k) for i in range(k + 1)]
        return [[ws[i], 0, ws[i + 1] - ws[i], Ho] for i in range(k)]
    if arr == "grid":
        rows = math.ceil(k / 2)
        out = []
        for i in range(k):
            r, c = divmod(i, 2)
            last_single = (k % 2 == 1 and i == k - 1)
            y, h = round(Ho * r / rows), round(Ho / rows)
            out.append([0, y, Wo, h] if last_single else [round(Wo * c / 2), y, round(Wo / 2), h])
        return out
    # main_plus_row: first panel takes half, the rest share the other half
    rest = k - 1
    if PORTRAIT:
        out = [[0, 0, Wo, Ho // 2]]
        y, h = Ho // 2, Ho - Ho // 2
        if rest <= 3:
            ws = [round(Wo * i / rest) for i in range(rest + 1)]
            out += [[ws[i], y, ws[i + 1] - ws[i], h] for i in range(rest)]
        else:
            out += [[(i % 2) * Wo // 2, y + (i // 2) * h // 2, Wo // 2, h // 2] for i in range(4)]
        return out
    out = [[0, 0, Wo // 2, Ho]]
    x, w = Wo // 2, Wo - Wo // 2
    if rest <= 3:
        hs = [round(Ho * i / rest) for i in range(rest + 1)]
        out += [[x, hs[i], w, hs[i + 1] - hs[i]] for i in range(rest)]
    else:
        out += [[x + (i % 2) * w // 2, (i // 2) * Ho // 2, w // 2, Ho // 2] for i in range(4)]
    return out


def tracked(panel, box, seg_start_frame, idx):
    """Let the crop follow a moving person: keyframes [[sec, x, y], ...] relative to the shot start."""
    person = panel.pop("_person", None)
    region = panel.pop("_region", None)
    height = panel.pop("_height", None)
    if person is None or FOLLOW == "fixed" or len(person["pts"]) < 4:
        return panel
    xs = np.array([p[1] for p in person["pts"]])
    lo, hi = np.percentile(xs, [10, 90])  # ignore the odd misdetection
    if FOLLOW == "auto" and hi - lo < W * 0.06:
        return panel
    fr = np.array([p[0] for p in person["pts"]], dtype=float)
    ys = np.array([p[2] for p in person["pts"]])
    k = min(9, len(xs))
    kern = np.ones(k) / k
    xs_s = np.convolve(np.pad(xs, (k // 2, k - 1 - k // 2), mode="edge"), kern, mode="valid")
    ys_s = np.convolve(np.pad(ys, (k // 2, k - 1 - k // 2), mode="edge"), kern, mode="valid")
    aspect = box[2] / box[3]
    keys, last = [], None
    for f, x, y in zip(fr, xs_s, ys_s):
        if last is not None and f - last < FPS * 0.5:
            continue
        r = fit_rect(region, (x, y), aspect, 0.42, height)
        keys.append([round((f - seg_start_frame) / FPS, 3), r[0], r[1]])
        last = f
    if len(keys) >= 2:
        panel["track"] = keys
        panel["src"][0], panel["src"][1] = keys[0][1], keys[0][2]
    return panel


# ---------------------------------------------------------------- pass 3: decide each shot
segments = []
for a, b in shots:
    idx = [i for i in range(a, b) if i in grays] or [max(i for i in grays if i <= a)]
    sigs = [signature(tiles_per[i]) for i in range(a, b)]
    common_sig = max(set(sigs), key=sigs.count)
    tiles = tiles_per[a + sigs.index(common_sig)]
    tk = tile_kind(tiles)
    items = []  # (kind, panel-maker(aspect, tight) )
    kind = tk

    if tk in ("tiles", "meme"):
        meme = None
        if tk == "meme":
            meme = next(t for t in tiles if (t[2] - t[0]) / (t[3] - t[1]) < 0.75 and t[3] - t[1] > H * 0.8)
        cams = [t for t in tiles if t is not meme]
        cams.sort(key=lambda t: -(t[2] - t[0]) * (t[3] - t[1]))
        cam_people = []
        for t in cams:
            cl = clusters_in(t, idx)
            person = cl[0] if cl else {"cx": (t[0] + t[2]) / 2, "cy": t[1] + (t[3] - t[1]) * 0.42,
                                       "size": (t[2] - t[0]) * 0.2, "pts": []}
            cam_people.append((t, person))
        show_content = meme is not None and SCREEN in ("auto", "fill", "with_faces")
        if meme is not None and SCREEN == "faces_only":
            show_content = False
        if ANGLE == "single" and FOCUS == "content" and meme is None:
            # "show the whole picture": all tiles together, as one image
            items = [("content", (min(t[0] for t in tiles), min(t[1] for t in tiles),
                                  max(t[2] for t in tiles), max(t[3] for t in tiles)))]
            kind = "content"
        elif ANGLE == "single" or (meme is not None and SCREEN in ("auto", "fill")):
            if show_content or (ANGLE == "single" and FOCUS == "content" and meme is not None):
                items = [("content", meme)]
                kind = "meme"
            else:
                items = [("cam", cam_people[0])]
                kind = "single"
        else:
            if show_content:
                items.append(("content", meme))
            # reading order (top-left first) keeps people where viewers expect them
            ordered = sorted(cam_people[: MAX_PANELS - len(items)], key=lambda tp: (round(tp[0][1] / H * 4), tp[0][0]))
            dominant = False
            if len(ordered) >= 3 and not show_content:
                biggest = max(ordered, key=lambda tp: (tp[0][2] - tp[0][0]) * (tp[0][3] - tp[0][1]))
                area = lambda tp: (tp[0][2] - tp[0][0]) * (tp[0][3] - tp[0][1])
                if area(biggest) > 1.5 * min(area(tp) for tp in ordered):  # one big webcam + small ones
                    ordered.remove(biggest)
                    ordered.insert(0, biggest)
                    dominant = True
            items += [("cam", tp) for tp in ordered]
            kind = "meme+faces" if show_content else (
                ("tiles_main" if dominant else "tiles") if len(items) > 1 else "single")
    else:
        region = content_box(tiles[0], idx)
        cw, ch = region[2] - region[0], region[3] - region[1]
        people = clusters_in(region, idx)
        facecam = None
        if people:
            p = people[0]
            rel_x, rel_y = (p["cx"] - region[0]) / cw, (p["cy"] - region[1]) / ch
            xs = [q[1] for q in p["pts"]]
            static = (max(xs) - min(xs)) < cw * 0.03 if xs else True
            if p["size"] < cw * 0.11 and static and (rel_x < 0.3 or rel_x > 0.7) and (rel_y < 0.4 or rel_y > 0.6):
                facecam = p
        if facecam is not None:
            kind = "content_face"
            if ANGLE == "single":
                items = [("content", region)] if FOCUS in ("content", "auto") else [("person", (region, facecam))]
            elif SCREEN == "faces_only":
                items = [("person", (region, facecam))]
            elif SCREEN == "fill":
                items = [("content", region)]
            else:
                items = [("content", region), ("facecam", (region, facecam))]
        elif not people:
            kind = "content"
            items = [("content", region)]
        elif len(people) == 1 or ANGLE == "single":
            kind = "single"
            target = people[0]
            if FOCUS == "center":
                target = {"cx": region[0] + cw / 2, "cy": region[1] + ch * 0.42, "size": people[0]["size"], "pts": []}
            if FOCUS == "content":
                items = [("content", region)]
            else:
                items = [("person", (region, target))]
        else:
            group = people[:MAX_PANELS]
            span = max(p["cx"] + p["size"] for p in group) - min(p["cx"] - p["size"] for p in group)
            one_crop_w = ch * (OUT_W / OUT_H)
            if span < one_crop_w * 0.9:  # everyone fits in one frame anyway
                kind = "single"
                cx = sum(p["cx"] for p in group) / len(group)
                cy = sum(p["cy"] for p in group) / len(group)
                items = [("person", (region, {"cx": cx, "cy": cy, "size": max(p["size"] for p in group), "pts": []}))]
            else:
                kind = "people"
                group.sort(key=lambda p: p["cx"])
                items = [("tight", (region, p)) for p in group]

    items = items[:MAX_PANELS]
    rects = boxes(len(items), kind)
    panels = []
    for (what, payload), box in zip(items, rects):
        aspect = box[2] / box[3]
        if what == "content":
            region = payload if not isinstance(payload, tuple) else payload
            p = content_panel(region, aspect)
        elif what == "cam":
            tile, person = payload
            p = {"src": fit_rect(content_box(tile, idx), (person["cx"], person["cy"]), aspect), "mode": "cover"}
        elif what == "facecam":
            region, person = payload
            p = {"src": fit_rect(region, (person["cx"], person["cy"]), aspect, 0.45, person["size"] * 3.0),
                 "mode": "cover"}
        elif what == "tight":
            region, person = payload
            p = face_panel(region, person, aspect, tight=True)
        else:  # person
            region, person = payload
            p = face_panel(region, person, aspect, tight=False)
        p = tracked(p, box, a, idx)
        for k in ("_person", "_region", "_height"):
            p.pop(k, None)
        p["box"] = box
        panels.append(p)
    segments.append({"start": round(A.start + a / FPS, 3), "end": round(A.start + b / FPS, 3),
                     "layout": kind, "panels": panels})

# merge neighbours that ended up identical (false cuts)
merged = []
for s in segments:
    if merged and merged[-1]["layout"] == s["layout"] and len(merged[-1]["panels"]) == len(s["panels"]) and all(
        "track" not in p and "track" not in q and p.get("mode") == q.get("mode")
        and max(abs(p["src"][k] - q["src"][k]) for k in range(4)) < 40
        for p, q in zip(merged[-1]["panels"], s["panels"])
    ):
        merged[-1]["end"] = s["end"]
        continue
    merged.append(s)

save_json(A.out, {"source": {"path": A.video, "w": W, "h": H, "fps": FPS}, "out": {"w": OUT_W, "h": OUT_H},
                  "start": A.start, "end": A.end, "offset": A.offset, "segments": merged})
for s in merged:
    desc = " ".join(f"{p['mode'][:3]}{'~' if 'track' in p else ''}{p['src']}" for p in s["panels"])
    print(f"{s['start']:9.2f}-{s['end']:9.2f}  {s['layout']:12s} {desc}")
