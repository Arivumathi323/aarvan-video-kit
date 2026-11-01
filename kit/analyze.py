"""Watch a raw video and write analysis.json + a timestamped contact sheet.
usage: python analyze.py raw.mp4 out_dir [--model base|small] [--lang en|ta|auto]

analysis.json holds: video info, every spoken word with times (Whisper), sentences, pauses
(good cut points), gesture/motion energy per half second, black or frozen parts, and face visibility.
"""
import argparse, json, os, subprocess, re
import numpy as np, cv2
import soundfile as sf
from common import probe, fpath
from track import read_frames, MODELS


def extract_audio(src, wav):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)


def transcribe(wav, model='base', lang=None):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        subprocess.run([os.sys.executable, '-m', 'pip', 'install', '-q', 'faster-whisper'], check=True)
        from faster_whisper import WhisperModel
    m = WhisperModel(model, device='cpu', compute_type='int8')
    segs, info = m.transcribe(wav, word_timestamps=True, vad_filter=True, language=None if lang in (None, 'auto') else lang)
    words = [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3)} for s in segs for w in (s.words or [])]
    return words, info.language


def pauses_from_audio(wav, thr_db=-38, min_len=0.22):
    a, sr = sf.read(wav)
    if a.ndim > 1: a = a.mean(1)
    hop = int(sr * 0.02)
    e = np.array([np.sqrt((a[i:i + hop] ** 2).mean() + 1e-12) for i in range(0, len(a) - hop, hop)])
    db = 20 * np.log10(e + 1e-9); quiet = db < max(thr_db, np.percentile(db, 20) + 6)
    out, run = [], 0
    for i, q in enumerate(list(quiet) + [False]):
        if q: run += 1
        else:
            if run * 0.02 >= min_len: out.append([round((i - run) * 0.02, 2), round(i * 0.02, 2)])
            run = 0
    return out


def sentences(words):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]['s'] - w['e'] if i + 1 < len(words) else 9
        if re.search(r'[.!?]$', w['w']) or gap > 0.6:
            out.append({'text': ' '.join(x['w'] for x in cur), 's': cur[0]['s'], 'e': cur[-1]['e']}); cur = []
    if cur: out.append({'text': ' '.join(x['w'] for x in cur), 's': cur[0]['s'], 'e': cur[-1]['e']})
    return out


def visual(src, info):
    """Motion energy, darkness and face visibility, every 0.5 s."""
    W = 192; H = int(round(W * info['h'] / info['w'])); H -= H % 2
    fd = cv2.FaceDetectorYN.create(os.path.join(MODELS, 'yunet.onnx'), '', (W, H), 0.6, 0.3, 20)
    prev = None; rows = []
    for i, fr in read_frames(src, W, H, fps=10):
        g = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY).astype(np.float32)
        mot = float(np.abs(g - prev).mean()) if prev is not None else 0.0; prev = g
        face = None
        if i % 5 == 0:
            _, f = fd.detect(cv2.cvtColor(fr, cv2.COLOR_RGB2BGR))
            face = bool(f is not None and len(f))
        rows.append((i / 10, mot, float(g.mean()), face))
    out = []
    for k in range(0, len(rows), 5):
        blk = rows[k:k + 5]
        out.append({'t': round(blk[0][0], 1), 'motion': round(float(np.mean([r[1] for r in blk])), 2),
                    'bright': round(float(np.mean([r[2] for r in blk])), 1),
                    'face': next((r[3] for r in blk if r[3] is not None), None)})
    if out:
        mx = max(o['motion'] for o in out) or 1
        for o in out: o['energy'] = round(o['motion'] / mx, 2)
    return out


def contact_sheet(src, info, path, every=None):
    every = every or max(0.5, round(info['dur'] / 36 * 2) / 2)
    cols = 6 if info['w'] >= info['h'] else 8
    tw = 240 if info['w'] >= info['h'] else 150
    n = int(info['dur'] / every) + 1; rows = (n + cols - 1) // cols
    vf = (f"fps=1/{every},scale={tw}:-2,drawtext=fontfile={fpath('heavy')}:"
          f"text='%{{pts\\:flt}}':x=4:y=4:fontsize=16:fontcolor=red:box=1:boxcolor=white@0.8,tile={cols}x{rows}")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-vf', vf, '-frames:v', '1', path], check=True)
    return every


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--model', default='base'); ap.add_argument('--lang', default='auto')
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    info = probe(a.src); res = {'source': os.path.abspath(a.src), 'info': info}
    print(f"{info['w']}x{info['h']}  {info['fps']:.2f}fps  {info['dur']:.1f}s  audio={info['audio']}", flush=True)
    res['orientation'] = 'vertical' if info['h'] > info['w'] else 'landscape'
    res['words'], res['sentences'], res['pauses'], res['language'] = [], [], [], None
    if info['audio']:
        wav = os.path.join(a.out, 'audio16k.wav'); extract_audio(a.src, wav)
        a16, _ = sf.read(wav); res['audio_level_db'] = round(float(20 * np.log10(np.sqrt((a16 ** 2).mean()) + 1e-9)), 1)
        res['silent'] = res['audio_level_db'] < -55
        res['pauses'] = pauses_from_audio(wav)
        if not res['silent']:
            print('Transcribing...', flush=True)
            try:
                res['words'], res['language'] = transcribe(wav, a.model, a.lang)
            except Exception as ex:  # e.g. no internet for the Whisper model download
                print('WARNING: transcription failed:', str(ex)[:300], flush=True); res['transcribe_error'] = str(ex)[:300]
            res['sentences'] = sentences(res['words'])
    else:
        res['silent'] = True
    print('Looking at the picture...', flush=True)
    res['visual'] = visual(a.src, info)
    res['dead'] = [v['t'] for v in res['visual'] if v['bright'] < 12]
    res['sheet'] = os.path.join(a.out, 'sheet.jpg'); res['sheet_every'] = contact_sheet(a.src, info, res['sheet'])
    json.dump(res, open(os.path.join(a.out, 'analysis.json'), 'w'), indent=1)
    print(f"words={len(res['words'])} sentences={len(res['sentences'])} pauses={len(res['pauses'])} silent={res['silent']}")
    for s in res['sentences']: print(f"  {s['s']:6.2f}-{s['e']:6.2f}  {s['text']}")
    print('Saved', os.path.join(a.out, 'analysis.json'), 'and', res['sheet'])


if __name__ == '__main__':
    main()
