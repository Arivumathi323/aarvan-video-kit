"""Brand voice-over with Kokoro TTS (am_fenrir, speed 1.05).
usage: python voiceover.py script.txt out_dir      (one line of the script per segment)
Names that Kokoro mispronounces are fixed with phoneme overrides below."""
import sys, os, json, urllib.request
import numpy as np, soundfile as sf
from common import BRAND

CACHE = os.path.expanduser('~/.cache/aarvan-video-kit/kokoro')
URL = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
# word (as Kokoro phonemizes it) -> phonemes we want
FIX = {
    'ˌæɹɪvjuːmˈæθi': 'ˈɑɹɪvʊmˌʌθi',   # Arivumathi
    'ˈɑːɹvæn': 'ˈɑːɹvʌn',             # Aarvan
}


def models():
    os.makedirs(CACHE, exist_ok=True)
    for f in ['kokoro-v1.0.onnx', 'voices-v1.0.bin']:
        p = os.path.join(CACHE, f)
        if not os.path.exists(p):
            print('Downloading', f, '(one time)...', flush=True)
            urllib.request.urlretrieve(URL + f, p + '.part'); os.replace(p + '.part', p)
    return os.path.join(CACHE, 'kokoro-v1.0.onnx'), os.path.join(CACHE, 'voices-v1.0.bin')


def make(lines, outdir):
    from kokoro_onnx import Kokoro
    from kokoro_onnx.tokenizer import Tokenizer
    v = BRAND['voice']; k = Kokoro(*models()); tok = Tokenizer()
    os.makedirs(outdir, exist_ok=True); meta = []
    for i, text in enumerate(lines):
        ph = tok.phonemize(text, v['lang'])
        for a, b in FIX.items(): ph = ph.replace(a, b)
        s, sr = k.create(ph, voice=v['voice'], speed=v['speed'], lang=v['lang'], is_phonemes=True)
        idx = np.where(np.abs(s) > 0.01)[0]; s = s[max(0, idx[0] - 240):idx[-1] + 2400]
        p = os.path.join(outdir, f'l{i}.wav'); sf.write(p, s, sr)
        meta.append({'text': text, 'file': p, 'dur': len(s) / sr})
        print(f'{i}: {len(s) / sr:.2f}s  {text}')
    json.dump(meta, open(os.path.join(outdir, 'lines.json'), 'w'), indent=1)
    return meta


if __name__ == '__main__':
    lines = [l.strip() for l in open(sys.argv[1], encoding='utf-8') if l.strip()]
    make(lines, sys.argv[2])
