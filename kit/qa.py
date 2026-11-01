"""Editor QA: checks an edit plan (and the finished video, if rendered) against the rules in docs/EDITOR_BRAIN.md.
usage: python qa.py plan.json [--target reels|shorts|youtube|assignment|client]

Prints one line per check (PASS / WARN / FAIL) and exits 1 if anything FAILs.
Everything here is a number, because sound and layout problems are easy to miss by eye.
"""
import argparse, json, os, re, subprocess, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R

FILL = {'uh', 'um', 'umm', 'uhh', 'hmm', 'er', 'ah', 'eh'}
LIMITS = {  # target -> (max length s, hook deadline s, max gap without change s)
    'reels': (90, 2.0, 4.5), 'shorts': (60, 2.0, 4.5), 'youtube': (900, 8.0, 7.0),
    'assignment': (600, 6.0, 8.0), 'client': (300, 5.0, 6.0)}


class Report:
    def __init__(self): self.rows = []
    def add(self, level, name, msg): self.rows.append((level, name, msg))
    def show(self):
        icon = {'PASS': 'PASS', 'WARN': 'WARN', 'FAIL': 'FAIL'}
        for lv, n, m in self.rows: print(f'{icon[lv]:4}  {n:22} {m}')
        f = sum(1 for r in self.rows if r[0] == 'FAIL'); w = sum(1 for r in self.rows if r[0] == 'WARN')
        print(f'\n{len(self.rows)} checks: {f} fail, {w} warn')
        return f


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('plan'); ap.add_argument('--target')
    ap.add_argument('--no-audio', action='store_true', help='skip the voice-vs-background mix check')
    a = ap.parse_args()
    plan = json.load(open(a.plan)); pdir = os.path.dirname(os.path.abspath(a.plan))
    E = R.Edit(plan, pdir, short=720)
    target = a.target or plan.get('target') or ('reels' if E.vertical else 'youtube')
    max_len, hook_by, max_gap = LIMITS.get(target, LIMITS['youtube'])
    rep = Report()

    # ---------- story ----------
    words = [w for w in E.words if re.sub(r'\W', '', w['w'].lower()) not in FILL and not w.get('skip')]
    start = E.segs[0]['start'] if not E.intro else E.intro['dur']
    if words:
        first = words[0]['t0']
        lv = 'PASS' if first <= hook_by else 'WARN'
        rep.add(lv, 'hook', f'first word at {first:.1f}s (target <= {hook_by:.0f}s for {target})')
    if E.intro and target in ('reels', 'shorts') and E.TOTAL < 45:
        rep.add('WARN', 'intro card', 'short vertical video: open on the hook, skip the intro card')
    lv = 'PASS' if E.TOTAL <= max_len else 'WARN'
    rep.add(lv, 'length', f'{E.TOTAL:.1f}s (target <= {max_len}s for {target})')

    # ---------- rhythm ----------
    gaps = []
    for x, y in zip(words, words[1:]):
        g = y['t0'] - x['t1']
        if g > 1.0: gaps.append((round(x['t1'], 1), round(g, 1)))
    rep.add('PASS' if not gaps else 'WARN', 'dead air', 'no silences over 1 s' if not gaps else f'{len(gaps)} silences over 1 s at ' + ', '.join(f'{t}s ({g}s)' for t, g in gaps[:6]))
    G = R.Renderer.__new__(R.Renderer); G.E = E; R.Renderer.prepare_graphics(G)
    events = sorted({round(s['start'], 2) for s in E.segs} | {round(t0, 2) for _, t0, _, _ in G.items})
    if E.sig: events.append(E.sig['t_out'])
    for e in plan.get('effects', []):
        o = E.src_to_out(e['start'])
        if o is not None: events.append(o)
    events = sorted(set(events + [E.TOTAL]))
    body = [t for t in events if t >= start - 0.01]
    gapv = [(b - a_, a_) for a_, b in zip(body, body[1:]) if not (E.end and a_ >= E.end['start'])]
    worst = max(gapv) if gapv else (0, 0)
    lv = 'PASS' if worst[0] <= max_gap else ('WARN' if worst[0] <= max_gap * 1.6 else 'FAIL')
    rep.add(lv, 'pacing', f'longest stretch with no visual change: {worst[0]:.1f}s at {worst[1]:.1f}s (target <= {max_gap}s); '
            f'{len(body) - 1} changes in {E.TOTAL - start:.0f}s')
    zs = [s['zoom'] for s in E.segs]
    if len(E.segs) > 3 and len(set(zs)) == 1:
        rep.add('WARN', 'shot variety', 'every shot has the same zoom: alternate about 1.0 / 1.15 (or 1.0 / 1.08 in fit layout)')

    # ---------- brand ----------
    rep.add('PASS' if E.sig else 'FAIL', 'Aarvan Drop', 'one signature' if E.sig else 'missing: every video gets exactly one Aarvan Drop')
    n_fx = len(plan.get('effects', []))
    rep.add('PASS' if n_fx <= 2 else 'FAIL', 'pack effects', f'{n_fx} (max 2 + the Drop)')
    if any(e.get('fx') == 'backdrop-word' for e in plan.get('effects', [])) and E.sig:
        rep.add('FAIL', 'pack effects', 'backdrop-word clashes with the Aarvan Drop')
    cap = plan.get('captions', True)
    rep.add('PASS' if cap is not False else 'FAIL', 'captions', 'on' if cap is not False else 'off: captions are always on')
    if E.end and words:
        late = E.end['start'] - words[-1]['t1']
        rep.add('PASS' if late <= 0.8 else 'WARN', 'ending', f'end card {late:+.1f}s after the last word (target <= 0.8s)')

    # ---------- layout (safe zones + face) ----------
    fit = plan.get('layout') == 'fit'
    face = None
    try:
        face = R.face_track(E.src, E.info, [(s['in'], s['out']) for s in E.segs])
    except Exception as ex:
        rep.add('WARN', 'face', f'face tracking unavailable ({ex})')
    issues = []
    for kind, t0, t1, d in G.items:
        if kind != 'sticker': continue
        x, y = d.get('x', .82), d.get('y', .4)
        if E.vertical:
            if y > 0.74: issues.append(f'"{d["text"]}" too low (y={y}; Reels UI covers the bottom)')
            if x > 0.8 and y > 0.45: issues.append(f'"{d["text"]}" under the Reels like/comment buttons')
            if y < 0.05: issues.append(f'"{d["text"]}" too close to the top edge')
        if face and not fit:
            ts = E.out_to_src(t0 + 0.3)
            if ts is not None:
                fx_, fy_, fw_ = face(ts)
                al = d.get('align', 'r' if x > .9 else ('l' if x < .1 else 'c'))
                cx = x - 0.12 if al == 'r' else (x + 0.12 if al == 'l' else x)
                if abs(cx - fx_) < fw_ * 0.8 and abs(y - fy_) < fw_ * 1.1 * (E.W / E.H):
                    issues.append(f'"{d["text"]}" may cover the face at {t0:.1f}s')
    rep.add('PASS' if not issues else 'WARN', 'graphics placement', 'stickers clear of face and platform UI' if not issues else '; '.join(issues[:5]))
    if E.vertical and E.AR < 1 and E.info['w'] > E.info['h'] and not fit:
        crop_scale = E.H / E.info['h']
        lv = 'PASS' if crop_scale <= 1.6 else 'WARN'
        rep.add(lv, 'reframe', f'landscape cropped to vertical is upscaled {crop_scale:.1f}x' + ('' if lv == 'PASS' else ': use "layout": "fit"'))

    # ---------- sound ----------
    if not a.no_audio:
        try:
            wav = os.path.join(E.work, 'qa_mix.wav')
            R.build_audio(E, G, wav)
            q = getattr(G, 'audio_qa', None)
            if q:
                r_ = q['voice_over_background_db']
                rep.add('PASS' if r_ >= 12 else 'FAIL', 'voice vs background', f'voice leads by {r_} dB (needs >= 12)')
            os.remove(wav)
        except Exception as ex:
            rep.add('WARN', 'voice vs background', f'could not build the mix ({str(ex)[:120]})')
    if os.path.exists(E.out):
        out = subprocess.run(['ffmpeg', '-v', 'info', '-nostats', '-i', E.out, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                             capture_output=True, text=True).stderr
        I = re.findall(r'I:\s+(-?[\d.]+) LUFS', out); P = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', out)
        if I:
            li = float(I[-1]); lv = 'PASS' if -15.5 <= li <= -12.5 else 'WARN'
            rep.add(lv, 'loudness', f'{li} LUFS (target -14)')
            if P:
                pk = float(P[-1]); rep.add('PASS' if pk <= -0.9 else 'WARN', 'true peak', f'{pk} dBFS (target <= -1)' + ('' if pk <= -0.9 else ': run --remix'))
    else:
        rep.add('PASS', 'loudness', 'not rendered yet (render normalises to -14 LUFS)')
    sys.exit(1 if rep.show() else 0)


if __name__ == '__main__':
    main()
