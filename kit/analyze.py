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
    cached = os.path.isdir(os.path.expanduser(f'~/.cache/huggingface/hub/models--Systran--faster-whisper-{model}'))
    if not cached:   # fail fast when huggingface.co is blocked, so the Parakeet fallback starts right away
        import urllib.request
        try:
            urllib.request.urlopen(f'https://huggingface.co/Systran/faster-whisper-{model}/resolve/main/config.json', timeout=6)
        except Exception as ex:
            raise RuntimeError(f'huggingface.co not reachable ({str(ex)[:60]})')
    m = WhisperModel(model, device='cpu', compute_type='int8')
    segs, info = m.transcribe(wav, word_timestamps=True, vad_filter=True, language=None if lang in (None, 'auto') else lang)
    words = [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3)} for s in segs for w in (s.words or [])]
    return words, info.language


FILLERS = {'uh', 'um', 'umm', 'uhh', 'hmm', 'er', 'ah', 'eh'}
ASR_DIR = os.path.expanduser('~/.cache/aarvan-video-kit/asr')
PARAKEET = 'sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8'
PARAKEET_URL = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/' + PARAKEET + '.tar.bz2'


def transcribe_parakeet(wav):
    """Fallback ASR (English) that downloads from GitHub instead of huggingface.co: NVIDIA Parakeet TDT 0.6B via sherpa-onnx."""
    try:
        import sherpa_onnx
    except ImportError:
        subprocess.run([os.sys.executable, '-m', 'pip', 'install', '-q', 'sherpa-onnx'], check=True)
        import sherpa_onnx
    d = os.path.join(ASR_DIR, PARAKEET)
    if not os.path.exists(os.path.join(d, 'tokens.txt')):
        os.makedirs(ASR_DIR, exist_ok=True); tb = os.path.join(ASR_DIR, 'p.tar.bz2')
        print('Downloading the Parakeet speech model from GitHub (one time, ~460 MB)...', flush=True)
        subprocess.run(['curl', '-sSL', '-o', tb, PARAKEET_URL], check=True)
        subprocess.run(['tar', 'xjf', tb, '-C', ASR_DIR], check=True); os.remove(tb)
    r = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=os.path.join(d, 'encoder.int8.onnx'), decoder=os.path.join(d, 'decoder.int8.onnx'),
                                                      joiner=os.path.join(d, 'joiner.int8.onnx'), tokens=os.path.join(d, 'tokens.txt'),
                                                      model_type='nemo_transducer', num_threads=max(1, os.cpu_count() or 2))
    a, sr = sf.read(wav, dtype='float32')
    if a.ndim > 1: a = a.mean(1)
    # chunks of <= 24 s, cut in the quietest spot near the end of each window
    hop = int(sr * 0.02); e = np.array([np.sqrt((a[i:i + hop] ** 2).mean() + 1e-12) for i in range(0, len(a), hop)])
    bounds, st = [], 0
    while st < len(a):
        en = st + 24 * sr
        if en >= len(a): bounds.append((st, len(a))); break
        lo, hi = (st + 16 * sr) // hop, en // hop
        cut = (lo + int(np.argmin(e[lo:hi]))) * hop; bounds.append((st, cut)); st = cut
    words = []
    for st, en in bounds:
        s = r.create_stream(); s.accept_waveform(sr, a[st:en]); r.decode_stream(s); res = s.result
        off = st / sr; cur = None
        for tok, ts in zip(res.tokens, res.timestamps):
            if tok.startswith(' ') or cur is None:
                if cur: words.append(cur)
                cur = {'w': tok.strip(), 's': round(off + ts, 3), 'e': round(off + ts + 0.08, 3)}
            else:
                cur['w'] += tok; cur['e'] = round(off + ts + 0.08, 3)
        if cur: words.append(cur)
    for i in range(len(words)):  # realistic word lengths: ~0.09 s per letter, never past the next word
        cap = words[i]['s'] + max(0.25, 0.09 * len(words[i]['w']) + 0.15)
        nxt = words[i + 1]['s'] if i + 1 < len(words) else 1e9
        words[i]['e'] = round(min(nxt, max(words[i]['e'], words[i]['s'] + 0.12), cap), 3)
    words = [w for w in words if w['w']]
    return words, 'en'


