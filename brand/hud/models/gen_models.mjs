// Two wireframe models for Arivu's reel. node gen_models.mjs → hub.json, phone.json
// Metres, y up, x = front/right, z = towards the viewer.
import { Model } from './mkmodel.mjs';
import { writeFileSync } from 'fs';
const here = new URL('.', import.meta.url).pathname;

// ---------- 1. automation hub: base unit, a lid that slides up, an AI core inside, three input ports ----------
{
  const M = new Model('AUTOMATION HUB');
  const BW = 1.2, BH = 0.34, BD = 0.72;
  M.part('hub', { anchor: [0, BH, 0] });
  M.piece('base');
  M.box([0, BH / 2, 0], [BW, BH, BD]);
  M.box([0, 0.02, 0], [BW + 0.04, 0.04, BD + 0.04]);                          // plinth
  for (let i = 0; i < 5; i++) M.box([-0.18 + i * 0.09, 0.07, BD / 2 + 0.005], [0.05, 0.02, 0.01]);       // status LEDs
  for (const x of [-0.56, 0.56]) M.box([x, BH * 0.5, BD / 2 + 0.005], [0.04, 0.2, 0.01]);                  // corner vents
  // the AI core part: the lid on top slides straight up (its own axis) and opens the core inside, which glows hot
  M.part('core', { anchor: [0, BH - 0.02, -0.06], center: [0, BH * 0.6, -0.06] });
  M.piece('lid', { explode: [0, 0.36, 0] });
  M.box([0, BH + 0.05, -0.06], [0.78, 0.1, 0.48]);
  M.box([0, BH + 0.105, -0.06], [0.6, 0.01, 0.34]);
  // the AI core inside the base: a stacked module with rings, hot while open
  M.piece('core', { internal: true, hot: true });
  M.box([0, BH * 0.45, -0.06], [0.42, 0.22, 0.3]);
  M.box([0, BH * 0.62, -0.06], [0.3, 0.1, 0.22]);
  M.ring([0, BH - 0.01, -0.06], [0, 1, 0], 0.13, 24);
  M.ring([0, BH - 0.01, -0.06], [0, 1, 0], 0.08, 18);
  // three input ports on the front face, each a short socket pointing at the viewer (they stay when the lid opens)
  [-0.38, 0, 0.38].forEach((x, i) => {
    const y = BH * 0.56, z0 = BD / 2;
    M.part('in' + i, { anchor: [x, y, z0 + 0.13] });
    M.piece('port' + i);
    M.box([x, y, z0 + 0.008], [0.2, 0.16, 0.016]);                            // mount plate on the front face
    M.tube([x, y, z0 + 0.016], [x, y, z0 + 0.13], 0.05, { rings: 4, seg: 14, longs: 7 });
    M.ring([x, y, z0 + 0.13], [0, 0, 1], 0.03, 12);
  });
  writeFileSync(here + 'hub.json', JSON.stringify(M.toJSON()));
}

// ---------- 2. phone: standing on the pad, three feed cards on its screen ----------
{
  const M = new Model('PHONE');
  const W = 0.74, H = 1.5, D = 0.08, y0 = 0.06;
  M.part('phone', { anchor: [0, y0 + H, 0] });
  M.piece('body');
  M.box([0, y0 + H / 2, 0], [W, H, D]);
  M.box([0, y0 + H / 2, D / 2 + 0.003], [W - 0.08, H - 0.12, 0.006]);       // screen glass
  M.box([0, y0 + H - 0.05, D / 2 + 0.008], [0.18, 0.03, 0.006]);            // speaker slot
  M.ring([0.24, y0 + H - 0.05, D / 2 + 0.008], [0, 0, 1], 0.02, 12);        // camera
  M.box([0, 0.03, 0], [0.5, 0.06, 0.3]);                                    // stand foot
  M.box([0, y0 + H - 0.2, D / 2 + 0.01], [W - 0.16, 0.12, 0.006]);          // page header
  // feed cards on the screen; each slides out towards the viewer when locked
  [0.95, 0.62, 0.29].forEach((cy, i) => {
    M.part('c' + i, { anchor: [-0.12, y0 + cy, D / 2 + 0.02] });
    M.piece('card' + i, { explode: [0, 0, 0.22] });
    M.box([0, y0 + cy, D / 2 + 0.012], [W - 0.16, 0.26, 0.012]);
    M.box([-0.17, y0 + cy, D / 2 + 0.02], [0.18, 0.16, 0.006]);              // thumbnail
    M.box([0.09, y0 + cy + 0.05, D / 2 + 0.02], [0.24, 0.025, 0.006]);       // headline line
    M.box([0.06, y0 + cy, D / 2 + 0.02], [0.18, 0.02, 0.006]);
    M.box([0.04, y0 + cy - 0.05, D / 2 + 0.02], [0.14, 0.02, 0.006]);
  });
  writeFileSync(here + 'phone.json', JSON.stringify(M.toJSON()));
}
