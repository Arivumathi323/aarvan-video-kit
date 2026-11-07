"""Break down a reference reel (one whose style you want to copy): every cut, shot lengths, hook, speaking pace,
music tempo, loudness, and a still of every shot. Writes REFERENCE.md + shots.jpg for Claude to read and turn
into a beat sheet for your own video ("same pace and rhythm, about my topic").
usage: python reference.py reel.mp4 out_dir

Instagram/YouTube links can't be downloaded from here: save or screen-record the reel and attach the file.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import probe, fpath
import analyze as A


def scene_cuts(src, info):
    """Cuts, including soft ones (crossfades, zoom punch-ins): compare each frame with the one 0.3 s earlier and
    keep the peaks that stand well above the local background motion."""
    from track import read_frames
    W = 160; H = int(round(W * info['h'] / info['w'])); H -= H % 2
    fps = 10; g = []
    for _, fr in read_frames(src, W, H, fps=fps):
        g.append(fr.mean(2).astype(np.float32))
    if len(g) < 6: return []
    k = 3; d = np.array([0.0] * k + [np.abs(g[i] - g[i - k]).mean() for i in range(k, len(g))])
    base = np.array([np.median(d[max(0, i - 15):i + 15]) for i in range(len(d))])
    cuts, last = [], -1e9
    for i in range(1, len(d) - 1):
        if d[i] >= d[i - 1] and d[i] >= d[i + 1] and d[i] > max(2.2 * base[i], 6.0) and (i - last) / fps > 0.6:
            cuts.append(round((i - k / 2) / fps, 2)); last = i
    return cuts


def tempo(wav):
    a, sr = sf.read(wav)
    if a.ndim > 1: a = a.mean(1)
    hop = 512; e = np.array([np.sqrt((a[i:i + hop] ** 2).mean()) for i in range(0, len(a) - hop, hop)])
    on = np.maximum(0, np.diff(np.log(e + 1e-6))); on -= on.mean()
    fps = sr / hop; ac = np.correlate(on, on, 'full')[len(on) - 1:]
    lags = np.arange(int(fps * 60 / 180), int(fps * 60 / 70))
    if len(lags) == 0 or lags[-1] >= len(ac): return None
    best = lags[np.argmax(ac[lags])]; strength = ac[best] / (ac[0] + 1e-9)
    return (round(60 * fps / best), round(float(strength), 2))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out')
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    info = probe(a.src); dur = info['dur']
    cuts = [c for c in scene_cuts(a.src, info) if 0.15 < c < dur - 0.15]
    bounds = [0.0] + cuts + [dur]; shots = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    lens = np.array([b - a_ for a_, b in shots])
    words, lang = [], None
    if info['audio']:
        wav = os.path.join(a.out, 'ref16k.wav')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.src, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)
        try:
            words, lang = A.transcribe(wav, 'base', None)
        except Exception:
            try: words, lang = A.transcribe_parakeet(wav)
            except Exception as ex: print('transcription failed:', ex)
        tp = tempo(wav)
        lufs = re.findall(r'I:\s+(-?[\d.]+) LUFS', subprocess.run(['ffmpeg', '-v', 'info', '-nostats', '-i', a.src, '-af', 'ebur128', '-f', 'null', '-'],
                                                                  capture_output=True, text=True).stderr)
    else:
        tp, lufs = None, []
    # stills: one per shot (just after the cut) + the first 3 seconds, to read layout and on-screen text
    times = sorted(set([round(min(b - 0.05, a_ + min(0.4, (b - a_) / 2)), 2) for a_, b in shots] + [0.3, 1.0, 2.0]))
    cols = 6 if info['w'] >= info['h'] else 8; tw = 300 if info['w'] >= info['h'] else 180
    th = int(tw * info['h'] / info['w']); th -= th % 2
    sel = '+'.join(f'eq(n\\,{int(round(t * info["fps"]))})' for t in times)
    rows = (len(times) + cols - 1) // cols
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.src, '-vf',
                    f"select='{sel}',scale={tw}:{th},drawtext=fontfile={fpath('heavy')}:text='%{{pts\\:flt}}':x=4:y=4:fontsize=14:fontcolor=red:box=1:boxcolor=white@0.8,tile={cols}x{rows}",
                    '-vsync', '0', '-frames:v', '1', os.path.join(a.out, 'shots.jpg')], check=True)
    # report
    spoken = [w for w in words if w['w']]
    wpm = (len(spoken) / ((spoken[-1]['e'] - spoken[0]['s']) / 60)) if len(spoken) > 3 else None
    hook = ' '.join(w['w'] for w in spoken if w['s'] < 3.0)
    L = [f'# Reference breakdown · {os.path.basename(a.src)}', '',
         f"{info['w']}x{info['h']} · {dur:.1f}s · {'vertical' if info['h'] > info['w'] else 'landscape'}", '',
         '## Pace', '',
         f'- **{len(shots)} shots**, a cut every **{lens.mean():.1f}s** on average (median {np.median(lens):.1f}s, shortest {lens.min():.1f}s, longest {lens.max():.1f}s)',
         f'- Cuts per 10 seconds: {10 * len(cuts) / dur:.1f}',
         f'- Speaking pace: {wpm:.0f} words per minute' if wpm else '- Speaking pace: (no speech found)',
         f'- First words (hook, 0–3s): "{hook}"' if hook else '- Hook: no speech in the first 3 seconds (visual hook)',
         f'- Music tempo: ~{tp[0]} bpm (beat strength {tp[1]})' if tp and tp[1] > 0.15 else '- Music tempo: no clear beat',
         f'- Loudness: {lufs[-1]} LUFS' if lufs else '', '',
         '## Shots', '', '| # | Time | Length | Words in this shot |', '|---|---|---|---|']
    for i, (s, e) in enumerate(shots):
        ws = ' '.join(w['w'] for w in spoken if s <= (w['s'] + w['e']) / 2 < e)
        L.append(f'| {i + 1} | {s:.1f}–{e:.1f}s | {e - s:.1f}s | {ws or "—"} |')
    L += ['', '## Next step (for Claude)', '',
          'Look at `shots.jpg` (one still per shot, plus 0.3/1/2 s) and add, per shot: what is on screen (framing, text, graphics, effects) '
          'and the transition. Then write a beat sheet for the new video with the SAME pace (shot lengths, hook timing, pattern of '
          'graphics) about the new topic, mapped to our kit: stickers, titles, punch-ins, the Aarvan Drop, pack effects.']
    open(os.path.join(a.out, 'REFERENCE.md'), 'w').write('\n'.join(x for x in L if x is not None) + '\n')
    json.dump({'shots': shots, 'cuts': cuts, 'words': spoken, 'tempo': tp, 'wpm': wpm}, open(os.path.join(a.out, 'reference.json'), 'w'), indent=1)
    print('\n'.join(L[:12])); print('Saved', os.path.join(a.out, 'REFERENCE.md'), 'and shots.jpg')


if __name__ == '__main__':
    main()