def refine_word_times(words, wav):
    """Line word timings up with the real speech in the audio.
    Speech models stamp words up to ~0.5 s off; captions and graphics then land late. Two steps:
    1) find the overall lag that puts the most word time on voiced audio and remove it;
    2) any word still sitting mostly in silence is pulled into the nearest speech next to it."""
    if not words: return words
    a, sr = sf.read(wav)
    if a.ndim > 1: a = a.mean(1)
    hop = int(sr * 0.01); e = np.array([np.sqrt((a[i:i + hop] ** 2).mean() + 1e-12) for i in range(0, len(a) - hop, hop)])
    db = 20 * np.log10(e + 1e-9); voiced = db > max(np.percentile(db, 95) - 28, np.percentile(db, 15) + 8)
    def vfrac(s0, e0):
        i, j = int(s0 * 100), max(int(s0 * 100) + 1, int(e0 * 100))
        return voiced[max(0, i):min(len(voiced), j)].mean() if j > i and i < len(voiced) else 0.0
    best = max(np.arange(-0.5, 0.51, 0.02), key=lambda L: np.mean([vfrac(w['s'] + L, w['e'] + L) for w in words]))
    out = [dict(w, s=round(max(0, w['s'] + best), 3), e=round(max(0, w['e'] + best), 3)) for w in words]
    def block(i):                      # the speech block (gaps < 0.15 s) that contains frame i
        a_ = i; b_ = i
        while a_ > 0 and voiced[max(0, a_ - 15):a_].any(): a_ -= 1
        while b_ < len(voiced) - 1 and voiced[b_ + 1:b_ + 16].any(): b_ += 1
        return a_ / 100, (b_ + 1) / 100
    def refit(idx, a_, b_):           # spread these words evenly (by length) across [a_, b_]
        wt = [max(2, len(out[i]['w'])) for i in idx]; tot = sum(wt); t = a_
        for i, x in zip(idx, wt):
            d = (b_ - a_) * x / tot; out[i]['s'], out[i]['e'] = round(t, 3), round(t + d, 3); t += d
    for k in range(len(out)):
        w = out[k]
        if vfrac(w['s'], w['e']) >= 0.4: continue
        i0 = int(w['s'] * 100)
        back = next((i for i in range(min(i0, len(voiced) - 1), max(0, i0 - 60), -1) if voiced[i]), None)
        fwd = next((i for i in range(i0, min(len(voiced), i0 + 60)) if voiced[i]), None)
        if back is not None and (fwd is None or i0 - back <= fwd - i0):
            a_, b_ = block(back)
            j = k
            while j - 1 >= max(0, k - 6) and out[j - 1]['s'] >= a_ - 0.05: j -= 1
            idx = list(range(j, k + 1))
            lo = out[idx[0] - 1]['e'] if idx[0] > 0 else 0.0
            refit(idx, max(a_, lo), b_)
        elif fwd is not None:
            a_, b_ = block(fwd)
            j = k
            while j + 1 < min(len(out), k + 7) and out[j + 1]['e'] <= b_ + 0.05: j += 1
            idx = list(range(k, j + 1))
            hi = out[idx[-1] + 1]['s'] if idx[-1] + 1 < len(out) else 1e9
            refit(idx, a_, min(b_, hi))
    for i in range(1, len(out)):      # final guarantee: in order, no overlaps, nothing shorter than 50 ms
        if out[i]['s'] < out[i - 1]['e']:
            mid = (out[i]['s'] + out[i - 1]['e']) / 2
            out[i - 1]['e'] = round(max(out[i - 1]['s'] + 0.05, mid), 3); out[i]['s'] = out[i - 1]['e']
        if out[i]['e'] < out[i]['s'] + 0.05: out[i]['e'] = round(out[i]['s'] + 0.05, 3)
    return out, round(float(best), 2)


def apply_fixes(words):
    """Fix names the speech model mishears (brand.json "asr_fixes": {"wrong words": "Right"})."""
    from common import BRAND
    fixes = BRAND.get('asr_fixes', {})
    if not fixes: return words
    out, i = [], 0
    norm = lambda w: re.sub(r"[^\w']", '', w.lower())
    while i < len(words):
        hit = None
        for wrong, right in fixes.items():
            parts = wrong.lower().split(); n = len(parts)
            if [norm(w['w']) for w in words[i:i + n]] == parts:
                tail = re.sub(r"^[\w']+", '', words[i + n - 1]['w'])
                rw = right.split(); s0, e0 = words[i]['s'], words[i + n - 1]['e']; d = (e0 - s0) / len(rw)
                hit = ([{'w': x + (tail if k == len(rw) - 1 else ''), 's': round(s0 + k * d, 3), 'e': round(s0 + (k + 1) * d, 3)}
                        for k, x in enumerate(rw)], n); break
        if hit: out.extend(hit[0]); i += hit[1]
        else: out.append(words[i]); i += 1
    return out


def pauses_from_audio(wav, thr_db=-38, min_len=0.22):
    a, sr = sf.read(wav)
    if a.ndim > 1: a = a.mean(1)
    hop = int(sr * 0.02)
    e = np.array([np.sqrt((a[i:i + hop] ** 2).mean() + 1e-12) for i in range(0, len(a) - hop, hop)])
    db = 20 * np.log10(e + 1e-9)
    quiet = db < min(thr_db, np.percentile(db, 95) - 20)   # relative to the voice, so quiet mics work too
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
    ap.add_argument('--asr', default='auto', help='auto (Whisper, falls back to Parakeet) | parakeet (English, from GitHub)')
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
                if a.asr == 'parakeet': raise RuntimeError('parakeet requested')
                res['words'], res['language'] = transcribe(wav, a.model, a.lang)
                res['asr'] = 'whisper-' + a.model
            except Exception as ex:  # e.g. huggingface.co blocked -> English fallback from GitHub
                print('Whisper unavailable (' + str(ex)[:120] + '); using Parakeet...', flush=True)
                try:
                    res['words'], res['language'] = transcribe_parakeet(wav); res['asr'] = 'parakeet-tdt-0.6b-v2'
                except Exception as ex2:
                    print('WARNING: transcription failed:', str(ex2)[:300], flush=True); res['transcribe_error'] = str(ex2)[:300]
            res['words'] = apply_fixes(res['words'])
            res['words'], res['asr_lag_fixed'] = refine_word_times(res['words'], wav)
            ws = res['words']   # pauses between words are the safest cut points
            res['word_gaps'] = [[round(ws[i]['e'], 2), round(ws[i + 1]['s'], 2)] for i in range(len(ws) - 1) if ws[i + 1]['s'] - ws[i]['e'] >= 0.3]
            res['fillers'] = [i for i, w in enumerate(ws) if re.sub(r'\W', '', w['w'].lower()) in FILLERS]
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
