"""Aarvan Labs video renderer. Turns a raw talking-head clip + an edit plan (JSON) into a finished video.

usage:
  python render.py plan.json                      full render -> plan["output"]
  python render.py plan.json --draft              720p, faster, for checking
  python render.py plan.json --still 3.5,12,20    check frames (output seconds) -> <output>_check_<t>.jpg
  python render.py plan.json --sheet 8            8-frame contact sheet of the edit -> <output>_sheet.jpg
  python render.py plan.json --timeline           print the output timeline only

All times in the plan are SOURCE seconds (times in the raw video), or word anchors {"word": "build", "n": 0}.
See README.md for the plan format.
"""
import argparse, json, os, re, subprocess, sys, math, hashlib, shutil
import numpy as np, cv2, soundfile as sf
from PIL import Image
from scipy.signal import resample_poly, butter, sosfilt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
from track import read_frames, face_track, masks_for

FPS = 30


# ====================================================================== plan + timeline
class Edit:
    def __init__(self, plan, plan_dir, short=None):
        self.p = plan; self.dir = plan_dir
        P = lambda x: x if os.path.isabs(x) else os.path.normpath(os.path.join(plan_dir, x))
        self.src = P(plan['source']); self.out = P(plan.get('output', os.path.splitext(self.src)[0] + '_aarvan.mp4'))
        self.work = os.path.splitext(self.out)[0] + '_work'; os.makedirs(self.work, exist_ok=True)
        self.info = probe(self.src)
        ar = plan.get('aspect', 'source')
        sw, sh = self.info['w'], self.info['h']
        if ar == '9:16': self.AR = 9 / 16
        elif ar == '16:9': self.AR = 16 / 9
        elif ar == '1:1': self.AR = 1.0
        else:
            self.AR = sw / sh
            for std in (16 / 9, 9 / 16, 1.0, 4 / 5):  # snap near-standard shapes
                if abs(self.AR - std) / std < 0.03: self.AR = std
        short = short or plan.get('size', 1080)
        if self.AR >= 1: self.H = short; self.W = int(round(short * self.AR / 2)) * 2
        else: self.W = short; self.H = int(round(short / self.AR / 2)) * 2
        self.u = min(self.W, self.H) / 720.0
        self.vertical = self.H > self.W
        self.T = plan.get('transition', {}).get('dur', 0.3)
        self.audio_mode = plan.get('audio', 'source' if self.info['audio'] else 'voiceover')
        self.segs = [dict(s) for s in plan['segments']]
        # ---- intro
        it = plan.get('intro', False)
        self.intro = None
        if it:
            d = dict(BRAND['intro']); d.update(it if isinstance(it, dict) else {})
            d.setdefault('dur', 1.7); self.intro = d
        # ---- lay segments on the output timeline
        # per-shot transition INTO the shot: "trans": 0.6 or {"dur": 0.6, "style": "whip"|"zoom"}; default = plan transition
        for s in self.segs:
            tr = s.get('trans')
            s['T'] = float(tr.get('dur', self.T)) if isinstance(tr, dict) else (float(tr) if isinstance(tr, (int, float)) else self.T)
            s['tstyle'] = tr.get('style', 'zoom') if isinstance(tr, dict) else 'zoom'
        t = (self.intro['dur'] - self.segs[0]['T']) if self.intro else 0.0
        for k, s in enumerate(self.segs):
            s['dur'] = s['out'] - s['in']; s['start'] = t; t += s['dur'] - self.Tnext(k)
            s.setdefault('zoom', 1.0)
        self.seg_end = self.segs[-1]['start'] + self.segs[-1]['dur']
        # ---- words (captions + anchors)
        self.words = self._words()
        # ---- end card
        ec = plan.get('end_card', False); self.end = None
        if ec:
            d = dict(BRAND['end_card']); d.update(ec if isinstance(ec, dict) else {})
            d.setdefault('dur', 3.0)
            at = d.get('at')
            last = self.words[-1]['t1'] + 0.25 if self.words else 0
            d['start'] = self.anchor(at) if at is not None else max(self.seg_end - 0.35, last)
            self.end = d
        self.TOTAL = max(self.seg_end, (self.end['start'] + self.end['dur']) if self.end else 0)
        # ---- signature
        sg = plan.get('signature'); self.sig = None
        if sg:
            self.sig = dict(sg); self.sig['t_out'] = self.anchor(sg.get('at', sg.get('t')))
            self.sig.setdefault('dur', 2.4); self.sig.setdefault('text', 'BUILD')
            self.sig['t_src'] = self.out_to_src(self.sig['t_out'])

    def Tnext(self, k):
        return self.segs[k + 1]['T'] if k + 1 < len(self.segs) else self.T

    # ---- time mapping
    def src_to_out(self, ts):
        for s in self.segs:
            if s['in'] - 1e-6 <= ts <= s['out'] + 1e-6: return s['start'] + ts - s['in']
        return None

    def out_to_src(self, t):
        s = self.seg_at(t)
        return s['in'] + min(max(t - s['start'], 0), s['dur'] - 1 / FPS) if s else None

    def seg_at(self, t):
        act = [s for s in self.segs if s['start'] <= t < s['start'] + s['dur']]
        return act[-1] if act else (self.segs[-1] if t >= self.seg_end else None)

    def anchor(self, a):
        """Resolve a plan time: number (source s), {"word": w, "n": k}, {"out": t} -> output seconds."""
        if a is None: return None
        if isinstance(a, (int, float)):
            o = self.src_to_out(float(a))
            if o is None: raise SystemExit(f'time {a}s is not inside any segment')
            return o
        if 'out' in a: return float(a['out'])
        w = a['word'].lower().strip(".,!?'\""); n = a.get('n', 0)
        hits = [x for x in self.words if x['w'].lower().strip(".,!?'\"") == w]
        if len(hits) <= n: raise SystemExit(f'word "{a["word"]}" (#{n}) not found in the kept speech')
        return hits[n]['t0'] + a.get('offset', 0.0)

    def until(self, a, t0):
        if a is None or a == 'segment_end':
            s = self.seg_at(t0 + 1e-3); return s['start'] + s['dur'] - self.Tnext(self.segs.index(s))
        return self.anchor(a)

    # ---- words
    def _words(self):
        out = []
        if self.audio_mode == 'source':
            an = self.p.get('analysis')
            if not an: return out
            an = json.load(open(an if os.path.isabs(an) else os.path.join(self.dir, an)))
            for k, s in enumerate(self.segs):
                a0, a1 = self.audible(k)
                for w in an['words']:
                    mid = (w['s'] + w['e']) / 2
                    if a0 <= mid < a1:
                        out.append({'w': w['w'], 'seg': k, 'skip': w.get('skip', False), 't0': s['start'] + w['s'] - s['in'], 't1': s['start'] + w['e'] - s['in']})
        else:
            vo = self.p.get('voiceover', {})
            vdir = vo.get('dir') if isinstance(vo, dict) else vo
            if not vdir: return out
            vdir = vdir if os.path.isabs(vdir) else os.path.join(self.dir, vdir)
            lines = json.load(open(os.path.join(vdir, 'lines.json')))
            self.vo_lines = []
            for k, s in enumerate(self.segs):
                li = s.get('vo', k if k < len(lines) else None)
                if li is None: continue
                L = lines[li]; f = L['file'] if os.path.isabs(L['file']) else os.path.join(vdir, os.path.basename(L['file']))
                t0 = s['start'] + (0.04 if k == 0 else 0.12) + s.get('vo_offset', 0)
                self.vo_lines.append((f, t0))
                out += vo_word_times(L['text'], f, t0, k)
        return out

    def audible(self, k):
        """Source window of segment k whose audio is used (cut happens mid-transition)."""
        s = self.segs[k]
        a0 = s['in'] + (s['T'] / 2 if (k > 0) else 0); a1 = s['out'] - (self.Tnext(k) / 2 if k < len(self.segs) - 1 else 0)
        return a0, a1


