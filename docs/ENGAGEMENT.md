# How the edit director scores an edit

The director proposes **3 edit options** for every raw video and scores each one out of 100 on this rubric. The scores are a reasoned estimate from proven short-form video patterns, not a prediction from platform data. Once real results exist in `docs/PERFORMANCE.md`, they override these defaults.

## Brand rules (every option must pass these, or it isn't offered)

1. **One Aarvan Drop**, on the single most important word: the payoff, the promise, or the surprising claim.
2. **At most 2 fresh effects** from the effects pack, on top of the signature. More than 3 big moments reads as a template.
3. **Captions always on**, in the brand style.
4. **Nothing covers the face.**
5. **Intro card and end card** for long-form or channel-intro videos. For Reels or Shorts under 45 s, skip the intro card: the hook *is* the intro.
6. Brand voice (Kokoro am_fenrir 1.05) only when the clip has no usable audio.
7. **Dialogue first.** The voice is levelled to -18 dBFS speech RMS. Music sits 20 dB under it while he speaks and 9 dB under in pauses, and effects peak well below the voice. The render's `Audio check` must show the voice leading the background by at least 12 dB. (Lesson from 1 Nov 2026: the voice came out lower than the music.)

## Scoring (100 points)

| Points | What | How to judge it |
|---|---|---|
| 25 | **Hook (first 2 s)** | Does the opening line or visual create a question or tension? Is something moving in second one? Starting cold on a strong line beats an intro card. |
| 20 | **Pace / pattern interrupts** | Something changes every 3–4 s: a cut, punch-in, sticker or effect. More than 6 s with nothing changing loses points, and so do back-to-back big effects. |
| 15 | **Payoff placement** | The Drop and the strongest effect land on the strongest lines, not on filler. |
| 15 | **Clarity** | Captions are readable, the speaker stays the focus, and no graphics compete with each other. |
| 10 | **Freshness** | The fresh effects haven't been used in the last 3 videos (check `docs/PERFORMANCE.md`). |
| 10 | **Retention ending** | It ends fast after the last point, with a clear CTA or loop. Dead air at the end loses points. |
| 5 | **Format fit** | Vertical 9:16 for Reels and Shorts, 16:9 for YouTube long-form. |

## The three options: make them genuinely different

- **A · Punchy:** fast cuts, a punch-in every sentence, stickers on key nouns, the Drop on the biggest claim, plus 1 high-energy effect (lean-in, reject-stamp, countdown-flip, comment-box). Music: punchy, 116–124 bpm.
- **B · Cinematic story:** fewer cuts, slow-push and spotlight or led-sign moments, the Drop on the emotional line, and title lines for the key sentence. Music: cinematic.
- **C · Trend mix:** built around 1–2 currently popular pack effects that suit the content (checklist or todo for steps, liquid-glass-graph for numbers, messages for client stories, glass-widgets for tech), plus the Drop. Music: punchy or chill.

For each option show: the name, the score with a one-line breakdown, where the Drop lands (quote the line), the fresh effects and where they land, the length, and a preview sheet.

## Learning loop

After a video is posted for 7 days, add a row to `docs/PERFORMANCE.md`:

| date | video | option | effects used | views | avg watch % | likes | shares | saves | notes |

Once there are 5 or more rows, weight the rubric toward what has actually worked. If one effect keeps lifting average watch percentage, favour it, and retire anything that keeps underperforming. If the YouTube connector is available, pull the numbers from it instead of asking.
