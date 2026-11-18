"""Connect a YouTube channel and upload clips to it.

One-time setup (the channel owner does this; see references/youtube.md):
  python youtube_upload.py auth --client-secret path/to/client_secret.json   # opens a Google sign-in page
  python youtube_upload.py whoami                                            # shows the connected channel

Uploading:
  python youtube_upload.py upload out/clips/x/1_title.mp4 --meta out/clips/x/1_title.meta.json [--dry-run]
  python youtube_upload.py publish <video_id> --privacy public               # after the owner approves a private upload
  python youtube_upload.py publish <video_id> --at 2026-11-20T18:00:00+00:00 # schedule it instead
  python youtube_upload.py schedule --count 5 --settings run_settings.json   # print publish times for N clips

The .meta.json file (written by Claude per clip):
  {"title", "description", "hashtags": [...], "tags": [...], "category": "Comedy",
   "privacy": "private|unlisted|public", "publish_at": "ISO time or null", "playlist": "name or null",
   "made_for_kids": false, "notify_subscribers": true, "altered_content": false, "language": "hi",
   "pinned_comment": "a comment to pin under the video", "best_time": "e.g. today 18:00-21:00 local",
   "platforms": {"instagram": {"caption": "...", "hashtags": [...]}, "tiktok": {"caption": "...", "hashtags": [...]}}}
After an upload, a "youtube" block with the video id and link is written back into it.
"""
import argparse
import datetime as dt
import json
import random
import re
import shutil
import sys
import time
from pathlib import Path

from common import HOME, load_json, probe, save_json, utf8

YT_DIR = HOME / "youtube"
SECRET = YT_DIR / "client_secret.json"
TOKEN = YT_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
CATEGORIES = {
    "film & animation": 1, "autos & vehicles": 2, "music": 10, "pets & animals": 15, "sports": 17,
    "travel & events": 19, "gaming": 20, "people & blogs": 22, "comedy": 23, "entertainment": 24,
    "news & politics": 25, "howto & style": 26, "education": 27, "science & technology": 28,
    "nonprofits & activism": 29,
}


def libs():
    try:
        from google.auth.transport.requests import Request  # noqa: F401
        from google.oauth2.credentials import Credentials  # noqa: F401
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
    except ImportError:
        sys.exit("YouTube libraries missing. Run: python setup.py --install --with-youtube")


def service():
    libs()
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    if not TOKEN.exists():
        sys.exit("No YouTube channel connected yet. Run: python youtube_upload.py auth --client-secret <file>")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json(), encoding="utf-8")
        else:
            sys.exit("The YouTube sign-in has expired. Run auth again.")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def cmd_auth(secret):
    libs()
    from google_auth_oauthlib.flow import InstalledAppFlow
    YT_DIR.mkdir(parents=True, exist_ok=True)
    if secret:
        shutil.copy2(secret, SECRET)
    if not SECRET.exists():
        sys.exit("Pass --client-secret with the OAuth client file downloaded from Google Cloud (see references/youtube.md)")
    flow = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    cmd_whoami()


def cmd_whoami():
    yt = service()
    r = yt.channels().list(part="snippet,statistics", mine=True).execute()
    for c in r.get("items", []):
        print(json.dumps({"channel": c["snippet"]["title"], "id": c["id"],
                          "subscribers": c["statistics"].get("subscriberCount")}, ensure_ascii=False))


def description_of(meta):
    desc = (meta.get("description") or "").strip()
    tags = [h if h.startswith("#") else "#" + h for h in meta.get("hashtags") or []]
    missing = [h for h in tags if h.lower() not in desc.lower()]
    if missing:
        desc = (desc + "\n\n" + " ".join(missing)).strip()
    return desc[:4900]


def playlist_id(yt, name):
    page = None
    while True:
        r = yt.playlists().list(part="snippet", mine=True, maxResults=50, pageToken=page).execute()
        for p in r.get("items", []):
            if p["snippet"]["title"].strip().lower() == name.strip().lower():
                return p["id"]
        page = r.get("nextPageToken")
        if not page:
            break
    r = yt.playlists().insert(part="snippet,status", body={"snippet": {"title": name},
                                                            "status": {"privacyStatus": "public"}}).execute()
    return r["id"]