def vo_word_times(text, wav, t0, seg):
    a, sr = sf.read(wav); a = np.abs(a if a.ndim == 1 else a.mean(1)); hop = int(sr * .01)
    e = np.array([a[i:i + hop].max() for i in range(0, len(a), hop)]); on = e > 0.02
    gaps, run = [], 0
    for k, v in enumerate(on):
        if not v: run += 1
        else:
            if run >= 9 and k - run > 0: gaps.append(((k - run) * .01, k * .01))
            run = 0
    last = (np.where(on)[0][-1] + 1) * .01 if on.any() else len(a) / sr
    ws = text.split(); phr, cur = [], []
    for w in ws:
        cur.append(w)
        if re.search(r'[,.!?]$', w): phr.append(cur); cur = []
    if cur: phr.append(cur)
    need = len(phr) - 1; gg = sorted(sorted(gaps, key=lambda g: g[0] - g[1])[:need])
    out = []
    for p, ph in enumerate(phr):
        if len(gg) == need:
            st = 0 if p == 0 else gg[p - 1][1]; en = last if p == len(phr) - 1 else gg[p][0]
        else:
            tot = sum(len(w) for w in ws); bef = sum(len(w) for q in phr[:p] for w in q)
            st = bef / tot * last; en = (bef + sum(len(w) for w in ph)) / tot * last
        wt = [len(re.sub(r'\W', '', w)) + 1.5 for w in ph]; c = st
        for w, x in zip(ph, wt):
            d = (en - st) * x / sum(wt); out.append({'w': w, 'seg': seg, 't0': t0 + c, 't1': t0 + c + d}); c += d
    return out


