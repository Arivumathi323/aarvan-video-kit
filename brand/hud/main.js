// Two silent Hologram HUD inserts for Arivu's intro reel. ?insert=1 (1080x1920, 3.0 s) or ?insert=2 (1080x1080, 4.5 s).
// Times are relative to the insert start and follow his spoken words (his voice runs underneath in the reel).
// Hue: pale ice; accent: Aarvan orange #FF741A, spent only on values at the frame they lock.
import { Holo, loadModel, drawPad, drawScanPlane } from './engine/holo.js';
import * as U from './engine/hud.js';

const Q = new URLSearchParams(location.search), N = Q.get('insert') || '1';
const W = innerWidth, H = innerHeight, FPS = 24;
const cv = document.getElementById('c'); cv.width = W; cv.height = H;
const ctx = cv.getContext('2d');
const T = U.theme(204, 24);
T.acc = a => `rgba(255,116,26,${a})`;                    // the brand orange, exact
const holo = new Holo(W, H);
const clamp = U.clamp, seg = (t, a, b) => clamp((t - a) / (b - a)), lerp = (a, b, k) => a + (b - a) * k;
const eo = k => 1 - Math.pow(1 - clamp(k), 3), eio = k => { k = clamp(k); return k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; };
const ss = k => { k = clamp(k); return k * k * (3 - 2 * k); };
const fr = t => Math.floor(t * FPS);
const flashAt = (t, t0) => t >= t0 && t < t0 + 3 / FPS;     // 3-frame white flash on a lock

const [hub, phone] = await Promise.all([loadModel('models/hub.json', { diag: 1.75 }), loadModel('models/phone.json', { diag: 1.8 })]);
await document.fonts.load(`600 40px ${U.FONT.ui}`); await document.fonts.load(`300 120px ${U.FONT.ui}`);
await document.fonts.load(`500 30px ${U.FONT.ui}`); await document.fonts.load(`20px ${U.FONT.mono}`);
await document.fonts.ready;

function textPlate(x, y, w, h, a) { U.plate(ctx, T, x, y, w, h, a); }
let TX = [];                                             // text boxes on screen this frame (readcheck)