def cmd_upload(path, meta_path, dry):
    meta = load_json(meta_path)
    if not meta:
        sys.exit(f"{meta_path} not found")
    cat = meta.get("category", 24)
    cat_id = cat if isinstance(cat, int) else CATEGORIES.get(str(cat).strip().lower(), 24)
    tags, total = [], 0
    for t in meta.get("tags") or []:
        t = t.lstrip("#").strip()
        if t and total + len(t) + 3 <= 480:  # YouTube's tag limit is 500 characters in total
            tags.append(t)
            total += len(t) + 3
    publish_at = meta.get("publish_at")
    status = {
        "privacyStatus": "private" if publish_at else meta.get("privacy", "private"),
        "selfDeclaredMadeForKids": bool(meta.get("made_for_kids", False)),
        "containsSyntheticMedia": bool(meta.get("altered_content", False)),
    }
    if publish_at:
        status["publishAt"] = publish_at
    snippet = {"title": meta["title"][:100], "description": description_of(meta), "tags": tags,
               "categoryId": str(cat_id)}
    if meta.get("language"):
        snippet["defaultLanguage"] = meta["language"]
        snippet["defaultAudioLanguage"] = meta["language"]
    body = {"snippet": snippet, "status": status}
    if dry:
        print(json.dumps({"dry_run": True, "file": str(path), "body": body,
                          "notify_subscribers": bool(meta.get("notify_subscribers", True)),
                          "playlist": meta.get("playlist")}, ensure_ascii=False, indent=1))
        return
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    yt = service()
    req = yt.videos().insert(part="snippet,status", body=body,
                             notifySubscribers=bool(meta.get("notify_subscribers", True)),
                             media_body=MediaFileUpload(str(path), mimetype="video/mp4",
                                                        chunksize=8 * 1024 * 1024, resumable=True))
    resp, tries = None, 0
    while resp is None:
        try:
            st, resp = req.next_chunk()
            if st:
                print(f"\r  uploading {int(st.progress() * 100)}%", end="", flush=True)
        except HttpError as e:
            text = str(e)
            if "quotaExceeded" in text or "uploadLimitExceeded" in text:
                sys.exit("\nYouTube's daily upload limit for this API project is used up; try again tomorrow.")
            if e.resp.status in (500, 502, 503, 504) and tries < 5:
                tries += 1
                time.sleep(2 ** tries + random.random())
                continue
            raise
    print()
    vid = resp["id"]
    info = probe(path)
    short = (info["height"] or 0) > (info["width"] or 0)
    url = f"https://youtube.com/shorts/{vid}" if short else f"https://youtube.com/watch?v={vid}"
    result = {"id": vid, "url": url, "privacy": status["privacyStatus"], "publish_at": publish_at,
              "uploaded_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    if meta.get("playlist"):
        try:
            pid = playlist_id(yt, meta["playlist"])
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
            result["playlist"] = meta["playlist"]
        except HttpError as e:
            result["playlist_error"] = str(e)[:200]
    meta["youtube"] = result
    save_json(meta_path, meta)
    print(json.dumps(result, ensure_ascii=False))


def cmd_publish(vid, privacy, at):
    yt = service()
    cur = yt.videos().list(part="status", id=vid).execute()["items"][0]["status"]
    body = {"privacyStatus": "private" if at else privacy,
            "selfDeclaredMadeForKids": cur.get("selfDeclaredMadeForKids", False)}
    if at:
        body["publishAt"] = at
    yt.videos().update(part="status", body={"id": vid, "status": body}).execute()
    print(json.dumps({"id": vid, "status": body}))


def plan_times(count, s, start=None):
    """Publish times for `count` clips from the schedule + max_uploads_per_day settings."""
    rule = str(s.get("schedule", "off")).strip().lower()
    per_day = max(1, int(s.get("max_uploads_per_day", 3) or 3))
    tz = dt.datetime.now().astimezone().tzinfo
    now = start or (dt.datetime.now(tz) + dt.timedelta(minutes=20))
    if rule in ("best_times", "best"):
        slots = ["12:00", "18:00", "21:00"]
    elif m := re.match(r"(\d{1,2}:\d{2})\s*daily", rule):
        slots = [m.group(1)]
    elif m := re.match(r"every\s*(\d+)\s*h(?:ours?)?(?:\s*from\s*(\d{1,2}:\d{2}))?", rule):
        step, first = int(m.group(1)), m.group(2) or "09:00"
        h0, m0 = map(int, first.split(":"))
        slots = [f"{h:02d}:{m0:02d}" for h in range(h0, 24, step)]
    else:
        return [None] * count
    times, day = [], now.date()
    while len(times) < count:
        today = []
        for sl in slots:
            h, m = map(int, sl.split(":"))
            t = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
            if t > now:
                today.append(t)
        times += today[:per_day]
        day += dt.timedelta(days=1)
    return [t.isoformat(timespec="seconds") for t in times[:count]]


if __name__ == "__main__":
    utf8()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("auth")
    p.add_argument("--client-secret")
    sub.add_parser("whoami")
    p = sub.add_parser("upload")
    p.add_argument("file")
    p.add_argument("--meta", required=True)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("publish")
    p.add_argument("video_id")
    p.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    p.add_argument("--at")
    p = sub.add_parser("schedule")
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--settings", required=True)
    a = ap.parse_args()
    if a.cmd == "auth":
        cmd_auth(a.client_secret)
    elif a.cmd == "whoami":
        cmd_whoami()
    elif a.cmd == "upload":
        cmd_upload(Path(a.file), a.meta, a.dry_run)
    elif a.cmd == "publish":
        cmd_publish(a.video_id, a.privacy, a.at)
    else:
        print(json.dumps(plan_times(a.count, load_json(a.settings, {})), indent=1))
