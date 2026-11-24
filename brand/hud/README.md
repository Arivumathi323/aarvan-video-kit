# Aarvan Hologram HUD inserts

Code-drawn cutaways for talking-head videos: a wireframe object is scanned in, target boxes lock onto its parts, and a value rolls in. Ice-blue lines on near-black; **Aarvan orange `#FF741A` only on a value at the frame it locks**. Silent (the voice runs underneath in the edit). Keep all HUD text above ~62% of the frame height so the reel captions stay clear.

- `main.js` – the two example inserts (`?insert=1` automation hub, `?insert=2` Aarvan Labs feed). Copy one and change the labels/timings to the words in the video.
- `models/gen_models.mjs` – builds `hub.json` and `phone.json` with `mkmodel.mjs` primitives (`node gen_models.mjs`).
- Render: `aarvan hud <this folder> out.mp4 --insert 1 --size 1080x1920`.

First used on 2026-11-24 (intro reel test): "business automation and AI agents" and "Aarvan Labs … AI agents, updates, news, daily posts".

Credits: `engine/holo.js`, `engine/hud.js` and `models/mkmodel.mjs` come from the Sci-fi Hologram HUD demo in **Lemo-Opuscar by Lemomo (LemoLab)**, https://github.com/lemomo-ai/lemo-opuscar, code under the MIT licence. Fonts: Rajdhani and Share Tech Mono (SIL OFL 1.1, `fonts/`).
