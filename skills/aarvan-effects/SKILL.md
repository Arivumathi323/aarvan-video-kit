---
name: aarvan-effects
description: Add video effects to Arivu's talking-head videos. Covers the Aarvan Drop signature and the 45-effect pack (spotlight, orbit, checklist, glass graph, LED sign and more), on the exact word. Use for /effects, a named effect, or "add an effect/zoom/sticker to my video".
---

# Aarvan effects

This skill adds effects to a video Arivu sends, and keeps everything else as it is: his audio and his cut. For a full edit (cutting, captions, music, three options to pick from), use the **aarvan-edit-director** skill instead.

Arivu isn't an editor. Keep replies short and friendly, do all the technical work yourself, and never ask him to run commands.

## 1. Set up the kit (first time in a session)

```bash
K=~/aarvan-video-kit
[ -d $K ] || git clone -q https://github.com/Arivumathi323/aarvan-video-kit $K
bash $K/setup.sh          # must print READY
```

- `NEED_FFMPEG`: install it (`sudo apt-get install -y ffmpeg`, or `brew install ffmpeg`).
- If the clone fails, the repo may be private or missing. Tell him in one line.

## 2. Find the words

```bash
$K/aarvan analyze <video> work/
```

This writes `work/analysis.json` (every word with its time, plus pauses and energy) and `work/sheet.jpg` (a timestamped contact sheet). Read the sheet yourself.

Transcription uses Whisper, and switches automatically to Parakeet (English only, from GitHub) when huggingface.co is blocked. For Tamil speech, ask him to allow `huggingface.co` in Settings → Capabilities, or ask for the timing in seconds.

Before anchoring effects, fix misheard words in `analysis.json`: change `"w"`, or set `"skip": true` to hide a word from captions.

If the clip is **silent**, say so. Offer the brand voice-over from aarvan-edit-director, or work from seconds.

## 3. Pick effects

- **The Aarvan Drop** is the channel's signature: the room dims, an orange band sweeps in, and a giant white word slams down behind his head with a whoosh-boom. Use it **once per video** on the most important word. Suggest it whenever he asks for "our effect", "signature" or "the drop".
- **Pack effects:** match his words to `$K/docs/EFFECTS.md` and the full table in `$K/vendor/claude-video-effects/SKILL.md`. Use at most 2 pack effects plus the Drop. Keep each one 1.5–4 s. Set `"color": "#FF741A"` where the effect has a colour.
- Never use `backdrop-word` together with the Drop.
- If he names an effect that doesn't exist, show the closest 3 from the list.
- Pack effects are built for vertical phone video. On tight landscape or webcam shots, check frames carefully: camera effects can over-zoom and panels can crowd the face.

## 4. Write the plan

Save it next to the video as `<name>_fx.json`. Use one segment covering the whole clip, keep his audio, and leave out captions, music, intro and end card unless he asks for them:

```json
{
  "source": "raw.mp4", "output": "raw_effects.mp4", "audio": "source", "analysis": "work/analysis.json",
  "segments": [{"in": 0, "out": <duration>, "zoom": 1.0, "push": 0}],
  "captions": false, "music": false, "intro": false, "end_card": false, "progress_bar": false, "look": "none",
  "signature": {"at": {"word": "build"}, "text": "BUILD", "dur": 2.4},
  "effects": [{"fx": "spotlight", "start": 3.2, "end": 5.8, "text": "AARVAN LABS", "color": "#FF741A"}]
}
```

How to write the plan:

- Pack effects use **source seconds**. Take them from the word times in `analysis.json`.
- Everything else uses word anchors: `{"word": "...", "n": k}`, where `n` counts repeats of that word starting at 0.
- `"aspect": "9:16"` turns a landscape clip vertical for Reels.
- The format is documented in `$K/README.md`.

## 5. Check, then render

1. Timeline: `$K/aarvan render <plan> --timeline`
2. Check frames in the middle of every effect and of the Drop: `$K/aarvan render <plan> --still t1,t2,...`. Look at every frame yourself. Fix anything that covers his face, is cut off or is hard to read, then check again.
3. Render: `$K/aarvan render <plan>`. A 30 s clip at 1080p takes a few minutes. Use `--draft` for a quick 720p version.
4. Send him the file and one line saying what was added and where. Remind him to watch it before posting.

Credit: the effect pack is claude-video-effects by @vibha.in.progress (MIT).
