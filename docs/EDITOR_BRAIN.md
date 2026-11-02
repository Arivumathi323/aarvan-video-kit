# The Aarvan editor brain

This is how a good editor thinks, written down so every Aarvan Labs video gets the same judgement. Work through the eight passes in order. Each pass ends with decisions you write into the plan. The **numbers** in each pass are what `aarvan qa` checks, because a rule that can't be measured gets missed (see the Lessons log at the end).

---

## Pass 1 · Understand the job

Before touching a frame, answer these four questions in one line each:

1. **Who is watching?** Instagram scrollers, YouTube subscribers, a teacher, a client.
2. **Where will it play?** That sets the `target` (Reels, Shorts, YouTube, assignment, client) and the orientation.
3. **What is the one message?** If you can't say it in one sentence, the edit will wander.
4. **What should they do after?** Follow, comment, hire, or nothing (an assignment).

| target | orientation | length | hook by | max still stretch | intro card | end card |
|---|---|---|---|---|---|---|
| reels / shorts | 9:16 | ≤ 90 s (≤ 60 for Shorts) | 2 s | 4.5 s | no if < 45 s | brand CTA |
| youtube | 16:9 | any | 8 s | 7 s | yes | brand CTA |
| assignment | source shape | any | 6 s | 8 s | yes, with a "SELF INTRODUCTION"-style label | THANK YOU + name |
| client | ask | ≤ 5 min | 5 s | 6 s | yes | client's CTA |

## Pass 2 · Story

- **Find the hook.** It's the most surprising, useful or emotional line, and it's often not the first one. For social media, open on it, even if that means moving it to the front as a cold open.
- **Structure:** hook, then context (who/why), then the value (the points), then the payoff (the big line, where the Aarvan Drop goes), then the call to action.
- **Cut everything that doesn't serve the one message:** retakes (keep the *last* clean take), false starts, stutters ("I am a college, I am a college student"), garbled sentences, rambling, "uh/um" pauses and setup chatter.
- **Never cut meaning.** If cutting a line would change what he meant, keep it.
- **The Drop word** is the single word that carries the message. Exactly one per video.
- **Numbers:** no silence over 1.0 s inside speech, and the hook lands by the target time.

## Pass 3 · Rhythm

- **Cut on breaths.** Segment boundaries go in pauses, at least 0.15 s from any word.
- **Change the shot size to keep energy without losing words.** Zoom changes of about 1.0 to 1.15 work as an overlap jump cut: the next segment's `in` is the previous `out` minus 0.3.
- **Pattern interrupts:** something visibly changes at least every 3–4 s for social media and every 6–8 s for long-form. That can be a cut, a punch-in, a sticker, a title, an effect or the Drop.
- **Let big lines breathe.** Hold about 0.4 s after the payoff before the next cut.
- **Don't stack big moments back to back.** Leave at least 4 s between the Drop and any pack effect.
- **End fast.** The end card arrives within 0.8 s of the last word, with no dead tail.
- **Numbers:** the longest stretch with no visual change stays within the target's limit.

## Pass 4 · Framing, by orientation

**Horizontal (16:9):**
- Face in the upper third, eyes near the top-third line, with a little headroom.
- Captions at about 86% height. Stickers on the empty side of the frame (`x: 0.975` right-aligns, `x: 0.025` left-aligns).
- Name tag top-left.

**Vertical (9:16), native phone footage:**
- Face in the upper third, captions at about 70% height.
- Keep graphics out of the platform UI: the bottom 25% (caption/username), the right edge from 45% to 85% height (like/comment/share buttons), and the top 5%.
- Stickers centred (`x: 0.5`) or top-right above 45% height.

**Landscape footage that needs to be vertical**, decided by resolution and framing:
- **Fill** (crop to 9:16 around the face): only when the source is at least 1080 p tall and it's a single close talking head. The upscale must stay ≤ 1.6×.
- **Fit** (`"layout": "fit"`): the whole shot in the middle with a blurred copy behind, labels above it (y 0.07–0.25), captions below it, and zooms 1.0 / 1.08. Use it for 720 p webcams, wide shots, screen shares, or anything where cropping would lose content.

**Tight webcam or close-up footage:**
- Keep zooms ≤ 1.15.
- Camera-moving pack effects (locked-on, lean-in) over-zoom, and panels (checklist, apple-toggles) crowd the frame. Use our own stickers instead.

**Numbers:** no sticker over the face, nothing in the platform UI zones, and the reframe upscale ≤ 1.6×.

## Pass 5 · Sound

**The voice is king.** The priority order is the voice, then the sound effects, then the music. When anything fights the voice, the voice wins.

