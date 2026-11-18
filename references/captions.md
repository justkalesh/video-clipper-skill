# Captions

## Choosing the caption language and script

`caption_language` decides it. `auto` means:
- speech in a language written in Latin letters (English, Spanish, Indonesian...): the transcript's own words
- Hindi or Urdu speech (including Hindi-English mixing): **Hinglish**, meaning Hindi written in Roman letters
  with English words kept in English. That's how most viewers type and read this content.
- other languages in non-Latin scripts: native script by default. If the creator writes their own titles in
  Roman letters, follow them.

YouTube's auto captions for Hindi come back in Devanagari, even for English words ("आई एम आस्किंग यू"), so
Hinglish always needs a tokens file.

## The three ways to give caption words

### 1. Nothing: the transcript as-is
Fine when the transcript is already in the right language and script. With `remove_fillers` on, "um/uh" and
immediate repeats ("I I I think") are dropped. To emphasise words in the accent colour, pass
`--emphasis "word,other"` to build_clip.py.

### 2. A tokens file (`captions_N.tokens.txt`): rewrite words, keep their timing
One line per **transcript word in the clip's range** (markers like [Laughter] excluded), in the same order:
- write the caption word you want shown for that word
- `-` hides it (fillers, stutters, a false start)
- `*word` emphasises it (punchline words, numbers, names): it shows in the accent colour
- two transcript words can't merge into one line, but one line can hold two words ("Kung Fu"), and you can
  leave the next line as `-`

build_clip.py checks the count. On a mismatch it prints both columns (transcript word | your line) with
times, so you can see where they drift. Usually a word was skipped or doubled.

To get the words to transliterate, print the range from words.json:
```bash
python -c "import json,sys; sys.stdout.reconfigure(encoding='utf-8'); w=json.load(open('RUN/words.json',encoding='utf-8'))['words']; print('\n'.join(f\"{x['t']:.2f} {x['w']}\" for x in w if S<=x['t']<E and not x.get('m')))"
```

### 3. A phrases file (`captions_N.phrases.txt`): translations
When the caption words don't map 1:1 onto spoken words, write timed lines in the original video's time:
```
1100.4-1103.1 | Wait, you genuinely believe in ghosts?
1103.2-1108.2 | Yes! We went to a friend's village and the *same* ghost threw eggs at our car
```
Words are spread across each line by length. Keep lines short (one breath) so the timing stays close.

## Hinglish rules

Write it the way people actually type it on Instagram and YouTube in India:
- **English words stay English**: "Rohit Singh is the most generic name", "concept", "location", "present".
  Devanagari spellings of English words go back to normal English spelling ("कूल" → cool, "ईमेल" → email).
- Common spellings: hai, hain, nahi, kya, kyun, toh, bhi, mein, main, hum, tum, aap, yaar, bhai, accha, theek,
  matlab, waise, bahut, zyada, kuch, sab, sach, abhi, phir, lekin, kyunki, chahiye, raha/rahi/rahe, gaya, hua.
- Drop the silent final "a" (कर → kar, not kara). Use "aa/ee/oo" only where the long vowel matters
  (aana, jeena, doosra).
- Names and brands in their usual spelling (people's names as they write them, brand names as the brand
  writes them: "DigiYatra", "Kung Fu Panda").
- Fix what auto captions mishear when the context makes it clear (in one test: "नकली एलएसटी" → nakli LSD,
  "शैल" → Shein, "काफी कुमकुम मूवी" → Kung Fu Panda movie). If unsure, keep the closest plain reading.
- Keep slang and swearing as spoken unless `censor` is on. With `censor: mask`, write it masked in the tokens
  (b***d).
- Punctuation drives the caption breaks: end sentences with . ? ! and use commas for pauses.

## Styles and their limits

- **karaoke / boxed**: `words_per_caption` words, at most `max_caption_chars` characters (so one line).
- **pop**: one word at a time. Hyphenate long compounds sparingly.
- **line**: up to ~7 words or 34 characters, like TV subtitles.
- **none**: no captions. Still write the tokens/phrases if you want an .srt (`export_srt`).
- Markers: with `captions_when_silent: describe`, labels like [laughs] / [music] show during non-speech.

Emoji (`emoji: light`): add at most one per clip section, as its own token after a punchline (😂, 🔥, 💀).
Never add one mid-sentence.
