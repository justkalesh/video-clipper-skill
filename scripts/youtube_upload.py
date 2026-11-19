"""Connect a YouTube channel and upload clips to it.

One-time setup (the channel owner does this; see references/youtube.md):
  python youtube_upload.py auth --client-secret path/to/client_secret.json   # opens a Google sign-in page
  python youtube_upload.py whoami                                            # shows the connected channel

Uploading:
  python youtube_upload.py upload "OUT/01 - Title.mp4" --meta "OUT/_data/01 - Title.meta.json" [--dry-run]
  python youtube_upload.py publish <video_id> --privacy public               # after the owner approves a private upload
  python youtube_upload.py publish <video_id> --at 2026-11-20T18:00:00+00:00 # schedule it instead
  python youtube_upload.py schedule --count 5 --settings run_settings.json   # print publish times for N clips

Several channels: add --channel "<channel name>" (the youtube_channel setting) to every command. Each channel
keeps its own sign-in; at `auth`, pick that channel on Google's screen. Uploads stop if the signed-in channel
isn't the one named.

The .meta.json file (written by Claude per clip):
  {"title", "description", "hashtags": [...], "tags": [...], "category": "Comedy",
   "privacy": "private|unlisted|public|scheduled", "publish_at": "ISO time with timezone, needed for scheduled",
   "playlist": "name or null",
   "made_for_kids": false, "notify_subscribers": true, "altered_content": false, "language": "hi",
   "pinned_comment": "a comment to pin under the video", "best_time": "e.g. today 18:00-21:00 local",
   "platforms": {"instagram": {"caption": "...", "hashtags": [...]}}}
After an upload, a "youtube" block with the video id and link is written back into it.
The API can't post or pin comments with this sign-in: the pinned comment is for the owner to post and pin by hand
(YouTube app or Studio) once the video is public.
"""
import argparse
import datetime as dt
import http.client
import json
import random
import re
import shutil
import socket
import ssl
import sys
import time
from pathlib import Path

from common import HOME, load_json, probe, save_json, slug, utf8

YT_DIR = HOME / "youtube"
SECRET = YT_DIR / "client_secret.json"
CHANNEL = "default"


def token_path():
    return YT_DIR / ("token.json" if CHANNEL in ("", "default") else f"token-{slug(CHANNEL, 60)}.json")

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
    token = token_path()
    if not token.exists():
        extra = f' --channel "{CHANNEL}"' if CHANNEL not in ("", "default") else ""
        sys.exit(f"No YouTube channel connected yet. Run: python youtube_upload.py auth --client-secret <file>{extra}")
    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token.write_text(creds.to_json(), encoding="utf-8")
        else:
            sys.exit("The YouTube sign-in has expired. Run auth again.")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel_check(yt):
    """With a named channel, make sure the sign-in belongs to it before changing anything."""
    if CHANNEL in ("", "default"):
        return
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    names = [c["snippet"]["title"] for c in items]
    if not any(n.strip().lower() == CHANNEL.strip().lower() for n in names):
        sys.exit(f"Signed in to {names or 'no channel'}, not '{CHANNEL}'. Run auth --channel \"{CHANNEL}\" and pick "
                 "that channel on Google's screen.")


def check_schedule(meta):
    """privacy + publish_at as YouTube accepts them: (privacyStatus, publishAt or None). Exits with a clear message
    instead of letting the API reject the upload."""
    privacy = str(meta.get("privacy") or "private").strip().lower()
    at = meta.get("publish_at")
    if privacy not in ("private", "unlisted", "public", "scheduled"):
        sys.exit(f"privacy '{privacy}' isn't one of private | unlisted | public | scheduled")
    if privacy == "scheduled" and not at:
        sys.exit("privacy is 'scheduled' but publish_at is empty: run `schedule` and put a time in publish_at")
    if not at:
        return privacy, None
    try:
        when = dt.datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        sys.exit(f"publish_at '{at}' isn't an ISO time like 2026-11-20T18:00:00+05:30")
    if when.tzinfo is None:
        sys.exit(f"publish_at '{at}' has no timezone: add one, like +05:30 or Z")
    if when <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        sys.exit(f"publish_at '{at}' is in the past (or under 5 minutes away): pick a later time")
    # YouTube publishes a scheduled video by switching it from private at that time
    return "private", when.isoformat(timespec="seconds")


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
    token_path().write_text(creds.to_json(), encoding="utf-8")
    cmd_whoami()


def cmd_whoami():
    yt = service()
    r = yt.channels().list(part="snippet,statistics", mine=True).execute()
    for c in r.get("items", []):
        print(json.dumps({"channel": c["snippet"]["title"], "id": c["id"],
                          "subscribers": c["statistics"].get("subscriberCount")}, ensure_ascii=False))
    channel_check(yt)


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
    if not Path(path).is_file():
        sys.exit(f"{path} not found")
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
    privacy, publish_at = check_schedule(meta)
    status = {
        "privacyStatus": privacy,
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
    channel_check(yt)
    # network trouble only (a reset, timeout, DNS or TLS hiccup); anything else, like a file error, stops at once
    net_errors = (ConnectionError, TimeoutError, socket.gaierror, ssl.SSLError, http.client.HTTPException)
    try:
        import httplib2
        net_errors += (httplib2.HttpLib2Error,)
    except ImportError:
        pass
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
        except net_errors as e:  # dropped connection, timeout, reset: the resumable upload continues where it was
            if tries >= 8:
                raise
            tries += 1
            wait = min(60, 2 ** tries) + random.random()
            print(f"\n  connection problem ({type(e).__name__}), retrying in {wait:.0f}s...", flush=True)
            time.sleep(wait)
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
    channel_check(yt)
    if at:
        _, at = check_schedule({"privacy": "scheduled", "publish_at": at})
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
    for p in sub.choices.values():
        p.add_argument("--channel", default="default", help="the youtube_channel setting")
    a = ap.parse_args()
    CHANNEL = a.channel or "default"
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
