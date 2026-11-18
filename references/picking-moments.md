# Picking moments

The clip list is the most important judgment in the whole pipeline. A perfectly rendered clip of a dull moment
still flops. Spend your effort here.

## What makes a short clip work

A clip works when someone who has never heard of the creator stops scrolling in the first second and feels
it was worth it by the end. That gives you five checks for every candidate:

1. **Hook in the first 1-2 seconds**: a surprising claim, a question, a funny line, a reaction face, the start
   of an action. If the best line comes 10 seconds in, start closer to it.
2. **One idea**: one story, one joke, one play, one tip. Two half-ideas lose to one whole one.
3. **Payoff**: the punchline, the reveal, the clutch, the answer. The clip exists for this moment.
4. **Reaction**: laughter, "no way", the crowd. It tells viewers the payoff landed, so keep 1-2 s of it.
5. **Clean ending**: end on the payoff or the reaction, not on the next topic starting.

Rank candidates by how strongly they pass these, and only then by length or position in the video.

## Finding candidates

Use several signals together. Each catches moments the others miss.

- **The transcript** (always): read it start to finish. Note stories, punchlines, strong opinions, questions with
  surprising answers, quotable lines, and clear explanations of one thing.
- **Loudness spikes** (`signals.py`): laughter, cheering, shouting, game explosions. A spike right after a line
  usually means that line landed.
- **Markers** in subtitles (`[Laughter]`, `[Applause]`, `[हंसी]`): the same idea, already labelled.
- **Visual cuts** (`--visual`): editors cut faster around exciting moments. In gameplay, bursts of cuts or
  motion often mean action.
- **Chapters and the description**: creators often name their best segments.

## By kind of video

These are tendencies, not rules. The same video can contain several kinds.

| Kind | Great moments usually are | Main signals | Watch out for |
|---|---|---|---|
| Podcast / interview | a story, a hot take, a surprising fact, a heated exchange | transcript, laughter | long setups: start at the hook and keep only the context the payoff needs |
| Panel / video call / reaction stream | a group laugh, a roast, a running joke paying off | laughter spikes, markers | clips that are mostly the thing being reacted to |
| Standup | a full joke: setup → punchline → laugh | laughter / applause spikes | cutting the setup; cutting before the laugh |
| Gaming with facecam | clutch plays, fails, rage or hype reactions, funny commentary | loudness, visual action, transcript | silent stretches; clips that need too much game context |
| Gaming, no facecam | the play itself | visual action, game audio | the action happening outside the crop (use `screen_content: fill` or contain) |
| Vlog | a reveal, a funny mishap, a striking place, a strong opinion | transcript, visuals | slow travel footage with nothing happening |
| Tutorial / lecture | one complete tip or step, a clear "aha" explanation | transcript | references to "the earlier slide" that break self-containment |
| Sports / action | the play, the goal, the crowd's reaction | crowd noise, visual action | broadcast footage: high copyright risk |
| Music performance | the chorus, a drop, a solo, the crowd singing along | audio energy | lyrics captions: leave them off (copyright) |

## Where to cut

- Start on the first word of the hook, or 0.3-0.5 s before the action begins. Use `words.json`: start a little
  before the first word's time and end a little after the last word's end.
- If a camera cut falls within ~0.5 s of your planned start, start on the cut: it looks intentional.
- End after the reaction (laughter usually lasts 1-3 s), but before the next speaker starts a new topic.
- Never end on a dangling word ("and then...", "so the..."). Move the end back to the last complete sentence.
- If the length rules force a cut in the middle of the payoff, the moment doesn't fit: skip it rather than
  cutting it badly.

## The ranked list

Show the user something they can decide from quickly:

| # | Time | Length | Working title | Opens with | Why it works |
|---|---|---|---|---|---|
| 1 | 18:20-18:59 | 39 s | The "beautiful" ghost | "Genuinely, you believe in ghosts?" | a full story with a twist; huge laugh at the end |

Mark candidates that rely on someone else's footage (memes, clips being reacted to, broadcasts), so the user
can weigh the copyright risk.
