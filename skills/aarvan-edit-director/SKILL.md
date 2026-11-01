---
name: aarvan-edit-director
description: Full edit for Arivu's raw Aarvan Labs videos. Watches the clip, proposes the 3 best edit options scored for engagement (each with the Aarvan Drop signature), lets him pick one, then renders it with captions, music and transitions. Use when he sends a raw video to edit or post.
---

# Aarvan edit director

Arivu sends a raw video and doesn't know editing. Your job: watch it, offer **3 genuinely different edit options** ranked for engagement, let him choose one, and deliver the finished video. Every option carries the channel identity: the brand look plus **one Aarvan Drop**.

Talk like a friendly creative partner, short and clear. Do every technical step yourself and never ask him to run commands. Give your opinion first when he asks for one.

## 1. Set up the kit

```bash
K=~/aarvan-video-kit
[ -d $K ] || git clone -q https://github.com/Arivumathi323/aarvan-video-kit $K
bash $K/setup.sh          # must print READY
```

Read `$K/README.md` (plan format), `$K/docs/ENGAGEMENT.md` (scoring and brand rules), `$K/docs/EFFECTS.md` and `$K/docs/PERFORMANCE.md` (what has worked before).

## 2. Watch the video

```bash
$K/aarvan analyze <raw video> work/
```

Then read `work/analysis.json` and **look at `work/sheet.jpg`**. Work out:

- **The story:** what he's saying, in 1–2 lines, and the audience.
- **Hook candidates:** the strongest line to open on. It's often not the first line.
- **The Drop word:** the single most important word, such as the payoff, the promise or a surprising claim.
- **Retakes and mistakes:** when he repeats a sentence, keep the last clean take.
- **Dead parts:** black frames, long pauses, "umm", setup chatter, walking to the camera.
- **Content shape:** steps, numbers, a story, a client, a before/after. This decides which fresh effects fit.
- **Format:** vertical goes to Reels/Shorts, landscape to YouTube. Ask only if it's unclear where it will be posted.

If you see `transcription failed`, the Whisper model download was blocked. Run the analysis on his linked computer if there is one. Otherwise ask him to allow `huggingface.co` in Settings → Capabilities.

If the clip is **silent** (no usable voice), offer the brand voice-over:

- Write the script from what's on screen and his notes, one line per shot, and show it to him first.
- Then run `$K/aarvan voice script.txt vo/` and use `"audio": "voiceover"`.
- The voice is Kokoro am_fenrir at speed 1.05. Never change it unless he asks.

## 3. Build 3 options

Write `work/option_A.json`, `option_B.json` and `option_C.json` following the A/B/C recipes in `docs/ENGAGEMENT.md` (Punchy, Cinematic story, Trend mix).

Every option must:

- have exactly one `signature` (the Aarvan Drop) and at most 2 pack effects;
- keep captions on;
- start every segment's `in`/`out` inside a pause (at least 0.15 s from any word);
- put graphics on the empty side of the frame, never on the face;
- skip the intro card for Reels under 45 s and open on the hook instead;
- end with the end card right after the last point;
- use `"aspect": "9:16"` for Reels and Shorts.

Use word anchors (`{"word": ..., "n": k}`) for graphics, and source seconds for `segments` and pack `effects`.

Score each option out of 100 with the rubric, and be honest. These scores are reasoned estimates, not platform predictions. If `PERFORMANCE.md` has 5 or more rows, let those results weigh more.

## 4. Preview and let him choose

For each option, run `$K/aarvan render work/option_X.json --sheet 8` and look at the sheet. Fix anything that's wrong before he sees it.

Send all three sheets, then a compact comparison:

| | A · Punchy | B · Cinematic | C · Trend mix |
|---|---|---|---|
| Score | 86 | 79 | 82 |
| Hook | "..." | ... | ... |
| Aarvan Drop on | "...**WORD**..." | ... | ... |
| Fresh effects | lean-in @ "...", comment-box @ end | ... | ... |
| Length | 34 s | 41 s | 37 s |

Add your recommendation in one line, then ask him to pick: use AskUserQuestion with the three options, recommended first. He may also mix options ("A, but with B's music"), so adjust the plan to match.

## 5. Render the chosen edit

1. `--still` frames at the Drop (word time + 0.4 s), at each effect and at any busy moment. Look at them and fix problems.
2. Final render: `$K/aarvan render work/option_X.json`. At 1080p this takes roughly 6–10× the video length. Tell him it's rendering.
3. Send the file with a one-line summary. Also offer one short caption and hashtags for the post, then stop.

## 6. Learning loop

Remind him once to share the numbers after 7 days: views, average watch %, likes, shares and saves. If the YouTube connector is available, pull them yourself. Then add a row to `$K/docs/PERFORMANCE.md` and push it to the repo if this session can push. Otherwise, give him the row to keep. Future options should lean toward what worked.

## Brand reference

The brand lives in `$K/brand/brand.json`:

- **Colours:** orange `#FF741A`, black and white.
- **Fonts:** Inter Black and Poppins.
- **Intro:** "AARVAN LABS · INTRO / ARIVUMATHI / AI & Automation Developer".
- **End card:** "LET'S BUILD / SOMETHING." with @aarvan_labs · aarvanlabs.com.
- **Tagline:** "I am the teacher. I am the learner."
- **Signature:** the Aarvan Drop, once per video. It's what makes viewers recognise the channel.