# ====================================================================== footage
class Footage:
    def __init__(self, E, path):
        self.E = E; self.path = path; self.info = probe(path)
        sw, sh = self.info['w'], self.info['h']
        lim = 1920 / max(sw, sh)
        self.SW, self.SH = (sw, sh) if lim >= 1 else (int(sw * lim) // 2 * 2, int(sh * lim) // 2 * 2)
        self.readers = {}

    def frame(self, key, ts):
        """RGB frame (SW x SH) at source time ts. key: reader id (segment index)."""
        r = self.readers.get(key)
        idx = int(round(ts * FPS))
        if r is None or r['idx'] > idx or idx - r['idx'] > FPS * 2:
            if r: r['gen'].close()
            g = read_frames(self.path, self.SW, self.SH, start=idx / FPS, fps=FPS)
            r = {'gen': g, 'idx': idx - 1, 'fr': None}; self.readers[key] = r
        while r['idx'] < idx:
            try: _, f = next(r['gen']); r['fr'] = f; r['idx'] += 1
            except StopIteration: r['idx'] = idx; break
        if r['fr'] is None: r['fr'] = np.zeros((self.SH, self.SW, 3), np.uint8)
        return r['fr']

    def close(self, keep):
        for k in list(self.readers):
            if k not in keep: self.readers[k]['gen'].close(); del self.readers[k]


# ====================================================================== renderer
class Renderer:
    def __init__(self, E, still=False):
        self.E = E; W, H, u = E.W, E.H, E.u
        self.spr = {}
        footage = E.src
        if E.p.get('effects'):
            footage = self.effects_pass()
        self.F = Footage(E, footage)
        ranges = [(s['in'], s['out']) for s in E.segs]
        print('Tracking your face...', flush=True)
        self.face = face_track(footage, self.F.info, ranges)
        self.masks = {}
        if E.sig:
            print('Cutting you out for the Aarvan Drop...', flush=True)
            a = max(0, E.sig['t_src'] - 0.6)
            s = E.seg_at(E.sig['t_out']); b = min(s['out'], E.sig['t_src'] + E.sig['dur'] + 0.2)
            self.masks = masks_for(footage, self.F.info, [(a, b)])
            self.mask_fps = self.F.info['fps']
        self.chunks = self.make_chunks()

    # ---------- repo effects (vendored claude-video-effects) ----------
    def effects_pass(self):
        E = self.E; fx = os.path.join(ROOT, 'vendor', 'claude-video-effects', 'scripts', 'fx.py')
        effs = E.p['effects']
        key = hashlib.md5((json.dumps(effs, sort_keys=True) + E.src).encode()).hexdigest()[:10]
        out = os.path.join(E.work, f'fx_{key}.mp4')
        if os.path.exists(out): return out
        plan = os.path.join(E.work, f'fx_{key}.json'); json.dump({'effects': effs}, open(plan, 'w'), indent=1)
        short = min(1080, min(E.info['w'], E.info['h']))
        py = os.path.join(ROOT, 'vendor', 'claude-video-effects', '.venv', 'bin', 'python')
        py = py if os.path.exists(py) else sys.executable
        print('Effects pass:', ', '.join(e['fx'] for e in effs), flush=True)
        r = subprocess.run([py, fx, '--plan', plan, E.src, out + '.tmp.mp4', '--width', str(short)], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out + '.tmp.mp4'):
            print(r.stdout[-2000:], r.stderr[-2000:]); raise SystemExit('effects pass failed')
        os.replace(out + '.tmp.mp4', out)
        return out

    def S(self, key, fn):
        if key not in self.spr: self.spr[key] = fn()
        return self.spr[key]

    # ---------- camera ----------
    def crop_M(self, ts, zoom):
        """Affine matrix mapping footage (SW x SH) -> output (W x H), centred on the face."""
        E, F = self.E, self.F
        SW, SH, W, H = F.SW, F.SH, E.W, E.H
        base_w = min(SW, SH * E.AR); base_h = base_w / E.AR
        cw, ch = base_w / zoom, base_h / zoom
        fx_, fy_, fw_ = self.face(ts)
        cx = fx_ * SW; cy = fy_ * SH + ch * 0.12  # keep the face in the upper third
        x0 = min(max(cx - cw / 2, 0), SW - cw); y0 = min(max(cy - ch / 2, 0), SH - ch)
        head_top = fy_ * SH - 1.05 * fw_ * SW          # hair line is ~1 face-width above the face centre
        y0 = max(0.0, min(y0, head_top - 0.04 * ch))    # keep a little headroom (tight webcam shots)
        return np.array([[W / cw, 0, -x0 * W / cw], [0, H / ch, -y0 * H / ch]], np.float32)

    def fit_box(self):
        """'fit' layout: the whole source frame sits inside the output (e.g. landscape inside vertical)."""
        E, F = self.E, self.F
        fw = E.W; fh = int(round(E.W * F.SH / F.SW))
        if fh > E.H: fh = E.H; fw = int(round(E.H * F.SW / F.SH))
        ox = (E.W - fw) / 2; oy = (E.H - fh) * E.p.get('fit_y', 0.42)
        return ox, oy, fw, fh

    def shot(self, k, lt, extra=1.0, blur=0.0, shake=(0, 0)):
        E = self.E; s = E.segs[k]
        lt = min(max(lt, 0), s['dur'] - 1 / FPS)
        ts = s['in'] + lt
        z = s['zoom'] * (1 + s.get('push', 0.035) * lt / s['dur']) * extra
        z *= self.sig_zoom(s['start'] + lt)
        if E.p.get('layout') == 'fit':
            F = self.F; src = self.F.frame(k, ts)
            ox, oy, fw, fh = self.fit_box()
            cw, ch = F.SW / z, F.SH / z
            fx_, fy_, _ = self.face(ts)
            x0 = min(max(fx_ * F.SW - cw / 2, 0), F.SW - cw); y0 = min(max(fy_ * F.SH - ch / 2, 0), F.SH - ch)
            M = np.array([[fw / cw, 0, ox - x0 * fw / cw + shake[0]], [0, fh / ch, oy - y0 * fh / ch + shake[1]]], np.float32)
            sc = max(E.W / F.SW, E.H / F.SH)
            Mb = np.array([[sc, 0, (E.W - F.SW * sc) / 2], [0, sc, (E.H - F.SH * sc) / 2]], np.float32)
            tiny = cv2.resize(src, (F.SW // 8, F.SH // 8), interpolation=cv2.INTER_AREA)
            Mt = Mb.copy(); Mt[0, 0] *= 8; Mt[1, 1] *= 8
            bg = cv2.GaussianBlur(cv2.warpAffine(tiny, Mt, (E.W, E.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT), (0, 0), 6 * E.u).astype(np.float32) * 0.45
            img = cv2.warpAffine(src, M, (E.W, E.H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
            inside = np.zeros((E.H, E.W), np.float32); cv2.rectangle(inside, (int(ox), int(oy)), (int(ox + fw) - 1, int(oy + fh) - 1), 1.0, -1)
            img = (img.astype(np.float32) * inside[..., None] + bg * (1 - inside[..., None])).astype(np.uint8)
        else:
            M = self.crop_M(ts, z); M[0, 2] += shake[0]; M[1, 2] += shake[1]
            img = cv2.warpAffine(self.F.frame(k, ts), M, (E.W, E.H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        out = grade(img, E.p.get('look', 'aarvan'), 0.6 if min(self.F.SW, self.F.SH) < 900 else 0.25)
        if blur > 0.5: out = cv2.GaussianBlur(out, (0, 0), blur * E.u)
        self._M, self._ts = M, ts
        return out

    def person_mask(self, ts, M):
        if not self.masks: return None
        fi = int(round(ts * self.mask_fps))
        if fi not in self.masks:
            ks = np.array(list(self.masks)); fi = int(ks[np.argmin(np.abs(ks - fi))])
        m = self.masks[fi].astype(np.float32) / 255
        sx, sy = self.F.SW / m.shape[1], self.F.SH / m.shape[0]
        Mm = M.copy(); Mm[0, 0] *= sx; Mm[1, 1] *= sy
        return cv2.warpAffine(m, Mm, (self.E.W, self.E.H), flags=cv2.INTER_LINEAR)

    # ---------- the Aarvan Drop ----------
    def sig_phase(self, t):
        sg = self.E.sig
        if not sg: return None
        lt = t - sg['t_out']
        if -0.45 <= lt <= sg['dur']: return lt
        return None

    def sig_zoom(self, t):
        lt = self.sig_phase(t)
        if lt is None: return 1.0
        if lt < 0: return 1.0
        return 1 + 0.07 * ease_out(lt / 0.18) * (1 - ease_io((lt - self.E.sig['dur'] + 0.4) / 0.4))

    def draw_signature(self, fr, t, mask):
        E = self.E; sg = E.sig; lt = self.sig_phase(t)
        if lt is None: return
        W, H, u = E.W, E.H, E.u; D = sg['dur']
        out = ease_io((lt - D + 0.35) / 0.35)          # 0 -> 1 during exit
        pre = ease_io((lt + 0.45) / 0.45)              # build-up before the word
        m = mask if mask is not None else np.zeros((H, W), np.float32)
        bgm = (1 - m)[..., None]
        # 1) dim the room (not you)
        dim = 0.42 * pre * (1 - out)
        fr[:] = fr * (1 - dim * bgm)
        # 2) orange diagonal band sweeps in behind you
        bp = ease_out((lt + 0.35) / 0.4) if lt < D - 0.35 else 1 - out
        fx_, fy_, fw_ = self.face(self._ts)
        word_y = H * (0.30 if not E.vertical else 0.27)
        if E.p.get('layout') == 'fit':
            ox_, oy_, fw_b, fh_b = self.fit_box(); word_y = oy_ + fh_b * 0.24
        if bp > 0:
            band = np.zeros((H, W), np.float32)
            th = (0.24 if not E.vertical else 0.13) * H
            ang = math.radians(-12)
            cx = W / 2 + (1 - bp) * W * 1.2 * (1 if lt < D - 0.35 else -1)
            dx, dy = math.cos(ang), math.sin(ang); L = W * 1.5
            p = np.array([[cx - dx * L - dy * th / 2, word_y - dy * L + dx * th / 2], [cx + dx * L - dy * th / 2, word_y + dy * L + dx * th / 2],
                          [cx + dx * L + dy * th / 2, word_y + dy * L - dx * th / 2], [cx - dx * L + dy * th / 2, word_y - dy * L - dx * th / 2]], np.int32)
            cv2.fillPoly(band, [p], 1.0, lineType=cv2.LINE_AA)
            a = (band * 0.94 * (1 - m))[..., None]
            fr[:] = fr * (1 - a) + np.array(ACCENT, np.float32) * a
        # 3) the word slams down behind you
        if lt >= -0.06:
            size = int((0.26 if not E.vertical else 0.105) * H)
            spr = self.S('sigword', lambda: text_sprite(sg['text'].upper(), 'display', size, fill=WHITE, shadow=True, pad=int(size * .25)))
            maxw = W * (0.92 if E.vertical else 0.86)
            fit = min(1.0, maxw / spr.shape[1])
            land = back_out((lt + 0.06) / 0.24, 2.4)
            sc = fit * (1.45 - 0.45 * land) * (1 + 0.025 * math.sin(max(lt, 0) * 3)) * (1 - 0.15 * out)
            y = word_y - (1 - ease_out((lt + 0.06) / 0.2)) * H * 0.18 - out * H * 0.08
            al = clamp((lt + 0.06) / 0.08) * (1 - out)
            if 'sig_front' not in self.__dict__:   # decide once: how much of the word would the head cover?
                hw, hh = spr.shape[1] * fit / 2, spr.shape[0] * fit / 2
                ys, xs = slice(int(max(0, word_y - hh)), int(min(H, word_y + hh))), slice(int(max(0, W / 2 - hw)), int(min(W, W / 2 + hw)))
                ink = spr[..., 3] > 128
                cover = float((m[ys, xs] > 0.5).mean()) if mask is not None else 0.0
                self.sig_front = cover > 0.22 or sg.get('front', False)
            blit(fr, spr, W / 2, y, scale=sc, alpha=al, mask_below=None if self.sig_front else m)
        # 4) white flash on impact
        if 0 <= lt < 0.1:
            f = 0.28 * (1 - lt / 0.1); fr[:] = fr * (1 - f) + 255 * f

    def sig_shake(self, t):
        lt = self.sig_phase(t)
        if lt is None or lt < 0 or lt > 0.16: return (0, 0)
        k = (1 - lt / 0.16) * 9 * self.E.u
        return (k * math.sin(lt * 157), k * math.cos(lt * 131))

    # ---------- footage with transitions ----------
    def footage(self, t):
        E = self.E; T = E.T
        if t >= E.seg_end:
            k = len(E.segs) - 1; return self.shot(k, E.segs[k]['dur']), k
        act = [k for k, s in enumerate(E.segs) if s['start'] <= t < s['start'] + s['dur']]
        if not act: return None, None
        k = act[-1]; s = E.segs[k]; lt = t - s['start']; sh = self.sig_shake(t); T = s['T']
        if lt < T and k > 0 and s['tstyle'] == 'whip':
            # whip pan: the old shot slides out left, the new one slides in from the right, with motion blur
            p = ease_io(lt / T)
            inc = self.shot(k, lt, shake=sh); M, ts = self._M, self._ts
            o = self.shot(k - 1, t - E.segs[k - 1]['start'])
            self._M, self._ts = M, ts
            off = int(round(p * E.W)); fr = np.empty_like(inc)
            if off < E.W: fr[:, :E.W - off] = o[:, off:]
            if off > 0: fr[:, E.W - off:] = inc[:, :off]
            kb = int(1 + 90 * E.u * math.sin(math.pi * p))
            if kb > 2: fr = cv2.blur(fr, (kb, 1))
            return fr, k
        if lt < T and (k > 0 or E.intro):
            p = ease_io(lt / T)
            inc = self.shot(k, lt, extra=1.12 - 0.12 * p, blur=(1 - p) * 6, shake=sh)
            M, ts = self._M, self._ts
            if k == 0:
                o = self.intro_card(t); sc = 1 + 0.25 * p
                o = cv2.warpAffine(o, np.float32([[sc, 0, E.W / 2 * (1 - sc)], [0, sc, E.H / 2 * (1 - sc)]]), (E.W, E.H))
                o = cv2.GaussianBlur(o, (0, 0), 0.5 + 8 * p * E.u)
            else:
                o = self.shot(k - 1, t - E.segs[k - 1]['start'], extra=1 + 0.14 * p, blur=p * 8)
            self._M, self._ts = M, ts
            return o * (1 - p) + inc * p, k
        return self.shot(k, lt, shake=sh), k

    # ---------- cards ----------
    def intro_card(self, t):
        E = self.E; W, H, u = E.W, E.H, E.u; I = E.intro
        fr = np.zeros((H, W, 3), np.float32); fr[:] = DARK
        vy, vx = np.ogrid[:H, :W]
        fr += np.exp(-(((vx - W * 0.35) / (520 * u)) ** 2 + ((vy - H * 0.55) / (380 * u)) ** 2))[..., None] * np.array([40, 22, 8], np.float32)
        diag_band(fr, t / 0.45, u=u)
        x0 = int(W * (0.086 if not E.vertical else 0.08)); yc = H * 0.5
        lab = self.S('i_lab', lambda: text_sprite(I['label'] + '  ·  INTRO' if I.get('label_suffix', True) else I['label'], 'label', 22 * u, fill=ACCENT, shadow=False))
        blit(fr, lab, x0, yc - 110 * u, alpha=ease_out((t - .1) / .3), anchor='l')
        big = self.S('i_big', lambda: text_sprite(I['title'], 'display', 132 * u, fill=WHITE, shadow=False))
        has_logo = os.path.exists(os.path.join(ROOT, 'brand', 'logo.png')) and I.get('logo', True)
        avail = (W * 0.79 - 0.30 * min(W, H) - x0) if (has_logo and not E.vertical) else (W - 2 * x0)
        fit = min(1.0, avail / big.shape[1]); p = ease_out((t - .15) / .5)
        if p > 0:
            sp = big.copy(); sp[:, int(sp.shape[1] * p):, 3] = 0
            blit(fr, sp, x0 - 14 * u * fit, yc - 10 * u + (1 - p) * 30 * u, scale=fit, anchor='l')
        sub = self.S('i_sub', lambda: text_sprite(I['subtitle'], 'body', 30 * u, fill=GREY, shadow=False))
        q = ease_out((t - .45) / .4)
        blit(fr, sub, x0, yc + 90 * u * max(fit, .6) + (1 - q) * 20 * u, alpha=q, anchor='l')
        lp = ease_out((t - .35) / .5)
        if lp > 0:
            yy = int(yc + 130 * u * max(fit, .6)); cv2.rectangle(fr, (x0, yy), (x0 + int(300 * u * lp), yy + int(6 * u)), ACCENT, -1)
        lp = os.path.join(ROOT, 'brand', 'logo.png')
        if os.path.exists(lp) and I.get('logo', True):
            sz = int((0.56 if not E.vertical else 0.3) * min(W, H) / (1 if not E.vertical else 1) * (1 if not E.vertical else 1.6))
            logo = self.S('i_logo', lambda: make_logo(sz, 'A'))
            q = back_out((t - .25) / .45)
            lx, ly = (W * 0.79, H * 0.5) if not E.vertical else (W * 0.5, H * 0.22)
            blit(fr, logo, lx, ly, scale=.6 + .4 * q, alpha=clamp((t - .25) / .2))
        cv2.rectangle(fr, (0, H - int(10 * u)), (W, H), ACCENT, -1)
        return fr

    def end_card(self, t, fr):
        E = self.E; W, H, u = E.W, E.H, E.u; ec = E.end; lt = t - ec['start']
        diag_band(fr, lt / 0.45, u=u); cv2.rectangle(fr, (0, H - int(10 * u)), (W, H), ACCENT, -1)
        logo = self.S('e_logo', lambda: make_logo(int(ec.get('logo_size', 230) * u), ec.get('logo_letter', 'A')))
        p = back_out((lt - .05) / .45)
        yb = H * (0.24 if not E.vertical else 0.33)
        blit(fr, logo, W / 2, yb, scale=.6 + .4 * p, alpha=clamp(lt / .25))
        sync = ec.get('sync') or []
        for i, line in enumerate(ec['lines']):
            spr = self.S('e_l' + str(i), lambda line=line, i=i: text_sprite(line, 'display', 96 * u, fill=WHITE if i % 2 == 0 else ACCENT))
            fit = min(1.0, W * 0.9 / spr.shape[1])
            t0 = E.anchor(sync[i]) if i < len(sync) else ec['start'] + 0.15 + 0.25 * i
            a = back_out((t - t0 + .05) / .3)
            blit(fr, spr, W / 2, yb + (160 + 105 * i) * u, scale=fit * (.7 + .3 * a), alpha=clamp((t - t0 + .05) / .15))
        ft = self.S('e_ft', lambda: text_sprite(ec['handle'], 'body', 28 * u, fill=GREY, shadow=False))
        fa = ease_out((lt - .9) / .4); n = len(ec['lines'])
        blit(fr, ft, W / 2, yb + (160 + 105 * n + 30) * u + (1 - fa) * 15 * u, scale=min(1, W * .9 / ft.shape[1]), alpha=fa)
        return fr

    # ---------- captions ----------
    def make_chunks(self):
        E = self.E; f = font('display', self.cap_size()); stroke = int(7 * E.u); gap = 18 * E.u
        maxw = E.W * 0.86; out = []; cur = []; cw = 0
        mw = lambda w: f.getbbox(w.upper(), stroke_width=stroke)[2] - f.getbbox(w.upper(), stroke_width=stroke)[0]
        cap = E.p.get('captions', {})
        if cap is False or (isinstance(cap, dict) and cap.get('on') is False): return []
        maxn = cap.get('max_words', 3) if isinstance(cap, dict) else 3
        FILL = {'uh', 'um', 'umm', 'uhh', 'hmm', 'er', 'ah', 'eh'}
        for i, w in enumerate(E.words):
            if re.sub(r'\W', '', w['w'].lower()) in FILL or w.get('skip'): continue
            ww = mw(w['w'])
            newseg = cur and cur[-1]['seg'] != w['seg']
            gap_t = cur and w['t0'] - cur[-1]['t1'] > 0.5
            if cur and (len(cur) >= maxn or cw + gap + ww > maxw or newseg or gap_t):
                out.append(cur); cur = []; cw = 0
            cur.append(w); cw += ww + (gap if len(cur) > 1 else 0)
            if re.search(r'[,.!?]$', w['w']): out.append(cur); cur = []; cw = 0
        if cur: out.append(cur)
        return out

    def cap_size(self): return (58 if not self.E.vertical else 64) * self.E.u

    def cap_sprite(self, ci, act):
        def mk():
            E = self.E; ch = self.chunks[ci]; f = font('display', self.cap_size()); stroke = int(7 * E.u); gap = int(18 * E.u)
            words = [re.sub(r'[.]$', '', w['w'].upper()) for w in ch]
            bbs = [f.getbbox(w, stroke_width=stroke) for w in words]
            widths = [b[2] - b[0] for b in bbs]; pad = int(30 * E.u)
            from PIL import ImageDraw, ImageFilter
            im = Image.new('RGBA', (sum(widths) + gap * (len(words) - 1) + pad * 2, int(self.cap_size() * 1.7) + pad), (0, 0, 0, 0))
            sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sh); x = pad
            for w, b, ww in zip(words, bbs, widths):
                ds.text((x - b[0] + 2, pad - b[1] + 6 * E.u), w, font=f, fill=(0, 0, 0, 170), stroke_width=stroke, stroke_fill=(0, 0, 0, 170)); x += ww + gap
            im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(5 * E.u)))
            d = ImageDraw.Draw(im); x = pad
            for k, (w, b, ww) in enumerate(zip(words, bbs, widths)):
                d.text((x - b[0], pad - b[1]), w, font=f, fill=ACCENT if k == act else WHITE, stroke_width=stroke, stroke_fill=STROKE); x += ww + gap
            return np.array(im)
        return self.S(('cap', ci, act), mk)

    def draw_captions(self, fr, t):
        E = self.E
        for (a, b) in self.title_windows:
            if a <= t < b: return
        cap = E.p.get('captions') if isinstance(E.p.get('captions'), dict) else {}
        dflt = 0.86 if not E.vertical else 0.70
        if E.p.get('layout') == 'fit' and E.vertical:
            ox_, oy_, fw_b, fh_b = self.fit_box(); dflt = min(0.74, (oy_ + fh_b) / E.H + 0.07)
        y = E.H * cap.get('y', dflt)
        for ci, ch in enumerate(self.chunks):
            t0 = ch[0]['t0']; nxt = self.chunks[ci + 1][0]['t0'] if ci + 1 < len(self.chunks) else 1e9
            t1 = min(ch[-1]['t1'] + 0.3, nxt)
            if t0 - 0.02 <= t < t1:
                act = 0
                for k, w in enumerate(ch):
                    if t >= w['t0'] - 0.02: act = k
                boost = 1.0
                if E.sig and any(abs(w['t0'] - E.sig['t_out']) < 0.05 for w in ch) and t >= E.sig['t_out']:
                    boost = 1 + 0.15 * (1 - ease_out((t - E.sig['t_out']) / 0.5))
                p = back_out((t - t0 + .02) / .16, 2.2)
                blit(fr, self.cap_sprite(ci, act), E.W / 2, y, scale=(.82 + .18 * p) * boost, alpha=clamp((t - t0 + .02) / .08))

    # ---------- graphics ----------
    def prepare_graphics(self):
        E = self.E; self.items = []; self.title_windows = []; self.pops = []
        nt = E.p.get('nametag')
        if nt:
            d = dict(BRAND['nametag']); d.update(nt if isinstance(nt, dict) else {})
            t0 = E.anchor(d['at']) if 'at' in d else E.segs[0]['start'] + 0.4
            self.items.append(('nametag', t0, E.until(d.get('until'), t0), d))
        for st in E.p.get('stickers', []):
            t0 = E.anchor(st['at']); self.items.append(('sticker', t0, E.until(st.get('until'), t0), st)); self.pops.append(t0)
        for tl in E.p.get('titles', []):
            ts = [E.anchor(a) for a in tl['at']]
            t1 = E.until(tl.get('until'), ts[0]); self.items.append(('title', ts[0], t1, dict(tl, times=ts)))
            self.title_windows.append((ts[0] - 0.05, t1 + 0.2)); self.pops += ts

    def draw_graphics(self, fr, t):
        E = self.E; W, H, u = E.W, E.H, E.u
        for kind, t0, t1, d in self.items:
            if not (t0 - 0.05 <= t < t1 + 0.25): continue
            oa = 1 - clamp((t - t1) / 0.25)
            if kind == 'nametag':
                p = ease_out((t - t0) / .35)
                nm = self.S('nm', lambda: text_sprite(d['name'], 'display', 44 * u, fill=WHITE, shadow=False, pad=int(6 * u)))
                sb = self.S('sb', lambda: text_sprite(d['sub'], 'label', 19 * u, fill=ACCENT, shadow=False, pad=int(6 * u)))
                bw = max(nm.shape[1], sb.shape[1]) + int(50 * u); x0, y0, bh = int(.04 * W), int(.065 * H), int(104 * u)
                if p > 0:
                    ov = fr[y0:y0 + bh, x0:x0 + int(bw * p)]
                    ov[:] = ov * (1 - .82 * oa) + np.array(DARK, np.float32) * .82 * oa
                    if oa > .5: cv2.rectangle(fr, (x0, y0), (x0 + int(8 * u), y0 + bh), ACCENT, -1)
                    ta = clamp((t - t0 - .2) / .25) * oa
                    blit(fr, nm, x0 + 28 * u - (1 - ta) * 12 * u, y0 + 36 * u, alpha=ta, anchor='l')
                    blit(fr, sb, x0 + 30 * u - (1 - ta) * 12 * u, y0 + 78 * u, alpha=ta, anchor='l')
            elif kind == 'sticker':
                style = d.get('style', 'dark')
                bg, fg, bd = {'dark': ((18, 18, 20), WHITE, ACCENT), 'accent': (ACCENT, (12, 12, 12), None), 'light': (WHITE, (12, 12, 12), None)}[style]
                spr = self.S(('st', d['text'], style), lambda: pill_sprite(d['text'], 'display', (34 if not E.vertical else 30) * u * d.get('scale', 1), bg, fg, border=bd))
                sc = back_out((t - t0) / .32); al = clamp((t - t0) / .1) * oa
                x, y = d.get('x', .82) * W, d.get('y', .4) * H + math.sin(t * 2.2 + d.get('x', .8) * 9) * 4 * u
                al_ = d.get('align', 'r' if d.get('x', .82) > .9 else ('l' if d.get('x', .82) < .1 else 'c'))
                blit(fr, spr, x, y, scale=sc, alpha=al, anchor=al_)
                if al_ == 'r': x = x - spr.shape[1] * sc / 2
                elif al_ == 'l': x = x + spr.shape[1] * sc / 2
                if d.get('strike') and t > t0 + .25 and oa > .3:
                    sp = ease_out((t - t0 - .25) / .2); hw = spr.shape[1] / 2 - 30 * u
                    cv2.line(fr, (int(x - hw), int(y)), (int(x - hw + 2 * hw * sp), int(y)), ACCENT, max(2, int(5 * u)), cv2.LINE_AA)
            elif kind == 'title':
                for i, (line, ti) in enumerate(zip(d['lines'], d['times'])):
                    spr = self.S(('tl', line, i), lambda line=line, i=i: text_sprite(line, 'display', 74 * u * d.get('scale', 1), fill=WHITE if i % 2 == 0 else ACCENT, stroke=int(6 * u)))
                    fit = min(1.0, W * .92 / spr.shape[1])
                    sc = back_out((t - ti) / .32); al = clamp((t - ti) / .1) * oa
                    y0 = d.get('y', .76 if not E.vertical else .62) * H
                    blit(fr, spr, W / 2, y0 + i * 90 * u * fit, scale=sc * fit, alpha=al)

    # ---------- one frame ----------
    def render(self, t):
        E = self.E
        if E.intro and t < E.segs[0]['start']:
            fr = self.intro_card(t)
        else:
            fr, k = self.footage(t)
            mask = None
            if self.sig_phase(t) is not None: mask = self.person_mask(self._ts, self._M)
            if E.end and t >= E.end['start'] - 0.35:
                p = ease_io((t - E.end['start'] + .35) / .4)
                fr = cv2.GaussianBlur(fr, (0, 0), 1 + 14 * p * E.u) * (1 - .72 * p) + np.array(DARK, np.float32) * .72 * p
            if not E.end or t < E.end['start']:
                self.draw_signature(fr, t, mask)
                self.draw_graphics(fr, t)
                if self.chunks: self.draw_captions(fr, t)
            else:
                fr = self.end_card(t, fr)
            if k is not None: self.F.close({k, k - 1})
        if E.p.get('progress_bar', True):
            cv2.rectangle(fr, (0, 0), (int(E.W * t / E.TOTAL), max(3, int(5 * E.u))), ACCENT, -1)
        return np.clip(fr, 0, 255).astype(np.uint8)


def make_logo(sz, letter):
    from PIL import ImageDraw
    lp = os.path.join(ROOT, 'brand', 'logo.png')
    if os.path.exists(lp):
        return np.array(Image.open(lp).convert('RGBA').resize((sz, sz), Image.LANCZOS))
    im = Image.new('RGBA', (sz, sz), (0, 0, 0, 0)); d = ImageDraw.Draw(im); w = max(3, sz // 26)
    d.ellipse((w, w, sz - w, sz - w), fill=(18, 18, 20, 255), outline=ACCENT, width=w)
    f = font('display', int(sz * .51)); bb = f.getbbox(letter)
    d.text(((sz - (bb[2] - bb[0])) / 2 - bb[0], (sz - (bb[3] - bb[1])) / 2 - bb[1] - 2), letter, font=f, fill=ACCENT)
    return np.array(im)


# ====================================================================== audio
def load(p, sr=48000):
    a, r = sf.read(p, always_2d=True)
    if a.shape[1] == 1: a = np.repeat(a, 2, 1)
    if r != sr:
        g = math.gcd(sr, r); a = resample_poly(a, sr // g, r // g, axis=0)
    return a


def build_audio(E, R, path):
    sr = 48000; N = int(E.TOTAL * sr) + 1
    voice = np.zeros((N, 2)); fx = np.zeros((N, 2))
    def put(buf, a, t, g=1.0):
        i = int(max(t, 0) * sr); j = min(N, i + len(a))
        if j > i: buf[i:j] += a[:j - i] * g
    if E.audio_mode == 'source' and E.info['audio']:
        wav = os.path.join(E.work, 'source48k.wav')
        if not os.path.exists(wav):
            af = ['-af', 'highpass=f=80,lowpass=f=12000,afftdn=nf=-25,dynaudnorm=f=200:g=15:p=0.9,acompressor=threshold=0.1:ratio=3:attack=10:release=150'] \
                if E.p.get('clean_voice', True) else []
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', E.src, '-vn', '-ac', '2', '-ar', str(sr)] + af + [wav], check=True)
        src = load(wav, sr); xf = int(0.03 * sr)
        for k, s in enumerate(E.segs):
            a0, a1 = E.audible(k)
            clip = src[int(a0 * sr):int(a1 * sr)].copy()
            if len(clip) > 2 * xf:
                clip[:xf] *= np.linspace(0, 1, xf)[:, None]; clip[-xf:] *= np.linspace(1, 0, xf)[:, None]
            put(voice, clip, s['start'] + a0 - s['in'])
        v = E.p.get('voice_gain', 1.0); voice *= v
    elif E.audio_mode == 'voiceover':
        for f, t0 in getattr(E, 'vo_lines', []):
            a = load(f, sr)
            a = a + sosfilt(butter(2, [2500, 6000], 'band', fs=sr, output='sos'), a, axis=0) * 0.35
            put(voice, np.tanh(a * 1.4) / np.tanh(1.4), t0)
    # sound design
    sfxdir = os.path.join(E.work, 'sfx')
    mu = E.p.get('music', {'mood': 'punchy'})
    import music as M
    if mu is not False:
        M.make(E.TOTAL + 0.5, sfxdir, bpm=mu.get('bpm', 116), mood=mu.get('mood', 'punchy'))
    elif not os.path.exists(os.path.join(sfxdir, 'whoosh.wav')):
        M.make(2.0, sfxdir)
    if E.p.get('sfx', True):
        wh, pop, imp, drop = (load(os.path.join(sfxdir, n + '.wav'), sr) for n in ['whoosh', 'pop', 'impact', 'drop'])
        if E.intro: put(fx, imp, 0.05, 0.55)
        for k, s in enumerate(E.segs):
            if k > 0 or E.intro: put(fx, wh, s['start'] + s['T'] / 2 - 0.33, (0.6 if s['T'] > 0.45 else 0.45) if k else 0.6)
        for t in R.pops: put(fx, pop, t, 0.35)
        if E.sig: put(fx, drop, E.sig['t_out'] - 0.5, 0.8)
        if E.end: put(fx, wh, E.end['start'] - 0.5, 0.5); put(fx, imp, E.end['start'] - 0.02, 0.5)
    # ---- dialogue-first mix: the voice sets every other level ----
    db = lambda x: 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)
    act = np.abs(voice).max(1) > max(0.002, np.abs(voice).max() * 0.06)
    if act.any():
        voice *= 10 ** ((-18.0 - db(voice[act])) / 20)          # speech RMS -> -18 dBFS
        voice = np.tanh(voice * 1.6) / 1.6                       # gentle peak control
        act = np.abs(voice).max(1) > 0.01
    v_db = db(voice[act]) if act.any() else -18.0
    k1 = int(.25 * sr); env = np.convolve(act.astype(float), np.ones(k1) / k1, 'same').clip(0, 1)
    k2 = int(.15 * sr); env = np.convolve(env, np.ones(k2) / k2, 'same')
    # sound effects: never louder than the voice (peaks ~6 dB under the voice peak)
    if np.abs(fx).max() > 0:
        fx *= min(1.0, (np.abs(voice).max() * 0.4 if act.any() else 0.5) / np.abs(fx).max())
    mix = voice + fx
    if mu is not False:
        m = load(os.path.join(sfxdir, 'music.wav'), sr)[:N]; m = np.pad(m, ((0, N - len(m)), (0, 0)))
        off = 20 * np.log10(max(mu.get('volume', 0.42), 1e-3) / 0.42)   # plan volume = trim around the defaults
        under, gaps = v_db - 20 + off, v_db - 9 + off                     # music under speech / in pauses
        g_under = 10 ** ((under - db(m)) / 20); g_gaps = 10 ** ((gaps - db(m)) / 20)
        mix += m * (g_gaps + (g_under - g_gaps) * env)[:, None]
        R._music_under = m * (g_gaps + (g_under - g_gaps) * env)[:, None]
    f = int(0.8 * sr); mix[-f:] *= np.linspace(1, 0, f)[:, None]
    pk = np.abs(mix).max()
    if pk > 0.98: mix = np.tanh(mix / pk * 1.2) / np.tanh(1.2) * 0.98   # limit, don't scale the voice down
    # ---- QA: the voice must clearly lead the background while you speak ----
    if act.any():
        bg = mix - voice
        ratio = db(voice[act]) - db(bg[act])
        R.audio_qa = {'voice_db': round(db(voice[act]), 1), 'background_db': round(db(bg[act]), 1), 'voice_over_background_db': round(ratio, 1)}
        print(f"Audio check: voice {R.audio_qa['voice_db']} dB, background {R.audio_qa['background_db']} dB -> voice leads by {ratio:.1f} dB",
              '(OK)' if ratio >= 12 else '(WARNING: voice too low, needs >= 12 dB)', flush=True)
    sf.write(path, mix, sr)


# ====================================================================== main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('plan'); ap.add_argument('--draft', action='store_true')
    ap.add_argument('--still'); ap.add_argument('--sheet', type=int); ap.add_argument('--timeline', action='store_true')
    ap.add_argument('--remix', action='store_true', help='rebuild only the sound and put it on the existing output video')
    a = ap.parse_args()
    plan = json.load(open(a.plan)); pdir = os.path.dirname(os.path.abspath(a.plan))
    E = Edit(plan, pdir, short=720 if (a.draft or a.still or a.sheet) else None)
    print(f'Output {E.W}x{E.H}, {E.TOTAL:.2f}s, {len(E.segs)} shots, audio={E.audio_mode}', flush=True)
    if a.timeline:
        if E.intro: print(f'  0.00-{E.intro["dur"]:.2f}  intro card')
        for k, s in enumerate(E.segs): print(f'  {s["start"]:6.2f}-{s["start"] + s["dur"]:6.2f}  shot {k}: source {s["in"]:.2f}-{s["out"]:.2f} zoom {s["zoom"]}')
        if E.sig: print(f'  {E.sig["t_out"]:6.2f}  AARVAN DROP "{E.sig["text"]}"')
        if E.end: print(f'  {E.end["start"]:6.2f}-{E.TOTAL:6.2f}  end card')
        print('  words:', ' '.join(f'{w["w"]}@{w["t0"]:.2f}' for w in E.words)); return
    if a.remix:
        if not os.path.exists(E.out): raise SystemExit('render the video first')
        G2 = Renderer.__new__(Renderer); G2.E = E; Renderer.prepare_graphics(G2)
        base = os.path.splitext(E.out)[0]; wav = base + '_mix.wav'; build_audio(E, G2, wav)
        tmp = base + '.remix.tmp.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', E.out, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                        '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.85:level=false', '-ar', '48000', '-movflags', '+faststart', '-shortest', tmp], check=True)
        os.replace(tmp, E.out); os.remove(wav); print('Remixed:', E.out); return
    R = Renderer(E); R.prepare_graphics()
    base = os.path.splitext(E.out)[0]
    if a.still or a.sheet:
        ts = [float(x) for x in a.still.split(',')] if a.still else list(np.linspace(0.6, E.TOTAL - 0.4, a.sheet))
        if a.sheet and E.sig and all(abs(t - E.sig['t_out'] - .4) > .5 for t in ts): ts = sorted(ts[:-1] + [E.sig['t_out'] + 0.4])
        ims = []
        for t in ts:
            im = Image.fromarray(R.render(t))
            if a.still: im.save(f'{base}_check_{t:.2f}.jpg', quality=90); print('saved', f'{base}_check_{t:.2f}.jpg')
            ims.append(im)
        if a.sheet:
            cols = 4 if E.vertical else 3; tw = 360 if not E.vertical else 220
            th = int(tw * E.H / E.W); rows = (len(ims) + cols - 1) // cols
            S = Image.new('RGB', (cols * tw, rows * th), (20, 20, 20))
            for i, im in enumerate(ims): S.paste(im.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
            S.save(base + '_sheet.jpg', quality=88); print('saved', base + '_sheet.jpg')
        return
    n = int(round(E.TOTAL * FPS)); tmp = base + '_video.tmp.mp4'
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{E.W}x{E.H}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    print(f'Rendering {n} frames...', flush=True)
    for i in range(n):
        enc.stdin.write(R.render(i / FPS).tobytes())
        if i % (FPS * 5) == 0: print(f'  {i / FPS:5.1f}s / {E.TOTAL:.1f}s', flush=True)
    enc.stdin.close()
    if enc.wait() != 0: raise SystemExit('video encode failed')
    print('Mixing sound...', flush=True)
    wav = base + '_mix.wav'; build_audio(E, R, wav)
    out_tmp = base + '.tmp.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.85:level=false', '-ar', '48000', '-movflags', '+faststart', '-shortest', out_tmp], check=True)
    os.replace(out_tmp, E.out); os.remove(tmp); os.remove(wav)
    print('Done:', E.out)


if __name__ == '__main__':
    main()