// ======================= insert 1: the automation hub =======================
const DUR1 = 3.25, IN_T = [0.38, 0.5, 0.62], LOCK = 1.3, OPEN = [1.15, 1.6], LEAD = [1.3, 1.55], CARD = 1.42, ROLL = [1.8, 2.05];
const LABELS1 = ['MSG', 'MAIL', 'FORM'];
function frame1(t) {
  const cam = { target: [0, 0.4, 0], yaw: lerp(0.24, 0.4, ss(t / DUR1)), pitch: 0.42, dist: 5.4, fov: 0.6, cx: W / 2, cy: 660 };
  U.background(ctx, W, H, T, { cx: W / 2, cy: 680, px: -cam.yaw * 220 });
  drawPad(ctx, cam, W, H, { hue: T.hue, rot: t * 0.25, alpha: 0.9 });
  const sy = hub.ymax * 1.08 * eio(seg(t, 0.05, 0.7)), scanning = t < 0.72;
  const flash = {}; LABELS1.forEach((_, i) => { if (t > IN_T[i] && t < IN_T[i] + 0.12) flash['in' + i] = 1; });
  if (flashAt(t, LOCK)) flash.core = 1;
  const info = holo.draw(ctx, hub, cam, { hue: T.hue, scan: scanning ? { y: sy } : null, explode: { core: eo(seg(t, OPEN[0], OPEN[1])) }, flash, focus: t > LOCK ? 'core' : null, dim: 0.55 });
  if (scanning) drawScanPlane(ctx, cam, W, H, sy, { hue: T.hue, r: 1.0, rot: t, alpha: 1 - seg(t, 0.62, 0.72) });
  // input markers: each port is pinged as its input arrives
  LABELS1.forEach((lab, i) => {
    const a = seg(t, IN_T[i] - 0.06, IN_T[i] + 0.06), p = info.anchor['in' + i];
    if (a > 0 && p) {
      ctx.save(); ctx.translate(p[0], p[1]); ctx.scale(1.55, 1.55);
      U.marker(ctx, T, [0, 0], lab, a, clamp((t - IN_T[i]) / 0.5), i === 0 ? -1 : 1);
      ctx.restore();
      TX.push({ id: 'm' + i, text: lab, x0: p[0] - 150, y0: p[1] - 24, x1: p[0] + 150, y1: p[1] + 24 });
    }
  });
  // lock onto the agent core
  // the box hugs the core itself (the engine's part box skips internal pieces), from its vertices on screen
  let bb = null; { const V = hub.byId.core.pieces.find(c => c.id === 'core').v, q = new Float32Array(3); let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (let i = 0; i < V.length; i += 3) { info.project(V[i], V[i + 1], V[i + 2], q); x0 = Math.min(x0, q[0]); y0 = Math.min(y0, q[1]); x1 = Math.max(x1, q[0]); y1 = Math.max(y1, q[1]); }
    bb = [x0, y0, x1, y1]; }
  if (bb && t > LOCK - 0.22) U.targetBox(ctx, T, bb, seg(t, LOCK - 0.22, LOCK), { flash: flashAt(t, LOCK), tag: 'TGT 01 · LOCK', pad: 18 });
  // leader to the card, the card rolls its value to DONE
  const cx = 300, cy = 1000, cw = 480;
  const anc = info.anchor.core;
  if (anc) U.leader(ctx, T, [anc[0], anc[1]], [anc[0] - 60, cy - 60], [cx + cw * 0.5, cy - 60], seg(t, LEAD[0], LEAD[1]), { pulse: clamp((t - LEAD[1]) / 0.6) % 1 });
  if (t > CARD) {
    U.specCard(ctx, T, cx, cy, { label: 'AI AGENT', value: 'DONE' }, { reveal: seg(t, CARD, CARD + 0.25), roll: seg(t, ROLL[0], ROLL[1]), detail: 0, frame: fr(t), flash: flashAt(t, ROLL[1]) }, { w: cw, big: 150, index: '01' });
    TX.push({ id: 'card', text: 'AI AGENT DONE', x0: cx, y0: cy, x1: cx + cw, y1: cy + 200 });
  }
  U.chrome(ctx, W, H, T, { tl: 'AUTOMATION // LIVE', tr: t < ROLL[1] ? 'AGENT · RUNNING' : 'AGENT · TASK DONE', px: cam.yaw * 200, alpha: 0.9 });
}

