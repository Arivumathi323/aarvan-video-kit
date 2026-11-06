# aarvan-video-kit

The Aarvan Labs video editing kit. You give it a raw talking-head clip and an edit plan, and it gives back a finished, on-brand video with:

- cuts with face-centred punch-ins and slow push-ins
- smooth zoom-blur transitions, each with a whoosh
- a colour grade
- word-by-word captions with the active word in orange
- stickers, a name tag and big title lines
- an intro card and an end card
- original synthesised music that ducks under the voice, plus sound effects
- loudness levelled to -14 LUFS
- **The Aarvan Drop**, the channel's signature move

It also runs the 45-effect [claude-video-effects](https://github.com/Vibha-Ramprakash/claude-video-effects) pack (MIT, by @vibha.in.progress) as an optional first pass.

## Setup (once)

```bash
git clone https://github.com/Arivumathi323/aarvan-video-kit ~/aarvan-video-kit
bash ~/aarvan-video-kit/setup.sh        # prints READY
```

You need ffmpeg, Python 3.10 or newer, and git. On Windows, use WSL (Ubuntu).

## Commands

```bash
K=~/aarvan-video-kit
$K/aarvan analyze raw.mp4 work/            # writes work/analysis.json + work/sheet.jpg
$K/aarvan render plan.json --timeline      # print the timeline
$K/aarvan render plan.json --sheet 8       # 8-frame preview sheet (fast)
$K/aarvan render plan.json --still 3,12.5  # check frames at output seconds
$K/aarvan render plan.json --draft         # 720p full render
$K/aarvan render plan.json                 # final render (1080 short side); prints an Audio check (voice must lead by >= 12 dB)
$K/aarvan render plan.json --remix         # rebuild only the sound onto the finished video (seconds)
$K/aarvan qa plan.json --target reels      # numeric checks: hook, dead air, pacing, safe zones, face, Drop, voice level, loudness
$K/aarvan voice script.txt vo/             # brand voice-over, one line per shot (for silent clips)
```

## The Aarvan Drop (signature)

Use it **exactly once per video**, on the single most important word.

1. The room dims (you stay lit).
2. An orange diagonal band sweeps in behind you.
3. The word slams down in giant white letters *behind your head*.
4. The camera punches in 7% with a short shake and a white flash.
5. The caption for that word pops bigger.
6. On sound, a rising swoosh lands on a deep boom.

```json
"signature": {"at": {"word": "build", "n": 1}, "text": "BUILD", "dur": 2.4}
```

## Plan format

There are two kinds of time in a plan:

- **Source time** is a number in seconds of the *raw* video. It's used for `segments` and `effects`.
- **Word anchors** like `{"word": "laptop", "n": 0, "offset": 0}` point at the n-th time a word is spoken among the *kept* speech. They're used for everything else, and are best for graphics because they always land on the word. Punctuation and case are ignored. `{"out": 12.3}` means output seconds.

```jsonc
// comments are only for explanation; real plan files are plain JSON
{
  "source": "raw.mp4",
  "output": "final.mp4",
  "target": "reels",                  // reels | shorts | youtube | assignment | client (sets the QA limits)
  "aspect": "source",                 // or "9:16", "16:9", "1:1" (crops around the face)
  "layout": "fill",                   // or "fit": the whole source inside the frame over a blurred copy (low-res landscape -> vertical)
  "size": 1080,                       // short side of the output
  "audio": "source",                  // your own voice; or "voiceover" for silent clips
  "analysis": "work/analysis.json",   // from `aarvan analyze` (needed for captions with audio=source)
  "voiceover": {"dir": "vo"},         // only for audio=voiceover; line i plays on segment i (override with "vo": k)
  "intro": {"title": "ARIVUMATHI", "subtitle": "AI & AUTOMATION DEVELOPER"},   // or false
  "segments": [                       // shots in order: source in/out seconds, zoom 1.0 = wide
    {"in": 2.4, "out": 6.1, "zoom": 1.0},
    {"in": 6.5, "out": 11.0, "zoom": 1.22},
    {"in": 40.0, "out": 46.0, "trans": {"dur": 0.6, "style": "whip"}}   // optional: transition INTO this shot ("whip" pan or "zoom" blur); default = "transition"
  ],
  "transition": {"dur": 0.3},
  "captions": {"max_words": 3},       // or false; "y": 0.86 to move them
  "signature": {"at": {"word": "build"}, "text": "BUILD", "dur": 2.4},
  "nametag": {"at": {"word": "student"}, "name": "ARIVUMATHI S", "sub": "FOUNDER · AARVAN LABS"},
  "stickers": [
    {"at": {"word": "laptop"}, "until": "segment_end", "text": "NO LAPTOP", "x": 0.83, "y": 0.44,
     "style": "dark", "strike": true},           // style: dark | accent | light
    {"at": {"word": "agent"}, "until": {"word": "agentic", "n": 1}, "text": "01  AI AGENT", "x": 0.975, "y": 0.17}
  ],                                              // x > 0.9 right-aligns, x < 0.1 left-aligns; same "until" = a list that builds up
  "titles": [                         // big lines; captions hide while they show
    {"at": [{"word": "i", "n": 3}, {"word": "i", "n": 4}], "lines": ["I AM THE TEACHER.", "I AM THE LEARNER."]}
  ],
  "effects": [                        // optional claude-video-effects pass, SOURCE seconds
    {"fx": "spotlight", "start": 23.0, "end": 25.2, "text": "AARVAN LABS", "color": "#FF741A"}
  ],
  "end_card": {"at": {"word": "let's"}, "sync": [{"word": "let's"}, {"word": "something"}], "dur": 3.5},
  "music": {"mood": "punchy", "bpm": 116, "volume": 0.42},   // or false; moods: punchy | chill | cinematic
  "sfx": true,
  "progress_bar": true
}
```

Transcript tips (`analysis.json`):

- Fix a misheard word by editing its `"w"`.
- `"skip": true` keeps a word in the audio but hides it from captions.
- Fillers (uh, um) are hidden automatically.
- Mishearings that keep coming back belong in `asr_fixes` in `brand/brand.json`.
- If Whisper can't download (huggingface.co blocked), the analyzer uses Parakeet TDT 0.6B (English) from GitHub releases.

Rules the renderer follows:

- With `audio: "source"`, the cut between two shots happens in the middle of the transition. Start and end segments in pauses, using `pauses` from `analysis.json`, at least 0.15 s away from words.
- For a zoom change with no words lost, set the next segment's `in` to the previous segment's `out` minus `transition.dur`.
- With `audio: "source"`, the voice is cleaned (noise reduction plus levelling) unless `"clean_voice": false`.
- Shots overlap by `transition.dur`. The output length is the sum of shot lengths, minus the overlaps, plus the intro and end card.
- Graphics never sit on the face: stickers go on the empty side of the frame, and the Drop word goes behind you.

The brand (colours, fonts, intro, end card, voice) lives in `brand/brand.json`. **How the editor thinks is in `docs/EDITOR_BRAIN.md`**, which is the source of truth for every decision and has a lessons log. See `docs/ENGAGEMENT.md` for how edits are chosen, and `docs/EFFECTS.md` for the effects pack.

## Credits

The effects pack, face tracking (YuNet, MIT) and person cut-out (MediaPipe Selfie Segmenter, Apache 2.0) come from claude-video-effects by Vibha Ramprakash (MIT). Fonts are Inter and Poppins (SIL OFL 1.1). The voice is Kokoro (Apache 2.0). See THIRD_PARTY.md.
