# Effects pack: when to use what

These come from the vendored [claude-video-effects](https://github.com/Vibha-Ramprakash/claude-video-effects) pack (51 effects). You put them in a plan's `effects` list with **source** times, and they render first, before the Aarvan edit goes on top. Every option is listed in `vendor/claude-video-effects/SKILL.md`.

Keep each effect short (1.5–4 s), and use at most 2 per video plus the Aarvan Drop. Set `"color": "#FF741A"` where an effect has a colour, so it stays on-brand.

| Content moment | Good effects |
|---|---|
| Hook / first line | `lean-in`, `locked-on`, `countdown-flip`, `dot-reveal`, `pause-point` |
| Name / brand reveal | `spotlight` (text = brand), `glitter-spotlight`, `led-sign`, `cover-star` |
| Steps, process, "how I built it" | `checklist`, `todo`, `apple-toggles`, `lineup` |
| Numbers, growth, results | `liquid-glass-graph` (and `look=bento`), `over-the-shoulder-zoom`, `profile-wall` |
| Client / DM / feedback stories | `messages`, `comment-box`, `tap` |
| "Don't do this", myths, "no X" | `huge-strike` (giant word crossed out, great for "no laptop"), `reject-stamp`, `uninstall`, `scribble` |
| One key word, hand-made feel | `crayon-write` (red crayon word behind the head, then underlined) |
| Label a fact about you | `tape-label` (yellow tape strip with your line on your chest; keep it under the face) |
| A number that matters | `select-resize` (selection box grabs the number and drags it bigger) |
| "I cut the boring parts" / editing reels | `wave-trim` (the silent parts of your voice waveform get trimmed on screen) |
| Your work portfolio (needs images) | `fan-build` (reel covers deal into a fan behind your head) |
| Tech / AI / tools | `glass-widgets`, `shortcut-rain`, `timeline`, `the-bill` |
| Emotional or big line | `slow-push`, `spotlight`, `red-collage` |
| Before / after | `swipe`, `moody` |
| Your work or portfolio (needs screenshots in `images`) | `orbit`, `carousel-spin`, `phone-fan`, `noise`, `place-in-grid`, `broll-split` |

**Don't use** `backdrop-word`, `huge-strike` or `crayon-write` within 4 s of the Aarvan Drop: they're the same kind of move (a word behind the head), and the Drop must stay special. The Drop is our own version of that move.

## Notes

- Camera effects (`locked-on`, `lean-in`, `slow-push`, `spotlight` push) change the framing. Keep that shot's `zoom` at 1.0 so the two zooms don't stack.
- The pack is designed for vertical phone videos with the face in frame. On landscape clips, check frames before rendering.
- The pack adds no audio. Our renderer adds the sound design on top.
