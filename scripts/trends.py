"""See what's working on YouTube right now for a topic: top recent videos, their titles, tags and hashtags.

Usage:
  python trends.py --query "cold approach india" [--region IN] [--lang hi] [--days 14] [--shorts]
  python trends.py --chart --region IN [--category Comedy]       # what's on the trending chart

Needs either a YouTube Data API key (env YOUTUBE_API_KEY, or the file ~/.video-clipper/youtube/api_key.txt)
or a connected channel (youtube_upload.py auth). With several channels, pass --channel "<name>" to use that one's
sign-in; without it, the default sign-in or else any saved one is used (a lookup reads public data, so any works).
Without a key or sign-in it exits with code 2: then use web search.
Quota: a search costs 100 of the 10,000 free daily units (the same pool uploads use, ~1,600 each).
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from common import HOME, utf8

KEY_FILE = HOME / "youtube" / "api_key.txt"
API = "https://www.googleapis.com/youtube/v3/"
CATS = {"comedy": 23, "gaming": 20, "entertainment": 24, "music": 10, "sports": 17, "education": 27,
        "people & blogs": 22, "howto & style": 26, "science & technology": 28, "news & politics": 25,
        "film & animation": 1}


def api_key():
    k = os.environ.get("YOUTUBE_API_KEY")
    if k:
        return k.strip()
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    return None


CHANNEL = ""


def signed_in_channel():
    """The channel whose saved sign-in to use, as youtube_upload.py names it, or None if there's none."""
    import youtube_upload as yu
    if CHANNEL and CHANNEL != "default":
        yu.CHANNEL = CHANNEL
        if yu.token_path().exists():
            return CHANNEL
    if (HOME / "youtube" / "token.json").exists():
        return "default"
    others = sorted((HOME / "youtube").glob("token-*.json"))
    return others[0].stem[len("token-"):] if others else None  # token-<slug>.json: the slug names it again


def call(endpoint, params):
    key = api_key()
    if key:
        params = {**params, "key": key}
        with urllib.request.urlopen(API + endpoint + "?" + urllib.parse.urlencode(params), timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    channel = signed_in_channel()
    if channel:
        import youtube_upload as yu
        yu.CHANNEL = channel
        res = getattr(yu.service(), endpoint)()
        return res.list(**params).execute()
    print("No YouTube API key or connected channel: use web search for trends instead "
          "(see references/youtube.md to add a key).", file=sys.stderr)
    sys.exit(2)


def summarise(items):
    tags, hashtags, words = collections.Counter(), collections.Counter(), collections.Counter()
    vids, lens, emoji, questions = [], [], 0, 0
    for v in items:
        sn, st = v["snippet"], v.get("statistics", {})
        title = sn["title"]
        vids.append({"title": title, "channel": sn.get("channelTitle"), "views": int(st.get("viewCount", 0)),
                     "published": sn.get("publishedAt", "")[:10]})
        for t in sn.get("tags", []) or []:
            tags[t.lower()] += 1
        for h in re.findall(r"#\w+", title + " " + sn.get("description", "")):
            hashtags[h.lower()] += 1
        for w in re.findall(r"\w{4,}", title.lower()):
            words[w] += 1
        lens.append(len(title))
        emoji += bool(re.search(r"[\U0001F300-\U0001FAFF☀-➿]", title))
        questions += "?" in title
    vids.sort(key=lambda v: -v["views"])
    n = max(len(items), 1)
    return {
        "top_videos": vids[:12],
        "common_tags": [t for t, _ in tags.most_common(25)],
        "common_hashtags": [h for h, _ in hashtags.most_common(15)],
        "common_title_words": [w for w, _ in words.most_common(20)],
        "title_length_avg": round(sum(lens) / n),
        "titles_with_emoji_pct": round(100 * emoji / n),
        "titles_with_question_pct": round(100 * questions / n),
    }


if __name__ == "__main__":
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--query")
    ap.add_argument("--chart", action="store_true")
    ap.add_argument("--region", default="")
    ap.add_argument("--lang", default="")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--category", default="")
    ap.add_argument("--shorts", action="store_true", help="only videos under 4 minutes")
    ap.add_argument("--channel", default="", help="the youtube_channel setting, when not default")
    a = ap.parse_args()
    CHANNEL = a.channel
    if a.chart:
        params = {"part": "snippet,statistics", "chart": "mostPopular", "maxResults": 30,
                  "regionCode": a.region or "US"}
        if a.category:
            params["videoCategoryId"] = CATS.get(a.category.lower(), a.category)
        items = call("videos", params).get("items", [])
    else:
        if not a.query:
            sys.exit("--query or --chart is required")
        after = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=a.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        params = {"part": "snippet", "type": "video", "order": "viewCount", "q": a.query, "maxResults": 25,
                  "publishedAfter": after}
        if a.region:
            params["regionCode"] = a.region
        if a.lang:
            params["relevanceLanguage"] = a.lang
        if a.shorts:
            params["videoDuration"] = "short"
        ids = [i["id"]["videoId"] for i in call("search", params).get("items", []) if i["id"].get("videoId")]
        items = call("videos", {"part": "snippet,statistics", "id": ",".join(ids)}).get("items", []) if ids else []
    print(json.dumps(summarise(items), ensure_ascii=False, indent=1))
