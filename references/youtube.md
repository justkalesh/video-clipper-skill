# YouTube: setup, titles that perform, uploading

## One-time channel setup (the channel owner does this)

Uploading goes through the official YouTube Data API. The owner creates their own free Google Cloud project,
so the uploads run under their account. Guide them step by step. They click through Google's pages and sign
in themselves; never ask for their password.

1. Go to console.cloud.google.com → create a project (any name, e.g. "my clipper").
2. **APIs & Services → Library** → search "YouTube Data API v3" → **Enable**.
3. **APIs & Services → OAuth consent screen** → User type **External** → fill in the app name and their email →
   under **Test users** add the Google account that owns the channel.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID** → Application type **Desktop app** →
   **Download JSON**.
5. Run `python SKILL/scripts/youtube_upload.py auth --client-secret <downloaded file>`. A browser page opens. They
   pick the channel's account and allow access. Google warns that the app isn't verified: that's their own app,
   so "Continue" is fine.
6. `youtube_upload.py whoami` shows the connected channel. The sign-in is saved in `~/.video-clipper/youtube/`.

Optional, for trend lookups without spending the channel's sign-in: **Credentials → Create credentials →
API key**, then save it in `~/.video-clipper/youtube/api_key.txt` (or the `YOUTUBE_API_KEY` env var).

## Limits to tell the user about up front

- **Private until audited.** Google keeps videos uploaded through a new, unaudited API project private (locked).
  The owner can still review them. To post public or scheduled videos through the API, the project needs
  Google's free API compliance audit (search "YouTube API Services audit and quota extension form"). Until then,
  upload as private and the owner publishes from YouTube Studio.
- **Daily quota.** 10,000 free units a day. An upload costs about 1,600 (so about 6 uploads), a trend search 100.
  `max_uploads_per_day` spreads larger batches across days.
- **Shorts.** A vertical or square video up to 3 minutes is treated as a Short automatically. No #Shorts tag is
  needed, but it doesn't hurt.
- **Made for kids** must be answered on every upload (`made_for_kids`). **Altered or synthetic content**
  (realistic AI-generated people or scenes) must be declared (`altered_content`).

## Copyright: say it plainly, once

Clipping someone else's video and reposting it can lead to:
- Content ID claims: the money goes to the owner, or the clip is blocked
- copyright strikes: three within 90 days and the channel is deleted
- no monetisation under YouTube's "reused content" rule

The safe cases: the user's own videos, creators who allow or pay for clipping ("clip programs"), or written
permission. Credit the source in the description (`credit_source`). Editing and captions help, but don't
make a reupload safe.

## Writing titles, descriptions and hashtags that perform

Aim for what makes a viewer tap and stay. Nobody can guarantee virality: never promise it to the user.

**Research first** (`trend_research: on`): run `trends.py --query "<what the clip is about>" --region <country>
--shorts`, using 2-4 topic words, not the clip title. From the result, note:
- recurring title words and formats (questions? numbers? quotes?)
- tags and hashtags that recur across several top videos
- typical title length and emoji use

Use what fits this clip. Never copy titles or hashtags that don't describe it.

**Title** (`title_style`):
- `hook`: create curiosity without lying ("He saw the same ghost in two places at once").
- `punchline`: lead with the funniest or most shocking line, made understandable out of context.
- `question`: one the clip answers ("Can you date someone 20 years older?").
- `quote`: the best line from the clip, in quotes, plus who said it if they're known.
- `descriptive`: plain and searchable ("Why Lemon Juice Doesn't Grow a Beard").
- Put the strongest words in the first ~40 characters (phones cut the rest). Use the language viewers search in.
- At most one emoji (`emoji_in_title`). No ALL CAPS titles.

**Description** (`description_style`):
- `short`: one or two lines that add context or a question, then the hashtags.
- `full`: hook line, one line of context, the credit line, a question to drive comments, then the hashtags.
- Credit line: `Clip from: <original title> - <link>`.

**Hashtags** (`hashtags` count, default 4): YouTube shows the first three above the title, so put the best
three first:
1. the clip's specific topic (#ColdApproach, #ValorantClutch)
2. the show or creator name if people search for it
3. a broader category viewers follow (#ComedyPodcast, #Gaming)
4. one current trend tag, only if it truly applies

Then the `always_hashtags`. Never more than ~8, never unrelated trending tags (that breaks YouTube's spam rules).

**Tags** (`tags: auto`): 8-15 search phrases (topic, names, show, language variants such as "hinglish comedy").
Keep the total under 480 characters.

**Pinned comment.** One line that starts a conversation: a question, a hot take, or "part 2?". YouTube ranks
Shorts partly on engagement, and the creator's own pinned comment is the first thing people reply to.
- Example: "Be honest: would you have noticed the worn-out 9? 👀"

**Suggested posting time** (`best_time`), when posting by hand:
- the audience's evening peak (about 18:00-21:00 in `trend_region`'s main time zone)
- or the lunch peak (12:00-13:00)
- if the topic is having a moment (a launch, a trailer, news), as soon as possible

## Post text for other platforms

People posting by hand usually cross-post the same vertical clip. Write each app's text in its own style
(`post_platforms`). Don't paste the YouTube text everywhere.

**Instagram Reels caption**
- The first line is the hook: only about 125 characters show before "more".
- 1-3 short lines, then a question to drive comments, then 3-5 relevant hashtags on their own line.
- Add a save/share prompt only if it's natural ("send this to the friend who…").
- Keywords in the caption help Instagram search, so name the topic plainly in the first line.

**TikTok caption**
- Short: one line hook plus the topic keywords (TikTok search reads captions).
- Then 3-5 hashtags, the specific ones first (#gta6), and at most one broad one (#gaming).
- A question or "part 2?" invites comments.

**On every platform**
- Hashtags must describe the clip. Stuffing popular unrelated tags gets the post shown to the wrong people,
  and can break the platform's spam rules.
- The credit line goes in the YouTube description. On Instagram and TikTok, credit the original creator with
  a short "via @creator" when their handle is known.

## Scheduling

`youtube_upload.py schedule --count N --settings RUN/settings.json` turns `schedule` into publish times:
- `best_times`: 12:00, 18:00 and 21:00 local time, the usual peaks for short-form viewing. Real channel
  analytics aren't connected yet.
- `"18:00 daily"`: one a day at 18:00.
- `"every 4h from 10:00"`: 10:00, 14:00, 18:00, 22:00.

`max_uploads_per_day` caps each day. Scheduled uploads are sent as private with a `publishAt` time, and
YouTube flips them public at that moment. That needs the audited project mentioned above.