// ======================= insert 2: the Aarvan Labs page =======================
const DUR2 = 5.2, LK = [1.1, 2.55, 3.05], CHIPS = ['AI AGENTS', 'AI UPDATES', 'AI NEWS'], DCARD = 3.3, DROLL = [3.38, 3.65];
// portrait (full screen in the reel): the same layout moved down 140 px, everything above the caption band (62 % of height)
const OY = H > W ? 140 : 0, DIST2 = H > W ? 5.2 * H / W : 5.2;
function frame2(t) {
  const cam = { target: [0, phone.ymax * 0.48, 0], yaw: lerp(0.42, 0.3, ss(t / DUR2)), pitch: 0.12, dist: DIST2, fov: 0.6, cx: 265, cy: 600 + OY };
  U.background(ctx, W, H, T, { cx: 275, cy: 620 + OY, px: -cam.yaw * 200 });
  drawPad(ctx, cam, W, H, { hue: T.hue, rot: t * 0.25, alpha: 0.85 });
  const sy = phone.ymax * 1.05 * eio(seg(t, 0.05, 0.65)), scanning = t < 0.67;
  // which card is open: the newest locked one; it closes fast when the next opens
  const ex = {}; LK.forEach((L, i) => { const next = LK[i + 1] ?? 99; ex['c' + i] = eo(seg(t, L - 0.05, L + 0.3)) * (1 - seg(t, next - 0.2, next)); });
  const flash = {}; LK.forEach((L, i) => { if (flashAt(t, L)) flash['c' + i] = 1; });
  const cur = LK.reduce((k, L, i) => (t > L - 0.25 ? i : k), -1);
  const info = holo.draw(ctx, phone, cam, { hue: T.hue, scan: scanning ? { y: sy } : null, explode: ex, flash, focus: cur >= 0 && t < LK[cur] + 0.6 ? 'c' + cur : null, dim: 0.6 });
  if (scanning) drawScanPlane(ctx, cam, W, H, sy, { hue: T.hue, r: 0.9, rot: t, alpha: 1 - seg(t, 0.57, 0.67) });
  // the page name rolls in like a value
  {
    const a = seg(t, 0.05, 0.2), k = seg(t, 0.1, 0.62);
    if (a > 0) {
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.letterSpacing = '10px';
      ctx.font = `600 78px ${U.FONT.ui}`; ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = T.hi(0.95 * a); ctx.fillText(U.rollText('AARVAN LABS', k, fr(t), 5), W / 2, 150 + OY);
      ctx.letterSpacing = '0px'; ctx.font = `22px ${U.FONT.mono}`; ctx.fillStyle = T.dim(0.9 * a); ctx.fillText('PAGE // DAILY FEED', W / 2, 190 + OY);
      ctx.restore();
      TX.push({ id: 'title', text: 'AARVAN LABS', x0: 250, y0: 85 + OY, x1: 830, y1: 160 + OY });
    }
  }
  // target box on the current card, leader to its chip in the rail
  const RX = 545, RY = [300 + OY, 420 + OY, 540 + OY], RW = 380;
  LK.forEach((L, i) => {
    const bb = info.bbox['c' + i], anc = info.anchor['c' + i];
    if (bb && t > L - 0.22 && t < (LK[i + 1] ?? 99) - 0.15) U.targetBox(ctx, T, bb, seg(t, L - 0.22, L), { flash: flashAt(t, L), pad: 14 });
    if (anc && t > L) U.leader(ctx, T, [anc[0], anc[1]], [anc[0] + 70, RY[i] + 26], [RX - 18, RY[i] + 26], seg(t, L, L + 0.25), { alpha: 1 - seg(t, L + 0.9, L + 1.3) * 0.6 });
    const ra = seg(t, L + 0.15, L + 0.35);
    if (ra > 0) {
      textPlate(RX - 16, RY[i] - 8, RW + 32, 76, ra);
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      ctx.font = `20px ${U.FONT.mono}`; ctx.fillStyle = T.dim(0.95 * ra); ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
      ctx.fillText('0' + (i + 1), RX, RY[i] + 42);
      ctx.letterSpacing = '4px'; ctx.font = `600 48px ${U.FONT.ui}`; ctx.fillStyle = T.hi(0.96 * ra);
      ctx.fillText(U.rollText(CHIPS[i], seg(t, L + 0.15, L + 0.5), fr(t), 9 + i), RX + 46, RY[i] + 50);
      ctx.restore();
      TX.push({ id: 'chip' + i, text: CHIPS[i], x0: RX, y0: RY[i], x1: RX + RW, y1: RY[i] + 60 });
    }
  });
  if (t > DCARD) {
    U.specCard(ctx, T, RX, 700 + OY, { label: 'POSTS', value: 'DAILY' }, { reveal: seg(t, DCARD, DCARD + 0.2), roll: seg(t, DROLL[0], DROLL[1]), detail: 0, frame: fr(t), flash: flashAt(t, DROLL[1]) }, { w: RW, big: 120, index: '04' });
    TX.push({ id: 'daily', text: 'POSTS DAILY', x0: RX, y0: 700 + OY, x1: RX + RW, y1: 860 + OY });
  }
  U.chrome(ctx, W, H, T, { tl: 'FEED // SCAN', tr: t < DROLL[1] ? 'SYNCING' : 'LIVE', px: cam.yaw * 200, alpha: 0.85 });
}

window.DUR = N === '1' ? DUR1 : DUR2;
window.render = t => {
  TX = [];
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1; ctx.filter = 'none';
  (N === '1' ? frame1 : frame2)(t);
  U.vignette(ctx, W, H, 0.55);
};
window.TEXTS = t => { window.render(t); return TX; };
window.EV = [];
window.READY = true;