- **Clean the voice:** high-pass at 80 Hz, noise reduction, then levelling. Quiet webcam mics need it most (done automatically with `clean_voice`).
- **Levels:**
  - voice speech RMS at -18 dBFS before the mix;
  - music 20 dB under the voice while he speaks and 9 dB under in pauses;
  - sound effects peaking at no more than 40% of the voice peak.
- **Music mood follows the target:**
  - punchy (116–124 bpm) for energetic social videos;
  - cinematic for story or emotional videos;
  - chill (92–100 bpm) for explainers and assignments, kept quiet.
- **Sound effects support the picture and never decorate silence:** a whoosh on a transition, a pop on a sticker, the whoosh-boom on the Drop. Busy edits with many stickers need fewer pops.
- **Finish** at -14 LUFS integrated, with true peak ≤ -1 dBFS.
- **Numbers:** the voice leads the background by **at least 12 dB** while speaking, and loudness is -14 ± 1.5 LUFS. If either fails, change the plan and run `--remix`; there's no need to re-render the picture.

## Pass 6 · Graphics

- **Every graphic means something.** It names a thing he said (XSPEED, n8n, Silambam), sums up a point, or builds a list. Nothing is decoration.
- **Restraint:** one Aarvan Drop plus at most two fresh pack effects. Stickers stay short (2–4 words) and on screen until the topic changes.
- **Lists that build up** (`until` set to the same anchor) are good for "my projects" and "3 tips" segments.
- **Name tag** on the first mention of his name. For Reels under 20 s, skip it.
- **Captions always on:** 2–3 words at a time, with the active word in orange.
- **Fix misheard words before anything else** in `analysis.json`. A wrong caption looks careless.
- **Brand:** orange #FF741A, black and white; Inter Black and Poppins; the logo on intro and end cards.

## Pass 7 · Look

- Grade for consistency: tame colour casts (yellow walls, blue webcams), lift contrast, and a slight vignette (`look: "aarvan"`).
- For overexposed webcams, don't push contrast further. Consider `"look": "none"`.
- Light sharpening for sources under 1080 p, never heavy.

## Pass 8 · QA before anyone sees it

1. `aarvan qa plan.json --target <target>`. There must be **no FAIL**. Explain any WARN or fix it.
2. **Look at the preview sheet and the `--still` frames:** the Drop, every effect, every busy moment, the first and last second.
3. **After the final render**, check the `Audio check` line and run `aarvan qa` again. Now it also measures the loudness of the real file.
4. **What you can't check:** say so plainly. Nobody has actually *listened* to the video, so ask him to watch it once before posting or submitting.

---

## The three options

When he asks for options, make them genuinely different in **approach**, not just in stickers. For example:

- clean versus punchy versus story-list;
- or, for social media, punchy versus cinematic versus trend mix.

Score each option for *that* audience using the rubric in `ENGAGEMENT.md`, recommend one, and let him pick.

## Lessons log

Add one line for every mistake Arivu catches, and turn it into a rule or a QA check above.

- **2026-11-01 · The voice was lower than the music and effects** (assignment video). Peak-normalising let the Drop and impact sounds set the level, and music sat only 5 dB under the voice. Now the mix is dialogue-first, with a QA rule that the voice leads by at least 12 dB, plus `--remix`.
- **2026-11-01 · Misheard names in captions** (Aviv Maju, Matos, NITEL). Now there's `asr_fixes` in brand.json and a fix-the-transcript step before planning.
- **2026-11-01 · Punch-ins cut the top of his head** on a tight webcam shot. Now the crop keeps headroom and zooms stay ≤ 1.15 on webcam footage.
- **2026-11-01 · His head hid the Drop word.** It now comes to the front automatically when more than 22% of it would be covered.
- **2026-11-01 · Pack effects crowded a landscape webcam shot.** They're now only used after checking frames; use our stickers instead.
- **2026-11-01 · 720 p landscape cropped to vertical was blurry** (2.7× upscale). Now the fit layout and the reframe QA check (≤ 1.6×) handle it.
- **2026-11-01 · 9.4 s with no visual change** in the assignment edit. Now the pacing QA check flags it.
- **2026-11-02 · Tamil speech came out as broken English** (first Reel). Parakeet is English-only and huggingface.co's model CDN was blocked. Fix: download `sherpa-onnx-whisper-large-v3` from the k2-fsa/sherpa-onnx GitHub `asr-models` release, run it per phrase with `language="ta"` and again with `"en"` (gives the meaning), keep Parakeet's word timings, and caption in Tanglish (Inter has no Tamil glyphs). Always show him the caption lines to confirm before the final render.
- **2026-11-02 · QA pacing counted the end card as a still stretch.** Put a sticker on the last lines (e.g. STAY TUNED) so the CTA shot isn't flagged.
